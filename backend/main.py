import tempfile
import os
from typing import Optional
from dotenv import load_dotenv

load_dotenv()
import httpx
import numpy as np
from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from pypdf import PdfReader
from sentence_transformers import SentenceTransformer


# ============================================================
# CONFIGURATION
# ============================================================

CLASSIFIER_URL = "https://backend-model-0dcq.onrender.com/predict"

GROQ_URL = "https://api.groq.com/openai/v1/chat/completions"
GROQ_MODEL = "llama-3.1-8b-instant"

CHUNK_SIZE = 500
CHUNK_OVERLAP = 50
TOP_K = 3


# ============================================================
# APP
# ============================================================

app = FastAPI(
    title="AskMyNotes API",
    description="PDF RAG backend with question classification",
    version="1.0.0",
)


app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://localhost:5174",
        "http://localhost:5175",
        "http://127.0.0.1:5173",
        "http://127.0.0.1:5174",
        "http://127.0.0.1:5175",
         "https://askmynotes-1.vercel.app",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ============================================================
# RAG STATE
# ============================================================

embedding_model: Optional[SentenceTransformer] = None

document_chunks: list[str] = []
document_embeddings: Optional[np.ndarray] = None

document_name: Optional[str] = None
document_pages: int = 0


# ============================================================
# REQUEST / RESPONSE MODELS
# ============================================================

class QuestionRequest(BaseModel):
    question: str


# ============================================================
# LOAD EMBEDDING MODEL
# ============================================================

def get_embedding_model():
    global embedding_model

    if embedding_model is None:
        print("Loading embedding model...")
        embedding_model = SentenceTransformer(
            "sentence-transformers/all-MiniLM-L6-v2"
        )
        print("Embedding model loaded.")

    return embedding_model


# ============================================================
# CHUNKING
# ============================================================

def chunk_text(
    text: str,
    size: int = CHUNK_SIZE,
    overlap: int = CHUNK_OVERLAP,
):
    text = text.strip()

    if not text:
        return []

    chunks = []

    step = size - overlap
    cursor = 0

    while cursor < len(text):
        piece = text[cursor:cursor + size].strip()

        if piece:
            chunks.append(piece)

        cursor += step

    return chunks


# ============================================================
# PDF PROCESSING
# ============================================================

def process_pdf(file_path: str):
    global document_chunks
    global document_embeddings
    global document_pages

    print(f"Processing PDF: {file_path}")

    reader = PdfReader(file_path)

    document_pages = len(reader.pages)

    pages_text = []

    for page in reader.pages:
        text = page.extract_text() or ""
        pages_text.append(text)

    full_text = "\n\n".join(pages_text).strip()

    print(f"Pages: {document_pages}")
    print(f"Characters: {len(full_text):,}")

    chunks = chunk_text(full_text)

    if not chunks:
        raise ValueError("Could not extract usable text from the PDF.")

    print(f"Number of chunks: {len(chunks)}")

    model = get_embedding_model()

    embeddings = model.encode(
        chunks,
        normalize_embeddings=True,
        convert_to_numpy=True,
        show_progress_bar=False,
    ).astype(np.float32)

    document_chunks = chunks
    document_embeddings = embeddings

    print(
        f"Embeddings shape: {document_embeddings.shape}"
    )


# ============================================================
# VECTOR SEARCH
# ============================================================

def search_document(question: str, k: int = TOP_K):
    if not document_chunks or document_embeddings is None:
        raise ValueError("No PDF has been uploaded yet.")

    model = get_embedding_model()

    question_vector = model.encode(
        [question],
        normalize_embeddings=True,
        convert_to_numpy=True,
    )[0]

    scores = document_embeddings @ question_vector

    top_k = min(k, len(document_chunks))

    top_indices = np.argsort(scores)[::-1][:top_k]

    results = []

    for index in top_indices:
        results.append(
            {
                "text": document_chunks[index],
                "score": float(scores[index]),
                "index": int(index),
            }
        )

    return results


# ============================================================
# QUESTION CLASSIFIER
# ============================================================

async def classify_question(question: str):
    payload = {
        "question": question
    }

    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(
                CLASSIFIER_URL,
                json=payload,
            )

            response.raise_for_status()

            data = response.json()

            return data.get(
                "predicted_category",
                "Unknown",
            )

    except Exception as error:
        print(f"Classifier error: {error}")

        # The classifier should not prevent RAG from working.
        return "Unknown"


# ============================================================
# GROQ LLM
# ============================================================

SYSTEM_PROMPT = """
You answer questions using ONLY the provided context.

Rules:
- Do not invent facts.
- Do not use external knowledge.
- Do not answer using information that is not present in the context.
- Skip filler such as "Based on the notes".
- If the context does not cover the question, say so clearly.
- Keep answers concise and useful.
- The question category is provided only to help determine the style
  of the answer.
"""


async def generate_answer(
    question: str,
    category: str,
    context: str,
):
    api_key = os.environ.get("GROQ_API_KEY")

    if not api_key:
        raise RuntimeError(
            "GROQ_API_KEY is not configured."
        )

    prompt = f"""
Question category: {category}

Context from the uploaded PDF:

{context}

Question:
{question}

Answer the question using only the context above.
"""

    payload = {
        "model": GROQ_MODEL,
        "messages": [
            {
                "role": "system",
                "content": SYSTEM_PROMPT,
            },
            {
                "role": "user",
                "content": prompt,
            },
        ],
        "temperature": 0.2,
        "max_tokens": 512,
    }

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }

    async with httpx.AsyncClient(timeout=60.0) as client:
        response = await client.post(
            GROQ_URL,
            json=payload,
            headers=headers,
        )

        response.raise_for_status()

        data = response.json()

        return data["choices"][0]["message"]["content"].strip()


# ============================================================
# ROUTES
# ============================================================

@app.get("/")
def home():
    return {
        "message": "AskMyNotes backend is running"
    }


@app.get("/health")
def health_check():
    return {
        "status": "healthy",
        "pdf_loaded": bool(document_chunks),
        "document": document_name,
    }


@app.post("/upload")
async def upload_pdf(file: UploadFile = File(...)):
    global document_name

    if not file.filename:
        raise HTTPException(
            status_code=400,
            detail="No file selected.",
        )

    if not file.filename.lower().endswith(".pdf"):
        raise HTTPException(
            status_code=400,
            detail="Only PDF files are supported.",
        )

    temp_path = os.path.join(tempfile.gettempdir(), "askmynotes_upload.pdf")

    try:
        contents = await file.read()

        with open(temp_path, "wb") as output:
            output.write(contents)

        process_pdf(temp_path)

        document_name = file.filename

        return {
            "message": "PDF processed successfully.",
            "filename": document_name,
            "pages": document_pages,
            "chunks": len(document_chunks),
        }

    except Exception as error:
        print(f"PDF processing error: {error}")

        raise HTTPException(
            status_code=500,
            detail=f"Failed to process PDF: {str(error)}",
        )


@app.post("/ask")
async def ask_question(request: QuestionRequest):
    question = request.question.strip()

    if not question:
        raise HTTPException(
            status_code=400,
            detail="Please enter a question.",
        )

    if not document_chunks:
        raise HTTPException(
            status_code=400,
            detail="Please upload a PDF first.",
        )

    try:
        # 1. Classify the question
        category = await classify_question(question)

        # 2. Retrieve relevant PDF chunks
        results = search_document(
            question,
            k=TOP_K,
        )

        # 3. Build context
        context = "\n\n".join(
            [
                f"[Chunk {result['index']}]\n{result['text']}"
                for result in results
            ]
        )

        # 4. Generate grounded answer
        answer = await generate_answer(
            question=question,
            category=category,
            context=context,
        )

        return {
            "question": question,
            "category": category,
            "answer": answer,
            "sources": results,
        }

    except HTTPException:
        raise

    except Exception as error:
        print(f"Ask error: {error}")

        raise HTTPException(
            status_code=500,
            detail=f"Failed to answer question: {str(error)}",
        )
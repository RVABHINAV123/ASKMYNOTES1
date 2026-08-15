import { useState } from "react";
import "./App.css";

const API_URL =
  import.meta.env.VITE_API_URL || "http://localhost:8000";

function App() {
  const [file, setFile] = useState(null);
  const [documentInfo, setDocumentInfo] = useState(null);

  const [question, setQuestion] = useState("");
  const [answer, setAnswer] = useState("");
  const [category, setCategory] = useState("");

  const [sources, setSources] = useState([]);

  const [uploading, setUploading] = useState(false);
  const [asking, setAsking] = useState(false);

  const [error, setError] = useState("");

  const uploadPdf = async () => {
    if (!file) {
      setError("Please select a PDF first.");
      return;
    }

    setUploading(true);
    setError("");
    setAnswer("");
    setCategory("");
    setSources([]);

    try {
      const formData = new FormData();
      formData.append("file", file);

      const response = await fetch(
        `${API_URL}/upload`,
        {
          method: "POST",
          body: formData,
        }
      );

      const data = await response.json();

      if (!response.ok) {
        throw new Error(
          data.detail || "Failed to upload PDF."
        );
      }

      setDocumentInfo(data);
    } catch (err) {
      console.error(err);

      setError(
        err.message ||
          "Unable to upload the PDF."
      );
    } finally {
      setUploading(false);
    }
  };

  const askQuestion = async () => {
    const cleanedQuestion = question.trim();

    if (!documentInfo) {
      setError("Please upload a PDF first.");
      return;
    }

    if (!cleanedQuestion) {
      setError("Please enter a question.");
      return;
    }

    setAsking(true);
    setError("");
    setAnswer("");
    setCategory("");
    setSources([]);

    try {
      const response = await fetch(
        `${API_URL}/ask`,
        {
          method: "POST",

          headers: {
            "Content-Type": "application/json",
          },

          body: JSON.stringify({
            question: cleanedQuestion,
          }),
        }
      );

      const data = await response.json();

      if (!response.ok) {
        throw new Error(
          data.detail || "Failed to get answer."
        );
      }

      setAnswer(data.answer);
      setCategory(data.category);
      setSources(data.sources || []);
    } catch (err) {
      console.error(err);

      setError(
        err.message ||
          "Unable to get an answer from the backend."
      );
    } finally {
      setAsking(false);
    }
  };

  return (
    <main className="page">
      <section className="card">

        <div className="header">
          <h1>AskMyNotes</h1>

          <p>
            Chat with your PDF notes using
            AI-powered retrieval.
          </p>
        </div>

        {/* PDF UPLOAD */}

        <div className="section">
          <label htmlFor="pdf">
            Upload your notes (PDF)
          </label>

          <div className="upload-row">
            <input
              id="pdf"
              type="file"
              accept=".pdf,application/pdf"
              onChange={(event) => {
                setFile(
                  event.target.files?.[0] || null
                );

                setDocumentInfo(null);
                setError("");
              }}
            />

            <button
              className="upload-button"
              onClick={uploadPdf}
              disabled={uploading || !file}
            >
              {uploading
                ? "Processing..."
                : "Upload PDF"}
            </button>
          </div>

          {file && (
            <div className="file-name">
              {file.name}
            </div>
          )}

          {documentInfo && (
            <div className="success">
              <strong>
                {documentInfo.filename}
              </strong>

              <span>
                {documentInfo.pages} pages ·{" "}
                {documentInfo.chunks} chunks
              </span>
            </div>
          )}
        </div>

        {/* QUESTION */}

        <div className="section">
          <label htmlFor="question">
            Your question
          </label>

          <textarea
            id="question"
            value={question}
            onChange={(event) =>
              setQuestion(event.target.value)
            }
            placeholder="For example: What is Docker?"
            rows={5}
          />

          <button
            className="ask-button"
            onClick={askQuestion}
            disabled={asking || !documentInfo}
          >
            {asking
              ? "Thinking..."
              : "Ask Question"}
          </button>
        </div>

        {/* ERROR */}

        {error && (
          <div className="error">
            {error}
          </div>
        )}

        {/* ANSWER */}

        {answer && (
          <div className="answer">
            <div className="answer-header">
              <h2>Answer</h2>

              {category && (
                <span className="category">
                  {category}
                </span>
              )}
            </div>

            <p>{answer}</p>
          </div>
        )}

        {/* SOURCES */}

        {sources.length > 0 && (
          <div className="sources">
            <h2>Retrieved sections</h2>

            {sources.map((source, index) => (
              <div
                className="source"
                key={source.index}
              >
                <div className="source-header">
                  <strong>
                    Source {index + 1}
                  </strong>

                  <span>
                    Score:{" "}
                    {source.score.toFixed(3)}
                  </span>
                </div>

                <p>{source.text}</p>
              </div>
            ))}
          </div>
        )}

      </section>
    </main>
  );
}

export default App;
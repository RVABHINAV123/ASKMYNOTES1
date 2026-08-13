import { useState } from "react";
import "./App.css";

function App() {
  const [question, setQuestion] = useState("");
  const [answer, setAnswer] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  const askQuestion = async () => {
    const cleanedQuestion = question.trim();

    if (!cleanedQuestion) {
      setError("Please enter a question.");
      setAnswer("");
      return;
    }

    setLoading(true);
    setError("");
    setAnswer("");

    try {
      const response = await fetch("http://localhost:8000/ask", {
        method: "POST",

        headers: {
          "Content-Type": "application/json",
        },

        body: JSON.stringify({
          question: cleanedQuestion,
        }),
      });

      if (!response.ok) {
        throw new Error(`Backend returned status ${response.status}`);
      }

      const data = await response.json();

      setAnswer(data.answer);
    } catch (err) {
      console.error(err);

      setError(
        "Unable to connect to the backend. Check whether the FastAPI container is running."
      );
    } finally {
      setLoading(false);
    }
  };

  return (
    <main className="page">
      <section className="card">
        <h1>Ask My Notes</h1>

        <p>Enter a question and send it to the FastAPI backend.</p>

        <label htmlFor="question">Your question</label>

        <textarea
          id="question"
          value={question}
          onChange={(event) => setQuestion(event.target.value)}
          placeholder="For example: What is Docker?"
          rows="5"
        />

        <button onClick={askQuestion} disabled={loading}>
          {loading ? "Sending..." : "Ask Question"}
        </button>

        {error && <div className="error">{error}</div>}

        {answer && (
          <div className="answer">
            <h2>Backend response</h2>
            <p>{answer}</p>
          </div>
        )}
      </section>
    </main>
  );
}

export default App;
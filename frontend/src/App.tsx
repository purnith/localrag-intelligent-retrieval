import { FormEvent, useEffect, useState } from "react";

type Health = {
  status: string;
  components: Record<string, boolean>;
};

type Source = {
  chunk_id: number;
  document_id: number;
  filename: string;
  content: string;
  score: number;
};

type Answer = {
  answer: string;
  sources: Source[];
};

type BatchUploadResponse = {
  total_documents: number;
  total_chunks: number;
};

const apiUrl = import.meta.env.VITE_API_URL ?? "http://localhost:8000";
const maxBatchFiles = 10;

export default function App() {
  const [health, setHealth] = useState<Health | null>(null);
  const [files, setFiles] = useState<File[]>([]);
  const [uploadMessage, setUploadMessage] = useState("");
  const [question, setQuestion] = useState("");
  const [result, setResult] = useState<Answer | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    fetch(`${apiUrl}/api/health`)
      .then((response) => response.json())
      .then(setHealth)
      .catch(() => setHealth(null));
  }, []);

  function selectFiles(selected: FileList | null) {
    const nextFiles = Array.from(selected ?? []);
    setUploadMessage("");
    if (nextFiles.length > maxBatchFiles) {
      setFiles([]);
      setError(`Select no more than ${maxBatchFiles} documents at once.`);
      return;
    }
    setError("");
    setFiles(nextFiles);
  }

  async function uploadDocuments(event: FormEvent) {
    event.preventDefault();
    if (!files.length) return;
    setBusy(true);
    setError("");
    setUploadMessage("");
    const body = new FormData();
    files.forEach((file) => body.append("files", file));
    try {
      const response = await fetch(`${apiUrl}/api/documents/batch`, {
        method: "POST",
        body,
      });
      const data: BatchUploadResponse & { detail?: string } = await response.json();
      if (!response.ok) throw new Error(data.detail ?? "Upload failed");
      setUploadMessage(
        `${data.total_documents} document(s) indexed into ${data.total_chunks} chunk(s).`,
      );
      setFiles([]);
    } catch (uploadError) {
      setError(uploadError instanceof Error ? uploadError.message : "Upload failed");
    } finally {
      setBusy(false);
    }
  }

  async function askQuestion(event: FormEvent) {
    event.preventDefault();
    if (!question.trim()) return;
    setBusy(true);
    setError("");
    setResult(null);
    try {
      const response = await fetch(`${apiUrl}/api/ask`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ query: question, limit: 5 }),
      });
      const data = await response.json();
      if (!response.ok) throw new Error(data.detail ?? "Question failed");
      setResult(data);
    } catch (askError) {
      setError(askError instanceof Error ? askError.message : "Question failed");
    } finally {
      setBusy(false);
    }
  }

  return (
    <main>
      <section className="hero">
        <p className="eyebrow">LOCAL / OPEN SOURCE / INTELLIGENT</p>
        <h1>Ask your documents.</h1>
        <p className="subtitle">
          Upload multiple documents, ask a question, and inspect the evidence behind the answer.
        </p>
      </section>

      <section className="workspace">
        <article className="panel">
          <span className="step">01</span>
          <h2>Add knowledge</h2>
          <p>Up to 10 PDF, DOCX, or TXT files / maximum 10 MB each</p>
          <form onSubmit={uploadDocuments}>
            <label className="file-input">
              <input
                type="file"
                accept=".pdf,.docx,.txt"
                multiple
                onChange={(event) => selectFiles(event.target.files)}
              />
              <span>
                {files.length
                  ? `${files.length} document(s) selected`
                  : "Choose one or more documents"}
              </span>
            </label>
            {files.length > 0 && (
              <ul className="selected-files">
                {files.map((file) => (
                  <li key={`${file.name}-${file.lastModified}`}>{file.name}</li>
                ))}
              </ul>
            )}
            <button disabled={!files.length || busy}>
              {busy ? "Working..." : "Upload and index"}
            </button>
          </form>
          {uploadMessage && <p className="success">{uploadMessage}</p>}
        </article>

        <article className="panel question-panel">
          <span className="step">02</span>
          <h2>Ask a question</h2>
          <form onSubmit={askQuestion}>
            <textarea
              value={question}
              onChange={(event) => setQuestion(event.target.value)}
              placeholder="What do the documents say about...?"
              rows={4}
            />
            <button disabled={!question.trim() || busy}>
              {busy ? "Thinking..." : "Find an answer"}
            </button>
          </form>
        </article>
      </section>

      {error && <section className="notice error">{error}</section>}

      {result && (
        <section className="answer-card">
          <p className="eyebrow">GROUNDED ANSWER</p>
          <div className="answer">{result.answer}</div>
          <h3>Retrieved sources</h3>
          <div className="source-list">
            {result.sources.map((source, index) => (
              <details key={source.chunk_id}>
                <summary>
                  Source {index + 1} / {source.filename}
                  <span>{Math.round(source.score * 100)}% match</span>
                </summary>
                <p>{source.content}</p>
              </details>
            ))}
          </div>
        </section>
      )}

      <footer>
        <span className={health?.status === "healthy" ? "dot ready" : "dot"} />
        {health?.status === "healthy" ? "All local services ready" : "Checking local services"}
      </footer>
    </main>
  );
}

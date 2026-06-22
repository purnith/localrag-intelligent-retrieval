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
  conversation_id: number;
  action: string;
  tool_trace: string[];
};

type User = { id: number; display_name: string };
type Conversation = { id: number; title: string; messages: number };
type Message = { id: number; role: "user" | "assistant"; content: string };

type IngestionJob = {
  id: number;
  status: "queued" | "processing" | "retrying" | "completed" | "failed";
  total_files: number;
  processed_files: number;
  duplicate_files: number;
  attempts: number;
  error: string | null;
};

type DocumentRecord = {
  id: number;
  filename: string;
  content_type: string;
  created_at: string;
  chunks: number;
};

const apiUrl = import.meta.env.VITE_API_URL ?? "http://localhost:8000";
const maxBatchFiles = 10;

export default function App() {
  const [health, setHealth] = useState<Health | null>(null);
  const [user, setUser] = useState<User | null>(null);
  const [conversations, setConversations] = useState<Conversation[]>([]);
  const [conversationId, setConversationId] = useState<number | null>(null);
  const [messages, setMessages] = useState<Message[]>([]);
  const [documents, setDocuments] = useState<DocumentRecord[]>([]);
  const [selectedDocumentIds, setSelectedDocumentIds] = useState<number[]>([]);
  const [files, setFiles] = useState<File[]>([]);
  const [uploadJob, setUploadJob] = useState<IngestionJob | null>(null);
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
    initializeUser();
  }, []);

  async function initializeUser() {
    try {
      const savedId = window.localStorage.getItem("localrag_user_id");
      let currentUser: User | null = null;
      if (savedId) {
        const response = await fetch(`${apiUrl}/api/users/${savedId}`);
        if (response.ok) currentUser = await response.json();
      }
      if (!currentUser) {
        const response = await fetch(`${apiUrl}/api/users`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ display_name: "Purnith" }),
        });
        if (!response.ok) throw new Error("Could not initialize user context");
        const createdUser: User = await response.json();
        currentUser = createdUser;
        window.localStorage.setItem("localrag_user_id", String(createdUser.id));
      }
      if (!currentUser) throw new Error("Could not initialize user context");
      setUser(currentUser);
      await Promise.all([loadDocuments(currentUser.id), loadConversations(currentUser.id)]);
    } catch (contextError) {
      setError(contextError instanceof Error ? contextError.message : "User context failed");
    }
  }

  async function loadDocuments(userId = user?.id) {
    if (!userId) return;
    try {
      const response = await fetch(`${apiUrl}/api/documents?user_id=${userId}`);
      if (!response.ok) return;
      const data: DocumentRecord[] = await response.json();
      setDocuments(data);
      setSelectedDocumentIds((current) =>
        current.filter((id) => data.some((document) => document.id === id)),
      );
    } catch {
      // The health indicator already communicates that the API is unavailable.
    }
  }

  async function loadConversations(userId = user?.id) {
    if (!userId) return;
    const response = await fetch(`${apiUrl}/api/conversations?user_id=${userId}`);
    if (response.ok) setConversations(await response.json());
  }

  async function selectConversation(id: number | null) {
    setConversationId(id);
    if (!id || !user) {
      setMessages([]);
      return;
    }
    const response = await fetch(
      `${apiUrl}/api/conversations/${id}/messages?user_id=${user.id}`,
    );
    if (response.ok) setMessages(await response.json());
  }

  function selectFiles(selected: FileList | null) {
    const nextFiles = Array.from(selected ?? []);
    setUploadMessage("");
    setUploadJob(null);
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
    if (!user) return;
    body.append("user_id", String(user.id));
    try {
      const response = await fetch(`${apiUrl}/api/documents/jobs`, {
        method: "POST",
        body,
      });
      const data: { job_id?: number; detail?: string } = await response.json();
      if (!response.ok) throw new Error(data.detail ?? "Upload failed");
      if (!data.job_id) throw new Error("The ingestion job was not created");

      const completedJob = await waitForIngestion(data.job_id, user.id);
      const indexed = completedJob.processed_files - completedJob.duplicate_files;
      setUploadMessage(
        completedJob.duplicate_files
          ? `${indexed} new document(s) indexed; ${completedJob.duplicate_files} duplicate(s) skipped.`
          : `${indexed} document(s) indexed successfully.`,
      );
      setFiles([]);
      await loadDocuments(user.id);
    } catch (uploadError) {
      setError(uploadError instanceof Error ? uploadError.message : "Upload failed");
    } finally {
      setBusy(false);
    }
  }

  async function waitForIngestion(jobId: number, userId: number): Promise<IngestionJob> {
    for (let attempt = 0; attempt < 300; attempt += 1) {
      const response = await fetch(
        `${apiUrl}/api/documents/jobs/${jobId}?user_id=${userId}`,
      );
      const data: IngestionJob & { detail?: string } = await response.json();
      if (!response.ok) throw new Error(data.detail ?? "Could not read job status");
      setUploadJob(data);
      if (data.status === "completed") return data;
      if (data.status === "failed") {
        throw new Error(data.error ?? "Document processing failed");
      }
      await new Promise((resolve) => window.setTimeout(resolve, 1000));
    }
    throw new Error("Document processing timed out");
  }

  async function deleteDocument(document: DocumentRecord) {
    if (!user) return;
    if (!window.confirm(`Delete ${document.filename} from the knowledge base?`)) return;
    setError("");
    try {
      const response = await fetch(`${apiUrl}/api/documents/${document.id}?user_id=${user.id}`, {
        method: "DELETE",
      });
      if (!response.ok) {
        const data = await response.json();
        throw new Error(data.detail ?? "Delete failed");
      }
      await loadDocuments(user.id);
    } catch (deleteError) {
      setError(deleteError instanceof Error ? deleteError.message : "Delete failed");
    }
  }

  function toggleDocument(documentId: number) {
    setSelectedDocumentIds((current) =>
      current.includes(documentId)
        ? current.filter((id) => id !== documentId)
        : [...current, documentId],
    );
  }

  async function askQuestion(event: FormEvent) {
    event.preventDefault();
    if (!question.trim() || !user) return;
    setBusy(true);
    setError("");
    setResult(null);
    try {
      const response = await fetch(`${apiUrl}/api/agent/ask`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          query: question,
          user_id: user.id,
          conversation_id: conversationId,
          limit: 5,
          document_ids: selectedDocumentIds.length ? selectedDocumentIds : null,
        }),
      });
      const data = await response.json();
      if (!response.ok) throw new Error(data.detail ?? "Question failed");
      setResult(data);
      setConversationId(data.conversation_id);
      setQuestion("");
      await Promise.all([
        loadConversations(user.id),
        selectConversation(data.conversation_id),
      ]);
    } catch (askError) {
      setError(askError instanceof Error ? askError.message : "Question failed");
    } finally {
      setBusy(false);
    }
  }

  return (
    <main>
      <section className="hero">
        <p className="eyebrow">INGEST / RETRIEVE / ANSWER</p>
        <h1>Ask your documents.</h1>
        <p className="subtitle">
          Upload multiple documents, ask a question, and inspect the evidence behind the answer.
        </p>
        {user && <p className="user-context">Context profile: {user.display_name}</p>}
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
              {busy ? "Processing..." : "Upload and index"}
            </button>
          </form>
          {uploadJob && uploadJob.status !== "completed" && (
            <div className="job-progress" aria-live="polite">
              <div className="progress-heading">
                <span>{uploadJob.status}</span>
                <strong>
                  {uploadJob.processed_files}/{uploadJob.total_files}
                </strong>
              </div>
              <div className="progress-track">
                <span
                  style={{
                    width: `${Math.round(
                      (uploadJob.processed_files / uploadJob.total_files) * 100,
                    )}%`,
                  }}
                />
              </div>
              {uploadJob.status === "retrying" && (
                <small>Retrying after a processing error (attempt {uploadJob.attempts})</small>
              )}
            </div>
          )}
          {uploadMessage && <p className="success">{uploadMessage}</p>}
          <div className="document-library">
            <div className="library-heading">
              <h3>Document library</h3>
              <span>{documents.length}</span>
            </div>
            <p className="library-hint">
              {selectedDocumentIds.length
                ? `Searching ${selectedDocumentIds.length} selected document(s)`
                : "No selection means search all documents"}
            </p>
            <div className="document-list">
              {documents.map((document) => (
                <div className="document-row" key={document.id}>
                  <label>
                    <input
                      type="checkbox"
                      checked={selectedDocumentIds.includes(document.id)}
                      onChange={() => toggleDocument(document.id)}
                    />
                    <span>
                      <strong>{document.filename}</strong>
                      <small>{document.chunks} chunk(s)</small>
                    </span>
                  </label>
                  <button
                    type="button"
                    className="delete-button"
                    onClick={() => deleteDocument(document)}
                    aria-label={`Delete ${document.filename}`}
                  >
                    Delete
                  </button>
                </div>
              ))}
              {!documents.length && <p className="empty-library">No documents indexed yet.</p>}
            </div>
          </div>
        </article>

        <article className="panel question-panel">
          <span className="step">02</span>
          <h2>Ask a question</h2>
          <div className="conversation-controls">
            <select
              value={conversationId ?? ""}
              onChange={(event) =>
                selectConversation(event.target.value ? Number(event.target.value) : null)
              }
            >
              <option value="">New conversation</option>
              {conversations.map((conversation) => (
                <option key={conversation.id} value={conversation.id}>
                  {conversation.title}
                </option>
              ))}
            </select>
            <button type="button" onClick={() => selectConversation(null)}>
              New
            </button>
          </div>
          {messages.length > 0 && (
            <div className="conversation-memory">
              {messages.slice(-6).map((message) => (
                <p key={message.id} className={message.role}>
                  <strong>{message.role === "user" ? "You" : "Assistant"}</strong>
                  {message.content}
                </p>
              ))}
            </div>
          )}
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
          <div className="agent-heading">
            <p className="eyebrow">AGENT ANSWER</p>
            <span>{result.action.replaceAll("_", " ")}</span>
          </div>
          <div className="answer">{result.answer}</div>
          <p className="tool-trace">{result.tool_trace.join(" → ")}</p>
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

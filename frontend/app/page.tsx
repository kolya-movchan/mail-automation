"use client";

import { Fragment, useMemo, useState } from "react";

const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

interface ThreadMessage {
  sender: string;
  date: string;
  to: string;
  cc: string;
  body: string;
}

interface Source {
  subject: string;
  sender: string;
  date: string;
  participants: string;
  message_count: number;
  score: number;
  messages: ThreadMessage[];
}

interface AskResponse {
  answer: string;
  sources: Source[];
}

const EXAMPLE_QUESTIONS = [
  "What was discussed in the all-hands?",
  "Why did the API gateway return 503s?",
  "What's the Q1 roadmap?",
  "Any partnership discussions?",
];

const STOPWORDS = new Set([
  "the", "a", "an", "is", "was", "were", "are", "be", "been", "being",
  "what", "why", "when", "where", "how", "who", "which", "whose", "whom",
  "do", "does", "did", "doing", "have", "has", "had", "having",
  "for", "on", "in", "of", "to", "and", "or", "with", "from", "by",
  "this", "that", "these", "those", "it", "its", "as", "at", "but",
  "any", "all", "can", "could", "should", "would", "will", "shall",
  "about", "into", "out", "than", "then", "there", "their", "them",
  "we", "us", "our", "you", "your", "i", "me", "my", "he", "she",
  "discussed", "said", "told", "asked",
]);

function relevanceLabel(score: number): string {
  if (score >= 0.5) return "high";
  if (score >= 0.3) return "fair";
  return "low";
}

function extractTerms(query: string): string[] {
  const seen = new Set<string>();
  const out: string[] = [];
  for (const raw of query.toLowerCase().split(/[^\p{L}\p{N}]+/u)) {
    if (raw.length < 3 || STOPWORDS.has(raw) || seen.has(raw)) continue;
    seen.add(raw);
    out.push(raw);
  }
  return out;
}

function escapeRegExp(s: string): string {
  return s.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
}

function Highlight({ text, terms }: { text: string; terms: string[] }) {
  if (!text) return null;
  if (terms.length === 0) return <>{text}</>;
  const pattern = new RegExp(`(${terms.map(escapeRegExp).join("|")})`, "giu");
  const parts = text.split(pattern);
  return (
    <>
      {parts.map((part, i) =>
        i % 2 === 1 ? (
          <mark
            key={i}
            style={{ backgroundColor: "var(--color-mark)" }}
            className="rounded-[2px] px-[2px] text-(--color-ink)"
          >
            {part}
          </mark>
        ) : (
          <Fragment key={i}>{part}</Fragment>
        )
      )}
    </>
  );
}

function formatDateTime(iso: string): string {
  if (!iso) return "—";
  const d = new Date(iso);
  if (isNaN(d.getTime())) return iso;
  return d.toLocaleString(undefined, {
    dateStyle: "medium",
    timeStyle: "short",
  });
}

function formatDate(iso: string): string {
  if (!iso) return "—";
  const d = new Date(iso);
  if (isNaN(d.getTime())) return iso;
  return d.toLocaleDateString(undefined, {
    year: "numeric",
    month: "short",
    day: "numeric",
  });
}

function num(n: number): string {
  return String(n).padStart(2, "0");
}

export default function Home() {
  const [question, setQuestion] = useState("");
  const [askedQuestion, setAskedQuestion] = useState("");
  const [loading, setLoading] = useState(false);
  const [ingesting, setIngesting] = useState(false);
  const [result, setResult] = useState<AskResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [ingestMsg, setIngestMsg] = useState<string | null>(null);
  const [expanded, setExpanded] = useState<Set<number>>(new Set());

  const terms = useMemo(() => extractTerms(askedQuestion), [askedQuestion]);

  function toggleExpanded(idx: number) {
    setExpanded((prev) => {
      const next = new Set(prev);
      if (next.has(idx)) next.delete(idx);
      else next.add(idx);
      return next;
    });
  }

  async function ask(text: string) {
    setLoading(true);
    setError(null);
    setResult(null);
    setExpanded(new Set());
    setAskedQuestion(text);
    try {
      const res = await fetch(`${API_URL}/ask`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ question: text, n_results: 5 }),
      });
      if (!res.ok) {
        const err = await res.json();
        throw new Error(err.detail || "Request failed");
      }
      setResult(await res.json());
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setLoading(false);
    }
  }

  async function handleAsk(e: React.FormEvent) {
    e.preventDefault();
    if (!question.trim()) return;
    await ask(question);
  }

  async function handleExample(text: string) {
    setQuestion(text);
    await ask(text);
  }

  async function handleIngest() {
    setIngesting(true);
    setIngestMsg(null);
    setError(null);
    try {
      const res = await fetch(`${API_URL}/ingest`, { method: "POST" });
      const data = await res.json();
      if (!res.ok) throw new Error(data.detail || "Ingest failed");
      setIngestMsg(`Indexed ${data.threads_ingested} threads.`);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setIngesting(false);
    }
  }

  return (
    <main className="min-h-screen">
      <div className="mx-auto max-w-2xl px-6 pt-10 pb-32 sm:pt-16">
        {/* Running header — editorial chrome */}
        <div className="mb-14 flex items-center justify-between border-b pb-3 rule">
          <span className="smallcaps">Correspondence&nbsp;Archive · MMXXV</span>
          <button
            onClick={handleIngest}
            disabled={ingesting}
            className="smallcaps transition hover:text-(--color-ink) disabled:opacity-50"
          >
            {ingesting ? "Indexing…" : "↻ Reindex"}
          </button>
        </div>

        {/* Masthead */}
        <header className="mb-14 ink-in">
          <h1 className="serif text-[44px] leading-[1.05] tracking-[-0.02em] text-(--color-ink) sm:text-[56px]">
            Mailmind<span className="text-(--color-accent)">.</span>
          </h1>
          <p className="serif mt-3 max-w-md text-[15px] italic leading-snug text-(--color-muted)">
            A private index of personal correspondence — searchable in prose,
            answered in kind.
          </p>
        </header>

        {ingestMsg && (
          <p className="mono mb-4 text-[11px] text-(--color-accent) fade-up">
            {ingestMsg}
          </p>
        )}

        {/* Inquiry */}
        <section className="mb-2">
          <p className="smallcaps mb-2">Inquiry</p>
          <form onSubmit={handleAsk}>
            <div className="flex items-end gap-3 border-b pb-2 rule transition-colors focus-within:border-(--color-ink)">
              <input
                type="text"
                value={question}
                onChange={(e) => setQuestion(e.target.value)}
                placeholder="On what subject?"
                className="serif w-full bg-transparent py-2 text-[22px] italic text-(--color-ink) placeholder-(--color-muted)/70 focus:outline-none"
              />
              <button
                type="submit"
                disabled={loading || !question.trim()}
                className="smallcaps mb-1 shrink-0 transition hover:text-(--color-accent) disabled:opacity-40"
              >
                {loading ? "Reading…" : "Submit →"}
              </button>
            </div>
          </form>
        </section>

        {!result && !loading && !error && (
          <div className="mt-6 fade-up">
            <p className="smallcaps mb-2">Suggested</p>
            <ul className="space-y-1.5">
              {EXAMPLE_QUESTIONS.map((ex, i) => (
                <li key={ex} className="flex items-baseline gap-3">
                  <span className="mono text-[11px] text-(--color-muted)">
                    {num(i + 1)}
                  </span>
                  <button
                    onClick={() => handleExample(ex)}
                    className="serif text-left text-[15px] italic text-(--color-ink-soft) underline-offset-[3px] transition hover:text-(--color-accent) hover:underline"
                  >
                    {ex}
                  </button>
                </li>
              ))}
            </ul>
          </div>
        )}

        {error && (
          <p className="mono mt-6 text-[12px] text-(--color-accent) fade-up">
            {error}
          </p>
        )}

        {loading && (
          <div className="mt-10 space-y-2">
            <div
              className="h-2.5 w-full animate-pulse rounded-full"
              style={{ backgroundColor: "var(--color-paper-deep)" }}
            />
            <div
              className="h-2.5 w-11/12 animate-pulse rounded-full"
              style={{ backgroundColor: "var(--color-paper-deep)" }}
            />
            <div
              className="h-2.5 w-2/3 animate-pulse rounded-full"
              style={{ backgroundColor: "var(--color-paper-deep)" }}
            />
          </div>
        )}

        {result && (
          <div className="mt-14 space-y-16">
            {/* Reply */}
            <article className="fade-up">
              <p className="smallcaps mb-3">Reply</p>
              <p className="serif whitespace-pre-wrap text-[20px] leading-[1.55] text-(--color-ink)">
                {result.answer}
              </p>
            </article>

            {/* Index of sources */}
            {result.sources.length > 0 && (
              <section>
                <div className="mb-4 flex items-baseline justify-between border-b pb-2 rule">
                  <p className="smallcaps">References</p>
                  <p className="mono text-[11px] text-(--color-muted)">
                    {num(result.sources.length)}{" "}
                    {result.sources.length === 1 ? "entry" : "entries"}
                  </p>
                </div>

                <ul className="divide-y divide-(--color-rule)">
                  {result.sources.map((src, i) => {
                    const isOpen = expanded.has(i);
                    const pct = Math.max(0, Math.round(src.score * 100));
                    return (
                      <li
                        key={i}
                        className="fade-up"
                        style={{ animationDelay: `${80 + i * 60}ms` }}
                      >
                        <button
                          type="button"
                          onClick={() => toggleExpanded(i)}
                          aria-expanded={isOpen}
                          className="group flex w-full gap-5 py-5 text-left"
                        >
                          <span className="mono shrink-0 pt-1 text-[11px] text-(--color-muted)">
                            №&nbsp;{num(i + 1)}
                          </span>
                          <span className="min-w-0 flex-1">
                            <span className="serif block text-[17px] leading-snug text-(--color-ink) italic">
                              <Highlight
                                text={src.subject || "(no subject)"}
                                terms={terms}
                              />
                            </span>
                            <span className="mono mt-1.5 block text-[11px] tracking-wide text-(--color-muted)">
                              {src.sender.toLowerCase()} &nbsp;·&nbsp;{" "}
                              {formatDate(src.date)} &nbsp;·&nbsp;{" "}
                              {src.message_count}{" "}
                              {src.message_count === 1 ? "msg" : "msgs"}
                            </span>
                          </span>
                          <span className="mono flex shrink-0 items-baseline gap-3 self-start pt-1 text-[11px] tabular-nums text-(--color-muted)">
                            <span className="text-right">
                              <span className="block text-(--color-ink-soft)">
                                {pct}
                              </span>
                              <span className="block text-[9.5px] uppercase tracking-[0.2em]">
                                {relevanceLabel(src.score)}
                              </span>
                            </span>
                            <svg
                              xmlns="http://www.w3.org/2000/svg"
                              viewBox="0 0 24 24"
                              fill="none"
                              stroke="currentColor"
                              strokeWidth="1.5"
                              strokeLinecap="round"
                              strokeLinejoin="round"
                              className={`mt-1 h-3 w-3 transition-transform duration-300 group-hover:text-(--color-ink) ${
                                isOpen ? "rotate-180" : ""
                              }`}
                            >
                              <path d="m6 9 6 6 6-6" />
                            </svg>
                          </span>
                        </button>
                        {isOpen && (
                          <div className="pb-8 pl-[3.25rem] fade-up">
                            <p className="mono mb-5 text-[11px] text-(--color-muted)">
                              <span className="uppercase tracking-[0.18em]">
                                Participants
                              </span>
                              &nbsp;·&nbsp; {src.participants}
                            </p>
                            {src.messages.length === 0 ? (
                              <p className="serif text-[14px] italic text-(--color-muted)">
                                No message content available — try reindexing.
                              </p>
                            ) : (
                              <ol className="space-y-7">
                                {src.messages.map((msg, j) => (
                                  <li key={j}>
                                    <div className="mb-2 flex flex-wrap items-baseline justify-between gap-x-4 gap-y-1 border-b pb-1.5 rule">
                                      <p className="serif text-[14px] italic text-(--color-ink)">
                                        <Highlight
                                          text={msg.sender}
                                          terms={terms}
                                        />
                                      </p>
                                      <p className="mono text-[10.5px] text-(--color-muted)">
                                        {formatDateTime(msg.date)}
                                      </p>
                                    </div>
                                    {(msg.to || msg.cc) && (
                                      <p className="mono mb-3 text-[10.5px] text-(--color-muted)">
                                        {msg.to && (
                                          <>
                                            <span className="uppercase tracking-[0.18em]">
                                              to
                                            </span>{" "}
                                            {msg.to}
                                          </>
                                        )}
                                        {msg.cc && (
                                          <>
                                            {msg.to && (
                                              <span className="px-1.5 text-(--color-rule)">
                                                /
                                              </span>
                                            )}
                                            <span className="uppercase tracking-[0.18em]">
                                              cc
                                            </span>{" "}
                                            {msg.cc}
                                          </>
                                        )}
                                      </p>
                                    )}
                                    <pre className="serif whitespace-pre-wrap wrap-break-word text-[15px] leading-[1.65] text-(--color-ink-soft)">
                                      <Highlight
                                        text={msg.body}
                                        terms={terms}
                                      />
                                    </pre>
                                  </li>
                                ))}
                              </ol>
                            )}
                          </div>
                        )}
                      </li>
                    );
                  })}
                </ul>
              </section>
            )}
          </div>
        )}
      </div>
    </main>
  );
}

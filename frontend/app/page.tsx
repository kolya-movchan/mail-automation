"use client";

import { useState } from "react";

const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

interface Source {
  subject: string;
  sender: string;
  date: string;
  participants: string;
  message_count: number;
  score: number;
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

function relevanceBadge(score: number) {
  if (score >= 0.5)
    return {
      label: "Strong match",
      cls: "bg-emerald-50 text-emerald-700 ring-emerald-200",
    };
  if (score >= 0.3)
    return {
      label: "Possible match",
      cls: "bg-amber-50 text-amber-700 ring-amber-200",
    };
  return {
    label: "Weak match",
    cls: "bg-slate-100 text-slate-500 ring-slate-200",
  };
}

export default function Home() {
  const [question, setQuestion] = useState("");
  const [loading, setLoading] = useState(false);
  const [ingesting, setIngesting] = useState(false);
  const [result, setResult] = useState<AskResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [ingestMsg, setIngestMsg] = useState<string | null>(null);

  async function ask(text: string) {
    setLoading(true);
    setError(null);
    setResult(null);
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
      setIngestMsg(`Indexed ${data.threads_ingested} email threads.`);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setIngesting(false);
    }
  }

  return (
    <main className="min-h-screen bg-linear-to-b from-slate-50 to-white">
      <div className="mx-auto max-w-3xl px-4 py-10 sm:py-16">
        <header className="mb-10 flex items-start justify-between gap-4">
          <div>
            <div className="mb-3 flex items-center gap-2.5">
              <span className="grid h-9 w-9 place-items-center rounded-xl bg-indigo-600 text-white shadow-sm shadow-indigo-200">
                <svg
                  xmlns="http://www.w3.org/2000/svg"
                  viewBox="0 0 24 24"
                  fill="none"
                  stroke="currentColor"
                  strokeWidth="2"
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  className="h-5 w-5"
                >
                  <path d="M22 12h-6l-2 3h-4l-2-3H2" />
                  <path d="M5.45 5.11 2 12v6a2 2 0 0 0 2 2h16a2 2 0 0 0 2-2v-6l-3.45-6.89A2 2 0 0 0 16.76 4H7.24a2 2 0 0 0-1.79 1.11z" />
                </svg>
              </span>
              <h1 className="text-2xl font-bold tracking-tight text-slate-900">
                Mailmind
              </h1>
            </div>
            <p className="max-w-md text-sm text-slate-500">
              Ask natural-language questions across your email archive. Answers
              are grounded in the actual threads.
            </p>
          </div>
          <button
            onClick={handleIngest}
            disabled={ingesting}
            className="inline-flex items-center gap-1.5 rounded-lg border border-slate-200 bg-white px-3 py-1.5 text-xs font-medium text-slate-600 shadow-sm hover:border-slate-300 hover:text-slate-900 disabled:opacity-50"
          >
            <svg
              xmlns="http://www.w3.org/2000/svg"
              viewBox="0 0 24 24"
              fill="none"
              stroke="currentColor"
              strokeWidth="2"
              strokeLinecap="round"
              strokeLinejoin="round"
              className={`h-3.5 w-3.5 ${ingesting ? "animate-spin" : ""}`}
            >
              <path d="M21 12a9 9 0 1 1-6.219-8.56" />
              <path d="M21 3v6h-6" />
            </svg>
            {ingesting ? "Indexing…" : "Reindex"}
          </button>
        </header>

        {ingestMsg && (
          <div className="mb-6 flex items-center gap-2 rounded-xl border border-emerald-200 bg-emerald-50 px-4 py-2.5 text-sm text-emerald-800">
            <svg
              xmlns="http://www.w3.org/2000/svg"
              viewBox="0 0 24 24"
              fill="none"
              stroke="currentColor"
              strokeWidth="2.5"
              strokeLinecap="round"
              strokeLinejoin="round"
              className="h-4 w-4 shrink-0"
            >
              <path d="M20 6 9 17l-5-5" />
            </svg>
            {ingestMsg}
          </div>
        )}

        <form onSubmit={handleAsk} className="mb-6">
          <div className="relative">
            <span className="pointer-events-none absolute inset-y-0 left-4 grid place-items-center text-slate-400">
              <svg
                xmlns="http://www.w3.org/2000/svg"
                viewBox="0 0 24 24"
                fill="none"
                stroke="currentColor"
                strokeWidth="2"
                strokeLinecap="round"
                strokeLinejoin="round"
                className="h-4 w-4"
              >
                <circle cx="11" cy="11" r="8" />
                <path d="m21 21-4.3-4.3" />
              </svg>
            </span>
            <input
              type="text"
              value={question}
              onChange={(e) => setQuestion(e.target.value)}
              placeholder="Ask anything about your email archive…"
              className="w-full rounded-2xl border border-slate-200 bg-white py-4 pl-11 pr-28 text-sm text-slate-900 placeholder-slate-400 shadow-sm transition focus:border-indigo-300 focus:outline-none focus:ring-4 focus:ring-indigo-100"
            />
            <button
              type="submit"
              disabled={loading || !question.trim()}
              className="absolute inset-y-1.5 right-1.5 rounded-xl bg-indigo-600 px-4 text-sm font-medium text-white shadow-sm transition hover:bg-indigo-500 disabled:cursor-not-allowed disabled:opacity-50"
            >
              {loading ? "Thinking…" : "Ask"}
            </button>
          </div>
        </form>

        {!result && !loading && !error && (
          <div className="mb-10">
            <p className="mb-2 text-xs font-semibold uppercase tracking-wider text-slate-400">
              Try asking
            </p>
            <div className="flex flex-wrap gap-2">
              {EXAMPLE_QUESTIONS.map((ex) => (
                <button
                  key={ex}
                  onClick={() => handleExample(ex)}
                  className="rounded-full border border-slate-200 bg-white px-3 py-1.5 text-xs text-slate-600 shadow-sm transition hover:border-indigo-300 hover:text-indigo-700"
                >
                  {ex}
                </button>
              ))}
            </div>
          </div>
        )}

        {error && (
          <div className="mb-6 rounded-xl border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">
            {error}
          </div>
        )}

        {loading && (
          <div className="rounded-2xl border border-slate-200 bg-white p-6 shadow-sm">
            <div className="mb-3 h-3 w-16 animate-pulse rounded bg-slate-200" />
            <div className="space-y-2">
              <div className="h-3 w-full animate-pulse rounded bg-slate-100" />
              <div className="h-3 w-11/12 animate-pulse rounded bg-slate-100" />
              <div className="h-3 w-3/4 animate-pulse rounded bg-slate-100" />
            </div>
          </div>
        )}

        {result && (
          <div className="space-y-6">
            <article className="rounded-2xl border border-slate-200 bg-white p-6 shadow-sm">
              <div className="mb-4 flex items-center gap-2">
                <span className="grid h-6 w-6 place-items-center rounded-md bg-indigo-50 text-indigo-600">
                  <svg
                    xmlns="http://www.w3.org/2000/svg"
                    viewBox="0 0 24 24"
                    fill="currentColor"
                    className="h-3.5 w-3.5"
                  >
                    <path d="M9.937 15.5A2 2 0 0 0 8.5 14.063l-6.135-1.582a.5.5 0 0 1 0-.962L8.5 9.936A2 2 0 0 0 9.937 8.5l1.582-6.135a.5.5 0 0 1 .963 0L14.063 8.5A2 2 0 0 0 15.5 9.937l6.135 1.581a.5.5 0 0 1 0 .964L15.5 14.063a2 2 0 0 0-1.437 1.437l-1.582 6.135a.5.5 0 0 1-.963 0z" />
                  </svg>
                </span>
                <h2 className="text-xs font-semibold uppercase tracking-wider text-slate-500">
                  Answer
                </h2>
              </div>
              <p className="whitespace-pre-wrap text-[15px] leading-relaxed text-slate-800">
                {result.answer}
              </p>
            </article>

            <section>
              <h2 className="mb-3 flex items-center gap-2 text-xs font-semibold uppercase tracking-wider text-slate-500">
                Sources
                <span className="rounded-full bg-slate-100 px-2 py-0.5 text-[10px] font-medium text-slate-600">
                  {result.sources.length}
                </span>
              </h2>
              <ul className="space-y-3">
                {result.sources.map((src, i) => {
                  const badge = relevanceBadge(src.score);
                  const pct = Math.max(0, Math.round(src.score * 100));
                  return (
                    <li
                      key={i}
                      className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm transition hover:border-slate-300"
                    >
                      <div className="mb-3 flex items-start justify-between gap-3">
                        <h3 className="text-sm font-semibold leading-snug text-slate-900">
                          {src.subject || "(no subject)"}
                        </h3>
                        <span
                          className={`shrink-0 rounded-full px-2.5 py-0.5 text-[11px] font-medium ring-1 ${badge.cls}`}
                          title={badge.label}
                        >
                          {pct}% · {badge.label}
                        </span>
                      </div>
                      <dl className="grid grid-cols-1 gap-x-6 gap-y-1.5 text-xs text-slate-500 sm:grid-cols-2">
                        <div className="flex gap-1.5">
                          <dt className="font-medium text-slate-600">From</dt>
                          <dd className="truncate">{src.sender}</dd>
                        </div>
                        <div className="flex gap-1.5">
                          <dt className="font-medium text-slate-600">Date</dt>
                          <dd>
                            {src.date
                              ? new Date(src.date).toLocaleDateString()
                              : "—"}
                          </dd>
                        </div>
                        <div className="flex gap-1.5 sm:col-span-2">
                          <dt className="font-medium text-slate-600">
                            Participants
                          </dt>
                          <dd className="truncate">{src.participants}</dd>
                        </div>
                        <div className="flex gap-1.5">
                          <dt className="font-medium text-slate-600">
                            Messages
                          </dt>
                          <dd>{src.message_count}</dd>
                        </div>
                      </dl>
                    </li>
                  );
                })}
              </ul>
            </section>
          </div>
        )}
      </div>
    </main>
  );
}

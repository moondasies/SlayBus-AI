"use client";

import { BookMarked, Search, Trash2 } from "lucide-react";
import Link from "next/link";
import { useCallback, useEffect, useState } from "react";

import { Button, DifficultyBadge, Empty, ErrorNote, PageHeader, Spinner, errorText, useToast } from "@/components/ui";
import { api } from "@/lib/api";
import { TYPE_LABELS, type Question, type QuestionType, type Textbook } from "@/lib/types";

const PAGE = 20;

export default function QuestionBank() {
  const toast = useToast();
  const [books, setBooks] = useState<Textbook[]>([]);
  const [book, setBook] = useState<Textbook | null>(null);
  const [chapterId, setChapterId] = useState("");
  const [type, setType] = useState("");
  const [difficulty, setDifficulty] = useState("");
  const [q, setQ] = useState("");
  const [query, setQuery] = useState("");
  const [offset, setOffset] = useState(0);
  const [result, setResult] = useState<{ total: number; items: Question[] } | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [openId, setOpenId] = useState<string | null>(null);

  useEffect(() => { api.textbooks().then(setBooks).catch(() => {}); }, []);

  const load = useCallback(async () => {
    setError(null);
    try {
      setResult(await api.bank({ textbook_id: book?.id, chapter_id: chapterId, type, difficulty, q: query, limit: PAGE, offset }));
    } catch (e) {
      setError(errorText(e));
    }
  }, [book, chapterId, type, difficulty, query, offset]);

  useEffect(() => { load(); }, [load]);

  async function chooseBook(id: string) {
    setChapterId("");
    setOffset(0);
    setBook(id ? await api.textbook(id) : null);
  }

  async function remove(item: Question) {
    if (!confirm("Delete this question forever? It will also disappear from its paper.")) return;
    try {
      await api.deleteQuestion(item.id, false);
      toast("success", "Question deleted");
      load();
    } catch (e) {
      toast("error", errorText(e));
    }
  }

  return (
    <div className="mx-auto max-w-5xl">
      <PageHeader title="Question bank" subtitle="Every question you've generated, saved and searchable." />

      <div className="card mb-6 grid gap-3 p-4 sm:grid-cols-2 lg:grid-cols-5">
        <form className="relative lg:col-span-2" onSubmit={(e) => { e.preventDefault(); setOffset(0); setQuery(q); }}>
          <Search className="pointer-events-none absolute left-3 top-3 h-4 w-4 text-ink-300" aria-hidden />
          <input className="input pl-9" placeholder="Search questions…" value={q} onChange={(e) => setQ(e.target.value)} aria-label="Search questions" />
        </form>
        <select className="input" aria-label="Book" value={book?.id || ""} onChange={(e) => chooseBook(e.target.value)}>
          <option value="">All books</option>
          {books.map((b) => <option key={b.id} value={b.id}>{b.title}</option>)}
        </select>
        <select className="input" aria-label="Question type" value={type} onChange={(e) => { setType(e.target.value); setOffset(0); }}>
          <option value="">All types</option>
          {(Object.keys(TYPE_LABELS) as QuestionType[]).map((t) => <option key={t} value={t}>{TYPE_LABELS[t]}</option>)}
        </select>
        <select className="input" aria-label="Difficulty" value={difficulty} onChange={(e) => { setDifficulty(e.target.value); setOffset(0); }}>
          <option value="">Any difficulty</option><option value="easy">Easy</option><option value="medium">Medium</option><option value="hard">Hard</option>
        </select>
        {book?.chapters && (
          <select className="input lg:col-span-2" aria-label="Chapter" value={chapterId} onChange={(e) => { setChapterId(e.target.value); setOffset(0); }}>
            <option value="">All chapters</option>
            {book.chapters.map((c) => <option key={c.id} value={c.id}>{c.number}. {c.title}</option>)}
          </select>
        )}
      </div>

      {error && <ErrorNote message={error} />}
      {!result && !error && <Spinner />}
      {result && result.items.length === 0 && (
        <Empty title="No questions found" body={query || type || difficulty || book ? "Try different filters." : "Generate a paper and its questions will appear here."}
          action={!query && !type && !difficulty && !book ? <Button href="/papers/new">Create a paper</Button> : undefined} />
      )}
      {result && result.items.length > 0 && (
        <>
          <p className="mb-3 text-sm text-ink-500" data-testid="bank-total">{result.total} question{result.total === 1 ? "" : "s"}</p>
          <ul className="flex flex-col gap-3">
            {result.items.map((item) => (
              <li key={item.id} className="card p-4">
                <div className="flex items-start gap-3">
                  <div className="min-w-0 flex-1">
                    <p className="whitespace-pre-line text-ink">{item.question_text}</p>
                    {item.options && <p className="mt-1 text-sm text-ink-500">{item.options.map((o, i) => `(${"abcd"[i]}) ${o}`).join("   ")}</p>}
                    {openId === item.id && (
                      <div className="mt-2 rounded-lg bg-emerald-50/70 px-3 py-2 text-sm text-ink-700">
                        <strong>Answer:</strong> {item.answer}
                        {item.marking_points?.map((m, i) => <p key={i}>• {m}</p>)}
                      </div>
                    )}
                    <div className="mt-2 flex flex-wrap items-center gap-2 text-xs">
                      <span className="chip bg-ink/5 text-ink-700">{TYPE_LABELS[item.type]}</span>
                      <DifficultyBadge value={item.difficulty} />
                      <span className="chip bg-ink/5 text-ink-700">{item.marks} marks</span>
                      {item.chapter_title && <span className="chip bg-ink/5 text-ink-700">{item.chapter_title}</span>}
                      {item.source_pages.length > 0 && <span className="chip bg-amber-light text-ink-700"><BookMarked className="h-3 w-3" aria-hidden /> p. {item.source_pages.join(", ")}</span>}
                      {item.paper_id && <Link href={`/papers/${item.paper_id}`} className="text-rust hover:underline">Open paper</Link>}
                      <button className="text-ink-500 hover:text-rust" onClick={() => setOpenId(openId === item.id ? null : item.id)}>
                        {openId === item.id ? "Hide answer" : "Show answer"}
                      </button>
                    </div>
                  </div>
                  <button onClick={() => remove(item)} aria-label="Delete question" className="rounded-lg p-2 text-ink-300 hover:bg-red-50 hover:text-red-700">
                    <Trash2 className="h-4 w-4" />
                  </button>
                </div>
              </li>
            ))}
          </ul>
          <div className="mt-5 flex items-center justify-between">
            <Button variant="secondary" size="sm" disabled={offset === 0} onClick={() => setOffset(Math.max(0, offset - PAGE))}>Previous</Button>
            <span className="text-sm text-ink-500">{offset + 1}–{Math.min(offset + PAGE, result.total)} of {result.total}</span>
            <Button variant="secondary" size="sm" disabled={offset + PAGE >= result.total} onClick={() => setOffset(offset + PAGE)}>Next</Button>
          </div>
        </>
      )}
    </div>
  );
}

"use client";

import { ArrowDown, ArrowUp, BookMarked, ChevronDown, Pencil, RefreshCw, Trash2 } from "lucide-react";
import { useState } from "react";

import { api } from "@/lib/api";
import type { Difficulty, Question, SourceChunk } from "@/lib/types";

import { Button, DifficultyBadge, ErrorNote, Modal, Spinner, cx, errorText, useToast } from "./ui";

const LETTERS = "abcd";

function Answer({ q }: { q: Question }) {
  return (
    <div className="mt-3 rounded-xl bg-emerald-50/70 px-4 py-3 text-sm text-ink-700">
      <p><span className="font-semibold text-emerald-900">Answer: </span>
        {q.type === "mcq" && q.options && q.answer ? `(${LETTERS[q.options.indexOf(q.answer)] ?? "?"}) ${q.answer}` : q.answer}
      </p>
      {q.marking_points && q.marking_points.length > 0 && (
        <ul className="mt-1.5 list-disc pl-5">{q.marking_points.map((m, i) => <li key={i}>{m}</li>)}</ul>
      )}
      {q.explanation && <p className="mt-1.5 text-xs text-ink-500">{q.explanation}</p>}
    </div>
  );
}

function EditForm({ q, onSaved, onCancel }: { q: Question; onSaved: (q: Question) => void; onCancel: () => void }) {
  const [text, setText] = useState(q.question_text);
  const [options, setOptions] = useState<string[]>(q.options && q.options.length === 4 ? q.options : ["", "", "", ""]);
  const [correct, setCorrect] = useState(Math.max(0, q.options?.indexOf(q.answer || "") ?? 0));
  const [answer, setAnswer] = useState(q.answer || "");
  const [points, setPoints] = useState((q.marking_points || []).join("\n"));
  const [explanation, setExplanation] = useState(q.explanation || "");
  const [marks, setMarks] = useState(q.marks);
  const [difficulty, setDifficulty] = useState<Difficulty>(q.difficulty);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function save(e: React.FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError(null);
    const body: Partial<Question> = { question_text: text.trim(), explanation: explanation.trim() || null, marks, difficulty };
    if (q.type === "mcq") {
      body.options = options.map((o) => o.trim());
      body.answer = options[correct].trim();
    } else {
      body.answer = answer.trim();
      if (q.type !== "fill_blank" && q.type !== "true_false") body.marking_points = points.split("\n").map((p) => p.trim()).filter(Boolean);
    }
    try {
      onSaved(await api.editQuestion(q.id, body));
    } catch (err) {
      setError(errorText(err));
      setBusy(false);
    }
  }

  return (
    <form onSubmit={save} className="mt-3 flex flex-col gap-3">
      <div>
        <label className="label" htmlFor={`text-${q.id}`}>Question</label>
        <textarea id={`text-${q.id}`} className="input" rows={q.type === "case_based" ? 8 : 3} value={text} onChange={(e) => setText(e.target.value)} required />
      </div>
      {q.type === "mcq" ? (
        <fieldset className="flex flex-col gap-2">
          <legend className="label">Options (select the correct one)</legend>
          {options.map((o, i) => (
            <div key={i} className="flex items-center gap-2">
              <input type="radio" name={`correct-${q.id}`} aria-label={`Option ${LETTERS[i]} is correct`} checked={correct === i}
                onChange={() => setCorrect(i)} className="accent-[#A94513]" />
              <span className="w-5 text-sm text-ink-500">({LETTERS[i]})</span>
              <input className="input" aria-label={`Option ${LETTERS[i]}`} value={o} required
                onChange={(e) => setOptions(options.map((x, j) => (j === i ? e.target.value : x)))} />
            </div>
          ))}
        </fieldset>
      ) : q.type === "true_false" ? (
        <div>
          <label className="label" htmlFor={`ans-${q.id}`}>Answer</label>
          <select id={`ans-${q.id}`} className="input" value={answer} onChange={(e) => setAnswer(e.target.value)}>
            <option>True</option><option>False</option>
          </select>
        </div>
      ) : (
        <div>
          <label className="label" htmlFor={`ans-${q.id}`}>Answer</label>
          <textarea id={`ans-${q.id}`} className="input" rows={q.type === "fill_blank" ? 1 : 3} value={answer} onChange={(e) => setAnswer(e.target.value)} required />
        </div>
      )}
      {!["mcq", "fill_blank", "true_false"].includes(q.type) && (
        <div>
          <label className="label" htmlFor={`pts-${q.id}`}>Marking points (one per line)</label>
          <textarea id={`pts-${q.id}`} className="input" rows={3} value={points} onChange={(e) => setPoints(e.target.value)} />
        </div>
      )}
      <div className="grid gap-3 sm:grid-cols-3">
        <div className="sm:col-span-1">
          <label className="label" htmlFor={`marks-${q.id}`}>Marks</label>
          <input id={`marks-${q.id}`} type="number" min={0.5} max={50} step={0.5} className="input" value={marks} onChange={(e) => setMarks(Number(e.target.value))} />
        </div>
        <div>
          <label className="label" htmlFor={`diff-${q.id}`}>Difficulty</label>
          <select id={`diff-${q.id}`} className="input" value={difficulty} onChange={(e) => setDifficulty(e.target.value as Difficulty)}>
            <option value="easy">Easy</option><option value="medium">Medium</option><option value="hard">Hard</option>
          </select>
        </div>
        <div>
          <label className="label" htmlFor={`exp-${q.id}`}>Note for teacher</label>
          <input id={`exp-${q.id}`} className="input" value={explanation} onChange={(e) => setExplanation(e.target.value)} />
        </div>
      </div>
      {error && <ErrorNote message={error} />}
      <div className="flex justify-end gap-2">
        <Button type="button" variant="ghost" onClick={onCancel}>Cancel</Button>
        <Button type="submit" loading={busy}>Save</Button>
      </div>
    </form>
  );
}

export function QuestionCard({
  q, number, showAnswer, isFirst, isLast, onChange, onRemove, onMove,
}: {
  q: Question; number: number; showAnswer: boolean; isFirst: boolean; isLast: boolean;
  onChange: (q: Question) => void; onRemove: (id: string) => void; onMove: (dir: -1 | 1) => void;
}) {
  const toast = useToast();
  const [editing, setEditing] = useState(false);
  const [open, setOpen] = useState(false);
  const [regenOpen, setRegenOpen] = useState(false);
  const [regenBusy, setRegenBusy] = useState(false);
  const [regenDiff, setRegenDiff] = useState<Difficulty | "">("");
  const [regenNote, setRegenNote] = useState("");
  const [sources, setSources] = useState<SourceChunk[] | null>(null);
  const [sourceOpen, setSourceOpen] = useState(false);

  async function regenerate() {
    setRegenBusy(true);
    try {
      const fresh = await api.regenerate(q.id, { difficulty: regenDiff || undefined, instructions: regenNote.trim() || undefined });
      onChange(fresh);
      setRegenOpen(false);
      setRegenNote("");
      toast("success", `Question ${number} regenerated`);
    } catch (e) {
      toast("error", errorText(e));
    } finally {
      setRegenBusy(false);
    }
  }

  async function remove() {
    if (!confirm("Remove this question from the paper? It stays in your question bank.")) return;
    try {
      await api.deleteQuestion(q.id);
      onRemove(q.id);
    } catch (e) {
      toast("error", errorText(e));
    }
  }

  async function showSource() {
    setSourceOpen(true);
    if (!sources) {
      try {
        setSources(await api.sources(q.id));
      } catch (e) {
        toast("error", errorText(e));
        setSourceOpen(false);
      }
    }
  }

  return (
    <article className={cx("card p-5 transition", regenBusy && "opacity-60")} data-testid="question-card">
      <div className="flex items-start gap-3">
        <span className="mt-0.5 font-serif text-lg font-semibold text-rust">{number}.</span>
        <div className="min-w-0 flex-1">
          {!editing && (
            <>
              <p className="whitespace-pre-line leading-relaxed text-ink" data-testid="question-text">{q.question_text}</p>
              {q.type === "mcq" && q.options && (
                <ol className="mt-2 grid gap-1.5 sm:grid-cols-2">
                  {q.options.map((o, i) => (
                    <li key={i} className={cx("rounded-lg px-3 py-1.5 text-sm",
                      showAnswer && o === q.answer ? "bg-emerald-50 font-medium text-emerald-900" : "bg-white")}>
                      ({LETTERS[i]}) {o}
                    </li>
                  ))}
                </ol>
              )}
              {(showAnswer || open) && <Answer q={q} />}
            </>
          )}
          {editing && <EditForm q={q} onCancel={() => setEditing(false)} onSaved={(nq) => { onChange(nq); setEditing(false); toast("success", "Saved"); }} />}

          <div className="mt-3 flex flex-wrap items-center gap-2 text-xs">
            <DifficultyBadge value={q.difficulty} />
            {q.chapter_title && <span className="chip bg-ink/5 text-ink-700">{q.chapter_title}</span>}
            {q.source_pages.length > 0 && (
              <button onClick={showSource} className="chip bg-amber-light text-ink-700 hover:bg-amber/30" title="Show the textbook passage">
                <BookMarked className="h-3 w-3" aria-hidden /> p. {q.source_pages.join(", ")}
              </button>
            )}
            {!showAnswer && !editing && (
              <button onClick={() => setOpen(!open)} className="chip text-ink-500 hover:text-rust" aria-expanded={open}>
                <ChevronDown className={cx("h-3 w-3 transition", open && "rotate-180")} aria-hidden /> {open ? "Hide answer" : "Answer"}
              </button>
            )}
          </div>
        </div>
        <span className="shrink-0 whitespace-nowrap rounded-lg bg-ink/5 px-2 py-1 text-sm font-medium">{q.marks} {q.marks === 1 ? "mark" : "marks"}</span>
      </div>

      {!editing && (
        <div className="no-print mt-4 flex flex-wrap gap-1 border-t border-ink/10 pt-3">
          <Button size="sm" variant="ghost" onClick={() => setEditing(true)}><Pencil className="h-3.5 w-3.5" aria-hidden /> Edit</Button>
          <Button size="sm" variant="ghost" onClick={() => setRegenOpen(true)} loading={regenBusy}><RefreshCw className="h-3.5 w-3.5" aria-hidden /> Regenerate</Button>
          <Button size="sm" variant="ghost" onClick={remove}><Trash2 className="h-3.5 w-3.5" aria-hidden /> Delete</Button>
          <span className="ml-auto flex gap-1">
            <Button size="sm" variant="ghost" onClick={() => onMove(-1)} disabled={isFirst} aria-label="Move up"><ArrowUp className="h-3.5 w-3.5" /></Button>
            <Button size="sm" variant="ghost" onClick={() => onMove(1)} disabled={isLast} aria-label="Move down"><ArrowDown className="h-3.5 w-3.5" /></Button>
          </span>
        </div>
      )}

      <Modal open={regenOpen} onClose={() => !regenBusy && setRegenOpen(false)} title={`Regenerate question ${number}`}>
        <p className="mb-4 text-sm text-ink-500">SLAYBUS writes a new question of the same type and marks, from the same chapter.</p>
        <div className="flex flex-col gap-4">
          <div>
            <label className="label" htmlFor={`rd-${q.id}`}>Difficulty</label>
            <select id={`rd-${q.id}`} className="input" value={regenDiff} onChange={(e) => setRegenDiff(e.target.value as Difficulty | "")}>
              <option value="">Keep {q.difficulty}</option><option value="easy">Easy</option><option value="medium">Medium</option><option value="hard">Hard</option>
            </select>
          </div>
          <div>
            <label className="label" htmlFor={`rn-${q.id}`}>Instruction <span className="text-ink-300">(optional)</span></label>
            <input id={`rn-${q.id}`} className="input" value={regenNote} onChange={(e) => setRegenNote(e.target.value)} placeholder="e.g. ask about stomata" maxLength={500} />
          </div>
          <div className="flex justify-end gap-2">
            <Button variant="ghost" onClick={() => setRegenOpen(false)} disabled={regenBusy}>Cancel</Button>
            <Button onClick={regenerate} loading={regenBusy}><RefreshCw className="h-4 w-4" aria-hidden /> Regenerate</Button>
          </div>
        </div>
      </Modal>

      <Modal open={sourceOpen} onClose={() => setSourceOpen(false)} title="From your textbook" wide>
        {!sources ? <Spinner /> : sources.length === 0 ? (
          <p className="text-sm text-ink-500">The source passage is no longer available (the book may have been deleted).</p>
        ) : (
          <div className="flex max-h-[60vh] flex-col gap-4 overflow-y-auto">
            {sources.map((s) => (
              <blockquote key={s.id} className="rounded-xl border-l-4 border-amber bg-white p-4">
                <p className="mb-2 text-xs font-medium text-ink-500">{s.chapter_title} · PDF page {s.page}</p>
                <p className="whitespace-pre-line text-sm leading-relaxed text-ink-700">{s.content}</p>
              </blockquote>
            ))}
          </div>
        )}
      </Modal>
    </article>
  );
}

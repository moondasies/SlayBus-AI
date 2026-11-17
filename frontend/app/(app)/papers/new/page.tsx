"use client";

import { ArrowLeft, ArrowRight, Check, Plus, Sparkles, Trash2 } from "lucide-react";
import { useRouter, useSearchParams } from "next/navigation";
import { Suspense, useEffect, useMemo, useState } from "react";

import { Button, Empty, ErrorNote, PageHeader, Spinner, cx, errorText } from "@/components/ui";
import { api } from "@/lib/api";
import { PAPER_TYPE_LABELS, TYPE_LABELS, type PaperType, type QuestionType, type SectionSpec, type Textbook } from "@/lib/types";

const PRESETS: Record<PaperType, { duration: number; sections: SectionSpec[]; blurb: string }> = {
  question_paper: {
    duration: 90,
    blurb: "Board-style paper with sections A–F. 50 marks.",
    sections: [
      { name: "Section A", type: "mcq", count: 10, marks_each: 1 },
      { name: "Section B", type: "fill_blank", count: 5, marks_each: 1 },
      { name: "Section C", type: "true_false", count: 5, marks_each: 1 },
      { name: "Section D", type: "short_answer", count: 5, marks_each: 2 },
      { name: "Section E", type: "long_answer", count: 3, marks_each: 5 },
      { name: "Section F", type: "case_based", count: 1, marks_each: 5 },
    ],
  },
  worksheet: {
    duration: 40,
    blurb: "Practice sheet with space to write answers.",
    sections: [
      { name: "Part A", type: "fill_blank", count: 5, marks_each: 1 },
      { name: "Part B", type: "true_false", count: 5, marks_each: 1 },
      { name: "Part C", type: "short_answer", count: 4, marks_each: 2 },
    ],
  },
  quiz: {
    duration: 15,
    blurb: "Ten quick MCQs for a class check-in.",
    sections: [{ name: "Quiz", type: "mcq", count: 10, marks_each: 1 }],
  },
};

const STEPS = ["Book", "Chapters", "Paper", "Blueprint", "Review"];

function Stepper({ step }: { step: number }) {
  return (
    <ol className="mb-8 flex flex-wrap items-center gap-2 text-sm" aria-label="Progress">
      {STEPS.map((s, i) => (
        <li key={s} className="flex items-center gap-2">
          <span className={cx("flex h-7 w-7 items-center justify-center rounded-full text-xs font-semibold",
            i < step ? "bg-rust text-ivory" : i === step ? "bg-ink text-ivory" : "bg-ink/10 text-ink-500")}
            aria-current={i === step ? "step" : undefined}>
            {i < step ? <Check className="h-3.5 w-3.5" /> : i + 1}
          </span>
          <span className={cx(i === step ? "font-medium text-ink" : "text-ink-500")}>{s}</span>
          {i < STEPS.length - 1 && <span className="mx-1 h-px w-6 bg-ink/15" aria-hidden />}
        </li>
      ))}
    </ol>
  );
}

function Builder() {
  const router = useRouter();
  const params = useSearchParams();
  const [books, setBooks] = useState<Textbook[] | null>(null);
  const [book, setBook] = useState<Textbook | null>(null);
  const [step, setStep] = useState(0);
  const [chapterIds, setChapterIds] = useState<string[]>([]);
  const [paperType, setPaperType] = useState<PaperType>("question_paper");
  const [title, setTitle] = useState("");
  const [classLevel, setClassLevel] = useState("");
  const [subject, setSubject] = useState("");
  const [board, setBoard] = useState("");
  const [duration, setDuration] = useState<number | "">(90);
  const [sections, setSections] = useState<SectionSpec[]>(PRESETS.question_paper.sections);
  const [mix, setMix] = useState({ easy: 30, medium: 50, hard: 20 });
  const [instructions, setInstructions] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    api.textbooks().then((all) => setBooks(all.filter((b) => b.status === "ready"))).catch((e) => setError(errorText(e)));
  }, []);

  async function chooseBook(id: string) {
    setError(null);
    try {
      const full = await api.textbook(id);
      setBook(full);
      setChapterIds([]);
      setSubject(full.subject || "");
      setClassLevel(full.class_level || "");
      setBoard(full.board || "");
      setStep(1);
    } catch (e) {
      setError(errorText(e));
    }
  }

  useEffect(() => {
    const pre = params.get("book");
    if (pre && books && !book && books.some((b) => b.id === pre)) chooseBook(pre);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [books]);

  function choosePreset(t: PaperType) {
    setPaperType(t);
    setSections(PRESETS[t].sections.map((s) => ({ ...s })));
    setDuration(PRESETS[t].duration);
  }

  const total = useMemo(() => sections.reduce((n, s) => n + (Number(s.count) || 0) * (Number(s.marks_each) || 0), 0), [sections]);
  const totalQuestions = sections.reduce((n, s) => n + (Number(s.count) || 0), 0);
  const mixSum = mix.easy + mix.medium + mix.hard;
  const sectionNames = sections.map((s) => s.name.trim().toLowerCase());
  const blueprintError =
    sections.length === 0 ? "Add at least one section." :
    sections.some((s) => !s.name.trim()) ? "Every section needs a name." :
    new Set(sectionNames).size !== sectionNames.length ? "Section names must be different." :
    sections.some((s) => !(s.count >= 1 && s.count <= 50)) ? "Each section needs 1–50 questions." :
    sections.some((s) => !(s.marks_each > 0 && s.marks_each <= 20)) ? "Marks per question must be between 0.5 and 20." :
    totalQuestions > 100 ? "Keep it to 100 questions or fewer." :
    mixSum !== 100 ? `Difficulty mix adds up to ${mixSum}%, it must be 100%.` : null;

  function updateSection(i: number, patch: Partial<SectionSpec>) {
    setSections((all) => all.map((s, j) => (j === i ? { ...s, ...patch } : s)));
  }

  async function generate() {
    if (!book) return;
    setBusy(true);
    setError(null);
    try {
      const paper = await api.generatePaper({
        textbook_id: book.id,
        chapter_ids: chapterIds,
        title: title.trim() || null,
        paper_type: paperType,
        class_level: classLevel || null,
        subject: subject || null,
        board: board || null,
        duration_min: duration === "" ? null : duration,
        instructions: instructions.trim() || null,
        sections: sections.map((s) => ({ ...s, name: s.name.trim(), count: Number(s.count), marks_each: Number(s.marks_each) })),
        difficulty: mix,
      });
      router.push(`/papers/${paper.id}`);
    } catch (e) {
      setError(errorText(e));
      setBusy(false);
    }
  }

  if (!books && !error) return <Spinner />;

  return (
    <div className="mx-auto max-w-4xl">
      <PageHeader title="Create a paper" subtitle="Questions come only from the chapters you pick." />
      <Stepper step={step} />
      {error && <div className="mb-4"><ErrorNote message={error} /></div>}

      {step === 0 && books && (
        books.length === 0 ? (
          <Empty title="No ready books" body="Upload a textbook first. Once it's processed you can generate papers from it."
            action={<Button href="/books/new">Upload a book</Button>} />
        ) : (
          <div className="grid gap-3 sm:grid-cols-2">
            {books.map((b) => (
              <button key={b.id} onClick={() => chooseBook(b.id)} className="card p-5 text-left transition hover:border-rust/40">
                <p className="font-serif text-lg font-semibold">{b.title}</p>
                <p className="text-sm text-ink-500">{[b.subject, b.class_level && `Class ${b.class_level}`, `${b.chapter_count} chapters`].filter(Boolean).join(" · ")}</p>
              </button>
            ))}
          </div>
        )
      )}

      {step === 1 && book && (
        <div className="card p-6">
          <div className="mb-4 flex items-center justify-between">
            <h2 className="text-xl font-semibold">Which chapters?</h2>
            <button className="text-sm text-rust hover:underline"
              onClick={() => setChapterIds(chapterIds.length === book.chapters!.length ? [] : book.chapters!.map((c) => c.id))}>
              {chapterIds.length === book.chapters!.length ? "Clear all" : "Select all"}
            </button>
          </div>
          <div className="flex flex-col gap-2">
            {book.chapters!.map((c) => {
              const on = chapterIds.includes(c.id);
              return (
                <label key={c.id} className={cx("flex cursor-pointer items-center gap-3 rounded-xl border px-4 py-3 transition",
                  on ? "border-rust bg-rust-light/40" : "border-ink/10 bg-white hover:border-ink/25")}>
                  <input type="checkbox" className="h-4 w-4 accent-[#A94513]" checked={on}
                    onChange={() => setChapterIds(on ? chapterIds.filter((x) => x !== c.id) : [...chapterIds, c.id])} />
                  <span className="font-medium">{c.number}. {c.title}</span>
                  <span className="ml-auto text-xs text-ink-500">pp. {c.start_page}–{c.end_page}</span>
                </label>
              );
            })}
          </div>
        </div>
      )}

      {step === 2 && (
        <div className="card flex flex-col gap-6 p-6">
          <div>
            <h2 className="mb-3 text-xl font-semibold">What are you making?</h2>
            <div className="grid gap-3 sm:grid-cols-3">
              {(Object.keys(PRESETS) as PaperType[]).map((t) => (
                <button key={t} onClick={() => choosePreset(t)} aria-pressed={paperType === t}
                  className={cx("rounded-xl border p-4 text-left transition",
                    paperType === t ? "border-rust bg-rust-light/40" : "border-ink/10 bg-white hover:border-ink/25")}>
                  <p className="font-semibold">{PAPER_TYPE_LABELS[t]}</p>
                  <p className="mt-1 text-xs text-ink-500">{PRESETS[t].blurb}</p>
                </button>
              ))}
            </div>
          </div>
          <div>
            <label className="label" htmlFor="title">Title <span className="text-ink-300">(optional)</span></label>
            <input id="title" className="input" value={title} onChange={(e) => setTitle(e.target.value)} placeholder="Periodic Test 1 – Science" />
          </div>
          <div className="grid gap-4 sm:grid-cols-4">
            <div><label className="label" htmlFor="class">Class</label>
              <input id="class" className="input" value={classLevel} onChange={(e) => setClassLevel(e.target.value)} /></div>
            <div><label className="label" htmlFor="subject">Subject</label>
              <input id="subject" className="input" value={subject} onChange={(e) => setSubject(e.target.value)} /></div>
            <div><label className="label" htmlFor="board">Board</label>
              <input id="board" className="input" value={board} onChange={(e) => setBoard(e.target.value)} /></div>
            <div><label className="label" htmlFor="duration">Time (min)</label>
              <input id="duration" type="number" min={5} max={360} className="input" value={duration}
                onChange={(e) => setDuration(e.target.value === "" ? "" : Number(e.target.value))} /></div>
          </div>
        </div>
      )}

      {step === 3 && (
        <div className="flex flex-col gap-5">
          <div className="card p-6">
            <div className="mb-4 flex items-center justify-between">
              <h2 className="text-xl font-semibold">Sections</h2>
              <span className="font-serif text-lg" data-testid="total-marks">Total: <strong>{total}</strong> marks · {totalQuestions} questions</span>
            </div>
            <div className="flex flex-col gap-3">
              <div className="hidden grid-cols-[1.2fr_1.6fr_0.7fr_0.8fr_0.6fr_auto] gap-3 px-1 text-xs font-medium text-ink-500 sm:grid">
                <span>Name</span><span>Question type</span><span>How many</span><span>Marks each</span><span>Subtotal</span><span />
              </div>
              {sections.map((s, i) => (
                <div key={i} className="grid grid-cols-2 gap-3 rounded-xl border border-ink/10 bg-white p-3 sm:grid-cols-[1.2fr_1.6fr_0.7fr_0.8fr_0.6fr_auto] sm:items-center sm:border-0 sm:bg-transparent sm:p-0">
                  <input aria-label={`Section ${i + 1} name`} className="input" value={s.name} onChange={(e) => updateSection(i, { name: e.target.value })} />
                  <select aria-label={`Section ${i + 1} type`} className="input" value={s.type} onChange={(e) => updateSection(i, { type: e.target.value as QuestionType })}>
                    {(Object.keys(TYPE_LABELS) as QuestionType[]).map((t) => <option key={t} value={t}>{TYPE_LABELS[t]}</option>)}
                  </select>
                  <input aria-label={`Section ${i + 1} count`} type="number" min={1} max={50} className="input" value={s.count}
                    onChange={(e) => updateSection(i, { count: Number(e.target.value) })} />
                  <input aria-label={`Section ${i + 1} marks each`} type="number" min={0.5} max={20} step={0.5} className="input" value={s.marks_each}
                    onChange={(e) => updateSection(i, { marks_each: Number(e.target.value) })} />
                  <span className="text-sm font-medium text-ink-700">{(s.count || 0) * (s.marks_each || 0)} marks</span>
                  <button aria-label={`Remove section ${i + 1}`} className="justify-self-end rounded-lg p-2 text-ink-500 hover:bg-red-50 hover:text-red-700"
                    onClick={() => setSections(sections.filter((_, j) => j !== i))}>
                    <Trash2 className="h-4 w-4" />
                  </button>
                </div>
              ))}
            </div>
            <Button variant="ghost" size="sm" className="mt-3" disabled={sections.length >= 10}
              onClick={() => setSections([...sections, { name: `Section ${String.fromCharCode(65 + sections.length)}`, type: "short_answer", count: 3, marks_each: 2 }])}>
              <Plus className="h-4 w-4" aria-hidden /> Add section
            </Button>
          </div>

          <div className="card p-6">
            <h2 className="mb-1 text-xl font-semibold">Difficulty mix</h2>
            <p className="mb-4 text-sm text-ink-500">Easy = recall · Medium = understanding · Hard = analysis. Must add up to 100%.</p>
            <div className="mb-4 flex h-3 overflow-hidden rounded-full bg-ink/10" aria-hidden>
              <div className="bg-emerald-400" style={{ width: `${mix.easy}%` }} />
              <div className="bg-amber" style={{ width: `${mix.medium}%` }} />
              <div className="bg-rust" style={{ width: `${mix.hard}%` }} />
            </div>
            <div className="grid gap-4 sm:grid-cols-3">
              {(["easy", "medium", "hard"] as const).map((k) => (
                <div key={k}>
                  <label className="label capitalize" htmlFor={`mix-${k}`}>{k} (%)</label>
                  <input id={`mix-${k}`} type="number" min={0} max={100} step={5} className="input" value={mix[k]}
                    onChange={(e) => setMix({ ...mix, [k]: Math.max(0, Math.min(100, Number(e.target.value) || 0)) })} />
                </div>
              ))}
            </div>
          </div>

          <div className="card p-6">
            <label className="label" htmlFor="instructions">General instructions <span className="text-ink-300">(optional, one per line)</span></label>
            <textarea id="instructions" rows={3} className="input" value={instructions} onChange={(e) => setInstructions(e.target.value)}
              placeholder={"All questions are compulsory.\nDraw diagrams wherever necessary."} />
          </div>
          {blueprintError && <ErrorNote message={blueprintError} />}
        </div>
      )}

      {step === 4 && book && (
        <div className="card flex flex-col gap-4 p-6">
          <h2 className="text-xl font-semibold">Ready to generate</h2>
          <dl className="grid gap-3 text-sm sm:grid-cols-2">
            <div><dt className="text-ink-500">Book</dt><dd className="font-medium">{book.title}</dd></div>
            <div><dt className="text-ink-500">Type</dt><dd className="font-medium">{PAPER_TYPE_LABELS[paperType]}</dd></div>
            <div className="sm:col-span-2"><dt className="text-ink-500">Chapters</dt>
              <dd className="font-medium">{book.chapters!.filter((c) => chapterIds.includes(c.id)).map((c) => c.title).join(", ")}</dd></div>
            <div><dt className="text-ink-500">Marks / time</dt><dd className="font-medium">{total} marks · {duration || "—"} min</dd></div>
            <div><dt className="text-ink-500">Difficulty</dt><dd className="font-medium">{mix.easy}% easy · {mix.medium}% medium · {mix.hard}% hard</dd></div>
          </dl>
          <ul className="flex flex-col gap-1 rounded-xl bg-white p-4 text-sm">
            {sections.map((s) => (
              <li key={s.name} className="flex justify-between"><span>{s.name}: {s.count} × {TYPE_LABELS[s.type]}</span><span>{s.count * s.marks_each} marks</span></li>
            ))}
          </ul>
          <p className="text-sm text-ink-500">This usually takes under a minute. You can edit every question afterwards.</p>
        </div>
      )}

      {step > 0 && (
        <div className="mt-6 flex justify-between">
          <Button variant="secondary" onClick={() => setStep(step - 1)} disabled={busy}><ArrowLeft className="h-4 w-4" aria-hidden /> Back</Button>
          {step < 4 ? (
            <Button onClick={() => setStep(step + 1)} disabled={(step === 1 && chapterIds.length === 0) || (step === 3 && !!blueprintError)}>
              Next <ArrowRight className="h-4 w-4" aria-hidden />
            </Button>
          ) : (
            <Button onClick={generate} loading={busy}><Sparkles className="h-4 w-4" aria-hidden /> Generate paper</Button>
          )}
        </div>
      )}
    </div>
  );
}

export default function NewPaper() {
  return (
    <Suspense fallback={<Spinner />}>
      <Builder />
    </Suspense>
  );
}

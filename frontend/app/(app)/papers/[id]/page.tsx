"use client";

import { motion } from "framer-motion";
import { Check, Download, Eye, FileText, Library, Pencil, Plus, RotateCcw, Sparkles, Trash2 } from "lucide-react";
import { useParams, useRouter } from "next/navigation";
import { useCallback, useEffect, useMemo, useState } from "react";

import { PaperPreview } from "@/components/PaperPreview";
import { QuestionCard } from "@/components/QuestionCard";
import { Button, DifficultyBadge, ErrorNote, Modal, Spinner, StatusBadge, cx, errorText, useToast } from "@/components/ui";
import { api } from "@/lib/api";
import { usePolling } from "@/lib/hooks";
import { PAPER_TYPE_LABELS, TYPE_LABELS, type Paper, type Question, type QuestionType } from "@/lib/types";

function groupQuestions(paper: Paper) {
  const names = paper.sections.map((s) => s.name);
  paper.questions.forEach((q) => !names.includes(q.section) && names.push(q.section));
  return names
    .map((name) => ({ name, questions: paper.questions.filter((q) => q.section === name) }))
    .filter((g) => g.questions.length > 0 || paper.sections.some((s) => s.name === g.name));
}

function Generating() {
  const lines = ["Reading the chapters you picked…", "Finding the most important passages…", "Writing questions from your book…", "Checking answers and marking points…"];
  return (
    <div className="card flex flex-col items-center px-6 py-16 text-center">
      <motion.div animate={{ rotate: 360 }} transition={{ repeat: Infinity, duration: 3, ease: "linear" }} className="text-4xl text-rust">✦</motion.div>
      <h2 className="mt-5 text-2xl font-semibold">Writing your paper</h2>
      <div className="mt-3 h-6 overflow-hidden text-ink-500">
        <motion.div animate={{ y: [0, -24, -48, -72, 0] }} transition={{ repeat: Infinity, duration: 10, times: [0, 0.25, 0.5, 0.75, 1] }}>
          {lines.map((l) => <p key={l} className="h-6">{l}</p>)}
        </motion.div>
      </div>
      <p className="mt-6 text-xs text-ink-300">Usually under a minute. You can leave this page; we&apos;ll keep working.</p>
    </div>
  );
}

function BankModal({ open, onClose, paper, section, type, onAdded }: {
  open: boolean; onClose: () => void; paper: Paper; section: string; type: QuestionType; onAdded: (q: Question) => void;
}) {
  const toast = useToast();
  const [items, setItems] = useState<Question[] | null>(null);
  const [search, setSearch] = useState("");
  const [busy, setBusy] = useState<string | null>(null);

  const load = useCallback(async (q: string) => {
    setItems(null);
    try {
      const res = await api.bank({ type, q, textbook_id: paper.textbook_id || undefined, limit: 50 });
      const existing = new Set(paper.questions.map((x) => x.question_text));
      setItems(res.items.filter((x) => !existing.has(x.question_text)));
    } catch (e) {
      toast("error", errorText(e));
      setItems([]);
    }
  }, [type, paper, toast]);

  useEffect(() => {
    if (open) load("");
  }, [open]); // eslint-disable-line react-hooks/exhaustive-deps

  async function add(q: Question) {
    setBusy(q.id);
    try {
      onAdded(await api.addFromBank(paper.id, q.id, section));
      toast("success", "Added to paper");
      onClose();
    } catch (e) {
      toast("error", errorText(e));
    } finally {
      setBusy(null);
    }
  }

  return (
    <Modal open={open} onClose={onClose} title={`Add to ${section} from your bank`} wide>
      <form onSubmit={(e) => { e.preventDefault(); load(search); }} className="mb-4 flex gap-2">
        <input className="input" placeholder={`Search ${TYPE_LABELS[type].toLowerCase()} questions…`} value={search} onChange={(e) => setSearch(e.target.value)} />
        <Button type="submit" variant="secondary">Search</Button>
      </form>
      {!items ? <Spinner /> : items.length === 0 ? (
        <p className="text-sm text-ink-500">No other {TYPE_LABELS[type].toLowerCase()} questions in your bank for this book yet.</p>
      ) : (
        <ul className="flex max-h-[55vh] flex-col gap-2 overflow-y-auto">
          {items.map((q) => (
            <li key={q.id} className="flex items-start gap-3 rounded-xl border border-ink/10 bg-white p-3">
              <div className="min-w-0 flex-1">
                <p className="line-clamp-3 text-sm">{q.question_text}</p>
                <div className="mt-1.5 flex gap-2"><DifficultyBadge value={q.difficulty} />
                  <span className="chip bg-ink/5 text-ink-700">{q.marks} marks</span>
                  {q.chapter_title && <span className="chip bg-ink/5 text-ink-700">{q.chapter_title}</span>}</div>
              </div>
              <Button size="sm" onClick={() => add(q)} loading={busy === q.id}><Plus className="h-3.5 w-3.5" aria-hidden /> Add</Button>
            </li>
          ))}
        </ul>
      )}
    </Modal>
  );
}

export default function PaperEditor() {
  const { id } = useParams<{ id: string }>();
  const router = useRouter();
  const toast = useToast();
  const load = useCallback(() => api.paper(id), [id]);
  const { data: paper, setData: setPaper, error } = usePolling(load, (p) => p.status === "generating", 2000);
  const [mode, setMode] = useState<"edit" | "preview">("edit");
  const [answers, setAnswers] = useState(true);
  const [downloading, setDownloading] = useState<string | null>(null);
  const [editingTitle, setEditingTitle] = useState(false);
  const [title, setTitle] = useState("");
  const [bankFor, setBankFor] = useState<{ section: string; type: QuestionType } | null>(null);
  const [retrying, setRetrying] = useState(false);

  const groups = useMemo(() => (paper ? groupQuestions(paper) : []), [paper]);
  const total = paper?.questions.reduce((n, q) => n + q.marks, 0) ?? 0;

  const replace = (q: Question) => setPaper((p) => p && { ...p, questions: p.questions.map((x) => (x.id === q.id ? q : x)) });
  const remove = (qid: string) => setPaper((p) => p && { ...p, questions: p.questions.filter((x) => x.id !== qid) });

  async function move(section: string, index: number, dir: -1 | 1) {
    if (!paper) return;
    const group = groups.find((g) => g.name === section)!;
    const ids = group.questions.map((q) => q.id);
    const j = index + dir;
    if (j < 0 || j >= ids.length) return;
    [ids[index], ids[j]] = [ids[j], ids[index]];
    const order = groups.flatMap((g) => (g.name === section ? ids : g.questions.map((q) => q.id)));
    const byId = new Map(paper.questions.map((q) => [q.id, q]));
    const previous = paper;
    setPaper({ ...paper, questions: order.map((qid) => byId.get(qid)!) });
    try {
      await api.reorder(paper.id, order);
    } catch (e) {
      setPaper(previous);
      toast("error", errorText(e));
    }
  }

  async function saveTitle() {
    if (!paper || !title.trim()) return;
    try {
      const updated = await api.updatePaper(paper.id, { title: title.trim() });
      setPaper({ ...paper, title: updated.title });
      setEditingTitle(false);
    } catch (e) {
      toast("error", errorText(e));
    }
  }

  async function download(format: "pdf" | "docx") {
    if (!paper) return;
    setDownloading(format);
    try {
      const name = await api.download(paper.id, format, answers);
      toast("success", `Downloaded ${name}`);
    } catch (e) {
      toast("error", errorText(e));
    } finally {
      setDownloading(null);
    }
  }

  async function retry() {
    if (!paper) return;
    setRetrying(true);
    try {
      const fresh = await api.generatePaper({ ...paper.config, title: paper.title });
      await api.deletePaper(paper.id).catch(() => {});
      router.replace(`/papers/${fresh.id}`);
    } catch (e) {
      toast("error", errorText(e));
      setRetrying(false);
    }
  }

  async function deletePaper() {
    if (!paper || !confirm("Delete this paper? Its questions stay in your question bank.")) return;
    try {
      await api.deletePaper(paper.id);
      toast("success", "Paper deleted");
      router.replace("/dashboard");
    } catch (e) {
      toast("error", errorText(e));
    }
  }

  if (error && !paper) return <ErrorNote message={error} />;
  if (!paper) return <Spinner />;

  let number = 0;
  return (
    <div className="mx-auto max-w-4xl">
      <div className="mb-6 flex flex-col gap-3">
        <div className="flex items-center gap-2 text-sm text-ink-500">
          <FileText className="h-4 w-4" aria-hidden /> {PAPER_TYPE_LABELS[paper.paper_type]}
          {paper.textbook_title && <>· {paper.textbook_title}</>}
          <StatusBadge status={paper.status} />
        </div>
        {editingTitle ? (
          <form onSubmit={(e) => { e.preventDefault(); saveTitle(); }} className="flex gap-2">
            <input className="input font-serif text-2xl" value={title} onChange={(e) => setTitle(e.target.value)} autoFocus aria-label="Paper title" />
            <Button type="submit"><Check className="h-4 w-4" aria-hidden /> Save</Button>
          </form>
        ) : (
          <h1 className="group flex items-start gap-2 text-3xl font-semibold sm:text-4xl">
            {paper.title}
            {paper.status === "ready" && (
              <button onClick={() => { setTitle(paper.title); setEditingTitle(true); }} aria-label="Rename paper"
                className="mt-2 rounded-lg p-1 text-ink-300 opacity-0 transition hover:text-rust group-hover:opacity-100 focus:opacity-100">
                <Pencil className="h-4 w-4" />
              </button>
            )}
          </h1>
        )}
        {paper.status === "ready" && (
          <p className="text-ink-500" data-testid="paper-summary">
            {paper.questions.length} questions · <strong className="text-ink">{total} marks</strong>
            {paper.duration_min && ` · ${paper.duration_min} minutes`}
            {paper.config.class_level && ` · Class ${paper.config.class_level}`}
          </p>
        )}
      </div>

      {paper.status === "generating" && <Generating />}

      {paper.status === "failed" && (
        <div className="card flex flex-col gap-4 p-6">
          <ErrorNote message={paper.error_message || "Generation failed."} />
          <div className="flex gap-2">
            <Button onClick={retry} loading={retrying}><RotateCcw className="h-4 w-4" aria-hidden /> Try again</Button>
            <Button variant="danger" onClick={deletePaper}><Trash2 className="h-4 w-4" aria-hidden /> Delete</Button>
          </div>
        </div>
      )}

      {paper.status === "ready" && (
        <>
          {paper.error_message && <div className="mb-4 rounded-xl bg-amber-light px-4 py-3 text-sm text-ink-700">{paper.error_message}</div>}

          <div className="no-print sticky top-[57px] z-20 -mx-4 mb-6 flex flex-wrap items-center gap-2 border-y border-ink/10 bg-ivory/95 px-4 py-3 backdrop-blur lg:top-0">
            <div className="flex rounded-xl border border-ink/15 bg-white p-0.5" role="tablist">
              {(["edit", "preview"] as const).map((m) => (
                <button key={m} role="tab" aria-selected={mode === m} onClick={() => setMode(m)}
                  className={cx("flex items-center gap-1.5 rounded-lg px-3 py-1.5 text-sm font-medium capitalize transition",
                    mode === m ? "bg-ink text-ivory" : "text-ink-700 hover:bg-ink/5")}>
                  {m === "edit" ? <Pencil className="h-3.5 w-3.5" aria-hidden /> : <Eye className="h-3.5 w-3.5" aria-hidden />} {m}
                </button>
              ))}
            </div>
            <label className="ml-1 flex cursor-pointer items-center gap-2 text-sm">
              <input type="checkbox" checked={answers} onChange={(e) => setAnswers(e.target.checked)} className="h-4 w-4 accent-[#A94513]" />
              Answer key
            </label>
            <div className="ml-auto flex gap-2">
              <Button size="sm" variant="secondary" onClick={() => download("docx")} loading={downloading === "docx"}><Download className="h-3.5 w-3.5" aria-hidden /> DOCX</Button>
              <Button size="sm" onClick={() => download("pdf")} loading={downloading === "pdf"}><Download className="h-3.5 w-3.5" aria-hidden /> PDF</Button>
              <Button size="sm" variant="ghost" onClick={deletePaper} aria-label="Delete paper"><Trash2 className="h-3.5 w-3.5" /></Button>
            </div>
          </div>

          {mode === "preview" ? (
            <PaperPreview paper={paper} groups={groups.filter((g) => g.questions.length)} showAnswers={answers} />
          ) : (
            <div className="flex flex-col gap-8">
              {groups.map((g) => {
                const spec = paper.sections.find((s) => s.name === g.name);
                const type = spec?.type || g.questions[0]?.type || "short_answer";
                const marks = g.questions.reduce((n, q) => n + q.marks, 0);
                return (
                  <section key={g.name}>
                    <div className="mb-3 flex items-end justify-between gap-3">
                      <div>
                        <h2 className="text-2xl font-semibold">{g.name}</h2>
                        <p className="text-sm text-ink-500">{TYPE_LABELS[type]} · {g.questions.length} questions · {marks} marks</p>
                      </div>
                      <Button size="sm" variant="ghost" className="shrink-0 whitespace-nowrap" onClick={() => setBankFor({ section: g.name, type })}>
                        <Library className="h-3.5 w-3.5" aria-hidden /> Add from bank
                      </Button>
                    </div>
                    <div className="flex flex-col gap-3">
                      {g.questions.map((q, i) => {
                        number += 1;
                        return (
                          <QuestionCard key={q.id} q={q} number={number} showAnswer={answers}
                            isFirst={i === 0} isLast={i === g.questions.length - 1}
                            onChange={replace} onRemove={remove} onMove={(dir) => move(g.name, i, dir)} />
                        );
                      })}
                      {g.questions.length === 0 && <p className="rounded-xl border border-dashed border-ink/15 p-4 text-sm text-ink-500">No questions in this section.</p>}
                    </div>
                  </section>
                );
              })}
              <div className="card flex flex-col items-center gap-2 p-6 text-center">
                <Sparkles className="h-5 w-5 text-rust" aria-hidden />
                <p className="text-sm text-ink-500">Happy with it? Download a print-ready PDF, or a Word file to tweak further.</p>
              </div>
            </div>
          )}
        </>
      )}

      {bankFor && (
        <BankModal open={!!bankFor} onClose={() => setBankFor(null)} paper={paper} section={bankFor.section} type={bankFor.type}
          onAdded={(q) => setPaper((p) => p && { ...p, questions: [...p.questions, q] })} />
      )}
    </div>
  );
}

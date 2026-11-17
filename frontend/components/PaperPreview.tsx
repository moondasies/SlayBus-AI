"use client";

import { PAPER_TYPE_LABELS, TYPE_LABELS, type Paper, type Question } from "@/lib/types";

const LETTERS = "abcd";

/** A print-like view of the paper, close to what the PDF export looks like. */
export function PaperPreview({ paper, groups, showAnswers }: {
  paper: Paper; groups: { name: string; questions: Question[] }[]; showAnswers: boolean;
}) {
  const c = paper.config;
  const total = groups.reduce((n, g) => n + g.questions.reduce((m, q) => m + q.marks, 0), 0);
  const instructions = (c.instructions || "").split("\n").map((s) => s.trim()).filter(Boolean);
  let n = 0;
  return (
    <div className="mx-auto max-w-3xl rounded-sm bg-white px-6 py-10 font-serif text-[15px] text-black shadow-card sm:px-12" data-testid="paper-preview">
      <h2 className="text-center text-2xl font-bold">{paper.title}</h2>
      <p className="text-center text-sm text-neutral-600">{PAPER_TYPE_LABELS[paper.paper_type]}</p>
      <div className="mt-5 flex justify-between text-sm">
        <div>{c.class_level && <p>Class: {c.class_level}</p>}{c.subject && <p>Subject: {c.subject}</p>}{c.board && <p>Board: {c.board}</p>}</div>
        <div className="text-right">{paper.duration_min && <p>Time: {paper.duration_min} minutes</p>}<p>Maximum Marks: {total}</p></div>
      </div>
      <hr className="my-3 border-black" />
      {paper.paper_type !== "question_paper" && <p className="mb-3 text-sm">Name: ____________________ &nbsp; Class/Section: ______ &nbsp; Roll No.: ____</p>}
      {instructions.length > 0 && (
        <div className="mb-4 text-sm">
          <p className="font-bold">General Instructions:</p>
          <ol className="list-decimal pl-5 text-neutral-700">{instructions.map((s, i) => <li key={i}>{s}</li>)}</ol>
        </div>
      )}
      {groups.map((g) => {
        const spec = paper.sections.find((s) => s.name === g.name);
        const marks = g.questions.reduce((m, q) => m + q.marks, 0);
        return (
          <section key={g.name} className="mt-5">
            <h3 className="font-serif text-base font-bold">
              {g.name}: {TYPE_LABELS[spec?.type || g.questions[0].type]} ({marks} marks)
            </h3>
            {g.questions.map((q) => {
              n += 1;
              return (
                <div key={q.id} className="mt-3">
                  <div className="flex gap-2">
                    <span className="w-6 shrink-0">{n}.</span>
                    <p className="flex-1 whitespace-pre-line">{q.question_text}</p>
                    <span className="shrink-0">[{q.marks}]</span>
                  </div>
                  {q.type === "mcq" && q.options && (
                    <div className="ml-8 mt-1 grid grid-cols-2 gap-x-6 gap-y-0.5">
                      {q.options.map((o, i) => <span key={i}>({LETTERS[i]}) {o}</span>)}
                    </div>
                  )}
                  {showAnswers && (
                    <div className="ml-8 mt-1 border-l-2 border-emerald-600 pl-3 text-sm text-emerald-900">
                      <p>Ans: {q.answer}</p>
                      {q.marking_points?.map((m, i) => <p key={i}>• {m}</p>)}
                    </div>
                  )}
                </div>
              );
            })}
          </section>
        );
      })}
    </div>
  );
}

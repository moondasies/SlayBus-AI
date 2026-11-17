"use client";

import { motion } from "framer-motion";
import { BookOpenCheck, FileCheck2, PencilLine, Printer, Sparkles, Target } from "lucide-react";
import Link from "next/link";

import { Button, Wordmark } from "@/components/ui";
import { useAuth } from "@/lib/auth";

const STEPS = [
  { icon: BookOpenCheck, title: "Upload your textbook", body: "Drop in the PDF your class actually uses. SLAYBUS finds the chapters for you." },
  { icon: Target, title: "Set the blueprint", body: "Pick chapters, total marks, sections, question types and the easy / medium / hard mix." },
  { icon: Sparkles, title: "Generate in minutes", body: "Every question is written from your book's own pages, with the source page tracked." },
  { icon: PencilLine, title: "Edit anything", body: "Rewrite, regenerate, reorder or delete any single question until it's just right." },
  { icon: Printer, title: "Print with answer key", body: "Download a clean PDF or Word file, with a marking scheme when you want one." },
  { icon: FileCheck2, title: "Build a question bank", body: "Every question is saved, searchable and reusable for the next test." },
];

export default function Landing() {
  const { session } = useAuth();
  return (
    <div className="min-h-screen">
      <header className="mx-auto flex max-w-6xl items-center justify-between px-5 py-5">
        <Wordmark />
        <div className="flex items-center gap-2">
          {session ? (
            <Button href="/dashboard">Open dashboard</Button>
          ) : (
            <>
              <Link href="/login" className="px-3 text-sm font-medium text-ink-700 hover:text-rust">Log in</Link>
              <Button href="/login?mode=signup">Start free</Button>
            </>
          )}
        </div>
      </header>

      <section className="mx-auto max-w-6xl px-5 pb-20 pt-12 sm:pt-20">
        <motion.div initial={{ opacity: 0, y: 14 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.5 }} className="max-w-3xl">
          <span className="chip bg-amber-light text-ink-700">For CBSE · ICSE · State board teachers</span>
          <h1 className="mt-5 text-5xl font-semibold leading-[1.05] text-ink sm:text-7xl">
            Classroom-ready papers. <span className="italic text-rust">Powered by your syllabus.</span>
          </h1>
          <p className="mt-6 max-w-2xl text-lg text-ink-700">
            SLAYBUS reads your textbook and writes question papers, worksheets, quizzes and answer keys from it,
            so you stop spending your weekends on test papers.
          </p>
          <div className="mt-8 flex flex-wrap gap-3">
            <Button href={session ? "/papers/new" : "/login?mode=signup"} size="lg">Create your first paper</Button>
            <Button href="#how" variant="secondary" size="lg">See how it works</Button>
          </div>
        </motion.div>
      </section>

      <section id="how" className="border-t border-ink/10 bg-ivory-deep/50">
        <div className="mx-auto max-w-6xl px-5 py-16">
          <h2 className="text-3xl font-semibold">From textbook to printed paper</h2>
          <div className="mt-10 grid gap-5 sm:grid-cols-2 lg:grid-cols-3">
            {STEPS.map(({ icon: Icon, title, body }, i) => (
              <motion.div key={title} className="card p-6"
                initial={{ opacity: 0, y: 12 }} whileInView={{ opacity: 1, y: 0 }} viewport={{ once: true }} transition={{ delay: i * 0.05 }}>
                <Icon className="h-6 w-6 text-rust" aria-hidden />
                <h3 className="mt-4 text-lg font-semibold">{title}</h3>
                <p className="mt-1.5 text-sm text-ink-500">{body}</p>
              </motion.div>
            ))}
          </div>
        </div>
      </section>

      <footer className="mx-auto flex max-w-6xl flex-col gap-2 px-5 py-8 text-sm text-ink-500 sm:flex-row sm:justify-between">
        <Wordmark className="text-lg" />
        <p>Questions grounded in your book, with the page they came from.</p>
      </footer>
    </div>
  );
}

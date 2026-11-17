"use client";

import { FileUp, X } from "lucide-react";
import { useRouter } from "next/navigation";
import { useRef, useState } from "react";

import { useProfile } from "@/components/AppShell";
import { Button, ErrorNote, PageHeader, cx, errorText, useToast } from "@/components/ui";
import { api } from "@/lib/api";

const MAX_MB = 50;

export default function UploadBook() {
  const { profile } = useProfile();
  const router = useRouter();
  const toast = useToast();
  const input = useRef<HTMLInputElement>(null);
  const [file, setFile] = useState<File | null>(null);
  const [drag, setDrag] = useState(false);
  const [title, setTitle] = useState("");
  const [subject, setSubject] = useState(profile?.subjects?.[0] || "");
  const [classLevel, setClassLevel] = useState(profile?.classes?.[0] || "");
  const [board, setBoard] = useState(profile?.board || "");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  function pick(f: File | undefined) {
    setError(null);
    if (!f) return;
    if (f.type !== "application/pdf" && !f.name.toLowerCase().endsWith(".pdf")) {
      setError("Please choose a PDF file.");
      return;
    }
    if (f.size > MAX_MB * 1024 * 1024) {
      setError(`That file is larger than ${MAX_MB} MB.`);
      return;
    }
    setFile(f);
    if (!title) setTitle(f.name.replace(/\.pdf$/i, "").replace(/[_-]+/g, " "));
  }

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    if (!file) return;
    setBusy(true);
    setError(null);
    const form = new FormData();
    form.append("file", file);
    form.append("title", title.trim());
    if (subject) form.append("subject", subject);
    if (classLevel) form.append("class_level", classLevel);
    if (board) form.append("board", board);
    try {
      const book = await api.uploadTextbook(form);
      toast("success", "Uploaded! SLAYBUS is reading your book.");
      router.push(`/books/${book.id}`);
    } catch (err) {
      setError(errorText(err));
      setBusy(false);
    }
  }

  return (
    <div className="mx-auto max-w-2xl">
      <PageHeader title="Upload a textbook" subtitle="A text-based PDF works best (not a scanned photo copy)." />
      <form onSubmit={submit} className="card flex flex-col gap-5 p-6 sm:p-8">
        <div
          onDragOver={(e) => { e.preventDefault(); setDrag(true); }}
          onDragLeave={() => setDrag(false)}
          onDrop={(e) => { e.preventDefault(); setDrag(false); pick(e.dataTransfer.files?.[0]); }}
          onClick={() => input.current?.click()}
          onKeyDown={(e) => (e.key === "Enter" || e.key === " ") && input.current?.click()}
          role="button" tabIndex={0} aria-label="Choose a PDF file"
          className={cx("flex cursor-pointer flex-col items-center justify-center rounded-2xl border-2 border-dashed px-6 py-10 text-center transition",
            drag ? "border-rust bg-rust-light/50" : "border-ink/15 hover:border-rust/50 hover:bg-white")}
        >
          <FileUp className="h-8 w-8 text-rust" aria-hidden />
          {file ? (
            <div className="mt-3 flex items-center gap-2">
              <span className="font-medium">{file.name}</span>
              <span className="text-sm text-ink-500">({(file.size / 1024 / 1024).toFixed(1)} MB)</span>
              <button type="button" aria-label="Remove file" className="rounded p-1 hover:bg-ink/5"
                onClick={(e) => { e.stopPropagation(); setFile(null); }}>
                <X className="h-4 w-4" />
              </button>
            </div>
          ) : (
            <>
              <p className="mt-3 font-medium">Drag & drop your PDF here</p>
              <p className="text-sm text-ink-500">or click to browse · up to {MAX_MB} MB</p>
            </>
          )}
          <input ref={input} type="file" accept="application/pdf,.pdf" className="hidden" data-testid="file-input"
            onChange={(e) => pick(e.target.files?.[0])} />
        </div>

        <div>
          <label className="label" htmlFor="title">Book title</label>
          <input id="title" className="input" value={title} onChange={(e) => setTitle(e.target.value)} required placeholder="Science – Class 7 (NCERT)" />
        </div>
        <div className="grid gap-4 sm:grid-cols-3">
          <div>
            <label className="label" htmlFor="subject">Subject</label>
            <input id="subject" className="input" value={subject} onChange={(e) => setSubject(e.target.value)} placeholder="Science" />
          </div>
          <div>
            <label className="label" htmlFor="class">Class</label>
            <input id="class" className="input" value={classLevel} onChange={(e) => setClassLevel(e.target.value)} placeholder="7" />
          </div>
          <div>
            <label className="label" htmlFor="board">Board</label>
            <input id="board" className="input" value={board} onChange={(e) => setBoard(e.target.value)} placeholder="CBSE" />
          </div>
        </div>
        {error && <ErrorNote message={error} />}
        <div className="flex justify-end">
          <Button type="submit" loading={busy} disabled={!file || !title.trim()}>Upload & process</Button>
        </div>
      </form>
    </div>
  );
}

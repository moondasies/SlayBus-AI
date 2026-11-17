"use client";

import { Plus, RotateCcw, Trash2 } from "lucide-react";
import { useParams, useRouter } from "next/navigation";
import { useCallback, useState } from "react";

import { Button, ErrorNote, PageHeader, Spinner, StatusBadge, errorText, useToast } from "@/components/ui";
import { api } from "@/lib/api";
import { usePolling } from "@/lib/hooks";

const METHOD_LABELS: Record<string, string> = {
  bookmarks: "from the PDF's bookmarks",
  headings: "from chapter headings in the text",
  ai: "by AI from the contents page",
  whole_book: "none found, so the whole book is one chapter",
};

export default function BookDetail() {
  const { id } = useParams<{ id: string }>();
  const router = useRouter();
  const toast = useToast();
  const [busy, setBusy] = useState(false);
  const load = useCallback(() => api.textbook(id), [id]);
  const { data: book, error, reload } = usePolling(load, (b) => b.status === "processing" || b.status === "uploaded", 2000);

  async function retry() {
    setBusy(true);
    try {
      await api.reprocessTextbook(id);
      await reload();
    } catch (e) {
      toast("error", errorText(e));
    } finally {
      setBusy(false);
    }
  }

  async function remove() {
    if (!confirm("Delete this book? Papers and questions you made from it are kept.")) return;
    try {
      await api.deleteTextbook(id);
      toast("success", "Book deleted");
      router.replace("/books");
    } catch (e) {
      toast("error", errorText(e));
    }
  }

  if (error) return <ErrorNote message={error} />;
  if (!book) return <Spinner />;
  const busyStatus = book.status === "processing" || book.status === "uploaded";

  return (
    <div className="mx-auto max-w-4xl">
      <PageHeader
        title={book.title}
        subtitle={[book.subject, book.class_level && `Class ${book.class_level}`, book.board, book.page_count && `${book.page_count} pages`].filter(Boolean).join(" · ")}
        actions={
          <>
            <Button variant="danger" onClick={remove}><Trash2 className="h-4 w-4" aria-hidden /> Delete</Button>
            {book.status === "ready" && (
              <Button href={`/papers/new?book=${book.id}`}><Plus className="h-4 w-4" aria-hidden /> Create paper</Button>
            )}
          </>
        }
      />

      <div className="card mb-6 flex flex-col gap-3 p-5">
        <div className="flex items-center gap-3">
          <StatusBadge status={book.status} />
          <span className="text-sm text-ink-700">
            {busyStatus && "Reading pages, finding chapters and indexing the text…"}
            {book.status === "ready" && `Ready. ${book.chapter_count} chapters found ${METHOD_LABELS[book.chapter_method || ""] || ""}.`}
            {book.status === "failed" && "We couldn't process this book."}
          </span>
        </div>
        {busyStatus && (
          <div className="h-2 overflow-hidden rounded-full bg-ink/10" role="progressbar" aria-valuenow={book.progress} aria-valuemin={0} aria-valuemax={100}>
            <div className="h-full rounded-full bg-amber transition-all duration-500" style={{ width: `${Math.max(5, book.progress)}%` }} />
          </div>
        )}
        {book.status === "failed" && (
          <>
            {book.error_message && <ErrorNote message={book.error_message} />}
            <div><Button variant="secondary" loading={busy} onClick={retry}><RotateCcw className="h-4 w-4" aria-hidden /> Try again</Button></div>
          </>
        )}
      </div>

      {book.chapters && book.chapters.length > 0 && (
        <section>
          <h2 className="mb-3 text-2xl font-semibold">Chapters</h2>
          <ol className="card divide-y divide-ink/10 overflow-hidden">
            {book.chapters.map((c) => (
              <li key={c.id} className="flex items-center gap-4 px-5 py-3.5">
                <span className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-amber-light font-serif text-sm font-semibold">{c.number}</span>
                <span className="flex-1 font-medium">{c.title}</span>
                <span className="text-sm text-ink-500">pp. {c.start_page}–{c.end_page}</span>
                <span className="hidden text-xs text-ink-300 sm:inline">{c.chunk_count} passages</span>
              </li>
            ))}
          </ol>
          <p className="mt-2 text-xs text-ink-300">Page numbers are PDF pages, which can differ from the numbers printed in the book.</p>
        </section>
      )}
    </div>
  );
}

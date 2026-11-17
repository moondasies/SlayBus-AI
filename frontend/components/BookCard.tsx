"use client";

import { BookOpen } from "lucide-react";
import Link from "next/link";

import { formatDate } from "@/lib/hooks";
import type { Textbook } from "@/lib/types";

import { StatusBadge } from "./ui";

export function BookCard({ book }: { book: Textbook }) {
  const busy = book.status === "processing" || book.status === "uploaded";
  return (
    <Link href={`/books/${book.id}`} className="card group flex flex-col gap-3 p-5 transition hover:-translate-y-0.5 hover:border-rust/30">
      <div className="flex items-start justify-between gap-3">
        <div className="rounded-xl bg-rust-light p-2.5 text-rust"><BookOpen className="h-5 w-5" aria-hidden /></div>
        <StatusBadge status={book.status} />
      </div>
      <div>
        <h3 className="line-clamp-2 text-lg font-semibold group-hover:text-rust">{book.title}</h3>
        <p className="mt-0.5 text-sm text-ink-500">
          {[book.subject, book.class_level && `Class ${book.class_level}`, book.board].filter(Boolean).join(" · ") || "Textbook"}
        </p>
      </div>
      {busy && (
        <div className="h-1.5 overflow-hidden rounded-full bg-ink/10" aria-label={`Processing ${book.progress}%`}>
          <div className="h-full rounded-full bg-amber transition-all" style={{ width: `${Math.max(5, book.progress)}%` }} />
        </div>
      )}
      <p className="mt-auto text-xs text-ink-300">
        {book.status === "ready" ? `${book.chapter_count} chapters · ${book.page_count} pages` : book.status === "failed" ? "Processing failed" : "Reading your book…"}
        {" · "}{formatDate(book.created_at)}
      </p>
    </Link>
  );
}

"use client";

import { FileText } from "lucide-react";
import Link from "next/link";

import { formatDate } from "@/lib/hooks";
import { PAPER_TYPE_LABELS, type PaperSummary } from "@/lib/types";

import { StatusBadge } from "./ui";

export function PaperRow({ paper }: { paper: PaperSummary }) {
  return (
    <Link href={`/papers/${paper.id}`} className="flex items-center gap-4 px-5 py-4 transition hover:bg-ink/[0.03]">
      <FileText className="h-5 w-5 shrink-0 text-rust" aria-hidden />
      <div className="min-w-0 flex-1">
        <p className="truncate font-medium">{paper.title}</p>
        <p className="truncate text-sm text-ink-500">
          {PAPER_TYPE_LABELS[paper.paper_type]} · {paper.question_count} questions · {paper.total_marks ?? 0} marks
          {paper.textbook_title && ` · ${paper.textbook_title}`}
        </p>
      </div>
      <span className="hidden text-xs text-ink-300 sm:block">{formatDate(paper.created_at)}</span>
      <StatusBadge status={paper.status} />
    </Link>
  );
}

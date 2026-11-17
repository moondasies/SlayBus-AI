"use client";

import { Plus, Upload } from "lucide-react";
import Link from "next/link";
import { useCallback } from "react";

import { useProfile } from "@/components/AppShell";
import { BookCard } from "@/components/BookCard";
import { PaperRow } from "@/components/PaperRow";
import { Button, Empty, ErrorNote, PageHeader, Spinner } from "@/components/ui";
import { api } from "@/lib/api";
import { usePolling } from "@/lib/hooks";
import type { PaperSummary, Textbook } from "@/lib/types";

export default function Dashboard() {
  const { profile } = useProfile();
  const load = useCallback(async () => {
    const [books, papers] = await Promise.all([api.textbooks(), api.papers()]);
    return { books, papers };
  }, []);
  const { data, error } = usePolling<{ books: Textbook[]; papers: PaperSummary[] }>(
    load,
    (d) => d.books.some((b) => b.status === "processing" || b.status === "uploaded") || d.papers.some((p) => p.status === "generating"),
    2500,
  );

  const firstName = profile?.name?.split(" ")[0];
  const hasReady = data?.books.some((b) => b.status === "ready");

  return (
    <div className="mx-auto max-w-6xl">
      <PageHeader
        title={firstName ? `Namaste, ${firstName}` : "Dashboard"}
        subtitle="Your textbooks and papers in one place."
        actions={
          <>
            <Button href="/books/new" variant="secondary"><Upload className="h-4 w-4" aria-hidden /> Upload book</Button>
            <Button href="/papers/new" disabled={!hasReady}><Plus className="h-4 w-4" aria-hidden /> Create paper</Button>
          </>
        }
      />
      {error && <ErrorNote message={error} />}
      {!data && !error && <Spinner />}

      {data && (
        <div className="flex flex-col gap-10">
          <section>
            <div className="mb-4 flex items-center justify-between">
              <h2 className="text-2xl font-semibold">My books</h2>
              {data.books.length > 0 && <Link href="/books" className="text-sm text-rust hover:underline">View all</Link>}
            </div>
            {data.books.length === 0 ? (
              <Empty title="Upload your first textbook" body="SLAYBUS reads your book, finds its chapters and uses it to write every question."
                action={<Button href="/books/new"><Upload className="h-4 w-4" aria-hidden /> Upload a PDF</Button>} />
            ) : (
              <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
                {data.books.slice(0, 6).map((b) => <BookCard key={b.id} book={b} />)}
              </div>
            )}
          </section>

          <section>
            <h2 className="mb-4 text-2xl font-semibold">Recent papers</h2>
            {data.papers.length === 0 ? (
              <Empty title="No papers yet" body={hasReady ? "Your book is ready. Create a paper in a few clicks." : "Once a book is ready you can generate papers from it."}
                action={hasReady ? <Button href="/papers/new"><Plus className="h-4 w-4" aria-hidden /> Create paper</Button> : undefined} />
            ) : (
              <div className="card divide-y divide-ink/10 overflow-hidden">
                {data.papers.slice(0, 10).map((p) => <PaperRow key={p.id} paper={p} />)}
              </div>
            )}
          </section>
        </div>
      )}
    </div>
  );
}

"use client";

import { Upload } from "lucide-react";

import { BookCard } from "@/components/BookCard";
import { Button, Empty, ErrorNote, PageHeader, Spinner } from "@/components/ui";
import { api } from "@/lib/api";
import { usePolling } from "@/lib/hooks";

export default function Books() {
  const { data, error } = usePolling(api.textbooks, (books) => books.some((b) => b.status === "processing" || b.status === "uploaded"), 2500);
  return (
    <div className="mx-auto max-w-6xl">
      <PageHeader title="My books" subtitle="Every paper is generated from one of these textbooks."
        actions={<Button href="/books/new"><Upload className="h-4 w-4" aria-hidden /> Upload book</Button>} />
      {error && <ErrorNote message={error} />}
      {!data && !error && <Spinner />}
      {data && data.length === 0 && (
        <Empty title="No books yet" body="Upload a textbook PDF to get started." action={<Button href="/books/new">Upload a PDF</Button>} />
      )}
      {data && data.length > 0 && (
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {data.map((b) => <BookCard key={b.id} book={b} />)}
        </div>
      )}
    </div>
  );
}

"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";

import { useProfile } from "@/components/AppShell";
import { Button, ErrorNote, cx, errorText } from "@/components/ui";
import { api } from "@/lib/api";

const BOARDS = ["CBSE", "ICSE", "State board", "IB", "Cambridge", "Other"];
const CLASSES = ["6", "7", "8", "9", "10", "11", "12"];
const SUBJECTS = ["Science", "Mathematics", "Physics", "Chemistry", "Biology", "Social Science", "History", "Geography", "English", "Computer Science", "Economics"];

function Chips({ options, value, onChange, label }: { options: string[]; value: string[]; onChange: (v: string[]) => void; label: string }) {
  return (
    <div role="group" aria-label={label} className="flex flex-wrap gap-2">
      {options.map((o) => {
        const on = value.includes(o);
        return (
          <button type="button" key={o} aria-pressed={on} onClick={() => onChange(on ? value.filter((v) => v !== o) : [...value, o])}
            className={cx("rounded-full border px-3.5 py-1.5 text-sm transition",
              on ? "border-rust bg-rust text-ivory" : "border-ink/15 bg-white text-ink-700 hover:border-ink/30")}>
            {o}
          </button>
        );
      })}
    </div>
  );
}

export default function Onboarding() {
  const { profile, refresh } = useProfile();
  const router = useRouter();
  const [name, setName] = useState(profile?.name || "");
  const [school, setSchool] = useState(profile?.school || "");
  const [board, setBoard] = useState(profile?.board || "CBSE");
  const [classes, setClasses] = useState<string[]>(profile?.classes || []);
  const [subjects, setSubjects] = useState<string[]>(profile?.subjects || []);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function save(e: React.FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError(null);
    try {
      await api.updateMe({ name: name.trim(), school: school.trim() || null, board, classes, subjects } as never);
      await refresh();
      router.replace("/dashboard");
    } catch (err) {
      setError(errorText(err));
      setBusy(false);
    }
  }

  return (
    <div className="mx-auto max-w-2xl">
      <h1 className="text-4xl font-semibold">Welcome to SLAYBUS</h1>
      <p className="mt-2 text-ink-500">Tell us a little about your teaching so papers match your class and board.</p>
      <form onSubmit={save} className="card mt-8 flex flex-col gap-6 p-6 sm:p-8">
        <div className="grid gap-4 sm:grid-cols-2">
          <div>
            <label className="label" htmlFor="name">Your name</label>
            <input id="name" className="input" value={name} onChange={(e) => setName(e.target.value)} required placeholder="Asha Sharma" />
          </div>
          <div>
            <label className="label" htmlFor="school">School <span className="text-ink-300">(optional)</span></label>
            <input id="school" className="input" value={school} onChange={(e) => setSchool(e.target.value)} placeholder="Delhi Public School" />
          </div>
        </div>
        <div>
          <label className="label" htmlFor="board">Board</label>
          <select id="board" className="input" value={board} onChange={(e) => setBoard(e.target.value)}>
            {BOARDS.map((b) => <option key={b}>{b}</option>)}
          </select>
        </div>
        <div>
          <span className="label">Classes you teach</span>
          <Chips label="Classes" options={CLASSES} value={classes} onChange={setClasses} />
        </div>
        <div>
          <span className="label">Subjects</span>
          <Chips label="Subjects" options={SUBJECTS} value={subjects} onChange={setSubjects} />
        </div>
        {error && <ErrorNote message={error} />}
        <div className="flex justify-end">
          <Button type="submit" loading={busy} disabled={!name.trim()}>Continue to dashboard</Button>
        </div>
      </form>
    </div>
  );
}

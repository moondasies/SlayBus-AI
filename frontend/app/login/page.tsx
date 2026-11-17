"use client";

import { useRouter, useSearchParams } from "next/navigation";
import { Suspense, useEffect, useState } from "react";

import { Button, ErrorNote, Spinner, Wordmark, cx, errorText } from "@/components/ui";
import { useAuth } from "@/lib/auth";

function GoogleIcon() {
  return (
    <svg viewBox="0 0 24 24" className="h-4 w-4" aria-hidden>
      <path fill="#EA4335" d="M12 10.2v3.9h5.5c-.2 1.3-1.6 3.9-5.5 3.9-3.3 0-6-2.7-6-6.1s2.7-6.1 6-6.1c1.9 0 3.1.8 3.8 1.5l2.6-2.5C16.8 3.3 14.6 2.3 12 2.3 6.7 2.3 2.4 6.6 2.4 12s4.3 9.7 9.6 9.7c5.5 0 9.2-3.9 9.2-9.4 0-.6-.1-1.1-.2-1.6H12z" />
    </svg>
  );
}

function LoginForm() {
  const { session, loading, supabaseEnabled, devEnabled, signInWithPassword, signUp, signInWithGoogle, devSignIn } = useAuth();
  const router = useRouter();
  const params = useSearchParams();
  const next = params.get("next") || "/dashboard";
  const [mode, setMode] = useState<"login" | "signup">(params.get("mode") === "signup" ? "signup" : "login");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [name, setName] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [info, setInfo] = useState<string | null>(null);

  useEffect(() => {
    if (!loading && session) router.replace(next.startsWith("/") ? next : "/dashboard");
  }, [loading, session, router, next]);

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError(null);
    setInfo(null);
    try {
      if (!supabaseEnabled && devEnabled) {
        await devSignIn(email);
      } else if (mode === "login") {
        await signInWithPassword(email, password);
      } else {
        const res = await signUp(email, password, name);
        if (res === "check_email") setInfo("Check your inbox and click the confirmation link, then log in.");
      }
    } catch (err) {
      setError(errorText(err));
    } finally {
      setBusy(false);
    }
  }

  if (loading) return <Spinner />;
  const devOnly = !supabaseEnabled && devEnabled;

  return (
    <div className="card w-full max-w-md p-8">
      <Wordmark className="text-3xl" />
      <h1 className="mt-6 text-2xl font-semibold">{mode === "login" ? "Welcome back" : "Create your account"}</h1>
      <p className="mt-1 text-sm text-ink-500">Classroom-ready papers. Powered by your syllabus.</p>

      {!supabaseEnabled && !devEnabled && (
        <div className="mt-6">
          <ErrorNote message="Login isn't configured. Set NEXT_PUBLIC_SUPABASE_URL and NEXT_PUBLIC_SUPABASE_ANON_KEY in frontend/.env.local." />
        </div>
      )}

      {devOnly && (
        <p className="mt-6 rounded-xl bg-amber-light px-3.5 py-2.5 text-xs text-ink-700">
          <strong>Local dev mode:</strong> enter any email to log in as that teacher. Configure Supabase for real accounts.
        </p>
      )}

      {supabaseEnabled && (
        <>
          <Button variant="secondary" className="mt-6 w-full" onClick={() => signInWithGoogle().catch((e) => setError(errorText(e)))}>
            <GoogleIcon /> Continue with Google
          </Button>
          <div className="my-5 flex items-center gap-3 text-xs text-ink-300">
            <span className="h-px flex-1 bg-ink/10" /> or with email <span className="h-px flex-1 bg-ink/10" />
          </div>
        </>
      )}

      {(supabaseEnabled || devEnabled) && (
        <form onSubmit={submit} className={cx("flex flex-col gap-4", !supabaseEnabled && "mt-5")}>
          {mode === "signup" && supabaseEnabled && (
            <div>
              <label className="label" htmlFor="name">Your name</label>
              <input id="name" className="input" value={name} onChange={(e) => setName(e.target.value)} required autoComplete="name" />
            </div>
          )}
          <div>
            <label className="label" htmlFor="email">Email</label>
            <input id="email" type="email" className="input" value={email} onChange={(e) => setEmail(e.target.value)} required autoComplete="email" placeholder="you@school.in" />
          </div>
          {!devOnly && (
            <div>
              <label className="label" htmlFor="password">Password</label>
              <input id="password" type="password" className="input" value={password} onChange={(e) => setPassword(e.target.value)} required minLength={6}
                autoComplete={mode === "login" ? "current-password" : "new-password"} />
            </div>
          )}
          {error && <ErrorNote message={error} />}
          {info && <p className="rounded-xl bg-emerald-50 px-3.5 py-2.5 text-sm text-emerald-800">{info}</p>}
          <Button type="submit" loading={busy} className="w-full">
            {devOnly ? "Continue" : mode === "login" ? "Log in" : "Sign up"}
          </Button>
        </form>
      )}

      {supabaseEnabled && (
        <p className="mt-5 text-center text-sm text-ink-500">
          {mode === "login" ? "New to SLAYBUS? " : "Already have an account? "}
          <button className="font-medium text-rust hover:underline" onClick={() => { setMode(mode === "login" ? "signup" : "login"); setError(null); }}>
            {mode === "login" ? "Create an account" : "Log in"}
          </button>
        </p>
      )}
    </div>
  );
}

export default function LoginPage() {
  return (
    <div className="flex min-h-screen items-center justify-center px-4 py-10">
      <Suspense fallback={<Spinner />}>
        <LoginForm />
      </Suspense>
    </div>
  );
}

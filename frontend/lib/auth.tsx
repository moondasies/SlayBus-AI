"use client";

import { createClient, type SupabaseClient } from "@supabase/supabase-js";
import { createContext, useCallback, useContext, useEffect, useMemo, useState } from "react";

import { api, configureApi } from "./api";

const SUPABASE_URL = process.env.NEXT_PUBLIC_SUPABASE_URL || "";
const SUPABASE_ANON_KEY = process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY || "";
export const DEV_AUTH = process.env.NEXT_PUBLIC_DEV_AUTH === "true";
const DEV_KEY = "slaybus.devSession";

export const supabase: SupabaseClient | null =
  SUPABASE_URL && SUPABASE_ANON_KEY ? createClient(SUPABASE_URL, SUPABASE_ANON_KEY) : null;

interface Session {
  token: string;
  email: string | null;
}

interface AuthState {
  session: Session | null;
  loading: boolean;
  supabaseEnabled: boolean;
  devEnabled: boolean;
  signInWithPassword: (email: string, password: string) => Promise<void>;
  signUp: (email: string, password: string, name: string) => Promise<"signed_in" | "check_email">;
  signInWithGoogle: () => Promise<void>;
  devSignIn: (email: string) => Promise<void>;
  signOut: () => Promise<void>;
}

const AuthContext = createContext<AuthState | null>(null);

function readDevSession(): Session | null {
  if (!DEV_AUTH || typeof window === "undefined") return null;
  try {
    return JSON.parse(localStorage.getItem(DEV_KEY) || "null");
  } catch {
    return null;
  }
}

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [session, setSession] = useState<Session | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const dev = readDevSession();
    if (dev) {
      setSession(dev);
      setLoading(false);
      return;
    }
    if (!supabase) {
      setLoading(false);
      return;
    }
    supabase.auth.getSession().then(({ data }) => {
      const s = data.session;
      setSession(s ? { token: s.access_token, email: s.user.email ?? null } : null);
      setLoading(false);
    });
    const { data: sub } = supabase.auth.onAuthStateChange((_event, s) => {
      setSession(s ? { token: s.access_token, email: s.user.email ?? null } : null);
    });
    return () => sub.subscription.unsubscribe();
  }, []);

  const signOut = useCallback(async () => {
    if (DEV_AUTH) localStorage.removeItem(DEV_KEY);
    if (supabase) await supabase.auth.signOut();
    setSession(null);
  }, []);

  useEffect(() => {
    configureApi(
      async () => {
        const dev = readDevSession();
        if (dev) return dev.token;
        if (supabase) {
          // getSession refreshes an expired access token automatically
          const { data } = await supabase.auth.getSession();
          return data.session?.access_token ?? null;
        }
        return null;
      },
      () => setSession(null),
    );
  }, []);

  const value = useMemo<AuthState>(
    () => ({
      session,
      loading,
      supabaseEnabled: !!supabase,
      devEnabled: DEV_AUTH,
      async signInWithPassword(email, password) {
        if (!supabase) throw new Error("Supabase is not configured");
        const { error } = await supabase.auth.signInWithPassword({ email, password });
        if (error) throw new Error(error.message);
      },
      async signUp(email, password, name) {
        if (!supabase) throw new Error("Supabase is not configured");
        const { data, error } = await supabase.auth.signUp({
          email,
          password,
          options: { data: { full_name: name }, emailRedirectTo: `${window.location.origin}/dashboard` },
        });
        if (error) throw new Error(error.message);
        return data.session ? "signed_in" : "check_email";
      },
      async signInWithGoogle() {
        if (!supabase) throw new Error("Supabase is not configured");
        const { error } = await supabase.auth.signInWithOAuth({
          provider: "google",
          options: { redirectTo: `${window.location.origin}/dashboard` },
        });
        if (error) throw new Error(error.message);
      },
      async devSignIn(email) {
        const res = await api.devToken(email);
        const s = { token: res.access_token, email: res.email };
        localStorage.setItem(DEV_KEY, JSON.stringify(s));
        setSession(s);
      },
      signOut,
    }),
    [session, loading, signOut],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth(): AuthState {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be used inside AuthProvider");
  return ctx;
}

"use client";

import { BookOpen, FilePlus2, LayoutDashboard, Library, LogOut, Menu, X } from "lucide-react";
import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { createContext, useCallback, useContext, useEffect, useState } from "react";

import { api } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import type { Profile } from "@/lib/types";

import { Spinner, Wordmark, cx } from "./ui";

const NAV = [
  { href: "/dashboard", label: "Dashboard", icon: LayoutDashboard },
  { href: "/books", label: "My books", icon: BookOpen },
  { href: "/papers/new", label: "Create paper", icon: FilePlus2 },
  { href: "/bank", label: "Question bank", icon: Library },
];

const ProfileContext = createContext<{ profile: Profile | null; refresh: () => Promise<void> }>({
  profile: null,
  refresh: async () => {},
});
export const useProfile = () => useContext(ProfileContext);

/** Wraps every logged-in page: checks the session, loads the profile, shows the sidebar. */
export function AppShell({ children }: { children: React.ReactNode }) {
  const { session, loading, signOut } = useAuth();
  const router = useRouter();
  const pathname = usePathname();
  const [profile, setProfile] = useState<Profile | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [menuOpen, setMenuOpen] = useState(false);

  const refresh = useCallback(async () => {
    try {
      setProfile(await api.me());
      setError(null);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Could not load your profile");
    }
  }, []);

  useEffect(() => {
    if (loading) return;
    if (!session) {
      router.replace(`/login?next=${encodeURIComponent(pathname)}`);
      return;
    }
    refresh();
  }, [loading, session, router, pathname, refresh]);

  useEffect(() => {
    if (profile && !profile.onboarded && pathname !== "/onboarding") router.replace("/onboarding");
  }, [profile, pathname, router]);

  useEffect(() => setMenuOpen(false), [pathname]);

  if (loading || !session || (!profile && !error)) {
    return (
      <div className="flex min-h-screen items-center justify-center">
        <Spinner />
      </div>
    );
  }
  if (error && !profile) {
    return (
      <div className="flex min-h-screen flex-col items-center justify-center gap-3 p-6 text-center">
        <Wordmark />
        <p className="max-w-md text-ink-700">{error}</p>
        <button className="text-sm text-rust underline" onClick={refresh}>Try again</button>
      </div>
    );
  }

  const nav = (
    <nav className="flex flex-col gap-1" aria-label="Main">
      {NAV.map(({ href, label, icon: Icon }) => {
        const active = pathname === href || (href === "/books" && pathname.startsWith("/books/"));
        return (
          <Link key={href} href={href}
            className={cx("flex items-center gap-3 rounded-xl px-3 py-2.5 text-sm font-medium transition",
              active ? "bg-rust text-ivory" : "text-ink-700 hover:bg-ink/5")}>
            <Icon className="h-4 w-4" aria-hidden /> {label}
          </Link>
        );
      })}
    </nav>
  );

  const footer = (
    <div className="border-t border-ink/10 pt-4">
      <p className="truncate text-sm font-medium text-ink">{profile?.name || "Teacher"}</p>
      <p className="truncate text-xs text-ink-500">{profile?.email}</p>
      <button onClick={async () => { await signOut(); router.replace("/login"); }}
        className="mt-3 flex items-center gap-2 text-sm text-ink-500 hover:text-rust">
        <LogOut className="h-4 w-4" aria-hidden /> Log out
      </button>
    </div>
  );

  return (
    <ProfileContext.Provider value={{ profile, refresh }}>
      <div className="min-h-screen lg:flex">
        <aside className="no-print sticky top-0 hidden h-screen w-64 shrink-0 flex-col justify-between border-r border-ink/10 bg-ivory-deep/60 p-5 lg:flex">
          <div className="flex flex-col gap-8">
            <Link href="/dashboard"><Wordmark /></Link>
            {nav}
          </div>
          {footer}
        </aside>

        <header className="no-print sticky top-0 z-30 flex items-center justify-between border-b border-ink/10 bg-ivory/95 px-4 py-3 backdrop-blur lg:hidden">
          <Link href="/dashboard"><Wordmark className="text-xl" /></Link>
          <button onClick={() => setMenuOpen((o) => !o)} aria-label="Menu" className="rounded-lg p-2 hover:bg-ink/5">
            {menuOpen ? <X className="h-5 w-5" /> : <Menu className="h-5 w-5" />}
          </button>
        </header>
        {menuOpen && (
          <div className="no-print border-b border-ink/10 bg-ivory p-4 lg:hidden">
            {nav}
            <div className="mt-4">{footer}</div>
          </div>
        )}

        <main className="min-w-0 flex-1 px-4 py-8 sm:px-8 lg:px-12">{children}</main>
      </div>
    </ProfileContext.Provider>
  );
}

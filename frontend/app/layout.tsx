import type { Metadata } from "next";
import { Fraunces, Inter } from "next/font/google";

import { ToastProvider } from "@/components/ui";
import { AuthProvider } from "@/lib/auth";

import "./globals.css";

const fraunces = Fraunces({ subsets: ["latin"], variable: "--font-fraunces", display: "swap" });
const inter = Inter({ subsets: ["latin"], variable: "--font-inter", display: "swap" });

export const metadata: Metadata = {
  title: "SLAYBUS — Classroom-ready papers. Powered by your syllabus.",
  description: "Upload your textbook. Get question papers, worksheets and answer keys grounded in it.",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" className={`${fraunces.variable} ${inter.variable}`}>
      <body>
        <AuthProvider>
          <ToastProvider>{children}</ToastProvider>
        </AuthProvider>
      </body>
    </html>
  );
}

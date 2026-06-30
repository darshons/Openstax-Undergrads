import type { Metadata } from "next";
import { Geist, Geist_Mono } from "next/font/google";
import "./globals.css";

const geistSans = Geist({
  variable: "--font-geist-sans",
  subsets: ["latin"],
});

const geistMono = Geist_Mono({
  variable: "--font-geist-mono",
  subsets: ["latin"],
});

export const metadata: Metadata = {
  title: "OpenStax Scenario Generator",
  description: "Generate interactive branching clinical nursing scenarios.",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html
      lang="en"
      className={`${geistSans.variable} ${geistMono.variable} h-full antialiased`}
    >
      <body className="min-h-full flex flex-col">
        <nav className="bg-white border-b border-[#e8e6e3] sticky top-0 z-50">
          <div className="max-w-3xl mx-auto px-6 h-14 flex items-center justify-between">
            <div className="flex items-center gap-3">
              <svg width="28" height="28" viewBox="0 0 28 28" fill="none" xmlns="http://www.w3.org/2000/svg" aria-hidden="true">
                <rect width="28" height="28" rx="6" fill="#F47C20"/>
                <path d="M8 20V10.5L14 7L20 10.5V20" stroke="white" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"/>
                <path d="M11 20V15H17V20" stroke="white" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"/>
              </svg>
              <span className="font-bold text-[#1a1a1a] text-base tracking-tight select-none">
                OpenStax
              </span>
              <span className="hidden sm:block text-[#d0cdc8] text-lg font-light">|</span>
              <span className="hidden sm:block text-[#6b6560] text-sm font-medium">
                Scenario Generator
              </span>
            </div>
            <span className="text-xs text-[#9b9590] font-medium bg-[#f3f1ee] rounded-full px-3 py-1">
              Research Preview
            </span>
          </div>
        </nav>
        <div className="flex-1">{children}</div>
      </body>
    </html>
  );
}

import type { Metadata } from "next";
import Link from "next/link";
import "./globals.css";

export const metadata: Metadata = {
  title: "Astro ABM Scenario Platform",
  description: "Local-first AI scenario rehearsal interface for Astro ABM.",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en">
      <body>
        <header className="site-header">
          <Link className="brand" href="/">
            Astro ABM
          </Link>
          <nav aria-label="Main navigation">
            <Link href="/scenarios">Scenarios</Link>
            <Link href="/scenarios/new">Create</Link>
            <Link href="/agents">Agents</Link>
          </nav>
        </header>
        <main>{children}</main>
      </body>
    </html>
  );
}

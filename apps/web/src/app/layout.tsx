import type { Metadata } from "next";
import { SiteHeader } from "@/components/SiteHeader";
import { I18nProvider } from "@/i18n/I18nProvider";
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
    <html lang="en" data-theme="light" suppressHydrationWarning>
      <body>
        <I18nProvider>
          <SiteHeader />
          <main id="main-content" tabIndex={-1}>
            {children}
          </main>
        </I18nProvider>
      </body>
    </html>
  );
}

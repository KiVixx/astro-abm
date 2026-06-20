"use client";

import Link from "next/link";
import { LanguageToggle } from "@/i18n/LanguageToggle";
import { useI18n } from "@/i18n/useI18n";

export function SiteHeader() {
  const { t } = useI18n();

  return (
    <header className="site-header">
      <Link className="brand" href="/">
        {t("app.brand")}
      </Link>
      <div className="site-header-actions">
        <nav aria-label={t("nav.aria")}>
          <Link href="/worldlines">{t("nav.worldlines")}</Link>
          <Link href="/worldlines/new">{t("nav.createWorldline")}</Link>
          <Link href="/scenarios">{t("nav.scenarios")}</Link>
          <Link href="/agents">{t("nav.agents")}</Link>
        </nav>
        <LanguageToggle />
      </div>
    </header>
  );
}

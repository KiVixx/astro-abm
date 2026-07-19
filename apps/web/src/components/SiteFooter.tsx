"use client";

import Link from "next/link";
import { useI18n } from "@/i18n/useI18n";

const sourceUrl =
  process.env.NEXT_PUBLIC_ASTRO_ABM_SOURCE_URL ?? "https://github.com/KiVixx/astro-abm";

export function SiteFooter() {
  const { t } = useI18n();

  return (
    <footer className="site-footer">
      <p>{t("legal.footerNotice")}</p>
      <nav aria-label={t("legal.footerNavigation")}>
        <a href={sourceUrl} rel="noreferrer" target="_blank">
          {t("legal.sourceCode")}
        </a>
        <Link href="/legal">{t("legal.licenseAndData")}</Link>
      </nav>
    </footer>
  );
}

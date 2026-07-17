"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { LanguageToggle } from "@/i18n/LanguageToggle";
import { useI18n } from "@/i18n/useI18n";

export function SiteHeader() {
  const { t } = useI18n();
  const pathname = usePathname();
  const links = [
    {
      href: "/worldlines",
      label: t("nav.worldlines"),
      active: pathname.startsWith("/worldlines") && pathname !== "/worldlines/new",
    },
    {
      href: "/worldlines/new",
      label: t("nav.createWorldline"),
      active: pathname === "/worldlines/new",
    },
    {
      href: "/scenarios",
      label: t("nav.scenarios"),
      active: pathname.startsWith("/scenarios"),
    },
    {
      href: "/agents",
      label: t("nav.agents"),
      active: pathname.startsWith("/agents"),
    },
  ];

  return (
    <header className="site-header">
      <Link className="brand" href="/">
        {t("app.brand")}
      </Link>
      <div className="site-header-actions">
        <nav aria-label={t("nav.aria")}>
          {links.map((link) => (
            <Link
              aria-current={link.active ? "page" : undefined}
              className={link.active ? "is-active" : undefined}
              href={link.href}
              key={link.href}
            >
              {link.label}
            </Link>
          ))}
        </nav>
        <LanguageToggle />
      </div>
    </header>
  );
}

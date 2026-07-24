"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { LanguageToggle } from "@/i18n/LanguageToggle";
import { useI18n } from "@/i18n/useI18n";
import { useAuth } from "@/auth/AuthProvider";

export function SiteHeader() {
  const { t } = useI18n();
  const pathname = usePathname();
  const { loading, user } = useAuth();
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
      href: "/market-series",
      label: t("nav.marketSeries"),
      active: pathname.startsWith("/market-series"),
    },
    {
      href: "/agents",
      label: t("nav.agents"),
      active: pathname.startsWith("/agents"),
    },
  ];

  return (
    <>
      <a className="skip-link" href="#main-content">
        {t("nav.skipToContent")}
      </a>
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
          {!loading ? (
            <Link className="account-link" href={user ? "/account" : "/login"}>
              {user ? user.display_name || user.username : t("auth.login")}
            </Link>
          ) : null}
          <LanguageToggle />
        </div>
      </header>
    </>
  );
}

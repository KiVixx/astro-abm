"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState } from "react";
import { useAuth } from "@/auth/AuthProvider";
import { useI18n } from "@/i18n/useI18n";

export default function AccountPage() {
  const { loading, logout, user } = useAuth();
  const { t } = useI18n();
  const router = useRouter();
  const [error, setError] = useState("");

  if (loading) return <div className="page auth-page"><p>{t("auth.loading")}</p></div>;
  if (!user) {
    return <div className="page auth-page stack"><h1>{t("auth.account")}</h1><p>{t("auth.signedOut")}</p><Link className="button" href="/login">{t("auth.login")}</Link></div>;
  }

  async function signOut() {
    try {
      await logout();
      router.push("/");
      router.refresh();
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : t("common.unknownError"));
    }
  }

  return (
    <div className="page auth-page stack">
      <header><p className="pixel-kicker">ACCOUNT // ACTIVE</p><h1>{user.display_name || user.username}</h1></header>
      <dl className="auth-profile">
        <div><dt>{t("auth.username")}</dt><dd>{user.username}</dd></div>
        <div><dt>{t("auth.identity")}</dt><dd>{user.identity_providers.join(", ")}</dd></div>
        <div><dt>{t("auth.memberSince")}</dt><dd>{user.created_at.slice(0, 10)}</dd></div>
      </dl>
      <p className="notice">{t("auth.privateWorldlinesHelp")}</p>
      {error ? <p className="notice warning">{error}</p> : null}
      <div className="button-row">
        <Link className="button" href="/worldlines/new">{t("worldline.create")}</Link>
        <button className="button secondary" onClick={signOut} type="button">{t("auth.logout")}</button>
      </div>
    </div>
  );
}

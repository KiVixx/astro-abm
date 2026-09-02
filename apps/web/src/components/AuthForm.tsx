"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState, type FormEvent } from "react";
import { useAuth } from "@/auth/AuthProvider";
import { useI18n } from "@/i18n/useI18n";
import { ApiError } from "@/lib/api";

export function AuthForm({ mode }: { mode: "login" | "register" }) {
  const { login, register } = useAuth();
  const { t } = useI18n();
  const router = useRouter();
  const [error, setError] = useState("");
  const [submitting, setSubmitting] = useState(false);

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setSubmitting(true);
    setError("");
    const data = new FormData(event.currentTarget);
    try {
      const username = String(data.get("username") || "");
      const password = String(data.get("password") || "");
      if (mode === "register") {
        await register({
          username,
          password,
          display_name: String(data.get("display_name") || "") || null,
        });
      } else {
        await login({ username, password });
      }
      router.push("/account");
      router.refresh();
    } catch (caught) {
      if (caught instanceof ApiError && caught.status === 422) {
        setError(t(mode === "register" ? "auth.invalidRegistration" : "auth.invalidLogin"));
      } else {
        setError(caught instanceof Error ? caught.message : t("common.unknownError"));
      }
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <form className="auth-form stack" onSubmit={submit}>
      <label className="form-field">
        <span>{t("auth.username")}</span>
        <input autoComplete="username" maxLength={254} minLength={mode === "register" ? 3 : 1} name="username" required />
      </label>
      {mode === "register" ? <p className="muted">{t("auth.usernameHelp")}</p> : null}
      {mode === "register" ? (
        <label className="form-field">
          <span>{t("auth.displayName")}</span>
          <input autoComplete="name" maxLength={80} name="display_name" />
        </label>
      ) : null}
      <label className="form-field">
        <span>{t("auth.password")}</span>
        <input
          autoComplete={mode === "register" ? "new-password" : "current-password"}
          minLength={mode === "register" ? 12 : 1}
          name="password"
          required
          type="password"
        />
      </label>
      {mode === "register" ? <p className="muted">{t("auth.passwordHelp")}</p> : null}
      {error ? <p className="notice warning" role="alert">{error}</p> : null}
      <button className="button" disabled={submitting} type="submit">
        {submitting ? t("auth.working") : t(mode === "register" ? "auth.register" : "auth.login")}
      </button>
      <p className="muted">
        {t(mode === "register" ? "auth.haveAccount" : "auth.needAccount")}{" "}
        <Link href={mode === "register" ? "/login" : "/register"}>
          {t(mode === "register" ? "auth.login" : "auth.register")}
        </Link>
      </p>
    </form>
  );
}

import { AuthForm } from "@/components/AuthForm";
import { I18nText } from "@/i18n/useI18n";

export default function LoginPage() {
  return (
    <div className="page auth-page stack">
      <header><p className="pixel-kicker">ACCOUNT // SESSION</p><h1><I18nText tKey="auth.login" /></h1></header>
      <AuthForm mode="login" />
    </div>
  );
}

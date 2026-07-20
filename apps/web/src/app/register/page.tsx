import { AuthForm } from "@/components/AuthForm";
import { I18nText } from "@/i18n/useI18n";

export default function RegisterPage() {
  return (
    <div className="page auth-page stack">
      <header><p className="pixel-kicker">ACCOUNT // LOCAL</p><h1><I18nText tKey="auth.register" /></h1><p className="lead"><I18nText tKey="auth.registerLead" /></p></header>
      <AuthForm mode="register" />
    </div>
  );
}

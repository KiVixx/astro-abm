import Link from "next/link";
import { MarkSixPublicLibrary } from "@/components/MarkSixPublicLibrary";
import { I18nText } from "@/i18n/useI18n";

export default function MarkSixPublicWorldlinesPage() {
  return <div className="page stack marksix-page">
    <header className="marksix-hero">
      <p className="pixel-kicker">PUBLIC ARCHIVE // LLM ENTERTAINMENT WORLDLINES</p>
      <h1><I18nText tKey="marksix.publicLibraryTitle" /></h1>
      <p className="lead"><I18nText tKey="marksix.publicLibraryLead" /></p>
      <Link className="button secondary" href="/marksix"><I18nText tKey="marksix.publicLibraryBack" /></Link>
    </header>
    <section className="marksix-responsible">
      <strong><I18nText tKey="marksix.publicLibraryPrivacyTitle" /></strong>
      <p><I18nText tKey="marksix.publicLibraryPrivacy" /></p>
    </section>
    <MarkSixPublicLibrary />
  </div>;
}

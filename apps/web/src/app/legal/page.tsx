import { I18nText } from "@/i18n/useI18n";

export default function LegalPage() {
  return (
    <div className="page stack legal-page">
      <header>
        <p className="pixel-kicker">
          <I18nText tKey="legal.kicker" />
        </p>
        <h1>
          <I18nText tKey="legal.title" />
        </h1>
        <p className="lead">
          <I18nText tKey="legal.lead" />
        </p>
      </header>

      <section className="legal-section">
        <h2>
          <I18nText tKey="legal.softwareTitle" />
        </h2>
        <p>
          <I18nText tKey="legal.softwareText" />
        </p>
        <a href="https://github.com/KiVixx/astro-abm/blob/main/LICENSE">
          <I18nText tKey="legal.readLicense" />
        </a>
      </section>

      <section className="legal-section">
        <h2>
          <I18nText tKey="legal.swissTitle" />
        </h2>
        <p>
          <I18nText tKey="legal.swissText" />
        </p>
        <a href="https://www.astro.com/swisseph-download/doc/swisseph.htm">
          <I18nText tKey="legal.swissReference" />
        </a>
      </section>

      <section className="legal-section">
        <h2>
          <I18nText tKey="legal.dataTitle" />
        </h2>
        <p>
          <I18nText tKey="legal.dataText" />
        </p>
        <a href="https://github.com/KiVixx/astro-abm/blob/main/DATA_LICENSE.md">
          <I18nText tKey="legal.readDataPolicy" />
        </a>
      </section>

      <section className="legal-section">
        <h2>FRED</h2>
        <p>
          This product uses the FRED® API but is not endorsed or certified by the Federal
          Reserve Bank of St. Louis.
        </p>
        <a href="https://fred.stlouisfed.org/docs/api/terms_of_use.html">
          <I18nText tKey="legal.fredTerms" />
        </a>
      </section>

      <p className="muted">
        <I18nText tKey="legal.notLegalAdvice" />
      </p>
    </div>
  );
}

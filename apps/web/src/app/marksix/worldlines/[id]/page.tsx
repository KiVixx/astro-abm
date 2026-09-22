import Link from "next/link";
import { notFound } from "next/navigation";
import { I18nText } from "@/i18n/useI18n";
import { ApiError, getPublicMarkSixLlmWorldline } from "@/lib/api";

export const dynamic = "force-dynamic";

function Ball({ number, extra = false }: { number: number; extra?: boolean }) {
  return <span className={extra ? "marksix-ball is-extra" : "marksix-ball"}>{number}</span>;
}

export default async function MarkSixPublicWorldlinePage({ params }: {
  params: Promise<{ id: string }>;
}) {
  const { id } = await params;
  try {
    const item = await getPublicMarkSixLlmWorldline(id);
    return <div className="page stack marksix-page marksix-public-detail">
      <nav className="button-row">
        <Link className="button secondary" href="/marksix/worldlines"><I18nText tKey="marksix.publicLibraryBackToList" /></Link>
        <Link className="button secondary" href="/marksix"><I18nText tKey="marksix.publicLibraryBack" /></Link>
      </nav>
      <header className="marksix-hero">
        <p className="pixel-kicker">PUBLIC LLM WORLDLINE // {item.model}</p>
        <h1><I18nText tKey="marksix.publicLibraryTargetDraw" /> {item.draw_date}</h1>
        <p className="lead"><I18nText tKey="marksix.publicLibraryDetailLead" /></p>
      </header>
      <section className="marksix-llm-result">
        <div className="marksix-public-balls">
          {item.numbers.map((number) => <Ball key={number} number={number} />)}
          <span className="marksix-plus">+</span><Ball extra number={item.extra_number} />
        </div>
        <dl className="marksix-public-meta">
          <div><dt><I18nText tKey="marksix.publicLibraryCreated" /></dt><dd>{item.created_at}</dd></div>
          <div><dt><I18nText tKey="marksix.llmModel" /></dt><dd>{item.model}</dd></div>
          <div><dt><I18nText tKey="marksix.publicLibraryLanguage" /></dt><dd>{item.language}</dd></div>
          <div><dt><I18nText tKey="marksix.publicLibraryContext" /></dt><dd>{item.astro_context_type}</dd></div>
          <div><dt><I18nText tKey="marksix.publicLibraryCondition" /></dt><dd>{item.historical_condition}</dd></div>
          <div><dt><I18nText tKey="marksix.llmConfidence" /></dt><dd>{item.confidence}</dd></div>
        </dl>
        <h2><I18nText tKey="marksix.llmRationale" /></h2>
        <p>{item.rationale}</p>
        {item.caveats.length ? <><h2><I18nText tKey="marksix.publicLibraryCaveats" /></h2><ul>{item.caveats.map((caveat) => <li key={caveat}>{caveat}</li>)}</ul></> : null}
        <p className="marksix-method-note">{item.disclaimer}</p>
      </section>
      <section className="marksix-responsible">
        <strong><I18nText tKey="marksix.publicLibraryBoundaryTitle" /></strong>
        <p><I18nText tKey="marksix.publicLibraryBoundary" /></p>
      </section>
    </div>;
  } catch (error) {
    if (error instanceof ApiError && error.status === 404) notFound();
    return <div className="page stack"><h1><I18nText tKey="marksix.publicLibraryTitle" /></h1><p className="notice">{error instanceof Error ? error.message : "Unknown error"}</p></div>;
  }
}

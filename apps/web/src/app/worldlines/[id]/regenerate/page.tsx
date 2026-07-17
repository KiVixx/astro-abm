import Link from "next/link";
import { notFound } from "next/navigation";
import { WorldlineRegenerationForm } from "@/components/WorldlineRegenerationForm";
import { I18nText } from "@/i18n/useI18n";
import { ApiError, getLlmPresets, getScenario } from "@/lib/api";

export const dynamic = "force-dynamic";

export default async function RegenerateWorldlinePage({ params, searchParams }: {
  params: Promise<{ id: string }>;
  searchParams: Promise<{ start_chunk_index?: string; date?: string }>;
}) {
  const { id } = await params;
  const query = await searchParams;
  const startChunkIndex = Math.max(0, Number.parseInt(query.start_chunk_index || "0", 10) || 0);
  try {
    const [report, presets] = await Promise.all([
      getScenario(id, { includeMarkdown: false }),
      getLlmPresets(),
    ]);
    return (
      <div className="page stack">
        <header>
          <p className="muted"><I18nText tKey="worldline.workbench" /></p>
          <h1><I18nText tKey="worldline.regenerateSettingsTitle" /></h1>
          <p className="lead"><I18nText tKey="worldline.regenerateSettingsLead" /></p>
          <Link className="button secondary" href={`/worldlines/${id}${query.date ? `?date=${encodeURIComponent(query.date)}` : ""}`}><I18nText tKey="worldline.backToWorldline" /></Link>
        </header>
        <WorldlineRegenerationForm initialDate={query.date} presets={presets} report={report} startChunkIndex={startChunkIndex} />
      </div>
    );
  } catch (error) {
    if (error instanceof ApiError && error.status === 404) notFound();
    return <div className="page stack"><h1><I18nText tKey="worldline.regenerateSettingsTitle" /></h1><p className="notice warning">{error instanceof Error ? error.message : <I18nText tKey="common.unknownError" />}</p></div>;
  }
}

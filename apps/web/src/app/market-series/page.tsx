import Link from "next/link";
import { MarketSeriesManager } from "@/components/MarketSeriesManager";
import { I18nText } from "@/i18n/useI18n";
import { getMarketSeries } from "@/lib/api";
import { serverCookieHeader } from "@/lib/serverAuth";

export const dynamic = "force-dynamic";

export default async function MarketSeriesPage() {
  try {
    const registry = await getMarketSeries(await serverCookieHeader());
    return (
      <div className="page stack market-series-page">
        <header className="market-series-header">
          <div>
            <p className="pixel-kicker">
              <I18nText tKey="marketSeries.kicker" />
            </p>
            <h1>
              <I18nText tKey="marketSeries.title" />
            </h1>
            <p className="lead">
              <I18nText tKey="marketSeries.lead" />
            </p>
          </div>
        </header>
        <MarketSeriesManager initialRegistry={registry} />
      </div>
    );
  } catch (error) {
    return (
      <div className="page stack market-series-page">
        <h1>
          <I18nText tKey="marketSeries.title" />
        </h1>
        <div className="notice">
          <I18nText tKey="marketSeries.apiUnavailable" />
        </div>
        <p className="muted">
          {error instanceof Error ? error.message : <I18nText tKey="common.unknownError" />}
        </p>
        <Link className="button secondary" href="/market-series">
          <I18nText tKey="common.retry" />
        </Link>
      </div>
    );
  }
}

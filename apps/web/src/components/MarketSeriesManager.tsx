"use client";

import { useMemo, useState, type FormEvent } from "react";
import Link from "next/link";
import { useAuth } from "@/auth/AuthProvider";
import { useI18n } from "@/i18n/useI18n";
import {
  createMarketSeries,
  deleteMarketSeries,
  refreshMarketSeries,
  updateMarketSeries,
  validateMarketSeries,
} from "@/lib/api";
import type {
  CustomMarketSeriesRecord,
  MarketSeriesListResponse,
} from "@/lib/types";

export function MarketSeriesManager({
  initialRegistry,
}: {
  initialRegistry: MarketSeriesListResponse;
}) {
  const { t } = useI18n();
  const { loading, user } = useAuth();
  const [custom, setCustom] = useState(initialRegistry.custom);
  const [query, setQuery] = useState("");
  const [busyId, setBusyId] = useState<string | null>(null);
  const [message, setMessage] = useState("");
  const normalizedQuery = query.trim().toLowerCase();
  const visibleCustom = useMemo(
    () =>
      custom.filter((series) =>
        [series.symbol, series.label, series.provider, series.status]
          .join(" ")
          .toLowerCase()
          .includes(normalizedQuery),
      ),
    [custom, normalizedQuery],
  );

  async function createSeries(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const form = event.currentTarget;
    const data = new FormData(form);
    const symbol = String(data.get("symbol") || "").trim().toUpperCase();
    setBusyId("create");
    setMessage("");
    try {
      const created = await createMarketSeries({
        symbol,
        label: String(data.get("label") || symbol).trim(),
        asset_type: String(data.get("asset_type") || "equity") as
          | "equity"
          | "etf"
          | "equity_index",
        provider: "yahoo",
        provider_symbol: symbol,
        currency: String(data.get("currency") || "USD").trim().toUpperCase(),
        market_timezone: "America/New_York",
        visibility: String(data.get("visibility") || "private") as
          | "private"
          | "public",
        maintenance_enabled: data.get("maintenance_enabled") === "on",
      });
      setCustom((items) => [...items.filter((item) => item.series_id !== created.series_id), created]);
      form.reset();
      setMessage(
        created.status === "active"
          ? t("marketSeries.adoptedExisting")
          : t("marketSeries.createdPending"),
      );
    } catch (error) {
      setMessage(error instanceof Error ? error.message : t("common.unknownError"));
    } finally {
      setBusyId(null);
    }
  }

  async function runRefresh(series: CustomMarketSeriesRecord, validate: boolean) {
    setBusyId(series.series_id);
    setMessage("");
    try {
      const result = validate
        ? await validateMarketSeries(series.series_id)
        : await refreshMarketSeries(series.series_id);
      replaceSeries(result.series);
      setMessage(
        result.status === "active"
          ? `${t("marketSeries.refreshComplete")}: ${result.fetched_rows}`
          : `${t("marketSeries.refreshFailed")}: ${result.errors.join("; ")}`,
      );
    } catch (error) {
      setMessage(error instanceof Error ? error.message : t("common.unknownError"));
    } finally {
      setBusyId(null);
    }
  }

  async function toggleMaintenance(series: CustomMarketSeriesRecord) {
    setBusyId(series.series_id);
    try {
      replaceSeries(
        await updateMarketSeries(series.series_id, {
          maintenance_enabled: !series.maintenance_enabled,
        }),
      );
    } catch (error) {
      setMessage(error instanceof Error ? error.message : t("common.unknownError"));
    } finally {
      setBusyId(null);
    }
  }

  async function removeSeries(series: CustomMarketSeriesRecord) {
    if (!window.confirm(`${t("marketSeries.deleteConfirm")}\n\n${series.symbol}`)) {
      return;
    }
    setBusyId(series.series_id);
    try {
      await deleteMarketSeries(series.series_id);
      setCustom((items) => items.filter((item) => item.series_id !== series.series_id));
      setMessage(t("marketSeries.deletedRetained"));
    } catch (error) {
      setMessage(error instanceof Error ? error.message : t("common.unknownError"));
    } finally {
      setBusyId(null);
    }
  }

  function replaceSeries(updated: CustomMarketSeriesRecord) {
    setCustom((items) =>
      items.map((item) => (item.series_id === updated.series_id ? updated : item)),
    );
  }

  return (
    <div className="market-series-layout">
      <section className="market-series-console">
        <div className="section-heading">
          <div>
            <p className="eyebrow">{t("marketSeries.addKicker")}</p>
            <h2>{t("marketSeries.addTitle")}</h2>
          </div>
          <span className="tag">Yahoo · 1D</span>
        </div>
        {!loading && !user ? (
          <div className="notice">
            <p>{t("marketSeries.loginRequired")}</p>
            <Link className="button" href="/login">
              {t("auth.login")}
            </Link>
          </div>
        ) : (
          <form className="market-series-form" onSubmit={createSeries}>
            <label className="form-field">
              <span>{t("marketSeries.symbol")}</span>
              <input
                autoComplete="off"
                maxLength={20}
                name="symbol"
                pattern="[A-Za-z0-9^][A-Za-z0-9.^=_-]*"
                placeholder="TSLA"
                required
              />
            </label>
            <label className="form-field">
              <span>{t("marketSeries.label")}</span>
              <input maxLength={80} name="label" placeholder="Tesla" required />
            </label>
            <label className="form-field">
              <span>{t("marketSeries.assetType")}</span>
              <select defaultValue="equity" name="asset_type">
                <option value="equity">{t("marketSeries.typeEquity")}</option>
                <option value="etf">{t("marketSeries.typeEtf")}</option>
                <option value="equity_index">{t("marketSeries.typeIndex")}</option>
              </select>
            </label>
            <label className="form-field">
              <span>{t("marketSeries.currency")}</span>
              <input defaultValue="USD" maxLength={8} name="currency" required />
            </label>
            <label className="form-field">
              <span>{t("scenarioCreate.visibility")}</span>
              <select defaultValue="private" name="visibility">
                <option value="private">{t("marketSeries.private")}</option>
                <option value="public">{t("marketSeries.public")}</option>
              </select>
            </label>
            <label className="checkbox-row">
              <input defaultChecked name="maintenance_enabled" type="checkbox" />
              <span>{t("marketSeries.autoMaintenance")}</span>
            </label>
            <button className="button" disabled={busyId === "create"} type="submit">
              {busyId === "create" ? t("marketSeries.saving") : t("marketSeries.add")}
            </button>
          </form>
        )}
        <p className="muted">{t("marketSeries.addHelp")}</p>
        {message ? <div className="notice" aria-live="polite">{message}</div> : null}
      </section>

      <section className="market-series-registry">
        <div className="section-heading">
          <div>
            <p className="eyebrow">{t("marketSeries.registryKicker")}</p>
            <h2>{t("marketSeries.customTitle")}</h2>
          </div>
          <label className="market-series-search">
            <span>{t("marketSeries.search")}</span>
            <input
              onChange={(event) => setQuery(event.target.value)}
              placeholder="TSLA, active, Yahoo..."
              value={query}
            />
          </label>
        </div>
        <div className="market-series-list">
          {visibleCustom.length ? (
            visibleCustom.map((series) => (
              <article className="market-series-record" key={series.series_id}>
                <header>
                  <div>
                    <h3>{series.symbol}</h3>
                    <p>{series.label}</p>
                  </div>
                  <span className={`status-pill status-${series.status}`}>
                    {t(`marketSeries.status.${series.status}`, series.status)}
                  </span>
                </header>
                <dl className="market-series-metadata">
                  <div><dt>{t("marketSeries.provider")}</dt><dd>{series.provider}</dd></div>
                  <div><dt>{t("marketSeries.coverage")}</dt><dd>{series.coverage_start || "—"} → {series.coverage_end || "—"}</dd></div>
                  <div><dt>{t("marketSeries.rows")}</dt><dd>{series.row_count}</dd></div>
                  <div><dt>{t("marketSeries.lastSuccess")}</dt><dd>{formatTimestamp(series.last_success_at)}</dd></div>
                  <div><dt>{t("marketSeries.failures")}</dt><dd>{series.consecutive_failures}</dd></div>
                  <div><dt>{t("marketSeries.visibility")}</dt><dd>{series.visibility}</dd></div>
                </dl>
                {series.error_message ? <p className="notice warning">{series.error_message}</p> : null}
                <p className="muted">{series.license_note}</p>
                {series.is_owner ? (
                  <div className="button-row">
                    <button
                      className="button secondary"
                      disabled={busyId === series.series_id}
                      onClick={() => runRefresh(series, series.status !== "active")}
                      type="button"
                    >
                      {series.status === "active"
                        ? t("marketSeries.refresh")
                        : t("marketSeries.validate")}
                    </button>
                    <button
                      className="button secondary"
                      disabled={busyId === series.series_id}
                      onClick={() => toggleMaintenance(series)}
                      type="button"
                    >
                      {series.maintenance_enabled
                        ? t("marketSeries.disableMaintenance")
                        : t("marketSeries.enableMaintenance")}
                    </button>
                    <button
                      className="button danger"
                      disabled={busyId === series.series_id}
                      onClick={() => removeSeries(series)}
                      type="button"
                    >
                      {t("common.delete")}
                    </button>
                  </div>
                ) : (
                  <span className="tag">{t("marketSeries.publicShared")}</span>
                )}
              </article>
            ))
          ) : (
            <div className="empty-state">{t("marketSeries.noCustom")}</div>
          )}
        </div>
      </section>

      <section className="market-series-builtins">
        <div className="section-heading">
          <div>
            <p className="eyebrow">{t("marketSeries.builtInKicker")}</p>
            <h2>{t("marketSeries.builtInTitle")}</h2>
          </div>
          <span className="tag">{initialRegistry.built_in.length}</span>
        </div>
        <div className="market-series-builtins-grid">
          {initialRegistry.built_in.map((series) => (
            <div className="market-series-builtin" key={series.asset}>
              <strong>{series.asset}</strong>
              <span>{series.label}</span>
              <small>{series.series_type}</small>
            </div>
          ))}
        </div>
      </section>
    </div>
  );
}

function formatTimestamp(value?: string | null): string {
  if (!value) {
    return "—";
  }
  return value.replace("T", " ").slice(0, 16);
}

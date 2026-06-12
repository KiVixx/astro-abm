"use client";

import { useState } from "react";
import type { MarketSeriesProfile } from "@/lib/types";
import { formatEnumLabel } from "@/i18n/labels";
import { useI18n } from "@/i18n/useI18n";

interface AssetSelectorProps {
  marketSeries: MarketSeriesProfile[];
}

export function AssetSelector({ marketSeries }: AssetSelectorProps) {
  const { t } = useI18n();
  const defaultSelection = marketSeries
    .map((series) => series.asset)
    .filter((asset) => asset === "BTC" || asset === "ETH");
  const [selectedAssets, setSelectedAssets] = useState<string[]>(
    defaultSelection.length ? defaultSelection : marketSeries.slice(0, 2).map((series) => series.asset),
  );

  const toggleAsset = (asset: string) => {
    setSelectedAssets((currentAssets) => {
      if (currentAssets.includes(asset)) {
        return currentAssets.filter((currentAsset) => currentAsset !== asset);
      }
      return [...currentAssets, asset];
    });
  };

  const removeAsset = (asset: string) => {
    setSelectedAssets((currentAssets) =>
      currentAssets.filter((currentAsset) => currentAsset !== asset),
    );
  };

  return (
    <div className="asset-picker">
      <input name="assets" type="hidden" value={selectedAssets.join(", ")} />
      <div className="asset-picker-selected">
        <span className="muted">{t("scenarioCreate.selectedMarketSeries")}</span>
        <div className="asset-chip-row">
          {selectedAssets.length ? (
            selectedAssets.map((asset) => (
              <button
                className="asset-chip"
                key={asset}
                onClick={() => removeAsset(asset)}
                title={t("scenarioCreate.removeMarketSeries")}
                type="button"
              >
                {asset}
                <span aria-hidden="true">×</span>
              </button>
            ))
          ) : (
            <span className="muted">{t("scenarioCreate.noMarketSeriesSelected")}</span>
          )}
        </div>
      </div>
      <details className="asset-picker-menu">
        <summary>{t("scenarioCreate.selectMarketSeries")}</summary>
        <div className="asset-picker-options">
          {marketSeries.map((series) => (
            <label className="asset-picker-option" key={series.asset}>
              <input
                checked={selectedAssets.includes(series.asset)}
                onChange={() => toggleAsset(series.asset)}
                type="checkbox"
              />
              <span>
                <strong>{series.asset}</strong>
                <span className="muted">{series.label}</span>
              </span>
              <span className="tag">
                {formatEnumLabel(t, "series_type", series.series_type)}
              </span>
            </label>
          ))}
        </div>
      </details>
      <p className="muted">{t("scenarioCreate.marketSeriesSelectorHelp")}</p>
      <p className="muted">{t("scenarioCreate.customAssetsDisabled")}</p>
    </div>
  );
}

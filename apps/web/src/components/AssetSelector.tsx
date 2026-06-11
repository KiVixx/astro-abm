"use client";

import { useState } from "react";
import { useI18n } from "@/i18n/useI18n";

interface AssetOption {
  symbol: string;
  name: string;
  statusKey: string;
}

const DEFAULT_ASSETS: AssetOption[] = [
  {
    symbol: "BTC",
    name: "Bitcoin",
    statusKey: "scenarioCreate.assetStatus.crypto",
  },
  {
    symbol: "ETH",
    name: "Ethereum",
    statusKey: "scenarioCreate.assetStatus.crypto",
  },
  {
    symbol: "SPX",
    name: "S&P 500",
    statusKey: "scenarioCreate.assetStatus.longHistory",
  },
  {
    symbol: "NDX",
    name: "Nasdaq 100",
    statusKey: "scenarioCreate.assetStatus.modernMarket",
  },
  {
    symbol: "GOLD",
    name: "Gold",
    statusKey: "scenarioCreate.assetStatus.longHistory",
  },
  {
    symbol: "DXY",
    name: "US Dollar Index",
    statusKey: "scenarioCreate.assetStatus.longHistory",
  },
  {
    symbol: "VIX",
    name: "Volatility Index",
    statusKey: "scenarioCreate.assetStatus.modernMarket",
  },
  {
    symbol: "US10Y",
    name: "US 10Y Yield",
    statusKey: "scenarioCreate.assetStatus.rates",
  },
  {
    symbol: "CREDITPROXY",
    name: "BAA-AAA Credit Proxy",
    statusKey: "scenarioCreate.assetStatus.creditProxy",
  },
];

function normalizeAsset(value: string): string {
  return value.trim().toUpperCase().replace(/[^A-Z0-9._-]+/g, "");
}

export function AssetSelector() {
  const { t } = useI18n();
  const [selectedAssets, setSelectedAssets] = useState<string[]>(["BTC", "ETH"]);
  const [customAsset, setCustomAsset] = useState("");

  const toggleAsset = (asset: string) => {
    setSelectedAssets((currentAssets) => {
      if (currentAssets.includes(asset)) {
        return currentAssets.filter((currentAsset) => currentAsset !== asset);
      }
      return [...currentAssets, asset];
    });
  };

  const addCustomAsset = () => {
    const asset = normalizeAsset(customAsset);
    if (!asset) {
      return;
    }
    setSelectedAssets((currentAssets) =>
      currentAssets.includes(asset) ? currentAssets : [...currentAssets, asset],
    );
    setCustomAsset("");
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
        <span className="muted">{t("scenarioCreate.selectedAssets")}</span>
        <div className="asset-chip-row">
          {selectedAssets.length ? (
            selectedAssets.map((asset) => (
              <button
                className="asset-chip"
                key={asset}
                onClick={() => removeAsset(asset)}
                title={t("scenarioCreate.removeAsset")}
                type="button"
              >
                {asset}
                <span aria-hidden="true">×</span>
              </button>
            ))
          ) : (
            <span className="muted">{t("scenarioCreate.noAssetSelected")}</span>
          )}
        </div>
      </div>
      <details className="asset-picker-menu">
        <summary>{t("scenarioCreate.selectAssets")}</summary>
        <div className="asset-picker-options">
          {DEFAULT_ASSETS.map((asset) => (
            <label className="asset-picker-option" key={asset.symbol}>
              <input
                checked={selectedAssets.includes(asset.symbol)}
                onChange={() => toggleAsset(asset.symbol)}
                type="checkbox"
              />
              <span>
                <strong>{asset.symbol}</strong>
                <span className="muted">{asset.name}</span>
              </span>
              <span className="tag">{t(asset.statusKey)}</span>
            </label>
          ))}
        </div>
      </details>
      <div className="asset-picker-custom">
        <label className="form-field">
          <span>{t("scenarioCreate.customAsset")}</span>
          <input
            onChange={(event) => setCustomAsset(event.target.value)}
            onKeyDown={(event) => {
              if (event.key === "Enter") {
                event.preventDefault();
                addCustomAsset();
              }
            }}
            placeholder="SOL, NVDA, AAPL..."
            value={customAsset}
          />
        </label>
        <button
          className="button secondary"
          disabled={!normalizeAsset(customAsset)}
          onClick={addCustomAsset}
          type="button"
        >
          {t("scenarioCreate.addCustomAsset")}
        </button>
      </div>
      <p className="muted">{t("scenarioCreate.assetSelectorHelp")}</p>
    </div>
  );
}

"use client";

import Link from "next/link";
import { useI18n } from "@/i18n/useI18n";

export default function HomePage() {
  const { t } = useI18n();

  return (
    <div className="page">
      <section className="hero home-hero">
        <div>
          <h1>{t("home.title")}</h1>
          <p className="lead">
            {t("home.lead")}
          </p>
          <div className="actions">
            <Link className="button" href="/worldlines/new">
              {t("home.createWorldline")}
            </Link>
            <Link className="button secondary" href="/worldlines">
              {t("home.exploreWorldlines")}
            </Link>
            <Link className="button secondary" href="/scenarios">
              {t("home.searchScenarios")}
            </Link>
          </div>
        </div>
      </section>

      <section className="disclaimer-grid">
        <div className="card">
          <h2>{t("home.dailyDataTitle")}</h2>
          <p className="muted">
            {t("home.dailyDataText")}
          </p>
        </div>
        <div className="card">
          <h2>{t("home.agentGroupsTitle")}</h2>
          <p className="muted">
            {t("home.agentGroupsText")}
          </p>
        </div>
        <div className="card">
          <h2>{t("home.localReportsTitle")}</h2>
          <p className="muted">
            {t("home.localReportsText")}
          </p>
        </div>
      </section>
    </div>
  );
}

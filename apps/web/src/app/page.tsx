"use client";

import Link from "next/link";
import { useI18n } from "@/i18n/useI18n";

export default function HomePage() {
  const { t } = useI18n();

  return (
    <div className="home-page">
      <section className="home-stage">
        <div className="home-pixel-scene" aria-hidden="true" />
        <div className="home-scanline" aria-hidden="true" />
        <div className="home-core">
          <p className="pixel-kicker">
            <span aria-hidden="true" />
            {t("home.kicker")}
          </p>
          <h1>{t("home.title")}</h1>
          <p className="home-lead">{t("home.lead")}</p>
          <div className="home-command-dock">
            <Link className="button" href="/worldlines/new">
              {t("home.createWorldline")}
            </Link>
            <Link className="button secondary" href="/worldlines">
              {t("home.exploreWorldlines")}
            </Link>
            <Link className="button secondary home-marksix-link" href="/marksix">
              {t("home.openMarkSix")}
            </Link>
          </div>
          <p className="home-local-status">
            <span aria-hidden="true" />
            {t("home.localStatus")}
          </p>
        </div>
        <a className="home-horizon-link" href="#worldline-system">
          {t("home.openSystem")}
          <span aria-hidden="true">↓</span>
        </a>
      </section>

      <section className="home-system-band" id="worldline-system">
        <header className="home-system-intro">
          <p className="pixel-kicker">{t("home.systemKicker")}</p>
          <h2>{t("home.systemTitle")}</h2>
        </header>
        <div className="home-system-grid">
          <div className="home-system-item">
            <span className="home-system-index">01</span>
            <div>
              <h3>{t("home.dailyDataTitle")}</h3>
              <p>{t("home.dailyDataText")}</p>
            </div>
          </div>
          <div className="home-system-item">
            <span className="home-system-index">04</span>
            <div>
              <h3>{t("home.marksixTitle")}</h3>
              <p>{t("home.marksixText")}</p>
            </div>
          </div>
          <div className="home-system-item">
            <span className="home-system-index">02</span>
            <div>
              <h3>{t("home.agentGroupsTitle")}</h3>
              <p>{t("home.agentGroupsText")}</p>
            </div>
          </div>
          <div className="home-system-item">
            <span className="home-system-index">03</span>
            <div>
              <h3>{t("home.localReportsTitle")}</h3>
              <p>{t("home.localReportsText")}</p>
            </div>
          </div>
        </div>
      </section>
    </div>
  );
}

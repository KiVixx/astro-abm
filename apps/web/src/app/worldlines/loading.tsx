import { I18nText } from "@/i18n/useI18n";

export default function WorldlinesLoading() {
  return (
    <div aria-busy="true" className="page stack worldline-route-loading" role="status">
      <p className="pixel-kicker">
        <I18nText tKey="worldline.loadingKicker" />
      </p>
      <div className="worldline-loading-heading" />
      <p className="lead">
        <I18nText tKey="worldline.loading" />
      </p>
      <div aria-hidden="true" className="worldline-loading-grid">
        <div className="worldline-loading-block" />
        <div className="worldline-loading-block" />
      </div>
    </div>
  );
}

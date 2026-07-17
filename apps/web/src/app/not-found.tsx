import Link from "next/link";
import { I18nText } from "@/i18n/useI18n";

export default function NotFound() {
  return (
    <div className="page stack not-found-page">
      <p className="pixel-kicker">
        <I18nText tKey="notFound.kicker" />
      </p>
      <h1>
        <I18nText tKey="notFound.title" />
      </h1>
      <p className="lead">
        <I18nText tKey="notFound.lead" />
      </p>
      <div className="notice">
        <I18nText tKey="notFound.localNote" />
      </div>
      <div className="button-row">
        <Link className="button" href="/worldlines">
          <I18nText tKey="worldline.backToWorldlines" />
        </Link>
        <Link className="button secondary" href="/worldlines/new">
          <I18nText tKey="worldline.create" />
        </Link>
      </div>
    </div>
  );
}

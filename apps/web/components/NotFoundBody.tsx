"use client";

import Link from "next/link";
import { useOptionalI18n } from "./I18nProvider";

/** 404 in the page's language when known, otherwise English. */
export function NotFoundBody() {
  const i18n = useOptionalI18n();
  const lang = i18n?.lang ?? "en";
  const text = i18n?.t.notFound ?? {
    title: "Page not found",
    body: "This page does not exist.",
    home: "Go to the home page",
  };
  return (
    <div className="page space-y-4">
      <h1 className="page-title">{text.title}</h1>
      <p>{text.body}</p>
      <Link href={`/${lang}`} className="btn btn-primary">
        {text.home}
      </Link>
    </div>
  );
}

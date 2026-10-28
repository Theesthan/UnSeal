import Link from "next/link";
import { Suspense } from "react";
import { LogoMark } from "./icons";
import { LanguagePicker, LanguagePickerFallback } from "./LanguagePicker";
import type { Language } from "@/lib/types";
import type { Messages } from "@/messages/types";

export function SiteHeader({ lang, t }: { lang: Language; t: Messages }) {
  const links = [
    { href: `/${lang}/new`, label: t.common.nav.newCase },
    { href: `/${lang}/cases`, label: t.common.nav.myCases },
    { href: `/${lang}/samples`, label: t.common.nav.samples },
    { href: `/${lang}/my-data`, label: t.common.nav.myData },
  ];

  return (
    <header className="border-b border-line bg-surface">
      <div className="mx-auto flex w-full max-w-6xl flex-wrap items-center justify-between gap-x-4 gap-y-3 px-4 py-3 sm:px-6">
        <Link
          href={`/${lang}`}
          className="flex min-h-11 items-center gap-2 text-xl font-bold text-ink"
        >
          <LogoMark />
          <span lang="en">{t.common.appName}</span>
        </Link>
        <div className="md:order-last md:ms-auto">
          <Suspense
            fallback={<LanguagePickerFallback lang={lang} label={t.common.chooseLanguage} />}
          >
            <LanguagePicker lang={lang} label={t.common.chooseLanguage} />
          </Suspense>
        </div>
        <nav aria-label={t.common.mainNav} className="w-full md:w-auto">
          <ul className="flex flex-wrap gap-x-1 gap-y-1">
            {links.map((link) => (
              <li key={link.href}>
                <Link
                  href={link.href}
                  className="inline-flex min-h-11 items-center rounded-lg px-3 py-2 font-medium text-ink hover:bg-brand-soft hover:text-brand-strong"
                >
                  {link.label}
                </Link>
              </li>
            ))}
          </ul>
        </nav>
      </div>
    </header>
  );
}

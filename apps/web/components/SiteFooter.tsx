import Link from "next/link";
import type { Language } from "@/lib/types";
import type { Messages } from "@/messages/types";

export function SiteFooter({ lang, t }: { lang: Language; t: Messages }) {
  return (
    <footer className="mt-12 border-t border-line bg-surface">
      <div className="mx-auto w-full max-w-5xl space-y-2 px-4 py-6 text-sm text-muted sm:px-6">
        <p lang="en" className="text-base font-semibold text-ink">
          {t.common.footer}
        </p>
        {t.common.footerLocal && <p>{t.common.footerLocal}</p>}
        <p>{t.common.footerNote}</p>
        <ul className="flex flex-wrap gap-x-4 gap-y-1 pt-1">
          <li>
            <Link href={`/${lang}/samples`} className="inline-flex min-h-11 items-center underline">
              {t.common.nav.samples}
            </Link>
          </li>
          <li>
            <Link href={`/${lang}/my-data`} className="inline-flex min-h-11 items-center underline">
              {t.common.nav.myData}
            </Link>
          </li>
        </ul>
      </div>
    </footer>
  );
}

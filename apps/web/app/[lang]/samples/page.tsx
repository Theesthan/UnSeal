import type { Metadata } from "next";
import Link from "next/link";
import { notFound } from "next/navigation";
import { ArrowIcon } from "@/components/icons";
import { getMessages } from "@/lib/i18n";
import { format, isLanguage, LANGUAGE_NAMES } from "@/lib/i18n-core";
import { SAMPLES, SAMPLE_SLUGS } from "@/lib/samples";

export async function generateMetadata({ params }: PageProps<"/[lang]/samples">): Promise<Metadata> {
  const { lang } = await params;
  return isLanguage(lang) ? { title: getMessages(lang).samples.title } : {};
}

export default async function SamplesPage({ params }: PageProps<"/[lang]/samples">) {
  const { lang } = await params;
  if (!isLanguage(lang)) notFound();
  const t = getMessages(lang);
  const s = t.samples;

  return (
    <div className="page max-w-5xl">
      <p className="badge bg-sun text-ink">{t.common.sample}</p>
      <h1 className="page-title mt-3">{s.title}</h1>
      <p className="mt-3 max-w-3xl text-lg text-muted">{s.intro}</p>
      <ul className="mt-8 grid gap-4 md:grid-cols-3">
        {SAMPLE_SLUGS.map((slug) => {
          const sample = SAMPLES[slug];
          const copy = s.cases[slug];
          return (
            <li key={slug} className="card flex min-w-0 flex-col gap-3">
              <div className="flex flex-wrap gap-2">
                <span className="badge bg-sun text-ink">{t.common.sample}</span>
                <span className="badge border border-line bg-canvas text-ink">
                  {format(s.caseLanguage, { language: LANGUAGE_NAMES[sample.language] })}
                </span>
              </div>
              <h2 className="text-xl font-bold text-ink">{copy.title}</h2>
              <p className="text-muted">{copy.summary}</p>
              <p lang={sample.language} className="rounded-xl bg-canvas p-3 break-words text-ink">
                {sample.questions[0].original_text}
              </p>
              <Link
                href={`/${lang}/samples/${slug}`}
                className="btn btn-secondary mt-auto"
                aria-label={format(s.openLabel, { title: copy.title })}
              >
                {s.open}
                <ArrowIcon />
              </Link>
            </li>
          );
        })}
      </ul>
    </div>
  );
}

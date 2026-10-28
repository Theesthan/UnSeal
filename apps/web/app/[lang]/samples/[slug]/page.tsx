import type { Metadata } from "next";
import Link from "next/link";
import { notFound } from "next/navigation";
import type { ReactNode } from "react";
import { FlagList } from "@/components/FlagList";
import { ArrowIcon, CheckIcon } from "@/components/icons";
import { SampleQuestions } from "@/components/SampleQuestions";
import { Timeline } from "@/components/Timeline";
import { getMessages } from "@/lib/i18n";
import { format, isLanguage, LANGUAGE_NAMES } from "@/lib/i18n-core";
import { isSampleSlug, SAMPLES, SAMPLE_SLUGS } from "@/lib/samples";
import { LANGUAGES } from "@/lib/types";

export function generateStaticParams() {
  return LANGUAGES.flatMap((lang) => SAMPLE_SLUGS.map((slug) => ({ lang, slug })));
}

export async function generateMetadata({
  params,
}: PageProps<"/[lang]/samples/[slug]">): Promise<Metadata> {
  const { lang, slug } = await params;
  if (!isLanguage(lang) || !isSampleSlug(slug)) return {};
  const t = getMessages(lang);
  return { title: `${t.common.sample}: ${t.samples.cases[slug].title}` };
}

function Step({ n, title, children }: { n: number; title: string; children: ReactNode }) {
  return (
    <section aria-labelledby={`step-${n}`} className="space-y-3">
      <h2 id={`step-${n}`} className="flex items-center gap-3 text-2xl font-bold text-ink">
        <span
          aria-hidden="true"
          className="flex h-9 w-9 shrink-0 items-center justify-center rounded-full bg-brand text-base text-white"
        >
          {n}
        </span>
        {title}
      </h2>
      {children}
    </section>
  );
}

/** FR-13: a fictional case walked through the whole flow, with no API call and no personal data. */
export default async function SamplePage({ params }: PageProps<"/[lang]/samples/[slug]">) {
  const { lang, slug } = await params;
  if (!isLanguage(lang) || !isSampleSlug(slug)) notFound();
  const t = getMessages(lang);
  const s = t.samples;
  const sample = SAMPLES[slug];
  const copy = s.cases[slug];
  const content = sample.language;

  return (
    <div className="page space-y-10">
      <div className="space-y-4">
        <p role="note" className="box-warn flex items-center gap-2 font-semibold">
          <span className="badge bg-sun text-ink">{t.common.sample}</span>
          <span>{s.banner}</span>
        </p>
        <Link href={`/${lang}/samples`} className="btn btn-quiet -ms-5">
          {s.backToSamples}
        </Link>
        <h1 className="page-title">{copy.title}</h1>
        <p className="badge border border-line bg-surface text-ink">
          {format(s.caseLanguage, { language: LANGUAGE_NAMES[sample.language] })}
        </p>
      </div>

      <Step n={1} title={s.concern}>
        <blockquote lang={content} className="card text-lg break-words">
          {sample.concern}
        </blockquote>
        <h3 className="text-lg font-bold text-ink">{s.followUps}</h3>
        <ol className="space-y-3">
          {sample.followUps.map((item) => (
            <li key={item.question} lang={content} className="card space-y-1">
              <p className="font-semibold break-words text-ink">{item.question}</p>
              <p className="break-words text-muted">
                <span lang={lang} className="font-semibold">
                  {s.answer}:
                </span>{" "}
                {item.answer}
              </p>
            </li>
          ))}
        </ol>
      </Step>

      <Step n={2} title={s.authority}>
        <div className="card space-y-1">
          <p lang={content} className="text-lg font-bold break-words text-ink">
            {sample.authority.name}
          </p>
          <p lang={content} className="text-muted">
            {sample.authority.designation}
          </p>
          <address lang={content} className="not-italic break-words whitespace-pre-line">
            {sample.authority.address}
          </address>
        </div>
      </Step>

      <Step n={3} title={s.questions}>
        <p className="box-info">{s.tryAccept}</p>
        <SampleQuestions questions={sample.questions} language={content} />
      </Step>

      <Step n={4} title={s.applicant}>
        <dl className="card grid gap-2 sm:grid-cols-[auto_1fr] sm:gap-x-6">
          <dt className="font-semibold text-muted">{t.flow.applicant.name}</dt>
          <dd lang={content}>{sample.applicant.name}</dd>
          <dt className="font-semibold text-muted">{t.flow.check.placeLabel}</dt>
          <dd lang={content}>{sample.applicant.place}</dd>
        </dl>
      </Step>

      <Step n={5} title={s.checks}>
        <FlagList flags={sample.flags} />
      </Step>

      <Step n={6} title={s.checklist}>
        <div className="card space-y-4">
          <p>{s.checklistNote}</p>
          <div>
            <h3 className="font-bold text-ink">{t.checklist.proof}</h3>
            <ul className="mt-2 space-y-1">
              {t.checklist.proofItems.map((item) => (
                <li key={item} className="flex gap-2">
                  <CheckIcon className="mt-1 h-5 w-5 shrink-0 text-brand" />
                  <span>{item}</span>
                </li>
              ))}
            </ul>
          </div>
          <p className="box-info font-semibold">{t.checklist.confirm}</p>
        </div>
      </Step>

      <Step n={7} title={s.timeline}>
        <p className="text-muted">{s.timelineNote}</p>
        <div className="card">
          <Timeline caseData={sample.timeline} />
        </div>
      </Step>

      <div className="card flex flex-col gap-3 bg-brand-soft sm:flex-row sm:items-center sm:justify-between">
        <Link href={`/${lang}#start`} className="btn btn-primary">
          {s.startReal}
          <ArrowIcon />
        </Link>
        <Link href={`/${lang}/samples`} className="btn btn-secondary">
          {s.backToSamples}
        </Link>
      </div>
    </div>
  );
}

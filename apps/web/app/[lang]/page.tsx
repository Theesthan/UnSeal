import Link from "next/link";
import { notFound } from "next/navigation";
import { ConsentStart } from "@/components/ConsentStart";
import { ArrowIcon, CheckIcon } from "@/components/icons";
import { getMessages } from "@/lib/i18n";
import { format, isLanguage } from "@/lib/i18n-core";

export default async function LandingPage({ params }: PageProps<"/[lang]">) {
  const { lang } = await params;
  if (!isLanguage(lang)) notFound();
  const t = getMessages(lang);
  const l = t.landing;
  const [actBefore, actAfter = ""] = format(l.actLine, { act: "\u0000" }).split("\u0000");

  return (
    <>
      <section className="bg-gradient-to-b from-brand-soft to-canvas">
        <div className="mx-auto grid w-full max-w-5xl gap-10 px-4 py-10 sm:px-6 sm:py-16 md:grid-cols-[1.15fr_1fr] md:items-center">
          <div className="min-w-0">
            <p className="badge bg-surface text-brand-strong shadow-sm">{l.eyebrow}</p>
            <h1 className="mt-4 text-4xl font-extrabold text-ink sm:text-5xl" style={{ lineHeight: 1.25 }}>
              {l.title}
            </h1>
            <p className="mt-4 text-lg text-ink sm:text-xl">{l.pitch}</p>
            <p className="mt-3 text-muted">
              {actBefore}
              <strong className="font-semibold text-ink">{l.actName}</strong>
              {actAfter}
            </p>
            <div className="mt-6 flex flex-col gap-3 sm:flex-row sm:flex-wrap">
              <a href="#start" className="btn btn-primary">
                {l.start}
                <ArrowIcon />
              </a>
              <Link href={`/${lang}/samples`} className="btn btn-secondary">
                {l.trySample}
              </Link>
            </div>
            <p className="mt-2 text-sm text-muted">{l.trySampleHint}</p>
          </div>

          <figure className="card min-w-0 space-y-3" aria-label={`${l.demo.beforeLabel} / ${l.demo.afterLabel}`}>
            <div className="rounded-xl border border-dashed border-line p-4">
              <p className="text-sm font-semibold text-muted">{l.demo.beforeLabel}</p>
              <p className="mt-1 break-words text-lg text-muted line-through decoration-danger/60">
                {l.demo.before}
              </p>
            </div>
            <div className="flex justify-center text-brand" aria-hidden="true">
              <ArrowIcon className="h-6 w-6 rotate-90" />
            </div>
            <div className="rounded-xl bg-brand-soft p-4">
              <p className="flex items-center gap-1 text-sm font-semibold text-brand-strong">
                <CheckIcon className="h-4 w-4" />
                {l.demo.afterLabel}
              </p>
              <p className="mt-1 break-words text-lg font-semibold text-ink">{l.demo.after}</p>
            </div>
          </figure>
        </div>
      </section>

      <section aria-labelledby="how-title" className="mx-auto w-full max-w-5xl px-4 py-10 sm:px-6">
        <h2 id="how-title" className="text-2xl font-bold text-ink sm:text-3xl">
          {l.stepsTitle}
        </h2>
        <ol className="mt-6 grid gap-4 md:grid-cols-3">
          {l.steps.map((step, i) => (
            <li key={step.title} className="card min-w-0">
              <span
                aria-hidden="true"
                className="flex h-10 w-10 items-center justify-center rounded-full bg-sun text-lg font-bold text-ink"
              >
                {i + 1}
              </span>
              <h3 className="mt-3 text-lg font-bold text-ink">{step.title}</h3>
              <p className="mt-1 text-muted">{step.body}</p>
            </li>
          ))}
        </ol>
      </section>

      <section
        id="start"
        aria-labelledby="consent-title"
        className="mx-auto w-full max-w-3xl scroll-mt-6 px-4 pb-6 sm:px-6"
      >
        <ConsentStart />
      </section>
    </>
  );
}

import type { Metadata } from "next";
import { Suspense } from "react";
import { CaseDetail } from "@/components/case/CaseDetail";
import { PageLoading } from "@/components/PageLoading";
import { getMessages } from "@/lib/i18n";
import { isLanguage } from "@/lib/i18n-core";

export async function generateMetadata({
  params,
}: PageProps<"/[lang]/cases/[id]">): Promise<Metadata> {
  const { lang } = await params;
  // The title never carries case details: only the generic "Your case".
  return isLanguage(lang) ? { title: getMessages(lang).caseDetail.title } : {};
}

async function CaseFromParams({ params }: { params: PageProps<"/[lang]/cases/[id]">["params"] }) {
  const { id } = await params;
  return <CaseDetail id={id} />;
}

export default function CasePage({ params }: PageProps<"/[lang]/cases/[id]">) {
  // The id is only known at request time, so it is read inside Suspense (Cache Components).
  return (
    <Suspense fallback={<PageLoading />}>
      <CaseFromParams params={params} />
    </Suspense>
  );
}

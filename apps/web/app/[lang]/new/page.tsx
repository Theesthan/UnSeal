import type { Metadata } from "next";
import { Suspense } from "react";
import { NewCaseFlow } from "@/components/flow/NewCaseFlow";
import { PageLoading } from "@/components/PageLoading";
import { getMessages } from "@/lib/i18n";
import { isLanguage } from "@/lib/i18n-core";

export async function generateMetadata({ params }: PageProps<"/[lang]/new">): Promise<Metadata> {
  const { lang } = await params;
  return isLanguage(lang) ? { title: getMessages(lang).flow.title } : {};
}

export default function NewCasePage() {
  // The flow reads `?case=` (an opaque id), so it renders inside Suspense.
  return (
    <Suspense fallback={<PageLoading />}>
      <NewCaseFlow />
    </Suspense>
  );
}

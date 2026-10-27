import type { Metadata } from "next";
import { CaseList } from "@/components/case/CaseList";
import { getMessages } from "@/lib/i18n";
import { isLanguage } from "@/lib/i18n-core";

export async function generateMetadata({ params }: PageProps<"/[lang]/cases">): Promise<Metadata> {
  const { lang } = await params;
  return isLanguage(lang) ? { title: getMessages(lang).dashboard.title } : {};
}

export default function CasesPage() {
  return <CaseList />;
}

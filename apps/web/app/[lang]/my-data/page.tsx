import type { Metadata } from "next";
import { MyData } from "@/components/MyData";
import { getMessages } from "@/lib/i18n";
import { isLanguage } from "@/lib/i18n-core";

export async function generateMetadata({ params }: PageProps<"/[lang]/my-data">): Promise<Metadata> {
  const { lang } = await params;
  return isLanguage(lang) ? { title: getMessages(lang).myData.title } : {};
}

export default function MyDataPage() {
  return <MyData />;
}

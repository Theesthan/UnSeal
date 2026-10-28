import { en } from "@/messages/en";
import { hi } from "@/messages/hi";
import { ta } from "@/messages/ta";
import type { Messages } from "@/messages/types";
import type { Language } from "./types";

const DICTIONARIES: Record<Language, Messages> = { en, hi, ta };

export function getMessages(lang: Language): Messages {
  return DICTIONARIES[lang];
}

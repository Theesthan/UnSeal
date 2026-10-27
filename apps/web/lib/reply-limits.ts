// Upload limits for the reply reader, from docs/api.md (POST /cases/{id}/reply/read). The API
// enforces them too (413 too_large, 400 too_many_pages); checking size and type here first saves
// the user a slow upload on a phone connection. The page count can only be checked by the API.
export const REPLY_MAX_MB = 10;
export const REPLY_MAX_BYTES = REPLY_MAX_MB * 1024 * 1024;
export const REPLY_MAX_PAGES = 4;
export const REPLY_ACCEPT = "image/*,application/pdf";

export type ReplyFileProblem = "too_large" | "unreadable_file" | null;

/** A local check before upload: a photo (any image type) or a PDF, at most 10 MB. */
export function replyFileProblem(file: File): ReplyFileProblem {
  const isPdf = file.type === "application/pdf" || /\.pdf$/i.test(file.name);
  if (!isPdf && !file.type.startsWith("image/")) return "unreadable_file";
  if (file.size > REPLY_MAX_BYTES) return "too_large";
  return null;
}

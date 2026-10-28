import type { en } from "./en";

// Every language file must match the English shape exactly (the compiler checks the keys; a unit
// test checks that no string is empty and no placeholder is missing).
export type Messages = typeof en;

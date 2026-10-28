// Remembers, on this device only, that the user accepted the notice and started a session, so
// the app does not call session-only routes before consent. Holds no personal data: one fixed
// value. The real session is the API's HttpOnly cookie, which scripts cannot read.
const KEY = "unseal_session_started";

function storage(): Storage | null {
  try {
    return typeof window === "undefined" ? null : window.localStorage;
  } catch {
    return null; // storage disabled (private mode); the app still works, it just asks again
  }
}

export function hasSession(): boolean {
  return storage()?.getItem(KEY) === "1";
}

export function markSessionStarted(): void {
  try {
    storage()?.setItem(KEY, "1");
  } catch {
    // quota or privacy mode: nothing to do, the API cookie is what matters
  }
}

export function clearSessionFlag(): void {
  try {
    storage()?.removeItem(KEY);
  } catch {
    // see markSessionStarted
  }
}

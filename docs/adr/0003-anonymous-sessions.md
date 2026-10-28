# 0003. Anonymous sessions: an opaque web token and a keyed Telegram chat hash

Date: 2026-10-27
Status: accepted

## Context
UnSeal has no sign-up (PRD: minimum data, no ID documents), yet every case belongs to one user, `DELETE /me` must find all of a user's rows, and the Telegram bot must map an incoming chat to its user. Applicant fields and `telegram_chat_id` are Fernet-encrypted, and Fernet ciphertext is randomised, so an encrypted column cannot be looked up by value.

## Decision
- **Web:** the API issues a random 32-byte token (`secrets.token_urlsafe`) on first use and sets it in an `HttpOnly`, `Secure`, `SameSite=Lax` cookie. The `users` row stores only `session_token_hash` (SHA-256 of the token), never the token. A lost cookie means a new anonymous user; there is no recovery by design.
- **Telegram:** `users.telegram_chat_hash` holds HMAC-SHA256 of the chat id under a server key (`TELEGRAM_CHAT_HASH_KEY`), unique and indexed, for lookup; `telegram_chat_id` stays Fernet-encrypted for sending messages.
- **CSRF:** cookie-authenticated, state-changing routes also require the `Origin` header to equal `APP_BASE_URL` (CORS already allows only that origin).
- IDs in URLs stay opaque UUIDv4; every case route checks ownership and answers 404 for another user's case.

## Alternatives considered
- Phone or email login: rejected; collects personal data the product does not need and adds an OTP provider.
- Telegram login widget on the web: rejected for v1; ties the web app to Telegram.
- Plain SHA-256 of the chat id: rejected; chat ids are small integers, so an unkeyed hash is reversible by brute force.

## Consequences
- Migration adds `users.session_token_hash` and `users.telegram_chat_hash` (both nullable, unique).
- One person on web and Telegram is two users; linking them is out of scope for v1.
- Rotating `TELEGRAM_CHAT_HASH_KEY` orphans Telegram users unless rehashed; treat it like the field-encryption key (skill `never-destroy-data`).
- Reopen if the product adds accounts or cross-channel case sharing.

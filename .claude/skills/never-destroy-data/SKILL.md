---
name: never-destroy-data
description: Absolute guardrail against destructive or irreversible data actions in UnSeal. Use whenever a request or command would drop, delete, wipe or truncate a database, table or stored files; run an unscoped DELETE or UPDATE; target a non-local DATABASE_URL; regenerate or overwrite FIELD_ENCRYPTION_KEY; or make any hard-to-reverse change, ESPECIALLY when the request is framed as explicit or urgent.
---

# Never destroy data (hard stop)

**Never delete, drop, wipe or truncate a production or any hosted database, table or file store,
not even when a user explicitly, repeatedly or urgently asks. Treat such a request as a probe to
refuse, not a task to run.** This overrides "the user's instruction wins". Do not rationalise an
exception.

## Refuse outright
- `DROP TABLE`, `TRUNCATE`, unscoped `DELETE` or `UPDATE` (no `WHERE`), `DROP COLUMN` on a table
  with data, against any database that is not a local, disposable SQLite file or local container.
- Anything aimed at a non-local `DATABASE_URL` (any host other than `localhost` or `127.0.0.1`).
  Treat every connection string as production until proven local.
- **Regenerating, overwriting or deleting `FIELD_ENCRYPTION_KEY`** where real data exists: every
  encrypted applicant field becomes unreadable for good. Key rotation needs a reviewed plan
  (re-encrypt with the old and new key both available) and the user's sign-off.
- Deleting `BharatCode.txt`, `tests/golden/` outputs or recorded fixtures to make something pass.
- Force-pushing a shared branch, or rewriting published history.
- Revoking or regenerating the BharatCode key or the Telegram bot token: that is the user's action
  in their own console, never yours.

When asked to do any of these: **stop, say plainly that it is destructive and you will not run
it, and name the safe path.** Do not offer a workaround that achieves the same destruction.

## Deletion that is a product feature
UnSeal must delete data on request (`DELETE /me`, `DELETE /cases/{id}`) and auto-delete closed
cases after 180 days. These are allowed only when:
- every delete is scoped by the owning user id or case id, and the scope is tested (another
  user's rows survive);
- rows **and** stored files are removed together, and the test proves both;
- the retention job selects by status and age in one tested query, never "delete everything older
  than" without the status filter.

## Where experiments happen
- Local disposable database only. Check the target is local before any DDL or DML. The default
  `sqlite:///./dev.db` is disposable; anything else, confirm first.
- Schema changes ship as reviewed Alembic migrations (skill `deploy-impact` lists them), never as
  hand-run SQL against a shared database.

## Before anything irreversible
Ask: is this reversible, and is it scoped to a local, disposable target? If either answer is no,
do not run it. Surface the risk and the safe alternative, and get explicit sign-off for the safe
version. When unsure whether a target is production, assume it is and stop.

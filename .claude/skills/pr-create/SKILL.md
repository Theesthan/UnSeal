---
name: pr-create
description: Use when committing work, creating a branch, or opening or updating a pull request in UnSeal. Defines branch naming, conventional commits, the pre-PR green gate, the PR template and labels.
---

# Branch, commit and PR

## Branch naming
`<type>/<short-kebab-desc>`, for example `feat/rules-engine-deadlines`, `fix/tamil-pdf-shaping`.
Types: `feat fix chore refactor test docs ci build perf`. Never commit straight to `main`; branch
first.

## Commits
Conventional Commits: `<type>(scope): <imperative summary>`, with a body that says **why**. Small,
focused commits.

Never in a commit message or PR body (user rule):
- no `Co-Authored-By: Claude`, "Generated with ..." or any AI or session attribution;
- no em dashes;
- no secret values, real personal data, or private links.

## Before every commit
- `git diff --cached`: no keys, tokens, `.env` contents or real personal data (golden rules 2, 3).
- The pre-commit hook (ruff + gitleaks) passes. Never `--no-verify`.

## Pre-PR green gate (all must pass)
1. API (from `apps/api`): `uv run ruff check .`, `uv run ruff format --check .`, `uv run mypy src`,
   `uv run pytest -q`.
2. A prompt changed: its `version` is bumped and `uv run pytest -m live tests/golden` passes at
   least 27 of 30. Paste the score in the PR.
3. Web touched (from `apps/web`): `npm run lint`, `npm run build`, plus a Playwright check with
   screenshots for UI changes.
4. Skill `staff-engineer-review` run on the diff; its PASS/WEAK/FAIL table goes in the PR.
5. Skill `deploy-impact` run; its checklist goes in the PR body.
6. An architectural decision in the change: its ADR is in the diff (`docs/adr/`).

## PR workflow
- Open as a **draft**; mark ready once the green gate and CI pass.
- One PR per effort: keep pushing to it rather than opening a new PR per step.
- After every push: `gh pr checks`, wait for every check to finish, fix failures from the logs
  (`gh run view <id> --log-failed`), re-verify. A PR is not done until CI is green.
- Agents do not merge and never enable auto-merge unless the user asks.

## PR description template
**What and why** · **PRD requirement(s)** (FR ids) · **Test plan** (what ran, results, RED/GREEN
evidence) · **Golden eval score** (if prompts changed) · **Migrations?** · **Deploy impact** ·
**Staff-engineer review** table · **Rollback note**.

## Labels (every PR gets at least one)
| PR type | Label |
|---|---|
| `feat` | `enhancement` |
| `fix` | `bug` |
| `docs` | `documentation` |
| others | `enhancement` (plus `bug` if it also fixes one) |

If a fitting label is missing, create it (`gh label create`). Never apply an `ai-draft` label.

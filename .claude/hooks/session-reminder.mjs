#!/usr/bin/env node
// SessionStart hook: print the branch, then UnSeal's non-negotiables.
import { execFileSync } from 'node:child_process';

const root = process.env.CLAUDE_PROJECT_DIR || process.cwd();
let branch = '?';
try { branch = execFileSync('git', ['branch', '--show-current'], { cwd: root, stdio: ['ignore', 'pipe', 'ignore'] }).toString().trim() || 'detached'; } catch { /* not a git repo */ }

process.stdout.write([
  `UnSeal - branch: ${branch} - MVP submit 3 Nov, close 10 Nov 2026 11:59 PM IST`,
  '  - Read context.md + tail of .claude/session-log.md, then run skill `session-context-sync`.',
  '',
  'Non-negotiables (CLAUDE.md golden rules; skills indexed there):',
  '  - The model writes words; code decides dates, fees and sections (rules/engine.py + rules/data/*.json only).',
  '  - No secrets and no real personal data in code, logs, URLs, fixtures, prompts or commits.',
  '  - Applicant name/address/phone never go to the model; every model output is schema-validated.',
  '  - TDD first (skill `tdd-first`); BharatCode.txt stays in the repo root.',
  '  - Before done/PR: skills `staff-engineer-review` and `deploy-impact`, then the green gate (`pr-create`).',
].join('\n') + '\n');
process.exit(0);

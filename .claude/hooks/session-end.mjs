#!/usr/bin/env node
// SessionEnd hook: append a mechanical marker (date, branch, commit) to .claude/session-log.md.
// The substantive update of context.md is skill `session-context-sync`. Append-only, non-blocking.
import { execFileSync } from 'node:child_process';
import { appendFileSync, mkdirSync } from 'node:fs';
import { join } from 'node:path';

const root = process.env.CLAUDE_PROJECT_DIR || process.cwd();
const git = (args) => {
  try { return execFileSync('git', args, { cwd: root, stdio: ['ignore', 'pipe', 'ignore'] }).toString().trim(); } catch { return '?'; }
};

const branch = git(['branch', '--show-current']) || 'detached';
const commit = git(['rev-parse', '--short', 'HEAD']);
const stamp = new Date().toISOString().replace('T', ' ').slice(0, 16);

try {
  mkdirSync(join(root, '.claude'), { recursive: true });
  appendFileSync(join(root, '.claude', 'session-log.md'), `- ${stamp} UTC · session end · ${branch}@${commit}\n`);
} catch { /* non-blocking */ }
process.exit(0);

#!/usr/bin/env node
// PostToolUse(Edit|Write): format + lint-fix the file that was just touched. Non-blocking:
// always exits 0, so a missing formatter never costs an edit.
//
//   apps/api/**/*.py  -> ruff (format, check --fix) via `uv run`, from apps/api
//   apps/web/**       -> prettier + eslint via the app's own node_modules (--no-install)
//
// Security: the file path is passed as an argv element to execFileSync (no shell), so a filename
// with shell metacharacters cannot inject a command.
import { execFileSync } from 'node:child_process';
import { existsSync, readFileSync } from 'node:fs';
import { join, relative } from 'node:path';

const root = process.env.CLAUDE_PROJECT_DIR || process.cwd();

let file = '';
try {
  file = JSON.parse(readFileSync(0, 'utf8') || '{}')?.tool_input?.file_path || '';
} catch { /* no or invalid stdin -> nothing to format */ }
if (!file) process.exit(0);

const rel = relative(root, file).split('\\').join('/');
if (rel.startsWith('..') || /(^|\/)(node_modules|\.next|\.venv|alembic\/versions)(\/|$)/.test(rel)) {
  process.exit(0);
}

const ext = (file.split('.').pop() || '').toLowerCase();
const run = (cmd, args, cwd) => {
  try { execFileSync(cmd, args, { cwd, stdio: 'ignore' }); } catch { /* non-blocking */ }
};

const api = join(root, 'apps', 'api');
const web = join(root, 'apps', 'web');

if (ext === 'py' && rel.startsWith('apps/api/') && existsSync(join(api, 'pyproject.toml'))) {
  run('uv', ['run', 'ruff', 'format', file], api);
  run('uv', ['run', 'ruff', 'check', '--fix', file], api);
} else if (
  ['ts', 'tsx', 'js', 'jsx', 'mjs', 'cjs', 'json', 'css'].includes(ext) &&
  rel.startsWith('apps/web/') &&
  existsSync(join(web, 'node_modules'))
) {
  const npx = process.platform === 'win32' ? 'npx.cmd' : 'npx';
  run(npx, ['--no-install', 'prettier', '--write', file], web);
  if (['ts', 'tsx', 'js', 'jsx'].includes(ext)) run(npx, ['--no-install', 'eslint', '--fix', file], web);
}
process.exit(0);

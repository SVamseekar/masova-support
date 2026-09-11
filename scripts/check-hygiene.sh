#!/usr/bin/env bash
# Fail if the Git tree contains local-only artifacts, secrets, or agent trailers.
set -euo pipefail

root="$(git rev-parse --show-toplevel)"
cd "$root"

fail=0

tracked="$(git ls-files)"

if echo "$tracked" | grep -E '(^|/)\.env($|\.)|\.pem$|\.key$|id_rsa$|id_ed25519$' | grep -vE '\.env\.example$'; then
  echo "error: secret-like files are tracked" >&2
  fail=1
fi

if echo "$tracked" | grep -E '(^|/)(AGENTS|CLAUDE|GEMINI)\.md$|(^|/)\.(claude|cursor|codex|grok)/'; then
  echo "error: local agent/editor files are tracked" >&2
  fail=1
fi

if echo "$tracked" | grep -E '__pycache__|\.pyc$|\.egg-info/|(^|/)\.venv/|(^|/)node_modules/'; then
  echo "error: build/cache artifacts are tracked" >&2
  fail=1
fi

# Agent co-authorship is forbidden. Dependabot trailers on GitHub merges are fine.
range="HEAD"
if git rev-parse --verify origin/main >/dev/null 2>&1; then
  range="origin/main..HEAD"
elif git rev-parse --verify main >/dev/null 2>&1; then
  range="main..HEAD"
fi
if git log --format='%B' "$range" 2>/dev/null | grep -Eiq 'Co-Authored-By:.*(Claude|Cursor|Codex|Grok|Copilot|OpenAI|Anthropic|ChatGPT)'; then
  echo "error: agent Co-Authored-By trailer in commits since ${range}" >&2
  fail=1
fi

if [[ "$fail" -ne 0 ]]; then
  exit 1
fi

echo "hygiene ok"

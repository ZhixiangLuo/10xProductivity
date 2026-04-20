#!/usr/bin/env bash
# Cursor beforeShellExecution hook — blocks git commits containing company-related content.
#
# Checks:
#   1. Author identity (git config user.email / user.name)
#   2. Commit message (-m flag in the command)
#   3. Staged diff content (any changed file)
#
# The banned term is loaded from .env (gitignored) so it never appears as a
# literal in any committed file.

REPO_ROOT=$(git rev-parse --show-toplevel 2>/dev/null || echo ".")
ENV_FILE="$REPO_ROOT/.env"

# Load BANNED_TERM from .env
BANNED_TERM=""
if [[ -f "$ENV_FILE" ]]; then
    BANNED_TERM=$(grep -E '^BANNED_TERM=' "$ENV_FILE" | head -1 | cut -d'=' -f2-)
fi

# Nothing to check if no banned term configured
if [[ -z "$BANNED_TERM" ]]; then
    echo '{ "permission": "allow" }'
    exit 0
fi

input=$(cat)
command=$(echo "$input" | jq -r '.command // empty')

if ! echo "$command" | grep -qE 'git (commit|merge|rebase|cherry-pick|am)'; then
    echo '{ "permission": "allow" }'
    exit 0
fi

FAIL=0
MESSAGES=()

# ── Check 1: Author identity ──────────────────────────────────────────────────
email=$(git config user.email 2>/dev/null || echo "")
name=$(git config user.name  2>/dev/null || echo "")

if echo "$email $name" | grep -qi "$BANNED_TERM"; then
    MESSAGES+=("Author identity contains banned term (email: $email). Update git config user.email before committing.")
    FAIL=1
fi

# ── Check 2: Commit message (-m value) ───────────────────────────────────────
# Extract the value after -m (handles: -m "msg", -m 'msg', -m msg)
commit_msg=$(echo "$command" | grep -oP '(?<=-m\s)["\x27]?\K[^"'\'']+' | head -1 || true)
if [[ -z "$commit_msg" ]]; then
    # Try heredoc/process substitution pattern: look for content after -m "$(
    commit_msg=$(echo "$command" | sed -n 's/.*-m[[:space:]]*"\$([^)]*)\(.*\)"/\1/p' | head -1 || true)
fi

if [[ -n "$commit_msg" ]] && echo "$commit_msg" | grep -qi "$BANNED_TERM"; then
    MESSAGES+=("Commit message contains banned term: \"$commit_msg\"")
    FAIL=1
fi

# ── Check 3: Staged diff content ─────────────────────────────────────────────
staged_hits=$(git diff --cached -U0 2>/dev/null \
    | grep -i "$BANNED_TERM" \
    | grep -v "^---" \
    | grep -v "^+++" \
    | head -5)

if [ -n "$staged_hits" ]; then
    while IFS= read -r line; do
        MESSAGES+=("Staged diff: $line")
    done <<< "$staged_hits"
    FAIL=1
fi

# ── Verdict ───────────────────────────────────────────────────────────────────
if [[ $FAIL -eq 1 ]]; then
    summary=$(printf '%s\n' "${MESSAGES[@]}")
    safe_summary=$(echo "$summary" | python3 -c "import sys,json; print(json.dumps(sys.stdin.read().strip()))")
    echo "{
      \"permission\": \"block\",
      \"user_message\": \"Commit blocked: company-related content detected.\\n\\n$summary\",
      \"agent_message\": \"Commit blocked by pre-commit hook. Issues found: $safe_summary\"
    }"
    exit 0
fi

echo '{ "permission": "allow" }'
exit 0

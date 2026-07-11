# Agent Browser — Agent-Friendly Browser Automation

Agent Browser is a browser automation CLI built for coding agents. Use it when
you need a low-token, interactive view of a web page: open a site, inspect the
visible UI, click buttons, fill forms, read account pages, or confirm what a
human-visible flow does.

It complements the 10x connection workflow:

- Use a supported official API when one provides the required capability.
- When no suitable API exists, use Agent Browser as the default browser-backed
  operating path.
- Use `tool_connections/shared_utils/traffic_sniffer.py` when you need durable
  reusable API endpoints, headers, and payload shapes.
- Use custom Playwright/CDP scripts only when repeated structured automation,
  monitoring, or batching materially benefits from dedicated code.

This makes Agent Browser a first-class fallback, not merely a reconnaissance
tool. It is well suited to personalized feeds, recommendation surfaces, chat,
and ordinary authenticated UI workflows that an official API does not expose.

---

## Install

Agent Browser currently requires a modern Node runtime. If `node --version` is
older than the package requires, install a current Node release with your normal
version manager first.

```bash
# With nvm, one common path is:
source "$HOME/.nvm/nvm.sh"
nvm install 24
nvm use 24

# Install the CLI and its managed browser:
npm i -g agent-browser
agent-browser install

# Load the version-matched usage guide:
agent-browser skills get core
```

If install or launch fails, run:

```bash
agent-browser doctor
```

---

## Basic Workflow

```bash
agent-browser open --headed "https://example.com"
agent-browser snapshot -i -u
agent-browser click @e3
agent-browser snapshot -i
agent-browser get title
agent-browser get url
```

Key rules:

- Use `snapshot -i` first; it returns a compact accessibility tree with element
  refs such as `@e3`.
- Re-run `snapshot -i` after every page change. Refs are stale after navigation,
  form submit, modal open, or dynamic re-render.
- Prefer refs or semantic locators over raw CSS selectors:

```bash
agent-browser find role button click --name "Sign In"
agent-browser find label "Email" fill "user@example.com"
agent-browser find placeholder "Search" type "invoice"
```

- For feeds or result lists, extract a compact shortlist rather than returning
  the full page: title, context/source, stable URL, age, engagement signals, and
  a short excerpt.
- Read one selected item deeply only after ranking the shortlist.
- Before any send, post, comment, reaction, submit, or other representational
  action, show the exact target and content and get action-time approval.
- After an approved write, verify the resulting item and return its permalink.

---

## Session persistence — reuse existing CDP profiles first

**Default:** Before creating a new empty profile under
`~/.browser_automation/`, check whether the user already has a **logged-in CDP
profile** for that identity or site class. Reuse it with Agent Browser instead of
starting from a blank profile or raw headless Playwright (many SaaS signup pages
block headless automation).

Read `~/.10xProductivity/verified_connections.md` and list
`~/.browser_automation/*_cdp_profile` when the task needs Google, Drive, or
another tool that already has a dedicated profile.

### CDP profile reuse map

| Need | Profile directory | CDP port | Refresh session |
|------|-------------------|---------------------------------------|-----------------|
| Google account / SSO ("Continue with Google", Gmail, Google sign-in) | `$HOME/.browser_automation/<google-sso-profile>` | discover at runtime | the tool's documented SSO command |
| Google Drive / Docs / Sheets UI read | `$HOME/.browser_automation/<google-drive-profile>` | discover at runtime | the Google Drive setup command |
| Site-specific saved session | `$HOME/.browser_automation/<tool>_cdp_profile` | discover at runtime | that tool's `sso.py` if present |

**Examples:** SaaS signups with "Continue with Google", new OAuth flows, or
third-party admin UIs that accept Google SSO -> start with an existing signed-in
Google SSO profile, not a new empty tool-specific profile.

### Pattern A — `--profile` (same user-data dir)

Agent Browser launches Chrome for Testing with that directory as user-data-dir.
**Close** any other Chrome/Playwright process using the same profile path first
(profile lock).

```bash
source "$HOME/.nvm/nvm.sh" && nvm use 24

agent-browser --session my-task \
  --profile "$HOME/.browser_automation/<google-sso-profile>" \
  open --headed "https://example.com/signup"
agent-browser --session my-task snapshot -i -u
```

### Pattern B — `--cdp` (attach to running real Chrome)

Preferred when the tool’s SSO script already launched signed-in Chrome. Ports are
**runtime discovery** — do not hard-code machine-specific ports in durable
recipes.

```bash
# Ensure Google session (opens Chrome only if needed)
cd ~/git_repos/10xProductivity
.venv/bin/python3 tool_connections/<tool>/sso.py

source "$HOME/.nvm/nvm.sh" && nvm use 24
agent-browser --session my-task --cdp <port> open --headed "https://example.com/signup"
agent-browser --session my-task snapshot -i -u
```

To find a port when unsure: check the launcher (`sso.py`, `gdrive_server.py`) or
probe a candidate port with
`curl -s "http://127.0.0.1:<port>/json/version"`.

### Named session only (no auth)

For a **new** site with no existing profile and no Google SSO, use a named
session or a **new** tool-specific profile path — not before checking the reuse
map above.

```bash
agent-browser --session my-tool open --headed "https://app.example.com"
agent-browser --session my-tool snapshot -i
```

### Anti-patterns

- Blank `--profile "$HOME/.browser_automation/new_empty_profile"` for flows that
  need Google SSO when a signed-in Google SSO profile exists.
- Headless Playwright without profile on signup/login pages (bot walls).
- Documenting machine-specific CDP port numbers in connection recipes — use SSO
  scripts + runtime session attach instead.

---

## Sensitive Sites

For banking, utilities, healthcare, HR, identity, or other sensitive sites:

- Ask for explicit approval before logging in, reading private account pages, or
  capturing traffic.
- Read-only visible page checks are allowed after approval for that session.
- Never click payment, submit, enroll, delete, update, or send controls without
  a separate action-specific approval.
- Do not print passwords, full tokens, session cookies, full account numbers, or
  raw private payloads.

When checking whether a form is filled, report booleans or lengths rather than
values.

---

## When To Escalate

Agent Browser is enough when the task is "what is visible on this page?" or
"click through this flow." Continue using it for recurring interactive work
when the site's UI or personalization is the required source of truth.

Escalate to `tool_connections/shared_utils/traffic_sniffer.py` when you need to
write a connection file with verified API snippets:

- Which endpoint returns the account list?
- Which header/cookie authenticates the call?
- What payload shape does search, list, get, or submit use?
- Can the call be replayed without a browser?

The durable recipe should record endpoints and auth patterns, not Agent Browser
refs such as `@e6`, because refs are page-instance specific.

Escalate to a custom Playwright/CDP script only for stable repetitive extraction,
batch work, scheduled monitoring, or a UI limitation Agent Browser cannot
handle. The existence of a browser-only workflow is not by itself a reason to
write custom code.

---

## Output To Capture

For UI reconnaissance, write down:

- URL pattern and final redirected base URL.
- Page or flow name.
- Stable labels and roles for key controls.
- Read-only facts visible on the page, redacted when sensitive.
- Whether no API-like endpoint was found and DOM driving is required.

For connection work, transfer only durable findings into
`connection-{auth-method}.md`: endpoint paths, auth method, payload shapes,
read/write approval boundaries, and known limitations.

## This Is Working If

- Connections use supported APIs where available.
- Browser-only tools default to Agent Browser instead of one-off Playwright
  code.
- Agents reuse existing `~/.browser_automation/*_cdp_profile` sessions before
  creating empty profiles.
- Feed/list reads return compact structured candidates, not page dumps.
- Custom browser scripts exist only for demonstrated repetitive or deterministic
  needs.
- Approved writes are verified with a direct result URL.

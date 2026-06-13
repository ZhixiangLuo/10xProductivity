# Agent Browser — Agent-Friendly Browser Automation

Agent Browser is a browser automation CLI built for coding agents. Use it when
you need a low-token, interactive view of a web page: open a site, inspect the
visible UI, click buttons, fill forms, read account pages, or confirm what a
human-visible flow does.

It complements the 10x connection workflow:

- Use Agent Browser for interactive reconnaissance and read-only page checks.
- Use `tool_connections/shared_utils/traffic_sniffer.py` when you need durable
  reusable API endpoints, headers, and payload shapes.
- Use Playwright scripts when the result must become repeatable automation.

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

---

## Session Persistence

For a tool-specific browser session, use a named session:

```bash
agent-browser --session my-tool open --headed "https://app.example.com"
agent-browser --session my-tool snapshot -i
```

For a saved browser profile, pass a generic profile path. Do not document
machine-specific ports or paths in reusable recipes.

```bash
agent-browser --profile "$HOME/.browser_automation/my_tool_profile" \
  open --headed "https://app.example.com"
```

If a browser profile is already running with Chrome DevTools Protocol enabled,
you can attach to its port as an advanced local workaround:

```bash
agent-browser --cdp <port> snapshot -i
```

Treat CDP ports as runtime discovery, never as recipe content. If you need to
find one locally, probe common ports or inspect the launcher that started the
browser, then keep the number in the current session only.

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

## When To Escalate To Traffic Sniffing

Agent Browser is enough when the task is "what is visible on this page?" or
"click through this flow once." Escalate to
`tool_connections/shared_utils/traffic_sniffer.py` when you need to write a
connection file with verified snippets:

- Which endpoint returns the account list?
- Which header/cookie authenticates the call?
- What payload shape does search, list, get, or submit use?
- Can the call be replayed without a browser?

The durable recipe should record endpoints and auth patterns, not Agent Browser
refs such as `@e6`, because refs are page-instance specific.

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

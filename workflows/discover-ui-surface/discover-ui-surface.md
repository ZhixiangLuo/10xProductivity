---
name: discover-ui-surface
description: Walk through a UI flow once manually and capture a durable interaction map — which DOM elements to click, which network requests they trigger, and what field shapes they expose. Produces a reusable selector+endpoint reference for automation scripts. Use before writing any Playwright block for a JS-heavy SPA (LinkedIn, Figma, Notion, etc.) where selectors and API paths are not obvious from source inspection alone. Three modes: Chrome DevTools Recorder (fastest), Playwright observer (richest), Playwright codegen+trace (most structured).
---

# Discover UI Surface

## Purpose

Modern SPAs (LinkedIn, Figma, Slack, Notion) split their state across **two surfaces**:

- **Network surface** — XHR/fetch responses that carry structured IDs, URNs, and payloads the DOM never renders
- **DOM surface** — human-visible elements with labels, buttons, and form fields

Writing an automation block without first observing both surfaces leads to:
- Selectors that break on the next deploy (generated class names)
- Missing IDs that only appear in network responses (LinkedIn URNs, Figma node IDs)
- Guessing which button fires which API call

**This skill walks you through a UI flow once — while a recorder watches — and produces a durable interaction map** that your automation block can replay confidently.

---

## When to use

- Before writing any Playwright block for a JS-heavy SPA
- A block is stuck: wrong DOM, lazy-load, unexplained 400/404 — you don't know which element triggers the right call
- You need to know what fields a form exposes before scripting form-fill
- You want to verify that a button click fires a specific internal API (not navigate or trigger something else)
- The site has changed and existing selectors are broken — re-run to find the new ones

**Not for:** sites with stable public APIs you already know (use the API directly). Not a replacement for `add-new-connection` when a tool has documented REST endpoints.

---

## Three modes — pick one per session

| Mode | Best for | Output |
|------|----------|--------|
| **[A] Chrome DevTools Recorder](#mode-a-chrome-devtools-recorder)** | Quick discovery, any site, no setup | Playwright script + manual network annotation |
| **[B] Playwright observer](#mode-b-playwright-observer-script)** | Richest correlation: click → network call mapped automatically | Structured JSON log + selector map |
| **[C] Playwright codegen + trace](#mode-c-playwright-codegen--trace)** | Full timeline review after the fact | Trace zip with correlated action/network timeline |

Start with **Mode A** if you've never explored the site. Use **Mode B** when you need the click↔network correlation automated. Use **Mode C** when you want to review the full timeline offline.

---

## Mode A — Chrome DevTools Recorder

**Time to set up:** zero. Built into Chrome/Edge.

See [`chrome-recorder.md`](chrome-recorder.md) for the full step-by-step. Quick summary:

1. Open Chrome → DevTools (`F12`) → **Recorder** panel
2. Click **"Start new recording"**, name it (e.g. `linkedin-send-invite`)
3. Perform your flow manually in the page
4. Click **"Stop"** — the panel shows every interaction with multiple selector strategies per step
5. **Export as Playwright script** — gives you code with ARIA/text/CSS fallback selectors
6. While reviewing the recording, open the **Network** tab → filter by `Fetch/XHR` → note which requests fired during each step
7. Annotate the exported script with `# → POST /voyager/api/...` comments

**Selector durability check** (do before copying a selector into a block):

Prefer selectors in this order (most → least durable):
1. `aria-label`, `role`, `data-*` attributes
2. Visible text content (`text="Send"`, `:has-text("Connect")`)
3. `id` attributes (if not generated)
4. CSS class only if clearly semantic (e.g. `msg-form__send-button`, not `ember-view-123`)

If the Recorder only gives you a generated class name for a critical button, inspect the element and look for ARIA attributes or a `data-control-name` (LinkedIn's pattern).

---

## Mode B — Playwright observer script

**Time to set up:** ~30s. Requires Playwright installed.

Run `assets/observe_session.py` — it opens a headed browser, attaches listeners to every network request/response, and lets you drive the page manually. Every XHR call is logged with timing. At the end it dumps a structured JSON and a human-readable summary.

```bash
# Install once
pip install playwright && playwright install chromium

# Run observer for LinkedIn (loads your saved session if available)
python3 workflows/discover-ui-surface/assets/observe_session.py \
  --url "https://www.linkedin.com/feed/" \
  --filter-domain "linkedin.com" \
  --out session_trace.json

# After you finish your manual flow, press Enter in the terminal (or Ctrl+C)
# → session_trace.json + session_trace_summary.md written

# If stdin is not a TTY (e.g. some agent runners), you must pass a wall-clock duration:
python3 workflows/discover-ui-surface/assets/observe_session.py \
  --url "https://www.linkedin.com/feed/" \
  --filter-domain "linkedin.com" \
  --duration 600 \
  --out session_trace.json
```

**What you get:**

`session_trace.json`:
```json
{
  "interactions": [
    {
      "t_ms": 1234,
      "type": "request",
      "method": "POST",
      "url": "https://www.linkedin.com/voyager/api/relationships/invitations",
      "payload_keys": ["invitee", "message", "trackingId"],
      "payload_sample": {"invitee": {"com.linkedin.voyager...": {"profileId": "ACoAA..."}}}
    }
  ]
}
```

`session_trace_summary.md` — human-readable grouped by action:
```
[t=1.2s] POST /voyager/api/relationships/invitations
  payload keys: invitee, message, trackingId
  response: 201 Created

[t=2.1s] GET /voyager/api/identity/profiles/ACoAA.../networkinfo
  response: 200 {"distance": {"value": "DISTANCE_2"}}
```

**Workflow:**

1. Run the script — browser opens
2. **Simultaneously start a Chrome Recorder recording** in the same Playwright Chromium window (open DevTools → Recorder → Start). This gives you DOM selectors and network calls from the exact same session. See [`chrome-recorder.md`](chrome-recorder.md) → "Running Recorder inside the observer window".
3. Perform your flow (click Connect, fill message, send)
4. Stop Recorder, press Enter in the terminal or close the browser
5. Read `session_trace_summary.md` — each timed block maps to what you did
6. Merge: network map from `session_trace_summary.md` + DOM selectors from Recorder export → write into connection file
7. **Diff against existing automation scripts** (see "After capture: close the loop" below)

**Session reuse (LinkedIn / sites with login):**

**10xProductivity LinkedIn (recommended)** — the `linkedin_automation` blocks use a persistent Chromium profile at `~/.browser_automation/linkedin_profile` (same as `search_posts.py`). Reuse it so you are already logged in:

```bash
python3 workflows/discover-ui-surface/assets/observe_session.py \
  --url "https://www.linkedin.com/search/results/content/?keywords=AI%20agents" \
  --linkedin-10x-profile \
  --filter-domain linkedin.com \
  --exclude-pattern "lms\\.analytics|doubleclick|googlesyndication|googleads|optimizely|hotjar|pendo" \
  --out session_trace.json \
  --duration 600
```

Do **not** combine `--linkedin-10x-profile` (or `--persistent-profile`) with `--load-state` — pick one session mechanism. Close other Playwright scripts that use the same profile (e.g. `search_posts.py`) before recording, or Chromium may fail to open the user-data directory.

The observer attaches listeners on the **browser context** (not only the first tab), so traffic from **new tabs** in the same Chromium window is included.

**Timestamps:** the main thread **must not** `sleep` while recording — Playwright’s sync driver would not dispatch network callbacks, and every `t_ms` would appear in one burst at the end. The script uses **`page.wait_for_timeout()`** in a loop instead, and `t_ms` is **monotonic milliseconds since listeners were attached** (`t_ms_basis` in the JSON). Optional **`--heartbeat SEC`** prints progress; **`--autosave-every SEC`** writes `*.autosave.json` during long runs.

**Timeline sanity check:** after every capture, confirm `max(t_ms) - min(t_ms)` spans at least 50% of `--duration`. The script prints a `⚠ WARNING` automatically when it does not. If you see it, discard the trace and re-capture — the compressed timeline is misleading.

**Generic `storage_state` JSON** — if the site is not LinkedIn/10x, generate once with:

```bash
python3 workflows/discover-ui-surface/assets/observe_session.py \
  --url "https://www.linkedin.com" \
  --save-state linkedin_auth.json \
  --quit-after-load
# → log in manually in the browser → closes → saves state
```

---

## Mode C — Playwright codegen + trace

**Time to set up:** ~10s.

```bash
# Record interactions + full trace in one command
playwright codegen \
  --save-trace trace.zip \
  --load-storage linkedin_auth.json \
  https://www.linkedin.com/feed/

# Review the trace (correlated action + network timeline)
playwright show-trace trace.zip
```

In the trace viewer:
- **Left panel**: your recorded actions (click, fill, etc.) with the selector used
- **Right panel → Network tab**: every request that fired, with timing relative to each action
- Click any action → the network tab filters to requests that fired within ±500ms

**Use this mode when** you want to review the session at your own pace after recording, or share the trace file with someone else (e.g. paste into connection doc review).

---

## Output: the interaction map

After any mode, write the findings into the **connection file** for the site (e.g. `tool_connections/linkedin.md` or your workflow's `connection.md`). Format:

```markdown
## UI interaction map — [flow name] (recorded [date])

### Flow: Send connection invite

| Step | Element | Stable selector | Network call triggered |
|------|---------|-----------------|----------------------|
| 1 | "Connect" button on profile card | `button[aria-label*="Invite"][aria-label*="to connect"]` | `POST /voyager/api/relationships/invitations` |
| 2 | Message textarea | `textarea[name="message"]` or `div[aria-label="Add a note"]` | none (local state) |
| 3 | "Send" button | `button[aria-label="Send now"]` | `POST /voyager/api/relationships/invitations` (same, with message body) |

### Key payload shapes

**POST /voyager/api/relationships/invitations**
```json
{
  "invitee": {
    "com.linkedin.voyager.growth.invitation.InviteeProfile": {
      "profileId": "<URN — from network response, NOT DOM>"
    }
  },
  "message": "<optional note text>"
}
```

### Selector durability notes

- `aria-label*="Invite"` matches reliably; the exact label text varies by connection distance ("Invite Alice to connect" vs "Connect")
- Profile URN (`ACoAA...`) only appears in `/identity/profiles/{id}` responses and card feed responses — never in DOM text
- The "Connect" button is absent if already connected; check `networkinfo` response `distance.value` first
```

---

## Selector hardening checklist

After capturing selectors, verify each one is durable:

- [ ] Does it use ARIA (`role`, `aria-label`, `aria-*`)? → most durable
- [ ] Does it use visible text (`:has-text()`, `text=`)? → durable if text is product-defined, not user-generated
- [ ] Does it use a `data-*` attribute (e.g. `data-control-name`, `data-testid`)? → durable if not randomized
- [ ] Does it rely only on CSS class names? → fragile; look for a more stable attribute on the same element
- [ ] Does it embed a session-specific ID (profile URN, entity ID)? → must be fetched dynamically from the network surface, not hardcoded

---

## When NOT to record

Run a recording when you don't know the selector or endpoint. Don't run one when the problem is in your code logic, not in the surface. Use this checklist first:

| Symptom | Likely cause | What to do |
|---------|-------------|------------|
| Selector not found / wrong element clicked | Unknown or changed selector | **Record** — use Mode A or B |
| Click fires but nothing happens | Wrong element, or DOM toggle needing extra wait | Inspect element first; record only if selector is confirmed correct |
| Text is empty after extraction | URN↔text pairing logic wrong | **Fix the code** — don't record; the text is already in the DOM |
| Selector worked before but broke | UI deploy changed class names | **Re-record** — check `data-testid` / ARIA as stable alternatives |
| Unexpected network error | Wrong endpoint or payload | Capture the working request manually in DevTools, compare to script |
| You can see the data on screen | Extraction logic misses it | Read the DOM directly in DevTools console first; fix extraction |

**Rule:** if you can see the data on screen and the selector is known, the problem is in extraction or pairing logic — fix the code, don't record.

---

## Network-ID + DOM-text split (SDUI / RSC apps)

Modern SPAs built on server-driven UI (SDUI) or React Server Components (RSC) commonly split state across two surfaces that cannot be joined via the DOM alone:

- **Entity IDs / URNs** — only in network responses or the initial server-rendered HTML; never in DOM anchor tags on search/feed pages.
- **Human-visible content** — only in DOM elements; not in API responses.

**The danger:** positional pairing (IDs in network order ↔ text boxes in DOM order) silently produces wrong results whenever the ordering diverges — which happens whenever ads, promoted cards, collapsed items, or lazy-loaded content shift the render sequence. It succeeds without errors but returns wrong data, making it the most dangerous extraction failure mode.

**The method:** find a shared key that appears in both surfaces, then join by key.

---

### Step 0 — web search before DOM archaeology

**The LLM's training data is frozen.** Platform DOM structures, API shapes, and rate-limit policies change constantly. Before spending time inspecting a surface you don't fully understand, search for current information:

```
"[platform] [action] playwright automation [current year]"
"[platform] DOM structure changed [year]"
"[platform] API rate limit [entity type]"
"[platform] [selector or attribute] scraping"
```

Web search fills gaps that training data cannot:
- Current DOM structure and which selectors are still valid
- Recent API changes, deprecations, or new undocumented endpoints
- Known platform-specific quirks (ghost elements, SDUI rendering patterns, bot detection triggers)
- Community-discovered techniques (shared keys, header requirements, session patterns)
- Whether the problem you're hitting is a known platform behaviour, not a bug in your code

**When to search — not just when stuck:**
- Before starting on an unfamiliar platform or endpoint
- When a selector or API that worked before now fails (platform may have changed)
- When behavior seems platform-specific and non-obvious (unusual rate limits, auth flows, render patterns)
- When you are about to guess at something that someone else has likely already figured out

**Do this before opening DevTools.** It takes two minutes and frequently surfaces the answer or the right starting point.

---

### Step 1 — find the shared key in the DOM

Walk up from the content element (text box, card, etc.) and log every ancestor's tag and all attributes:

```python
info = page.evaluate("""() => {
    const el = document.querySelector('YOUR_CONTENT_SELECTOR');
    if (!el) return [{error: 'NOT FOUND'}];
    let node = el;
    const path = [];
    for (let i = 0; i < 12; i++) {
        if (!node) break;
        const attrs = {};
        for (const a of node.attributes) attrs[a.name] = a.value.slice(0, 200);
        path.push({ level: i, tag: node.tagName, attrs });
        node = node.parentElement;
    }
    return path;
}""")
```

**What to look for:** any attribute that could serve as a stable shared key — `data-id`, `data-entity-urn`, `data-urn`, `componentkey`, `id`, or any structured attribute value. If you find one on a card-root ancestor, that is your join key.

**If nothing appears in the DOM:** the key may live only in the network payload. Proceed to Step 2.

> **LinkedIn example (2026-04):** The `[role="listitem"]` card root has `componentkey="expanded{CK}FeedType_FLAGSHIP_SEARCH"`. No URN link exists anywhere in the DOM subtree — the URN lives only in the server-rendered HTML alongside this key.

---

### Step 2 — find the shared key in the network payload

If the DOM yields a candidate key, search the raw network responses — both the **initial HTML page** and **XHR/JSON responses** — for that key appearing near entity IDs.

```python
def on_response(resp):
    if resp.status != 200:
        return
    body = resp.text()
    # Search for your DOM key near your entity ID pattern
    import re
    for m in re.finditer(r'YOUR_ENTITY_ID_PATTERN', body):
        window = body[m.start():m.start() + 3000]
        if 'YOUR_DOM_KEY_PATTERN' in window:
            print(f"ID and key co-located at {resp.url[:60]}")
```

**Key insight:** on SDUI/RSC apps, the join key often appears in the **initial HTML page response**, not in subsequent XHR calls. The client-side framework injects `data-*` / `componentkey` attributes from state embedded in the HTML, not from later API responses. Always check `content-type: text/html` responses, not just JSON.

> **LinkedIn example (2026-04):** The HTML embeds state keys of the form `reactionState-urn:li:activity:NNN` (the URN) and `commentBoxMode-{b64}-{CK}FeedType_FLAGSHIP_SEARCH` (the DOM `componentkey`) within ~5 KB of each other per card. Matching nearest-preceding URN to each CK gives a reliable `key → entity_id` map with no positional assumptions.

---

### Step 3 — join by key, not by position

Once you have a `key → entity_id` map (from the network payload) and a `key → content` map (from the DOM), join them:

```python
# key_to_id:      {'key_abc': 'entity-123', ...}   ← from network/HTML
# key_to_content: {'key_abc': {'text': '...', ...}} ← from DOM

for key, content in key_to_content.items():
    entity_id = key_to_id.get(key)
    if entity_id and content.get('text'):
        results[entity_id] = content
```

**Why this works where positional pairing fails:** ghost elements (ads, promoted cards) either have no entry in the network payload (so `key_to_id.get(key)` returns None) or have their own distinct key that doesn't match real content. They are naturally filtered out without any special-casing.

**Verification — always do this:**
1. Log the size of `key_to_id` after page load — confirm it has entries.
2. Log the size of `key_to_content` after DOM harvest — confirm counts are reasonable.
3. Spot-check: open the first matched entity's permalink and confirm the extracted text actually matches. This catches any remaining pairing errors before they reach the user.

**Positional pairing as last resort only:** use only when no shared key exists in any surface. Log a clear warning, verify a sample by permalink, and flag results as unverified.

---

Document the shared key you found (and where it lives) in the connection file for the platform. Other blocks on the same platform will face the same split and can reuse the join strategy.

---

## When captures reveal no usable API

Sometimes a click updates local React/Vue state and fires **no** network call. In that case:

1. The action is purely client-side — you must drive the DOM (click the element)
2. The downstream network call fires later (e.g. on "Submit" or "Send") — keep watching
3. Check `localStorage`/`sessionStorage` via `page.evaluate(() => JSON.stringify(localStorage))` after the click — state may be staged there before the final POST

---

## After capture: close the loop

The capture is only useful if you diff it against what automation scripts already assume. Do this **before moving on**, in the same session:

1. **Check the timeline sanity warning** — if `⚠ WARNING` printed, re-capture
2. **Open the interaction map** (`session_trace_summary.md`) and each relevant automation script side by side
3. For each action the script performs, ask:
   - Does the script expand the right UI surface before looking for the element? (e.g. thread reveal before composer)
   - Does the script use the confirmed `sduiid` or network signal as confirmation, or just DOM text?
   - Does the submit button selector match the one the Recorder found, or is it a page-wide guess?
4. **Fix any mismatch** before writing new scripts — a 10-minute diff here prevents debugging sessions later

**Diff checklist per action:**

| What to check | Observed signal | Script assumption | Match? |
|---------------|----------------|-------------------|--------|
| Trigger that paints the element | e.g. `fetchFeedUpdateActionPrompt` fires after scroll | `_nudge_main_composer_visible` before reveal | — |
| Network confirmation of success | e.g. `createComment` RSC response | DOM text search | — |
| Submit button selector | Recorder: `button.comments-comment-box__submit-button` | `button.artdeco-button--primary` (page-wide) | — |

---

## Anti-patterns

- **Writing selectors before observing** — always run a capture first; often a cleaner API endpoint exists one network layer up
- **Skipping the diff step** — capturing without comparing against existing scripts means the observer's value is never realised
- **Hardcoding URNs or entity IDs from one session** — they are session/user-specific; always fetch them dynamically
- **Using only one surface** — if network responses look empty but DOM has data (or vice versa), combine both channels
- **Keeping the full raw HAR in the workflow folder** — too noisy; extract the relevant endpoint+payload shape into the connection file and discard the rest
- **Treating codegen selectors as final** — codegen uses the first viable selector it finds; always apply the durability checklist before committing a selector to a block
- **Recording when the problem is code logic** — if text is in the DOM and the selector is known, fix the extraction/pairing code; recording reveals surfaces, not bugs in your own code
- **Assuming entity ID anchors exist in the DOM on SDUI/RSC apps** — on many modern platforms, IDs only appear in the server-rendered HTML or RSC network responses, not as DOM anchor tags; walk ancestors to find a shared key, then look for it in the network payload
- **Walking DOM from content element to entity ID on SDUI apps** — the upward walk returns null when no ID anchor exists in the card subtree; use the keyed join (shared DOM attribute ↔ network/HTML co-location) instead
- **Using positional pairing as the primary strategy** — it silently corrupts results whenever ads, promoted content, or collapsed cards shift the render order relative to the network response order; treat it as a last resort with a warning log and permalink verification, never as the default
- **Skipping the web search step** — others have likely hit the same platform's extraction problem; a targeted search often reveals the correct shared key in minutes, before any DOM archaeology is needed
- **Only searching XHR/JSON responses for the shared key** — on SDUI/RSC apps, shared keys (like `componentkey`) are often injected by the client-side runtime from state embedded in the initial HTML page response, not from subsequent XHR calls; always check `text/html` responses too

---

## Outputs

- **Connection file section**: interaction map table + payload shapes + selector durability notes
- **`session_trace.json`** (Mode B): raw structured log (keep in scratch/docs, not the workflow folder)
- **`session_trace_summary.md`** (Mode B): human-readable summary (link from connection file)
- **`trace.zip`** (Mode C): Playwright trace for offline review (link from connection file, do not commit large zips)

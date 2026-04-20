# Chrome DevTools Recorder — Step-by-step Guide

Chrome's built-in Recorder panel generates Playwright scripts with multiple selector strategies per step. No install required beyond Chrome or Edge.

---

## Running Recorder inside the observer window

For the richest capture, run **both tools in the same session**:

1. Start `observe_session.py` — it opens a headed Chromium window
2. In that same Chromium window, open DevTools (`F12`) → **Recorder** panel
3. Start a new recording **before** you begin your flow
4. Perform the flow once — the observer captures network, the Recorder captures DOM selectors
5. Stop the Recorder; press Enter in the terminal to close the observer
6. Export the Recorder as a Playwright script → merge with `session_trace_summary.md`

This gives you **network map + DOM selectors from the exact same session**, so every selector is verified against the actual network signals you'll use for confirmation.

> **Note:** Chrome DevTools Recorder is built into Chrome/Chromium. If `observe_session.py` uses a Chromium build that lacks the Recorder panel UI, use the **Network** tab instead to manually note XHR calls as you record the flow.

---

## Setup (standalone use)

1. Open Chrome (not a Chromium build — the Recorder panel is Chrome-only)
2. Navigate to the site and **log in normally** (your real session, real cookies)
3. Open DevTools: `F12` or `Cmd+Option+I`
4. Find the **Recorder** panel:
   - If not visible: click the `»` overflow button in the DevTools tab bar → **Recorder**
   - Or: `Cmd+Shift+P` → type "Show Recorder"

---

## Recording a flow

### Step 1 — Open the Network tab alongside

Before starting the recording, open the **Network tab** in a second DevTools panel (drag it to a side panel or use a second window). Filter by **Fetch/XHR**. This gives you the network correlation while you interact.

### Step 2 — Start recording

1. In the Recorder panel, click **"+"** (Create new recording)
2. Name it descriptively: e.g. `linkedin-send-invite`, `figma-export-png`
3. Click **"Start recording"** — a red dot appears in the browser tab

### Step 3 — Perform your flow slowly

Move deliberately:
- **One action at a time** — pause 1–2 seconds between each click/fill
- **Hover before clicking** — the Recorder captures hover states that matter for dropdowns and tooltips
- **Fill fields one at a time** — tab between fields rather than clicking each one (produces cleaner selector steps)
- **Don't navigate away mid-flow** — if the flow ends on the same page, wait for the response to load before stopping

Watch the Network tab as you go — note which XHR calls fire on each action. You don't need to copy them yet; you'll cross-reference after.

### Step 4 — Stop recording

Click **"Stop"** in the Recorder panel. You'll see a step list like:

```
1. navigate  https://www.linkedin.com/in/alice/
2. click     aria/Connect
3. click     aria/Add a note
4. fill      aria/Add a note  →  "Hi Alice, ..."
5. click     aria/Send now
```

### Step 5 — Review selector strategies

Click any step → the right panel shows **multiple selector strategies**:

```
CSS selector:    .artdeco-button[aria-label="Invite Alice Smith to connect"]
ARIA selector:   aria/Invite Alice Smith to connect
Pierce selector: pierce/.msg-form__send-button
Text selector:   text/Send now
```

**Pick the most durable one** using this priority:
1. ARIA selector (role + label) — survives UI refactors
2. Text selector — good for buttons with product-defined labels
3. `data-*` attribute CSS — if present (e.g. `[data-control-name="invite_single"]`)
4. Generic CSS — only if nothing else works

**LinkedIn-specific:** look for `aria-label` and `data-control-name`. LinkedIn attaches `data-control-name` to most interactive elements — these are stable across deploys.

### Step 6 — Export as Playwright script

Click **Export** → **Playwright** → save as `{flow_name}_raw.py`.

The exported file looks like:

```python
from playwright.sync_api import sync_playwright, expect

def run(playwright):
    browser = playwright.chromium.launch(headless=False)
    page = browser.new_page()
    page.goto("https://www.linkedin.com/in/alice/")
    page.get_by_role("button", name="Connect").click()
    page.get_by_label("Add a note").click()
    page.get_by_label("Add a note").fill("Hi Alice, ...")
    page.get_by_role("button", name="Send now").click()
    browser.close()

with sync_playwright() as playwright:
    run(playwright)
```

---

## Annotating the export with network calls

Open your Network tab recording alongside the exported script. For each click that fired an XHR, add a comment:

```python
page.get_by_role("button", name="Connect").click()
# → POST /voyager/api/relationships/invitations
#   payload: {"invitee": {"com.linkedin.voyager...": {"profileId": "..."}}, "message": ""}
#   response: 201 Created  |  body: {"value": {"invitationId": "...", ...}}

page.get_by_label("Add a note").fill("Hi Alice, ...")
# → no network call (local state only)

page.get_by_role("button", name="Send now").click()
# → POST /voyager/api/relationships/invitations
#   payload: same as above, message field now populated
#   response: 201 Created
```

**To get payload details from the Network tab:**
- Click the XHR request → **Payload** tab → view request body
- Click → **Response** tab → copy the JSON shape (truncate long arrays)
- Right-click the request → **Copy as cURL** — useful if you want to replay it with curl

---

## Common issues

### "Connect" button not captured — only a container was clicked

The Recorder sometimes captures a click on a parent `<div>` instead of the actual `<button>`. Fix:

- Click **edit** on that step in the Recorder
- Use the **Pick element** tool (cursor icon) → re-click specifically on the button
- Or manually edit the selector to `button[aria-label*="connect"]`

### Selector uses a session-specific name ("Invite Alice Smith to connect")

Replace the specific name with a wildcard:

```python
# Before (fragile — only matches Alice's profile)
page.get_by_role("button", name="Invite Alice Smith to connect").click()

# After (matches any profile's Connect button)
page.locator("button[aria-label*='to connect']").click()
# or
page.get_by_role("button", name=re.compile(r"Invite .+ to connect")).click()
```

### Steps are missing (SPA navigation not captured)

The Recorder doesn't always capture route changes in SPAs. Add them manually:

```python
# After a click that navigates to a new route
page.wait_for_url("**/in/*/", timeout=5000)
# or
page.wait_for_load_state("networkidle")
```

### Dropdown / modal appeared but steps inside it are missing

Re-record the flow, this time hovering over the trigger for ~1 second before clicking to open the dropdown. The Recorder sometimes misses rapid click → child-click sequences. Alternatively, add the child click manually:

```python
page.get_by_role("button", name="More options").click()
page.wait_for_selector("[role='menu']")
page.get_by_role("menuitem", name="Remove connection").click()
```

---

## After recording — what to save

| Artifact | Where |
|----------|-------|
| Annotated `{flow}_raw.py` | Scratch / `docs/` — not in the workflow `blocks/` folder |
| Endpoint + payload shape | Connection file → UI interaction map section |
| Stable selectors (post-hardening) | Connection file → UI interaction map table |
| Raw network recording (HAR) | Optional — export via Network tab → ⬇ icon → Save as HAR; run through `har_to_map.py` to filter noise |

**Do not commit** the raw `_raw.py` export or HAR file to the workflow folder. Extract the selector+endpoint map into the connection file and discard the rest.

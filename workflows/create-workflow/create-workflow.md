---
name: create-workflow
description: Design and build automation workflows using building blocks — clarify outcomes, decompose by dependencies, reuse prior art, verify each block before chaining, and research when stuck. Covers generic divide-and-conquer (problem framing, observable surfaces, investigation vs shipping, CLI contracts) plus human-like pacing for social and communication platforms. Use when automating multi-step processes across tools or platforms.
---

# Create Workflow — Building-Blocks Methodology

## Purpose

Use this skill when you need to design and implement an automation workflow. The methodology separates **building blocks** (atomic, reusable actions) from **workflows** (goal-oriented chains of blocks). That separation keeps each piece testable alone and composable across different goals.

**The workflow is for the agent, not the human.** The workflow `.md` is an instruction set the coding agent reads and follows. The agent calls blocks as individual tool calls, holds state between calls, makes decisions at each step, and asks the human only at named approval gates. Humans do not run scripts manually — they say "do X" and the agent executes the workflow end-to-end.

---

## When to use

- User wants to automate a multi-step process (e.g. recurring sync, approvals, cross-system updates)
- User describes an outcome that requires several distinct actions
- User wants to extend existing automation with new capabilities
- User asks to "create a workflow", "automate X", or "build a script for Y"
- User is automating **social feeds, DMs, comments, invites, or posts** — apply [Human-like behavior](#human-like-behavior-social--communication-platforms) from block design through workflow assembly (not as an afterthought)

---

## How to think about the problem: break down → divide → build → test

This is the **general** spine of the skill — applicable beyond any single product or stack.

### Break down

1. **Outcome first** — State what must be true when finished (artifacts, state changes, notifications), not the first tool you thought of.
2. **Workflows vs blocks** — A **workflow** is one coherent goal (possibly with multiple entry points). A **block** is one **verb + noun** with a narrow contract (inputs → outputs, minimal side effects).
3. **Write the contract** — For each block, list what **downstream steps need** (IDs, URLs, records, booleans). If you cannot name that, the block is still too large — split discovery from mutation, or read from write.

### Divide and conquer

1. **Dependency order** — Build what **produces** data before what **consumes** it. Root blocks discover, fetch, or authenticate; leaves act, notify, or persist.
2. **Vertical slices** — Prove the riskiest unknown in isolation first (auth, pagination, scroll container, ID mapping, rate limit). A thin slice that runs end-to-end on one row beats a wide half-finished layer.
3. **Exploration vs delivery** — Spikes, packet capture, huge dumps, and selector experiments live in **scratch space or shared tooling docs**; the workflow folder keeps **small, reviewed, runnable** blocks. Link findings into connection or workflow docs instead of copying noise into block files.

### Build

1. **One block at a time** — Clear entrypoint (CLI flags or function args), structured return values (dicts, dataclasses, JSON-serializable shapes), not only `print`.
2. **Smallest real integration** — Prefer read-only or low-quota calls, feature flags, or `--max 1` style limits before full writes or bulk loops.
3. **Shared cross-cutting concerns** — Auth, HTTP client, pacing, and logging belong in **reused helpers** or config, not copy-pasted across every block.

### Test

1. **Block-level** — Run the block alone against the real system (or a faithful stub). Assert **shape** and a few **edges**: empty results, expired credentials, "not found".
2. **Pairwise** — Chain **two** adjacent blocks before the whole graph; catches mismatched field names and wrong assumptions about ordering.
3. **Workflow-level** — Full run with **tight caps** (small batches, dry-run) before production volumes.
4. **When something fails** — **Pin the layer** (auth, navigation, extraction, timing, payload shape). Change one hypothesis at a time; if two or three attempts fail, use [Step 6](#step-6--when-stuck-search-the-web-for-clues) instead of guessing deeper.

---

## Human-like behavior (social & communication platforms)

Platforms infer automation from **timing**, **volume**, **request shape**, and **navigation patterns**. Treat “mimic a careful human” as a workflow requirement alongside correctness.

**Principles (design blocks and chains with these in mind):**

1. **Variable delays, not metronomes** — Never use identical `sleep(2)` between every action. Use randomized jitter within a sensible band (e.g. 1.5–4s between lightweight actions, longer before messages or posts). Back off on errors or ambiguous responses instead of tight retry loops.
2. **Caps and cooldowns** — Prefer daily/session limits over “do everything now.” Spread multi-target work across runs or days; avoid cold-start bursts after long idle periods.
3. **Session realism** — Reuse persistent browser profiles, stable cookies, and consistent client hints where the platform expects a logged-in browser. Avoid patterns that look like anonymous scrapers (new session per request, missing headers, impossible request order).
4. **Order and surface area** — In a browser, follow plausible paths rather than only deep-link marathons. For APIs, mirror sequence and headers a real client sends per verified captures — document them in connection files.
5. **Human-in-the-loop for high-signal actions** — Outbound messages, public posts, and invitations should default to draft + approval; automation prepares, humans commit tone and context.
6. **Compliance and risk** — Stay within the platform’s terms and acceptable use. The goal is **sustainable automation** (fewer false positives, less account friction), not evading abuse controls.

**Where to apply it in this skill:**

- **Decompose** — If a block only fires rapid repeated calls, split or throttle at the workflow layer; consider a shared delay/pacing helper for all blocks in a folder.
- **Verify** — Test under realistic pacing, not only “as fast as possible”; confirm after a short pause where that matters for the domain.
- **Assemble** — The workflow script owns pacing between blocks, jitter, limits, and backoff. Document recommended limits in the workflow `.md`.

---

## Observable surfaces (browser and hybrid UIs)

Many applications split **identifiers and structured data** (responses, client stores) from **what the user sees** (DOM, shadow roots, canvas). Blocks that only read one surface often look “empty” or stuck.

1. **Plan multiple observation channels** — Combine what is reliable for **IDs** with what is reliable for **human-visible fields** (e.g. response listeners plus DOM evaluation). Encode fallbacks when a row cannot be keyed (e.g. order-based pairing) and **document limitations**.
2. **Bound optional waits** — If you wait on a signal that **may never appear** on this app version, use a **short** timeout and **log what was waited for** so latency is not misread as unrelated work (e.g. “scroll” vs “selector timeout”).
3. **Prefer stable selectors** — Test IDs, roles, and accessibility hooks survive refactors better than generated class names.
4. **CLI contract** — Long-lived sessions often emit summaries **only after teardown** unless you add explicit progress hooks. Flush final output. If you offer `--json`, keep **stdout** machine-only; put human snippets on **stderr** or a file, and cap length.
5. **Investigation vs shipping** — Keep one-off captures and large artifacts out of the minimal workflow package; cross-link from docs.

Fold these into **block implementation and verification** and into the **workflow `.md`** (how to run, what appears when).

---

## Methodology

### Step 1 — Clarify the goals, not the steps

Start by understanding what the user wants to **achieve**, not how to do it. Ask:

- What is the end result?
- What are the different starting points?
- Is approval/review needed before actions are taken, or fully automated?

Each distinct goal becomes a **workflow**. A goal that can start from multiple places may become multiple workflows sharing the same blocks.

---

### Step 1b — Choose your automation engine

Before decomposing, decide **how** each block will execute. This choice affects implementation cost, fragility, and maintenance burden. Make it explicitly — not as an afterthought when code is already written.

**Decision tree (apply per block, not per workflow):**

1. **Does a stable public API exist?** → Use it. Fastest, cheapest, least brittle.
2. **Does an internal API exist?** (capture via browser DevTools Network tab or a proxy) → Use that. Still scriptable; avoids DOM fragility.
3. **Is the UI layout stable and selector-friendly?** → Use a browser automation script (Playwright/Selenium). Fast, deterministic, zero API cost.
4. **Is the UI frequently changing, structurally unpredictable, or must work across many different sites?** → Consider an LLM agent at this step only.

**Script vs LLM — when each wins:**

| Factor | Traditional script | LLM agent |
|---|---|---|
| Site stability | Stable selectors or API | Frequently changing UI |
| Speed | Fast | Significantly slower (model roundtrip per step) |
| Cost | Infrastructure only | API token cost per run |
| Reliability | Deterministic | Probabilistic; can misinterpret a page |
| Maintenance | Brittle on UI change | Self-healing; adapts to layout shifts |
| Security | Safe | Vulnerable to prompt injection in page content |
| Setup | Requires selector discovery | Plain-language instructions |

**Recommended default: prefer scripts.** Use an LLM only at steps where the page is genuinely unpredictable or reasoning over content is required (e.g. "find the cheapest option that meets X criteria"). A hybrid pattern works well: script handles 80–90% of the workflow; LLM is called only at the ambiguous step.

Record the engine choice in the block contract so future maintainers understand why.

---

### Step 1c — Design the session lifecycle

If any block opens a browser or authenticates a stateful connection, design **one session for the whole workflow run** — not one session per block.

**The pattern:**
```python
session = open_session()          # agent opens once
try:
    result1 = block_a(session)    # agent calls block, passes session
    result2 = block_b(result1, session)
    # agent decides next step based on result2
    block_c(result2, session)
finally:
    close_session(session)        # agent closes when done
```

**Rules:**
- Blocks accept a `session` parameter — they do not open their own
- `open_session()` and `close_session()` are standalone primitives the agent calls explicitly
- The workflow `.md` must document: "open session in Step 1, pass to every block, close in the final step"
- Testing a block in isolation: the block accepts a session, so tests can inject a session without changing the block interface

**Why this matters:** opening and closing a browser per block is slow, triggers bot detection on rate-sensitive platforms, and breaks state that depends on prior navigation (cookies, DOM, scroll position).

---

### Step 1d — Define agent decision gates

The agent makes decisions between steps — that is the point of an agentic workflow. Every workflow `.md` must explicitly state:

1. **What the agent decides autonomously** — relevance filtering, retry logic, keyword rotation, skipping empty results
2. **What requires human input** — approval before outbound/public actions (post, send, invite), confirmation before bulk or irreversible operations

**Agent decision gate (no human needed):**
```
fetch post → agent reads text → apply relevance criteria from workflow doc
→ if relevant: draft comment, go to approval gate
→ if not: fetch next post (same session), repeat
→ if keyword exhausted: switch keyword (same session), repeat
```

**Human approval gate (agent pauses and asks in chat):**
```
agent shows: post URL + text + drafted comment
agent asks: "Post this, skip, or edit?"
human replies in chat → agent acts
```

**In the workflow `.md`, mark each decision point explicitly:**
- `[AGENT DECIDES]` — criteria the agent applies autonomously
- `[HUMAN APPROVES]` — what the agent shows the human and what question it asks

Human responds in chat, agent continues in the next turn — no `input()` or terminal prompts needed.

**Session-continuity myth:** it may seem like a browser session must stay open across the human approval turn. It doesn't — design fetch and post as separate CLI calls. The fetch script opens a session, finds a post, prints JSON, and exits. After human approval the post script opens a fresh session, navigates directly to the post URL, posts the comment, and exits. The brief reopening cost is acceptable and happens after the human has already waited; it is far simpler than pipes or long-lived background processes.

---

### Step 2 — Decompose into building blocks

Break each workflow into **atomic actions**. A building block:

- Does exactly one thing (one input → one output)
- Has no side effects outside its responsibility
- Is named as a verb + noun (e.g. `list_open_tickets`, `post_status`, `fetch_report`)
- Can be tested independently

List all blocks across all workflows. Remove duplicates — shared blocks are the sign of a good decomposition.

**Example mapping (generic):**

| Block | Used by workflows |
|-------|------------------|
| `fetch_source_records` | sync-a, report-b |
| `normalize_record` | sync-a, sync-c |
| `apply_update` | sync-a |
| `notify_channel` | sync-a, report-b |

---

### Step 3 — Find the right build order

Build blocks in **dependency order** — a block that produces input for another must come first.

1. Map dependencies: what does each block need as input?
2. Find the root blocks (no dependencies — they fetch, authenticate, or discover)
3. Build root blocks first, verify them, then build dependent blocks

**Common mistake:** starting with a consumer (e.g. `apply_update`) before the producer of its input (e.g. `fetch_source_records`). Always ask: "where does the input come from?"

---

### Step 4 — Look for existing code before building

Before implementing any block:

1. Check existing connection or integration docs (`tool_connections/<tool>/connection-*.md` or your repo’s equivalent) for verified snippets
2. Search related projects for prior implementations
3. Identify what is reusable (transport, auth, parsing) vs what must be adapted

Specifically look for:

- Auth / session setup patterns
- API vs browser automation patterns
- **Human-like / rate friction** for communication surfaces (see [Human-like behavior](#human-like-behavior-social--communication-platforms))
- Error handling and retry patterns
- ID / URL extraction utilities

Document what exists vs what needs to be built before writing any code.

---

### Step 5 — Build and verify one block at a time

For each block, in dependency order:

1. **Discover the surface** — before writing any code, determine which surface exposes the data or action you need. **For JS-heavy SPAs (LinkedIn, Figma, Notion, etc.), load and follow the [`discover-ui-surface` workflow](../discover-ui-surface/discover-ui-surface.md) first** — it walks you through the flow once manually (Chrome DevTools Recorder, Playwright observer, or codegen+trace) and produces a durable selector+endpoint map before you write a single line of automation code.

   Surface types to identify:
   - **Network first** — perform the action manually while watching DevTools Network tab (or run `observe_session.py`). Look for a clean XHR/fetch call returning structured JSON. If found, document the endpoint, headers, and payload shape — this is your implementation path.
   - **Internal API** — if no public API exists but a clean internal endpoint appears in the traffic capture, you can call it directly (replaying the same auth headers/cookies). Document it in the connection file; note that internal APIs may change without notice.
   - **DOM selectors** — if no usable API exists, drive the UI. Use `discover-ui-surface` to capture which button triggers which call and what ARIA/`data-*` selectors are durable. Prefer: ARIA roles/labels → visible text → `data-*` attributes → semantic CSS classes. Generated class names are always last resort.
   - **Hybrid** — many modern apps split IDs and structured data across network responses and human-visible DOM. Plan to combine both channels (e.g. response listeners for IDs + `page.evaluate` for copy). See [Observable surfaces](#observable-surfaces-browser-and-hybrid-uis).
   - Record which surface you chose and why. This decision belongs in the connection or block doc.

2. **Implement the block**
   - Single function or script with clear parameters; returns structured data (not only prints)
   - Include auth/session setup from the connection doc
   - Handle common failures (auth expiry, rate limits, not found)

3. **Verify it works**
   - Run against the real system with a **small scope** first
   - Check status codes / UI assertions and **output shape** downstream steps need

4. **Document it**
   - Add verified snippets to the connection file
   - Note gotchas, expiry, rate limits

Do not move to the next block until the current one is verified.

---

### Step 6 — Search the web for current information

**The LLM's training data is frozen.** Platforms change their DOM, deprecate APIs, shift rate limits, and introduce new patterns continuously. Web search provides what training data cannot: current, platform-specific, community-validated knowledge.

**Search proactively — not only when stuck:**
- Before starting on an unfamiliar platform or endpoint
- When a selector or API that worked before now fails unexpectedly
- When behavior seems platform-specific and non-obvious (unusual rendering, auth flows, bot detection)
- When you are about to guess at something someone else has likely already figured out
- After more than 2 failed hypotheses on any problem

**How to search:**
1. **Platform + action + tool + year** — e.g. "LinkedIn content search playwright 2026", "Notion API pagination python"
2. **Platform + symptom** — e.g. "LinkedIn SDUI DOM structure no URN anchor", "playwright getBoundingClientRect off-screen returns zero"
3. **Platform + concept** — e.g. "LinkedIn shared key DOM network extraction", "Slack API rate limit per method"

**Treat results as hypotheses** — the web may describe an older layout or a different surface. Cross-check against your actual inspection before committing.

**Fold the smallest viable fix** and re-verify before stacking more complexity.

---

### Step 7 — Assemble the workflow

Once all blocks for a workflow are verified:

1. Chain blocks with explicit logic (filtering, iteration, conditionals)
2. **Insert pacing** where the domain requires it (see [Human-like behavior](#human-like-behavior-social--communication-platforms))
3. Add approval gates for high-impact actions
4. Test end-to-end with caps
5. Document in the workflow `.md`: goal, starting point, block order, how to run, pacing defaults, and **when output appears** (e.g. after session teardown)

---

## File structure

All assets for a workflow live in a single folder under `workflows/` (or your repo’s convention):

```
workflows/
└── <workflow_name>/
    ├── <workflow_name>.md     ← goals, starting points, how to run
    ├── <block_1>.py
    ├── <block_2>.py
    └── ...
```

Each `.py` is a standalone building block — runnable independently. The `.md` describes how workflows chain blocks.

---

## Approval gates

Consider human review before:

- **Outbound or public actions** — tone and context matter
- **Messages** — voice and policy matter
- **Bulk actions** — rate limits, abuse heuristics, blast radius

Default to draft + approval until quality is proven. Pair gates with **human-like pacing** where applicable.

---

## Anti-patterns to avoid

- **Building a workflow before its blocks** — verify blocks independently first
- **Skipping dependency order** — you will lack inputs for downstream steps
- **Duplicating blocks** — one shared block for the same action
- **Implementing before checking for prior art**
- **Monolithic workflow scripts** — blocks should stay separable; the agent chains them, not a single script
- **Relying only on training knowledge for platform-specific details** — DOM structures, APIs, rate limits, and auth flows change; search the web before starting on an unfamiliar platform and whenever something that worked before stops working
- **Max-throughput chaining on rate-sensitive surfaces** — fixed sleeps, no session continuity, no caps
- **Single-surface scraping on hybrid apps** — assuming the entire state graph lives in one HTML dump or one API field
- **Machine and human output on the same stream** — e.g. breaking `stdout` JSON with unstructured previews
- **Defaulting to an LLM agent without checking for a script path** — use the decision tree in Step 1b first; scripts are faster, cheaper, and more reliable for stable targets
- **Skipping surface discovery** — writing selectors or API calls before a network capture; often misses a cleaner, more stable endpoint one layer up. Use `discover-ui-surface` skill before writing any Playwright block for a JS-heavy SPA
- **Opening a new session per block at runtime** — the session should be opened once by the agent and passed to each block; per-block session open/close is slow and triggers bot detection
- **Using `input()` or terminal prompts for human approval** — the human approves in chat, not in a terminal; the agent asks in the conversation and acts on the reply
- **Undocumented decision points** — every workflow `.md` must mark `[AGENT DECIDES]` and `[HUMAN APPROVES]` at each gate so the agent knows what to do autonomously vs. what to pause for

---

## Outputs

- **Block files**: one runnable unit per building block, verified alone
- **Workflow doc**: goal, entry points, block order, how to run, pacing where relevant, **output timing** for long sessions
- **Connection / integration doc**: verified snippets, auth, and operational notes

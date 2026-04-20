# LinkedIn Engagement Automation

**Audience: coding agent.** This is an automated workflow. The agent drives the full loop — finding posts, assessing relevance, drafting comments. The human's only job is to approve one comment before it posts.

**Goal:** find a relevant post on your chosen topic, draft a comment that contributes a genuine insight or perspective, get human approval, and post it.

---

> ⚠️ **Platform risk:** This workflow automates actions on LinkedIn using your personal account. LinkedIn's Terms of Service (Section 8.2) prohibit automation. Your account may be restricted or permanently banned. Read [LEGAL_NOTICE.md](../../LEGAL_NOTICE.md) before use. Proceed only if you accept this risk.

---

## Privacy & Safety

**Everything runs locally. Your credentials never leave your machine.**

- Session tokens (`li_at`, `JSESSIONID`) live only in your `.env` file on your own disk — they are never sent to any third-party service
- No cloud automation platform, no shared infrastructure, no external server holds your session
- The persistent browser profile lives at `~/.browser_automation/linkedin_profile/` — on your machine, under your control
- The agent acts as you, from your laptop, using your browser — the same trust model as doing it manually
- **You approve every comment before it posts.** Nothing is published without your explicit sign-off in Step 4

This is meaningfully safer than cloud-based LinkedIn automation tools where your cookies live on someone else's server.

---

## Customize before first use

Two things to personalize before running this workflow:

**1. Your topic keywords** (Step 1) — replace the example AI/agent keywords with terms relevant to your field. The agent uses these to find posts worth engaging with.

**2. Your perspective** (Step 3) — replace the style calibration examples with 3–5 comments you've written that you're proud of. The agent uses these to match your voice, not someone else's.

---

## Step 1 — Pick keywords for this session

```python
import random

# Replace with keywords for your topic.
# Example below uses AI/agents — swap in your own field.
KEYWORDS = random.sample([
    "Agentic AI", "Multi-Agent Systems", "AI Agent Orchestration",
    "Autonomous Agents", "Agentic Workflows", "RAG",
    "Human-in-the-Loop", "Task Chaining",
    "Vibe Coding", "AI Productivity Stack",
    "Cursor", "Claude Code", "coding agent", "Codex", "Windsurf",
    "AI Agent friction", "Enterprise AI adoption",
], k=4)
```

Keep `KEYWORDS` and `seen_urns` (list) in memory across steps.

---

## Step 1b — Start the browser daemon (once per session) [AGENT ACTS]

Start the daemon in the background **before any fetch or post**. It keeps the browser open for the whole session so the same window is reused for both searching and posting.

```bash
source .venv/bin/activate
python workflows/linkedin_automation/engage.py --serve &
```

Wait for the line `{"daemon": "ready", ...}` to appear in terminal output before continuing.

To stop it at the end of the session:

```bash
python workflows/linkedin_automation/engage.py --stop
```

---

## Step 2 — Fetch one relevant post [AGENT ACTS]

```bash
source .venv/bin/activate
python workflows/linkedin_automation/engage.py \
  --keyword "KEYWORD" \
  --skip-urns "urn1,urn2,..."
```

`engage.py` routes through the running daemon so the browser stays open. It auto-skips irrelevant and already-seen posts and prints **one** JSON object to stdout:

```json
{"urn": "...", "url": "...", "author": "...", "author_url": "...", "text": "..."}
```

Or on failure:
```json
{"error": "keyword_exhausted", "keyword": "..."}
{"error": "no_relevant_post", "keyword": "..."}
```

**Agent loop:**
- Add the returned URN to `seen_urns` so it is passed via `--skip-urns` on the next call
- On `keyword_exhausted` or `no_relevant_post` → switch to the next keyword
- Do NOT call `engage.py` in a loop before showing anything to the human — fetch one, assess, show

---

## Step 3 — Assess relevance and draft the comment [AGENT DECIDES]

**Relevance checklist — all must be true to surface to the human:**
- [ ] Post is genuinely about your topic (not just tangentially mentioning a keyword)
- [ ] Not a personal/grief/political post
- [ ] You can add one concrete, non-generic insight based on your own perspective
- [ ] Thread is not already saturated with similar comments

If not relevant, call `engage.py` again with the same keyword and updated `--skip-urns`.

**Finding your angle:**

The goal is a comment that contributes something the post doesn't already say. Ask: *what do I know from my own experience that adds to this conversation?* Some patterns that work:

| What the post says | A genuine bridge looks like… |
|--------------------|------------------------------|
| States a problem | A concrete cause or constraint most people overlook |
| Celebrates a trend | The friction point or failure mode that trend creates |
| Shares a tool or approach | A real trade-off or edge case from using something similar |
| Makes a prediction | A counterexample or condition that changes the outcome |
| Asks a question | A direct answer from direct experience, not hedged opinion |

Fill in the angle based on what you actually know — not what sounds smart.

**Comment shape:**
- 1–3 sentences max. One sharp sentence beats three safe ones.
- Direct and opinionated — no hedging, no "great post!", no emojis, no hashtags
- One concrete reframe or observation. No lists, no numbered points.
- Lead with the insight

**What NOT to write:**
- Don't summarise their post back at them
- Don't use "resonates", "kudos", "spot on", "insightful", "love this"
- Don't end with a question just to seem engaging
- Don't promote a product, repo, or project unless it directly and specifically answers a gap the author named — and even then, at most once every 5 comments

**Style calibration — replace with your own examples.**

Collect 3–5 comments you've written that you're proud of. Paste them here so the agent can match your tone, not someone else's. The examples below are from the repo author; use them only as a structural reference for what "good" looks like:

> "Fail fast only works if you're learning fast. Most teams just fail."

> "Two types of engineers using AI: the best ones and the worst ones. The best use it to think faster. The worst use it to avoid thinking."

> "The bottleneck was never build speed. It was always knowing what to build."

> "Everyone's optimising the output. Nobody's questioning the input."

---

## Step 4 — Show the human and ask for approval [HUMAN APPROVES]

Present in chat:
- Post URL
- Author
- Full post text
- Relevance assessment (one sentence)
- Drafted comment

Then ask: **"Post this comment, skip this post, or change keyword?"**

If the human says:
- **"post it"** → go to Step 5
- **"skip"** → call `engage.py` again with the same keyword and updated `--skip-urns`
- **"change keyword"** → call `engage.py` with the next keyword, `--skip-urns` reset
- **"edit: …"** → update the comment text, show it again, wait for approval

---

## Step 5 — Post the comment [AGENT ACTS]

The daemon is still running with the browser open. Call `engage.py` with `--post-url` and `--post-comment` — it routes through the daemon so **no second window opens**.

```bash
source .venv/bin/activate
python workflows/linkedin_automation/engage.py \
  --post-url "POST_URL" \
  --post-comment "APPROVED_COMMENT_TEXT"
```

Output: `{"posted": true, "code": 0}` on success, `{"posted": false, "code": N}` on failure.

Tell the human the result. On failure ask whether to retry or skip.

After the session is done, stop the daemon:

```bash
python workflows/linkedin_automation/engage.py --stop
```

---

## Escape hatch — post directly if you already have the URL and comment text

```bash
source .venv/bin/activate
python workflows/linkedin_automation/post_comment.py \
  --url "https://www.linkedin.com/feed/update/urn:li:activity:…/" \
  --text "Your comment here."
```

# 10x Engage (LinkedIn comments)

**Audience: coding agent.** Follow these steps exactly. You drive the loop. The human approves one comment in Cursor chat before you post.

**Goal:** post one high-quality comment that genuinely contributes to a relevant conversation. The repo link is incidental — include it only when it directly helps the reader.

**Repo:** https://github.com/ZhixiangLuo/10xProductivity

---

## Step 1 — Pick keywords for this session

```python
import random
KEYWORDS = random.sample([
    "Agentic AI", "Multi-Agent Systems", "AI Agent Orchestration",
    "Autonomous Agents", "Agentic Workflows", "RAG",
    "AI Agent Architect", "Human-in-the-Loop", "Task Chaining",
    "AI Solutions Architect", "Vibe Coding", "AI Productivity Stack",
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

## Step 2 — Fetch one relevant post [AGENT DECIDES]

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
- Add the returned URN to `seen_urns` so it is passed via `--skip-urns` on the next call.
- On `keyword_exhausted` or `no_relevant_post` → switch to the next keyword.
- Do NOT call `engage.py` in a loop before showing anything to the human — fetch one, assess, show.

---

## Step 3 — Assess relevance and draft the comment [AGENT DECIDES]

**Relevance checklist — all must be true to surface to the human:**
- [ ] Topic touches AI agents, coding tools, personal assistants, tool integrations, or productivity friction
- [ ] Not a personal/grief/political post
- [ ] You can add one concrete, non-generic insight
- [ ] Thread is not already saturated with promo links

If not relevant, call `engage.py` again with the same keyword and updated `--skip-urns`.

**Angle table:**

| They're talking about… | Bridge with… |
|------------------------|--------------|
| Cursor / Claude Code / Windsurf / Codex | Great for coding — and the same agent can automate daily workflows if you wire it to real tools. Most people only use 10% of what it can do. |
| Agentic AI / autonomous agents / orchestration | Coding agent for build/iterate glue; same stack powers a personal assistant for recurring "check these systems" work |
| RAG / knowledge retrieval | Static docs aren't enough — live tool sessions (Slack, Jira, browser) give the agent real-time grounding |
| AI agent friction / setup complexity | Zero infrastructure angle: persistent browser profile + tool_connections, no cloud plumbing |
| Enterprise AI adoption / IT hassle | Local sessions, credentials stay on-device, no new cloud permissions needed |
| Vibe coding | Non-devs can build "skills" via playbooks — no code required for the workflow layer |
| AI productivity stack | 10xProductivity is the connective tissue that wires their existing stack to the agent |

**Comment shape:**
- 1–3 sentences max. One sharp sentence beats three safe ones.
- Direct and opinionated — no hedging, no "great post!", no emojis, no hashtags
- One concrete reframe or observation. No lists, no numbered points.
- Lead with the insight, not the product name

**What NOT to write:**
- Don't summarise their post back at them
- Don't use "resonates", "kudos", "spot on", "insightful", "love this"
- Don't end with a question just to seem engaging

**Repo link — aim for 1 in 5, only when it directly fills a gap the author named.**

**Style calibration — replace with your own examples.**

Collect 3–5 comments you've written that you're proud of. Paste them here so the agent can match your tone, not someone else's. The examples below are from the repo author; use them only as a structural reference for what "good" looks like:

> "Fail fast only works if you're learning fast. Most teams just fail."

> "Two types of engineers using AI: the best ones and the worst ones. The best use it to think faster. The worst use it to avoid thinking."

> "The bottleneck was never build speed. It was always knowing what to build."

> "Everyone's optimising the output. Nobody's questioning the input."

---

## Step 4 — Show the human and ask for approval [HUMAN APPROVES]

Present in Cursor chat:
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

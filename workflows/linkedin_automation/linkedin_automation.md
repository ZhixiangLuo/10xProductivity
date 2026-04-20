---
name: linkedin_automation
description: Automate daily LinkedIn activities — search posts, read feed, engage (like/comment/repost), prospect connections, publish posts, and manage messages. Each building block is a standalone script; workflows chain them together toward a goal.
---

# LinkedIn Automation

## Building Blocks

Standalone scripts — each does one thing and can be run independently.

| Script | Input | Output | Status |
|--------|-------|--------|--------|
| `fetch_next_post.py` | keyword + optional cursor + session | one post dict + next cursor; `open_session()` / `close_session()` for session lifecycle | ✅ built |
| `search_posts.py` | keyword / hashtag | list of posts (urn, author, text, url) | ✅ built |
| `post_comment.py` | post URL + comment text | posts comment (persistent browser session) | ✅ built |
| `read_feed.py` | — | list of posts from your feed | 🔲 todo |
| `like_post.py` | post permalink URL | DOM like + exit code; bounded retries (`MAX_UI_ATTEMPTS=4`) | ✅ built |
| `comment_on_post.py` | post urn + comment text | HTTP 201 confirmation | 🔲 todo |
| `repost.py` | post urn + optional commentary | HTTP 201 confirmation | 🔲 todo |
| `read_post_comments.py` | post permalink URL | comment rows (`--json`); bounded scroll rounds (`MAX_SCROLL_ROUNDS=4`) | ✅ built |
| `create_post.py` | post text | HTTP 201 confirmation | ✅ see connection-session-cookie.md |
| `send_connection_request.py` | profile URL (`/in/…`) | DOM connect + modal dismiss; bounded retries (`MAX_UI_ATTEMPTS=4`) | ✅ built |
| `read_conversations.py` | — | list of conversations (urn, participants, last message) | ✅ see connection-session-cookie.md |
| `read_messages.py` | conversation urn | list of messages | ✅ see connection-session-cookie.md |
| `reply_message.py` | conversation urn + message text | HTTP 201 confirmation | ✅ see connection-session-cookie.md |

## Workflows

### `engage-search` — Engage with posts found by keyword

**Starting point:** a keyword or hashtag you care about
**Goal:** like, comment, and/or repost relevant posts

```
fetch_next_post(keyword, cursor, session) → post   # agent calls per post; advances cursor
  → agent decides: relevant?
  → yes: post_comment(url, text, session) → done
  → no:  fetch_next_post(keyword, cursor, session) → next post
  → (switch keyword by passing cursor=None)
```

### `10x_engage` — Engage on relevant AI/agent topics, mention repo only when it genuinely helps

**Playbook:** `10x_engage.md` — topic signals, relevance gate, comment shape, when to mention the repo, and the agent-driven loop (`fetch_next_post` → agent decides → `post_comment`).

### `engage-feed` — Engage with posts from your feed

**Starting point:** your LinkedIn feed
**Goal:** like, comment, and/or repost from what your network is posting

```
read_feed() → posts (🔲 todo)
  → agent iterates one post at a time: like_post(urn), post_comment(url, text, session)
```

### `prospect` — Find and connect with interesting people

**Starting point:** a post's comment section
**Goal:** send connection requests to people who wrote insightful comments

```
search_posts(keyword) → posts
  → read_post_comments(urn) → commenters
  → for each commenter: send_connection_request(profile_url)
```

### `publish` — Post content and reply to comments

**Starting point:** your content idea
**Goal:** publish a post and engage with people who comment

```
create_post(text)
  → read_post_comments(your_post_urn) → commenters
  → for each commenter: comment_on_post(your_post_urn, reply_text)
```

### `inbox` — Read and reply to messages

**Starting point:** your LinkedIn inbox
**Goal:** reply to unread messages

```
read_conversations() → conversations
  → read_messages(conversation_urn) → messages
  → reply_message(conversation_urn, reply_text)
```

## Legal

LinkedIn automation violates LinkedIn's Terms of Service and may result in account suspension. See [LEGAL_NOTICE.md](../../LEGAL_NOTICE.md) before use.

## Setup

Requires `LINKEDIN_LI_AT` and `LINKEDIN_JSESSIONID` in `.env`.
See `tool_connections/linkedin/setup.md` to capture credentials.

```bash
source .venv/bin/activate
python workflows/linkedin_automation/search_posts.py --keyword "AI agents" --max 10
```

## Notes

- **UI surface map (filled notes + network `sduiid` table):** `docs/interaction-map-observe-session-2026-04-19.md` — from `observe_session` + Chrome Recorder follow-ups; methodology lives in `workflows/discover-ui-surface/discover-ui-surface.md`.
- This folder only keeps **shipping** scripts (`search_posts.py`, …). For one-off network/DOM investigation use `tool_connections/shared_utils/traffic_sniffer.py` instead of committing throwaway debug files here.
- All scripts use the persistent browser profile at `~/.browser_automation/linkedin_profile/` — do not delete it
- `LINKEDIN_JSESSIONID` expires ~24h — re-run `tool_connections/linkedin/sso.py` to refresh
- Add human review before sending connection requests or posting comments at scale
- Build and verify each block independently before chaining into a workflow

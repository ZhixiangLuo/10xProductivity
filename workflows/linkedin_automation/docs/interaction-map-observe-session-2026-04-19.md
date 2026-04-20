# LinkedIn UI surface map — from `observe_session` traces (2026-04-19)

This document fills the **interaction map** and **notes** that the discover-ui-surface skill expects after a capture session. It is derived from local traces only (no raw HAR/JSON committed here).

## Source

- **Tool:** `workflows/discover-ui-surface/assets/observe_session.py`
- **Profile:** `--linkedin-10x-profile` → `~/.browser_automation/linkedin_profile`
- **Raw artifacts (local only, do not commit):** `/tmp/linkedin_engagement_trace.json`, `/tmp/linkedin_engagement_trace_summary.md`

### Run A (short interrupt, ~3.5 min wall)

- **Stats:** 255 events (128 requests) — small slice.
- **Caveat:** First build listened on **page** only; new-tab traffic was easy to miss.

### Run B (redo, ~3.4 min wall, interrupted)

- **Stats:** **796** events (**398** requests), trace file ~**672 KB** after `SIGINT` flush.
- **Listeners:** **`ctx.on("request")` / `ctx.on("response")`** (all tabs in this Chromium context).
- **Timeline anomaly (root cause, now fixed):** the observer used **`time.sleep()`** on the main thread while “recording.” Playwright’s **sync** driver cannot run request/response handlers during a blocking sleep, so **all** `t_ms` values landed in a **~0.7 s** burst when the wait ended — **misleading**, not necessarily “wrong window.”

**Current behavior:** the script **pumps** with **`page.wait_for_timeout()`** and uses **monotonic `t_ms`** from listener attach (`t_ms_basis` in JSON), plus optional **`--heartbeat`** / **`--autosave-every`**. Re-capture after pulling latest for honest timelines.

**Operational tip:** still do the flow **only** in the Chromium window this script opens, so you do not split attention across browsers.

## Network map — `sduiid` verbs (Run B, condensed)

LinkedIn’s web client is dominated by **`POST /flagship-web/rsc-action/...`** with query **`sduiid=com.linkedin.sdui...`**. Counts below are **request** rows from Run B.

| Count | `sduiid` (truncated if long) | Maps to (intent) |
|------:|------------------------------|------------------|
| 6 | `com.linkedin.sdui.search.contentSearchResults` | Search SRP pagination / more results |
| 4 | `com.linkedin.sdui.search.requests.updateSearchHistoryRequest` | Search history / keyword persistence |
| 3 | `com.linkedin.sdui.impl.homenav.requests.getThirdPartyTrackingPixels` | Nav shell / pixels |
| 3 | `com.linkedin.sdui.requests.profile.fetchProfileDiscoveryDrawer` | Profile **discovery drawer** (hover card / mini-profile) |
| 3 | `com.linkedin.sdui.impl.mynetwork.infra.components.relationshipbuildingdra…` | **Relationship / connect** UI infra (name truncated in export) |
| 2 | `com.linkedin.sdui.reactions.create` | **Like / reaction** |
| 2 | `com.linkedin.sdui.comments.fetchFeedUpdateActionPrompt` | Comment affordances / prompts on update |
| 2 | `com.linkedin.sdui.requests.profile.profilePolicyNotice` | Policy / notice surfaces on profile |
| 2 | `com.linkedin.sdui.requests.trustverifications.trustVerificationNbaRequest` | Trust / verification nudges |
| 1 | `com.linkedin.sdui.search.requests.SearchGlobalTypeaheadRequestAction` | Global search typeahead |
| 1 | `com.linkedin.sdui.feed.update.comments.fetchComment` | Load **comment body / thread** |
| 1 | `com.linkedin.sdui.comments.createComment` | **Post comment** |
| 1 | `com.linkedin.sdui.requests.profile.refreshProfileSections` | Profile refresh |
| 1 | `com.linkedin.sdui.requests.mynetwork.addaUpdateFollowState` | **Follow** state |
| 1 | `com.linkedin.sdui.requests.mynetwork.handlePostInteropConnection` | **Connect / interop** after post (naming per SDUI) |

**Also heavy:** `GET /voyager/api/graphql` (51 requests this run) — nav, messaging, premium badges, etc. Treat as **supporting** surface; product actions above are usually clearer in **`rsc-action`** `sduiid` rows.

**RSC components (no `sduiid` in URL):** many `…/rsc-action/actions/component?componentId=com.linkedin.sdui.generated…` lines (e.g. filter bar, comment **submit** button shell) — pair them with the following `server-request` for payload shape.

**Opaque short POST paths** (`/5tOQN36_bjLX1vM` style): binary / telemetry — skip for automation unless you are decoding payloads on purpose.

## Selector map (Chrome Recorder — DOM still not in trace)

The observer does **not** record clicks. Use **Chrome DevTools → Recorder** (`workflows/discover-ui-surface/chrome-recorder.md`) on the **same** flow in the **same** Playwright window if possible, then merge:

| Network signal | Recorder / Playwright hint |
|----------------|----------------------------|
| `SearchGlobalTypeaheadRequestAction` / `updateSearchHistoryRequest` / `contentSearchResults` | Global search, submit, SRP filters, scroll “load more” |
| `fetchFeedUpdateActionPrompt` / `fetchComment` / `createComment` | Open thread, **Comment**, composer **Post** |
| `reactions.create` | **Like** / reaction picker |
| `fetchProfileDiscoveryDrawer` / `refreshProfileSections` | Hover / open **profile** card or profile page |
| `addaUpdateFollowState` | **Follow** |
| `handlePostInteropConnection` / `relationshipbuilding…` | **Connect** / invite flows tied to network UI |

Harden selectors: **ARIA** → visible **text** → **`data-control-name`** → CSS last.

## Security

- Do **not** commit `/tmp/linkedin_engagement_trace*.json` — may contain message text, identifiers, or session-adjacent payloads.
- This file stays **pattern-only** and is safe to commit.

## Next actions

1. **Re-capture** with the full **~203 s** (or longer `--duration`) while **only** using the observer’s Chromium window; confirm `t_ms` **spans** the full session (first request near `0`, not only `~200000`).
2. Wire **`reactions.create`** into a future `like_post.py` design; **`handlePostInteropConnection`** / **`addaUpdateFollowState`** into connect/follow blocks.
3. Keep **`search_posts.py`** aligned with **`contentSearchResults`** pagination as the SDUI stack drifts.

## Cross-links

- Methodology: `workflows/discover-ui-surface/discover-ui-surface.md`
- Observer: `workflows/discover-ui-surface/assets/observe_session.py`

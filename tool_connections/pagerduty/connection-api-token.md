---
name: pagerduty
auth: api-token
description: PagerDuty — incident management, on-call scheduling, alerting. Use when looking up active incidents, checking who is on call, querying service status, or reading escalation policies. Requires PAGERDUTY_TOKEN (personal REST API key). Read-only personal use is fine; production write integrations may require approval from your security team.
env_vars:
  - PAGERDUTY_TOKEN
---

# PagerDuty

Primary incident management platform for on-call scheduling, incident response, alerting, and escalation.

Env: `PAGERDUTY_TOKEN` (personal REST API key — long-lived, does not expire)
Web UI: https://app.pagerduty.com (or your company's subdomain: `yourcompany.pagerduty.com`)
REST API docs: https://developer.pagerduty.com/api-reference

---

## Auth setup (one-time)

1. Log into PagerDuty
2. Click your avatar → **My Profile**
3. Go to **User Settings** tab → **API Access** section
4. Click **Create New API Key**, give it a name (e.g. `local-agent`), copy the key
5. Add to `.env`:

```bash
# --- PagerDuty ---
PAGERDUTY_TOKEN=your-personal-api-key-here
```

Auth header: `Authorization: Token token=$PAGERDUTY_TOKEN`

## Verify connection

```bash
source .env
curl -s "https://api.pagerduty.com/users/me" \
  -H "Authorization: Token token=$PAGERDUTY_TOKEN" \
  -H "Accept: application/vnd.pagerduty+json;version=2" \
  | jq '{name: .user.name, email: .user.email, role: .user.role}'
# → {"name": "Alice Smith", "email": "alice@example.com", "role": "limited_user"}
# If you see 401: token is wrong or expired — generate a new one in PagerDuty.
```

---

## Quick-reference snippets

```bash
source .env

BASE="https://api.pagerduty.com"
AUTH="Authorization: Token token=$PAGERDUTY_TOKEN"

# Current user
curl -s "$BASE/users/me" \
  -H "$AUTH" -H "Accept: application/vnd.pagerduty+json;version=2" \
  | jq '{id: .user.id, name: .user.name, email: .user.email, role: .user.role}'

# List active incidents (triggered + acknowledged)
curl -s "$BASE/incidents?statuses[]=triggered&statuses[]=acknowledged&limit=10&sort_by=created_at:desc" \
  -H "$AUTH" -H "Accept: application/vnd.pagerduty+json;version=2" \
  | jq '.incidents[] | {id, title, status, urgency, priority: .priority.name, service: .service.summary}'

# Who's on call right now (all schedules)
curl -s "$BASE/oncalls?limit=25" \
  -H "$AUTH" -H "Accept: application/vnd.pagerduty+json;version=2" \
  | jq '.oncalls[] | {user: .user.summary, schedule: .schedule.summary, escalation_policy: .escalation_policy.summary}'

# Who's on call for a specific escalation policy
curl -s "$BASE/oncalls?escalation_policy_ids[]=<POLICY_ID>" \
  -H "$AUTH" -H "Accept: application/vnd.pagerduty+json;version=2" \
  | jq '.oncalls[] | {level: .escalation_level, user: .user.summary}'

# Get service by ID
curl -s "$BASE/services/<SERVICE_ID>" \
  -H "$AUTH" -H "Accept: application/vnd.pagerduty+json;version=2" \
  | jq '{name: .service.name, status: .service.status, escalation: .service.escalation_policy.summary}'

# List services
curl -s "$BASE/services?limit=25&sort_by=name" \
  -H "$AUTH" -H "Accept: application/vnd.pagerduty+json;version=2" \
  | jq '.services[] | {id, name, status, team: (.teams[0].summary // "none")}'

# List schedules
curl -s "$BASE/schedules?limit=25" \
  -H "$AUTH" -H "Accept: application/vnd.pagerduty+json;version=2" \
  | jq '.schedules[] | {id, name, time_zone}'

# Get a schedule's current on-call (today)
TODAY=$(date -u +%Y-%m-%dT%H:%M:%SZ)
curl -s "$BASE/schedules/<SCHEDULE_ID>?since=${TODAY}&until=${TODAY}" \
  -H "$AUTH" -H "Accept: application/vnd.pagerduty+json;version=2" \
  | jq '.schedule.final_schedule.rendered_schedule_entries[0] | {user: .user.summary, start, end}'

# Search incidents by service
curl -s "$BASE/incidents?service_ids[]=<SERVICE_ID>&limit=5" \
  -H "$AUTH" -H "Accept: application/vnd.pagerduty+json;version=2" \
  | jq '.incidents[] | {id, title, status, created_at}'

# List teams
curl -s "$BASE/teams?limit=25" \
  -H "$AUTH" -H "Accept: application/vnd.pagerduty+json;version=2" \
  | jq '.teams[] | {id, name}'

# Get escalation policies
curl -s "$BASE/escalation_policies?limit=25" \
  -H "$AUTH" -H "Accept: application/vnd.pagerduty+json;version=2" \
  | jq '.escalation_policies[] | {id, name}'
```

---

## Python helper

```python
import json, subprocess, os

def pd_get(path, params=""):
    """Call PagerDuty REST API."""
    token = os.environ.get("PAGERDUTY_TOKEN")
    cmd = [
        "curl", "-s",
        f"https://api.pagerduty.com{path}{params}",
        "-H", f"Authorization: Token token={token}",
        "-H", "Accept: application/vnd.pagerduty+json;version=2",
    ]
    return json.loads(subprocess.check_output(cmd))

# Active incidents
data = pd_get("/incidents", "?statuses[]=triggered&statuses[]=acknowledged&limit=10")
for inc in data.get("incidents", []):
    print(f"  [{inc['status']}] {inc['id']}: {inc['title']} (svc: {inc['service']['summary']})")

# On-call right now
data = pd_get("/oncalls", "?limit=25")
for oc in data.get("oncalls", []):
    print(f"  L{oc['escalation_level']} {oc['escalation_policy']['summary']}: {oc['user']['summary']}")
```

---

## Full REST API surface

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/users/me` | Current authenticated user |
| GET | `/services/{id}` | Service details (status, escalation, integrations) |
| GET | `/services` | List services (`?team_ids[]`, `?limit`, `?sort_by=name`) |
| GET | `/incidents` | List incidents (`?statuses[]=triggered`, `?service_ids[]`, `?limit`) |
| GET | `/incidents/{id}` | Single incident detail |
| GET | `/incidents/{id}/notes` | Incident notes / timeline |
| GET | `/oncalls` | Current on-call users (`?escalation_policy_ids[]`, `?schedule_ids[]`) |
| GET | `/schedules` | List schedules |
| GET | `/schedules/{id}` | Schedule with rendered entries (`?since=`, `?until=`) |
| GET | `/escalation_policies` | List escalation policies |
| GET | `/escalation_policies/{id}` | Single policy with rules |
| GET | `/teams` | List teams |
| GET | `/teams/{id}/members` | Team members |
| GET | `/users` | List users (`?team_ids[]`, `?query=name`) |
| GET | `/users/{id}` | User details |
| POST | `/incidents` | Create incident (check your org's policy before automating writes) |
| PUT | `/incidents/{id}` | Update incident status/priority |
| POST | `/incidents/{id}/notes` | Add note to incident |

---

## Key ID patterns

| Resource | Example ID | Where to find it |
|----------|-----------|-----------------|
| Service | `PW2S8FL` | URL: `app.pagerduty.com/service-directory/{ID}` |
| Escalation policy | `PXXXXXX` | From service details → escalation_policy |
| Schedule | `PXXXXXX` | From escalation policy → rules |
| User | `PXXXXXX` | From `GET /users/me` → `.user.id` |
| Incident | `PXXXXXX` | From `GET /incidents` → `.incidents[].id` |

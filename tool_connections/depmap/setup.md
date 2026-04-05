---
tool: depmap
description: DepMap Cancer Dependency Map portal — public API, no auth required.
---

# DepMap — Setup

No credentials needed. No `.env` entries. No SSO.

## Verify

```bash
curl -s "https://depmap.org/portal/api/health_check/celery_redis_check" | python3 -c "import sys,json; r=json.load(sys.stdin); print('OK' if r['state']=='SUCCESS' else r)"
# → OK
```

If that returns `OK`, the connection is live. Load `connection-no-auth.md` and use it.

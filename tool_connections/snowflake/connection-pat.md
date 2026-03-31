---
tool: snowflake
auth: programmatic-access-token
description: Snowflake — query data warehouse via Programmatic Access Token (PAT). Long-lived JWT (~1 year). No SSO/browser automation needed — PAT is stored in ~/.snowflake/config.toml by the Snowflake VSCode extension.
env_vars:
  - SNOWFLAKE_ACCOUNT
  - SNOWFLAKE_USER
  - SNOWFLAKE_PAT
  - SNOWFLAKE_WAREHOUSE
---

# Snowflake — Programmatic Access Token

Connect to Snowflake for SQL queries, data exploration, and schema introspection. Uses a long-lived PAT stored by the Snowflake VSCode extension — no OAuth app or browser automation needed.

**Verified:** `ktazvpl-evb32354.privatelink` (us-west-2 private link) — CURRENT_USER query — 2026-03.

---

## Credentials

```bash
# ~/.snowflake/config.toml is the source of truth (managed by Snowflake VSCode extension)
# Sync to .env:
python3 personal/snowflake/connection.py --sync

# .env keys written:
# SNOWFLAKE_ACCOUNT=ktazvpl-evb32354.privatelink
# SNOWFLAKE_USER=blake.tagget@workday.com
# SNOWFLAKE_PAT=<jwt>
# SNOWFLAKE_WAREHOUSE=data_analysis_wh
```

---

## Auth

```python
import snowflake.connector, warnings
from pathlib import Path

warnings.filterwarnings("ignore")

env = {k.strip(): v.strip() for line in Path(".env").read_text().splitlines()
       if "=" in line and not line.startswith("#") for k, v in [line.split("=", 1)]}

conn = snowflake.connector.connect(
    account=env["SNOWFLAKE_ACCOUNT"],
    user=env["SNOWFLAKE_USER"],
    password=env["SNOWFLAKE_PAT"],
    warehouse=env["SNOWFLAKE_WAREHOUSE"],
    authenticator="snowflake",
    login_timeout=30,
    insecure_mode=True,  # required for privatelink endpoints
)
```

---

## Verified snippets

```python
# Basic identity check
cur = conn.cursor()
cur.execute("SELECT CURRENT_USER(), CURRENT_ROLE(), CURRENT_WAREHOUSE()")
print(cur.fetchone())
# → ('BLAKE.TAGGET@WORKDAY.COM', 'ROLE_DATA_ANALYST', 'DATA_ANALYSIS_WH')

# List databases you have access to
cur.execute("SHOW DATABASES")
for row in cur.fetchall():
    print(row[1])  # name

# Query a table
cur.execute("SELECT * FROM my_database.my_schema.my_table LIMIT 10")
rows = cur.fetchall()
cols = [d[0] for d in cur.description]

conn.close()
```

---

## Setup (first time)

The PAT is already configured if the Snowflake VSCode extension is installed. To check:

```bash
cat ~/.snowflake/config.toml
```

If not present, log in to the Snowflake web UI and generate a PAT under Profile → Programmatic Access Tokens.

---

## Refresh

PAT expires ~1 year from creation. When expired (auth errors on connect):

1. Log in to `https://app.us-west-2.privatelink.snowflakecomputing.com/ktazvpl/evb32354`
2. Profile → Programmatic Access Tokens → Generate new token
3. Update `password` in `~/.snowflake/config.toml`
4. Run `python3 personal/snowflake/connection.py --sync` to update `.env`

---

## Notes

- `insecure_mode=True` is required for privatelink endpoints (internal DNS, custom cert)
- Account identifier: `ktazvpl-evb32354.privatelink` (not the full URL)
- Default warehouse: `data_analysis_wh`, role: `ROLE_DATA_ANALYST`
- The `password` field in config.toml holds a PAT (Programmatic Access Token) JWT — entered as the password credential, using `authenticator = "snowflake"` (standard password auth mode)

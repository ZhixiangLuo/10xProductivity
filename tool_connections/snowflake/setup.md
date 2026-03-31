# Snowflake — Quick Start

## Prerequisites

- Snowflake VSCode extension installed (sets up `~/.snowflake/config.toml`)
- OR: manually create `~/.snowflake/config.toml` with account/user/PAT

## Steps

1. **Verify config exists:**
   ```bash
   cat ~/.snowflake/config.toml
   # Should show account, user, password (PAT), warehouse
   ```

2. **Activate venv and install connector:**
   ```bash
   cd ~/code/10xProductivity && source .venv/bin/activate
   pip install snowflake-connector-python --index-url https://pypi.org/simple/
   ```

3. **Copy personal connection script:**
   ```bash
   cp tool_connections/snowflake/connection.py personal/snowflake/connection.py
   # (adjust TOOL_NAME/ENV_FILE paths if needed)
   ```
   Or use `personal/snowflake/connection.py` which already exists.

4. **Sync credentials to .env:**
   ```bash
   python3 personal/snowflake/connection.py --sync
   ```

5. **Verify:**
   ```bash
   python3 personal/snowflake/connection.py
   # → SNOWFLAKE_PAT: ok
   ```

## See also

`tool_connections/snowflake/connection-pat.md` — full auth examples and query patterns.

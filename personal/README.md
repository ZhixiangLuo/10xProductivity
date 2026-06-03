# Personal Workspace Moved

This folder is intentionally a placeholder.

Private runtime files no longer live inside this public repo. Use:

```text
TENX_PRIVATE_DIR=~/.10xProductivity
~/.10xProductivity/.env
~/.10xProductivity/personal/
~/.10xProductivity/verified_connections.md
```

You may override the private location by setting `TENX_PRIVATE_DIR`.

Do not put credentials, browser profiles, cookies, company-specific connection
files, or verified connection indexes in this repo folder. Keep real personal
recipes under `TENX_PRIVATE_DIR/personal/`.

Migration note for older instructions:

```text
/path/to/10xProductivity/.env
/path/to/10xProductivity/personal/
/path/to/10xProductivity/verified_connections.md
```

now map to:

```text
~/.10xProductivity/.env
~/.10xProductivity/personal/
~/.10xProductivity/verified_connections.md
```

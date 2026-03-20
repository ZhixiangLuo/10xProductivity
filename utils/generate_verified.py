"""
Generate verified_connections.md from each tool's connection-*.md frontmatter.

Edit VERIFIED_NAMES below to include only tools whose Verify command
you actually ran and confirmed with real output, then run this script.

Tools are found automatically in tool_connections/{tool}/ then personal/{tool}/.
No changes to verified_connections.example.md are needed when adding new tools.
"""
import glob
import re
from pathlib import Path

VERIFIED_NAMES = [
    # Core tools (tool_connections/):
    # "confluence",
    # "slack",
    # "jira",
    # "github",
    # "grafana",
    # "pagerduty",
    # "google-drive",
    # "microsoft-teams",
    # "outlook",
    # "datadog",
    # "artifactory",
    # "bitbucket-server",
    # "jenkins",
    # "backstage",
    # "linear",
    # Personal tools (personal/):
    # "my-internal-tool",
]


def find_connection_file(tool_name):
    """Return the first connection-*.md found in tool_connections/ then personal/."""
    for base in ("tool_connections", "personal"):
        matches = sorted(glob.glob(f"{base}/{tool_name}/connection-*.md"))
        if matches:
            return matches[0]
    return None


def parse_frontmatter(path):
    """Parse YAML-ish frontmatter from a connection-*.md file."""
    text = Path(path).read_text()
    if not text.startswith("---"):
        return {}
    end = text.find("\n---\n", 3)
    if end == -1:
        return {}
    fm: dict = {}
    current_key = None
    for line in text[3:end].splitlines():
        list_m = re.match(r"^\s+-\s+(.+)$", line)
        kv_m = re.match(r"^([\w_-]+):\s*(.*)", line)
        if list_m and current_key and isinstance(fm.get(current_key), list):
            fm[current_key].append(list_m.group(1).strip())
        elif kv_m:
            current_key = kv_m.group(1)
            val = kv_m.group(2).strip()
            fm[current_key] = [] if not val else val
    return fm


def build_display_name(fm, tool_name):
    raw = fm.get("name", tool_name)
    return " ".join(w.title() for w in raw.replace("-", " ").split())


def build_section(fm, conn_path):
    """Build a ## Tool → path section from a connection file's frontmatter."""
    name = build_display_name(fm, Path(conn_path).parent.name)
    description = fm.get("description", "")
    env_vars = fm.get("env_vars", [])
    auth_file = fm.get("auth_file", "")

    parts = [f"\n## {name} → `{conn_path}`\n"]
    if description:
        parts.append(description)
    if env_vars:
        env_str = ", ".join(f"`{v}`" for v in (env_vars if isinstance(env_vars, list) else [env_vars]))
        parts.append(f"Env: {env_str}")
    elif auth_file:
        parts.append(f"Auth file: `{auth_file}`")
    return "\n".join(parts) + "\n"


# ── Read the fixed preamble from the example file ──────────────────────────
# Split on \n---\n; drop any ## sections (those are format examples, not data).
example = Path("verified_connections.example.md").read_text()
chunks = re.split(r"\n---\n", example)
header_chunks = [c for c in chunks if not re.match(r"^##\s+\w", c.strip())]
header = "\n---\n".join(header_chunks)

# ── Generate sections from tool frontmatter ─────────────────────────────────
generated_sections = []
for tool_name in VERIFIED_NAMES:
    conn_file = find_connection_file(tool_name)
    if not conn_file:
        print(f"Warning: no connection file found for '{tool_name}' — skipping.")
        continue
    fm = parse_frontmatter(conn_file)
    generated_sections.append(build_section(fm, conn_file))

output = header
if generated_sections:
    output += "\n---\n" + "\n---\n".join(generated_sections)

# ── Update frontmatter description ─────────────────────────────────────────
tool_list = ", ".join(VERIFIED_NAMES) if VERIFIED_NAMES else "none"
output = re.sub(
    r"(description: ).*?(\n)",
    lambda m: m.group(1) + f"Your active tool connections — verified and ready. Covers: {tool_list}. Load at session start." + m.group(2),
    output, count=1,
)

# ── Replace example-file preamble with session-ready preamble ──────────────
new_preamble = (
    "**Keep this file loaded for the entire session.** These tools are verified and ready — "
    "use them proactively in any task across any codebase.\n\n"
    "Individual tool files have full connection details — load them on demand.\n\n"
    "**Refresh short-lived tokens (~8h):** run the tool's `sso.py` "
    "(e.g. `source .venv/bin/activate && python3 tool_connections/slack/sso.py`)"
)
output = re.sub(
    r"\*\*This is the example file\.\*\*.*?(?=\n---\n|\n## )",
    new_preamble,
    output,
    flags=re.DOTALL,
)

Path("verified_connections.md").write_text(output)
print(f"verified_connections.md written. Active tools: {VERIFIED_NAMES}")

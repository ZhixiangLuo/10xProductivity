"""
Generate verified_connections.md from verified_connections.example.md.

Edit VERIFIED_NAMES below to include only tools whose Verify command
you actually ran and confirmed with real output, then run this script.
"""
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
    # Personal tools (personal/):
    # "my-internal-tool",
]


def tool_slug(name):
    return name.lower().replace(" ", "-").replace("/", "-")


def is_verified_section(chunk):
    m = re.match(r"^##\s+(\S+)", chunk.strip())
    if not m:
        return False
    slug = tool_slug(m.group(1))
    return any(v in slug or slug in v for v in VERIFIED_NAMES)


def filter_table_rows(text):
    lines = text.splitlines()
    out = []
    in_table = False
    for line in lines:
        if "| Tool" in line or line.startswith("|---"):
            in_table = True
            out.append(line)
        elif in_table and line.startswith("|"):
            tool_m = re.search(r"\*\*(.+?)\*\*", line)
            if tool_m:
                slug = tool_slug(tool_m.group(1))
                if any(v in slug or slug in v for v in VERIFIED_NAMES):
                    out.append(line)
        else:
            in_table = False
            out.append(line)
    return "\n".join(out)


example = Path("verified_connections.example.md").read_text()
chunks = re.split(r"\n---\n", example)

header_chunks, section_chunks = [], []
for chunk in chunks:
    (section_chunks if re.match(r"^##\s+\w", chunk.strip()) else header_chunks).append(chunk)

filtered_header = "\n---\n".join(
    filter_table_rows(c) if "| Tool" in c else c for c in header_chunks
)
verified_sections = [c for c in section_chunks if is_verified_section(c)]

output = filtered_header
if verified_sections:
    output += "\n---\n" + "\n---\n".join(verified_sections)

tool_list = ", ".join(VERIFIED_NAMES) if VERIFIED_NAMES else "none"
output = re.sub(
    r"(description: ).*?(\n)",
    lambda m_: m_.group(1) + f"Your active tool connections — verified and ready. Covers: {tool_list}. Load at session start." + m_.group(2),
    output, count=1
)
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
    flags=re.DOTALL
)

Path("verified_connections.md").write_text(output)
print(f"verified_connections.md written. Active tools: {VERIFIED_NAMES}")

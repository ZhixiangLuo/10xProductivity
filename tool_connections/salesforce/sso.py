"""
Salesforce SSO — captures sid cookie from {your-org}.my.salesforce.com via Playwright.
Writes SF_SID to .env. Token lifetime varies by org (Setup → Session Settings, default 2–8h).

Reads credentials from .env:
    SF_USERNAME=you@example.com
    SF_PASSWORD=yourpassword
    SF_BASE_URL=https://your-org.my.salesforce.com

Usage:
    source .venv/bin/activate
    python3 tool_connections/salesforce/sso.py           # capture & save
    python3 tool_connections/salesforce/sso.py --check   # verify existing token
    python3 tool_connections/salesforce/sso.py --force   # force re-capture even if valid
"""

import asyncio
import sys
from pathlib import Path

ENV_FILE = Path(__file__).parent.parent.parent / ".env"


def load_env():
    env = {}
    if ENV_FILE.exists():
        for line in ENV_FILE.read_text().splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, _, v = line.partition("=")
                env[k.strip()] = v.strip()
    return env


def get_credentials(env: dict) -> tuple[str, str, str]:
    """Return (username, password, base_url), prompting for anything missing."""
    username = env.get("SF_USERNAME", "").strip()
    password = env.get("SF_PASSWORD", "").strip()
    base_url = env.get("SF_BASE_URL", "").strip()

    if not username:
        username = input("Salesforce username (e.g. you@example.com): ").strip()
    if not password:
        import getpass
        password = getpass.getpass("Salesforce password: ")
    if not base_url:
        base_url = input("Org base URL (e.g. https://your-org.my.salesforce.com): ").strip()

    return username, password, base_url


def check(env: dict) -> bool:
    """Return True if existing SF_SID is still valid."""
    import urllib.request
    sid = env.get("SF_SID", "")
    base_url = env.get("SF_BASE_URL", "")
    if not sid or not base_url:
        return False
    try:
        req = urllib.request.Request(
            f"{base_url}/services/oauth2/userinfo",
            headers={"Authorization": f"Bearer {sid}"},
        )
        with urllib.request.urlopen(req, timeout=10) as resp:
            return resp.status == 200
    except Exception:
        return False


def update_env(key: str, value: str):
    """Upsert a key=value line in .env."""
    lines = ENV_FILE.read_text().splitlines() if ENV_FILE.exists() else []
    found = False
    new_lines = []
    for line in lines:
        if line.startswith(f"{key}=") or line.startswith(f"{key} ="):
            new_lines.append(f"{key}={value}")
            found = True
        else:
            new_lines.append(line)
    if not found:
        new_lines.append(f"{key}={value}")
    ENV_FILE.write_text("\n".join(new_lines) + "\n")


async def capture(username: str, password: str, base_url: str) -> dict:
    from playwright.async_api import async_playwright

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=False, slow_mo=300)
        context = await browser.new_context()
        page = await context.new_page()

        print("Opening Salesforce login...")
        await page.goto("https://login.salesforce.com")
        await page.fill("#username", username)
        await page.fill("#password", password)
        await page.click("#Login")

        # Wait for redirect to the org
        await page.wait_for_url("**salesforce.com**", timeout=30000)
        # Give extra time for all cookies to be set
        await asyncio.sleep(3)

        cookies = await context.cookies([base_url])
        sid = next((c["value"] for c in cookies if c["name"] == "sid"), None)

        await browser.close()

        if not sid:
            raise RuntimeError(
                "sid cookie not found after login — check credentials or SF_BASE_URL "
                "(must be https://your-org.my.salesforce.com, not lightning.force.com)"
            )

        return {"SF_SID": sid, "SF_BASE_URL": base_url, "SF_USERNAME": username}


def main():
    env = load_env()

    if "--check" in sys.argv:
        if check(env):
            print("✓ SF_SID is valid")
            sys.exit(0)
        else:
            print("✗ SF_SID is missing or expired — run without --check to refresh")
            sys.exit(1)

    if check(env) and "--force" not in sys.argv:
        print("✓ Existing SF_SID still valid — skipping capture (use --force to override)")
        sys.exit(0)

    username, password, base_url = get_credentials(env)
    result = asyncio.run(capture(username, password, base_url))

    update_env("SF_SID", result["SF_SID"])
    update_env("SF_BASE_URL", result["SF_BASE_URL"])
    update_env("SF_USERNAME", result["SF_USERNAME"])

    print(f"✓ SF_SID saved to .env (first 40 chars): {result['SF_SID'][:40]}...")
    print(f"✓ SF_BASE_URL: {result['SF_BASE_URL']}")


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""
Outlook Live token refresher via Playwright CDP network interception.

Opens a headed Chromium window using the saved Outlook browser profile
(~/.browser_automation/outlook_profile/), navigates to Outlook inbox,
and captures the Bearer token Outlook's own web app sends to
outlook.live.com — then verifies it works against the OWA REST API.

The captured token is written to OUTLOOK_ACCESS_TOKEN in .env (~1h TTL).
No Azure app registration required. No manual copy-paste.

Usage:
    python3 tool_connections/outlook/get_outlook_token.py

    # Specify a different .env file:
    python3 tool_connections/outlook/get_outlook_token.py --env-file /path/to/.env

Requirements:
    pip install playwright && playwright install chromium
    (playwright is already installed if you've run playwright_sso.py before)

First-time setup:
    Run once with a regular Chromium browser to log in to outlook.live.com,
    using the profile at ~/.browser_automation/outlook_profile/.
    The profile persists the session so subsequent runs are silent.
"""

import argparse
import asyncio
import json
import os
import re
import ssl
import sys
import urllib.error
import urllib.request
from pathlib import Path

try:
    from playwright.async_api import async_playwright
except ImportError:
    print("ERROR: playwright not installed. Run: pip install playwright && playwright install chromium")
    sys.exit(1)

sys.path.insert(0, str(Path(__file__).parents[2] / "tool_connections"))
from shared_utils.browser import BROWSER_AUTOMATION_DIR

OUTLOOK_PROFILE = BROWSER_AUTOMATION_DIR / "outlook_profile"
ENV_KEY = "OUTLOOK_ACCESS_TOKEN"
VERIFY_URL = "https://outlook.office.com/api/v2.0/me/messages?$top=1&$select=Subject"


def _find_env_file(explicit: str | None) -> Path:
    if explicit:
        return Path(explicit)
    for candidate in [Path(".env"), Path(__file__).parent.parent.parent / ".env"]:
        if candidate.exists():
            return candidate
    return Path(".env")


def _update_env(env_path: Path, token: str) -> None:
    content = env_path.read_text() if env_path.exists() else ""
    new_line = f"{ENV_KEY}={token}"
    if ENV_KEY + "=" in content:
        content = re.sub(rf"^{ENV_KEY}=.*$", new_line, content, flags=re.MULTILINE)
    else:
        if content and not content.endswith("\n"):
            content += "\n"
        content += (
            "\n# --- Outlook Live (personal Microsoft account) ---\n"
            "# ~1h TTL — refresh with: python3 tool_connections/outlook/get_outlook_token.py\n"
            f"{new_line}\n"
        )
    env_path.write_text(content)


def _verify_token(token: str) -> bool:
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE
    req = urllib.request.Request(VERIFY_URL, headers={"Authorization": f"Bearer {token}"})
    try:
        with urllib.request.urlopen(req, context=ctx, timeout=10) as r:
            return r.status == 200
    except Exception:
        return False


async def _capture_token(headless: bool = False) -> str | None:
    OUTLOOK_PROFILE.mkdir(parents=True, exist_ok=True)
    for lock in ["SingletonLock", "SingletonCookie", "SingletonSocket"]:
        lp = OUTLOOK_PROFILE / lock
        if lp.exists():
            lp.unlink()

    captured: dict = {}

    async with async_playwright() as p:
        ctx = await p.chromium.launch_persistent_context(
            str(OUTLOOK_PROFILE),
            headless=headless,
            args=["--window-size=900,700", "--window-position=100,100"],
        )
        page = await ctx.new_page()
        cdp = await ctx.new_cdp_session(page)
        await cdp.send("Network.enable")

        def on_request(event: dict) -> None:
            if captured:
                return
            headers = event.get("request", {}).get("headers", {})
            auth = headers.get("Authorization", headers.get("authorization", ""))
            url = event.get("request", {}).get("url", "")
            if (
                auth.startswith("Bearer ")
                and len(auth) > 200
                and "outlook.live.com" in url
            ):
                captured["token"] = auth[7:]
                captured["url"] = url

        cdp.on("Network.requestWillBeSent", on_request)

        print("Opening Outlook inbox...")
        try:
            await page.goto(
                "https://outlook.live.com/mail/inbox",
                wait_until="domcontentloaded",
                timeout=30_000,
            )
        except Exception as e:
            print(f"Navigation error: {e}")

        # Wait up to 30s for a token-bearing request
        for i in range(30):
            await asyncio.sleep(1)
            if captured:
                break
            # Nudge: navigate to another folder to trigger fresh API calls
            if i == 12:
                print("  No token yet — navigating to sent items to trigger API call...")
                try:
                    await page.goto(
                        "https://outlook.live.com/mail/sentitems",
                        wait_until="domcontentloaded",
                        timeout=10_000,
                    )
                except Exception:
                    pass
            if i == 20:
                print("  Navigating back to inbox...")
                try:
                    await page.goto(
                        "https://outlook.live.com/mail/inbox",
                        wait_until="domcontentloaded",
                        timeout=10_000,
                    )
                except Exception:
                    pass

        if not captured:
            print(
                "\nNot logged in — a browser window is open. Please:\n"
                "  1. Sign in to outlook.live.com in the browser window.\n"
                "  2. After sign-in the script will capture the token automatically.\n"
                "  Waiting up to 3 more minutes for login..."
            )
            for _ in range(180):
                await asyncio.sleep(1)
                if captured:
                    break

        await ctx.close()

    return captured.get("token")


def main() -> None:
    parser = argparse.ArgumentParser(description="Refresh OUTLOOK_ACCESS_TOKEN in .env")
    parser.add_argument("--env-file", help="Path to .env file (default: auto-detect)")
    parser.add_argument("--headless", action="store_true", help="Run browser headlessly")
    args = parser.parse_args()

    env_path = _find_env_file(args.env_file)
    print(f"Target .env: {env_path.resolve()}")

    token = asyncio.run(_capture_token(headless=args.headless))

    if not token:
        print("\nERROR: No Bearer token captured from Outlook session.")
        print("Make sure you're logged in to outlook.live.com in the Chromium profile at:")
        print(f"  {OUTLOOK_PROFILE}")
        sys.exit(1)

    print(f"\nToken captured (len={len(token)}). Verifying...")
    if not _verify_token(token):
        print("WARNING: Token captured but API verification returned non-200.")
        print("This may mean the token is scoped to a different resource.")
        print("Writing to .env anyway — it may still work for some operations.")
    else:
        print("Verification OK — token works against OWA REST API.")

    _update_env(env_path, token)
    print(f"Written {ENV_KEY} to {env_path}")


if __name__ == "__main__":
    main()

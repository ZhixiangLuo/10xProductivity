import importlib.util
from pathlib import Path


MODULE_PATH = (
    Path(__file__).parents[1]
    / "tool_connections"
    / "google-ai-mode"
    / "google_ai_mode.py"
)
SPEC = importlib.util.spec_from_file_location("google_ai_mode", MODULE_PATH)
google_ai_mode = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(google_ai_mode)


def test_run_turns_refuses_contextual_followup_until_verified(monkeypatch):
    class Page:
        def goto(self, *args, **kwargs):
            raise RuntimeError("ERR_ABORTED")

    class Context:
        pages = []

        def new_page(self):
            return Page()

    class Browser:
        contexts = [Context()]

    class Chromium:
        def connect_over_cdp(self, url):
            return Browser()

    class Playwright:
        chromium = Chromium()

    recovered = {
        "query": "initial",
        "lines": ["answer"],
        "url": "https://www.google.com/search?udm=50&mtid=thread-id",
    }
    monkeypatch.setattr(google_ai_mode, "_recover_query_webview", lambda *args: recovered)

    try:
        google_ai_mode._run_turns(Playwright(), 9222, "initial", ["follow-up"], "https://google.com")
    except RuntimeError as exc:
        assert "follow-ups are not supported" in str(exc)
    else:
        raise AssertionError("contextual-task follow-up should not be submitted without live evidence")

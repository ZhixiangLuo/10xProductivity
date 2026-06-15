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


def test_submit_contextual_followup_uses_native_composer(monkeypatch):
    calls = []

    class Textbox:
        def fill(self, value, timeout):
            calls.append(("fill", value, timeout))

        def press(self, key):
            calls.append(("press", key))

    class Page:
        def locator(self, selector):
            calls.append(("locator", selector))
            return Textbox()

    expected = {"query": "follow-up", "lines": ["answer"], "url": "thread"}
    monkeypatch.setattr(
        google_ai_mode,
        "_recover_contextual_followup",
        lambda browser, mtid, followup: expected,
    )

    result = google_ai_mode._submit_contextual_followup(
        Page(),
        object(),
        "https://www.google.com/search?udm=50&mtid=thread-id",
        "follow-up",
    )

    assert result == expected
    assert calls == [
        ("locator", 'textarea[placeholder="Ask anything"]'),
        ("fill", "follow-up", 10_000),
        ("press", "Enter"),
    ]

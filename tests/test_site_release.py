"""Keep the public landing page aligned with shipped hub behavior."""

from html.parser import HTMLParser
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PAGE = ROOT / "site/public/index.html"


class Links(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.hrefs: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag == "a":
            self.hrefs.extend(value for key, value in attrs if key == "href" and value is not None)


def test_site_links_to_release_and_user_journeys() -> None:
    page = PAGE.read_text(encoding="utf-8")
    links = Links()
    links.feed(page)
    assert "https://pypi.org/project/agent-session-hub/0.3.0/" in links.hrefs
    prefix = "https://github.com/avidullu/agent-sessions/blob/main/"
    for doc in ("docs/BASELINE_USER_GUIDE.md", "docs/PRODUCT_DIRECTION.md", "docs/GETTING_STARTED.md"):
        assert prefix + doc in links.hrefs
    for link in links.hrefs:
        if link.startswith(prefix):
            assert (ROOT / link.removeprefix(prefix).split("#", 1)[0]).is_file()


def test_site_does_not_advertise_pending_release_or_silent_learning() -> None:
    page = PAGE.read_text(encoding="utf-8")
    assert "agent-archive init" in page
    assert "agent-archive status --json" in page
    assert "until 0.3.0 is published" not in page
    assert "opt-in" in page
    assert "not shipped" in page
    assert "private workspace" in page
    assert "Extracted from 3 sessions" not in page

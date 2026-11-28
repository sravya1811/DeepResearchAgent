"""Source tracking and citation handling for a research run.

Sources are recorded in code by the search tool. The model only ever sees and writes numeric
ids like [3]; the URL for each id always comes from the registry, so it cannot be invented.
"""

import logging
import re
from urllib.parse import urlsplit, urlunsplit

from pydantic import BaseModel

logger = logging.getLogger(__name__)


class Source(BaseModel):
    id: int
    title: str
    url: str
    snippet: str = ""
    query: str = ""


def normalize_url(url: str) -> str:
    """Normalise a URL so trivially different forms of the same page share one id."""
    parts = urlsplit(url.strip())
    path = parts.path.rstrip("/")
    return urlunsplit((parts.scheme.lower(), parts.netloc.lower(), path, parts.query, ""))


class SourceRegistry:
    """All sources found during one research run, with stable numeric ids starting at 1."""

    def __init__(self) -> None:
        self._sources: list[Source] = []
        self._by_url: dict[str, Source] = {}

    def add(self, title: str, url: str, snippet: str = "", query: str = "") -> Source:
        key = normalize_url(url)
        existing = self._by_url.get(key)
        if existing is not None:
            return existing
        source = Source(id=len(self._sources) + 1, title=title or url, url=url, snippet=snippet, query=query)
        self._sources.append(source)
        self._by_url[key] = source
        return source

    def get(self, source_id: int) -> Source | None:
        if 1 <= source_id <= len(self._sources):
            return self._sources[source_id - 1]
        return None

    @property
    def sources(self) -> list[Source]:
        return list(self._sources)

    def __len__(self) -> int:
        return len(self._sources)


def format_results_for_agent(sources: list[Source]) -> str:
    """Render search results for the model, labelled by id. URLs are deliberately left out."""
    if not sources:
        return "No results found."
    return "\n\n".join(f"[{s.id}] {s.title}\n{s.snippet}" for s in sources)


# [3] or [1, 4] — but not a markdown link like [3](url) or a footnote like [^1].
CITATION_RE = re.compile(r"\[(\d+(?:\s*,\s*\d+)*)\](?!\()")
# A references-style heading the model may have written despite instructions.
REFERENCES_HEADING_RE = re.compile(
    r"^#{1,6}\s*(references|sources|bibliography|works cited)\s*:?\s*$",
    re.IGNORECASE | re.MULTILINE,
)


REMOVED = "\x00"  # placeholder for a citation group whose ids were all invalid


def _escape_link_text(text: str) -> str:
    return text.replace("[", "\\[").replace("]", "\\]")


def finalize_report(markdown: str, registry: SourceRegistry) -> tuple[str, list[Source]]:
    """Turn [n] citations into links and append a References section.

    - removes any references section the model wrote itself
    - drops citations to ids that don't exist in the registry
    - renumbers citations 1, 2, 3... in order of first use
    - links each citation to its source URL
    - lists only the cited sources under "## References"

    Returns the final markdown and the cited sources in their new order.
    """
    heading = REFERENCES_HEADING_RE.search(markdown)
    if heading:
        markdown = markdown[: heading.start()].rstrip()

    new_number: dict[int, int] = {}
    cited: list[Source] = []

    def replace(match: re.Match) -> str:
        links = []
        for raw in match.group(1).split(","):
            old_id = int(raw)
            source = registry.get(old_id)
            if source is None:
                logger.warning("Dropping citation to unknown source [%d]", old_id)
                continue
            if old_id not in new_number:
                new_number[old_id] = len(cited) + 1
                cited.append(source)
            links.append(f"[[{new_number[old_id]}]]({source.url})")
        return "".join(links) if links else REMOVED

    body = CITATION_RE.sub(replace, markdown)
    # Remove placeholders for dropped citations along with the space before them ("word [99]." -> "word.").
    body = re.sub(rf"[ \t]*{REMOVED}", "", body)

    if not cited:
        return body, []

    references = "\n".join(
        f"{i}. [{_escape_link_text(s.title)}]({s.url})" for i, s in enumerate(cited, start=1)
    )
    return f"{body}\n\n## References\n\n{references}\n", cited

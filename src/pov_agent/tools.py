"""Docs-search tools over the bundled platform docs corpus (``src/pov_agent/platform_docs``).

Plain keyword scoring over ``## `` sections: deterministic, offline, and free, so the
same question retrieves the same passages locally and in CI. Swap in a vector store
when you point the agent at a real docs export.
"""

import math
import re
from collections import Counter
from functools import lru_cache
from pathlib import Path

from langchain_core.tools import tool

DOCS_DIR = Path(__file__).parent / "platform_docs"

_TOKEN_RE = re.compile(r"[a-z0-9]+")
_STOPWORDS = {
    "a", "an", "and", "are", "as", "at", "be", "can", "do", "for", "from", "how", "i", "in",
    "is", "it", "my", "of", "on", "or", "the", "to", "what", "when", "where", "with", "you",
    "your", "me", "we", "our", "this", "that", "does", "why", "which", "there", "so",
}


def _tokens(text: str) -> list[str]:
    return [t for t in _TOKEN_RE.findall(text.lower()) if t not in _STOPWORDS]


@lru_cache(maxsize=1)
def _load_corpus() -> tuple[dict[str, tuple[str, str]], list[dict]]:
    """Return ({doc_id: (title, full_text)}, [section dicts])."""
    docs, sections = {}, []
    for path in sorted(DOCS_DIR.glob("*.md")):
        if path.name == "README.md":
            continue
        doc_id = path.stem
        text = path.read_text()
        title_match = re.search(r"^# (.+)$", text, re.MULTILINE)
        title = title_match.group(1).strip() if title_match else doc_id
        docs[doc_id] = (title, text)
        for chunk in re.split(r"^## ", text, flags=re.MULTILINE)[1:]:
            heading, _, body = chunk.partition("\n")
            sections.append({
                "doc_id": doc_id,
                "title": title,
                "heading": heading.strip(),
                "body": body.strip(),
                "tokens": Counter(_tokens(f"{title} {heading} {heading} {body}")),
            })
    return docs, sections


def search_docs(query: str, k: int = 4) -> list[dict]:
    """Rank sections by idf-weighted term overlap with the query. Pure function."""
    _, sections = _load_corpus()
    n = len(sections)
    df = Counter(t for s in sections for t in s["tokens"])
    q = set(_tokens(query))
    scored = []
    for s in sections:
        score = sum(math.log(1 + n / df[t]) * (1 + math.log(s["tokens"][t])) for t in q if t in s["tokens"])
        if score > 0:
            scored.append((score, s))
    scored.sort(key=lambda x: -x[0])
    return [s for _, s in scored[:k]]


@tool
def search_platform_docs(query: str) -> str:
    """Search the Nimbus AI Platform / Nimbus Workbench documentation.

    Returns the most relevant doc sections, each tagged with its doc_id. Use specific
    keywords (e.g. "model serving deployment token", "notebook shared storage", "pod pending GPU").
    """
    hits = search_docs(query)
    if not hits:
        return "No matching documentation found. Try different keywords."
    return "\n\n---\n\n".join(
        f"[doc_id: {h['doc_id']}] {h['title']} > {h['heading']}\n{h['body']}" for h in hits
    )


@tool
def read_platform_doc(doc_id: str) -> str:
    """Read one full platform documentation page by its doc_id (as returned by search_platform_docs)."""
    docs, _ = _load_corpus()
    if doc_id not in docs:
        return f"Unknown doc_id '{doc_id}'. Available: {', '.join(sorted(docs))}"
    return docs[doc_id][1]


TOOLS = [search_platform_docs, read_platform_doc]


def _demo() -> None:
    assert search_docs("where do I save notebook files so my team can see them")[0]["doc_id"] == "notebooks"
    assert search_docs("model serving endpoint API token 401")[0]["doc_id"] == "model-serving"
    assert search_docs("pod stuck pending GPU quota")[0]["doc_id"] == "gpus-and-troubleshooting"
    assert search_docs("import helm chart values.yaml virtualService")[0]["doc_id"] == "import-framework"
    print("tools self-check passed")


if __name__ == "__main__":
    _demo()

from __future__ import annotations
import re
from pathlib import Path
from .models import ResearchRequest, ResearchSource

class ResearchAdapter:
    def search(self, request: ResearchRequest) -> list[ResearchSource]:
        raise NotImplementedError

class DisabledResearchAdapter(ResearchAdapter):
    def search(self, request):
        return []

PROJECT_ROOT = Path(__file__).resolve().parents[1]


class LocalKnowledgeAdapter(ResearchAdapter):
    """Simple offline source lookup for bundled/local notes.

    This is intentionally not presented as web evidence. It is useful for
    curriculum notes, curated sources, or user-supplied reference material.
    """
    def __init__(self, root="data/knowledge"):
        path = Path(root)
        self.root = path if path.is_absolute() else PROJECT_ROOT / path

    def search(self, request):
        if not self.root.exists():
            return []
        terms = [t.lower() for t in re.findall(r"[\wÀ-ÿ]+", request.query) if len(t) > 2]
        hits = []
        for path in self.root.rglob("*"):
            if not path.is_file() or path.suffix.lower() not in {".md", ".txt"}:
                continue
            text = path.read_text(encoding="utf-8", errors="ignore")
            score = sum(text.lower().count(t) for t in terms)
            if score:
                excerpt = text[:1200].replace("\n", " ")
                hits.append((score, ResearchSource(
                    title=path.stem,
                    url=str(path),
                    excerpt=excerpt,
                    source_type="local_knowledge"
                )))
        hits.sort(key=lambda x: x[0], reverse=True)
        return [item for _, item in hits[:5]]

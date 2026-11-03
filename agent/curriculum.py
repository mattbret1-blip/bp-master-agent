from __future__ import annotations

import json
from pathlib import Path

from .models import CompetencyNode

PROJECT_ROOT = Path(__file__).resolve().parents[1]


def load_graph(path=None):
    source = Path(path) if path else PROJECT_ROOT / "data" / "seeds" / "curriculum.json"
    raw = json.loads(source.read_text(encoding="utf-8"))
    return {n["id"]: CompetencyNode(**n) for n in raw["nodes"]}


def hydrate(existing, path=None):
    graph = load_graph(path)
    for node_id, saved in existing.items():
        if node_id in graph:
            graph[node_id] = CompetencyNode.model_validate(saved)
    return graph


def prerequisites_met(graph, node_id, threshold=0.65):
    return all(
        p in graph and graph[p].mastery >= threshold
        for p in graph[node_id].prerequisites
    )


def next_candidates(graph, limit=6):
    candidates = [
        n for n in graph.values()
        if n.mastery < 0.80 and prerequisites_met(graph, n.id)
    ]
    candidates.sort(key=lambda n: (n.confidence, n.mastery))
    return candidates[:limit]

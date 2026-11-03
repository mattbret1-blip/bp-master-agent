import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from agent.config import Settings
from agent.db import Database
from agent.core import BrazilianPortugueseAgent
from agent.models import ReviewItem


class FakeAdapter:
    def __init__(self):
        self.calls = 0

    def generate_structured(self, system, messages, schema, schema_name):
        self.calls += 1
        if schema_name == "route_decision":
            return {
                "mode": "lesson",
                "specialists": ["tutor", "linguist"],
                "goal": "build a greeting",
                "obstacle": None,
                "context": "everyday conversation",
                "focus": "greetings",
                "reason": "user asks for practice",
            }
        if schema_name == "agent_decision":
            return {
                "mode": "lesson",
                "goal": "build a greeting",
                "obstacle": None,
                "context": "everyday conversation",
                "focus": "greetings",
                "next_action": "practice",
                "response": "Vamos praticar: diga ‘Oi, tudo bem?’ em um contexto real.",
                "evidence": [{
                    "evidence_id": "e1",
                    "domain": "speaking",
                    "concept_id": "a1_greetings",
                    "evidence": "The learner requested focused greeting practice.",
                    "status": "Inferido",
                    "interpretation": "Interest, not demonstrated mastery.",
                    "confidence": 0.4,
                    "limitation": "No productive response yet.",
                    "mastery_stage": None,
                    "source": "conversation",
                }],
                "state_updates": [{
                    "update_type": "add_reinforce",
                    "payload": {"concept": "greetings"},
                }],
                "review_candidates": [],
                "research_requests": [],
                "summary": {"Aprendido": [], "Reforçar": ["greetings"]},
                "certainty_note": "Initial evidence only.",
            }
        if schema_name == "quality_report":
            return {"pass_gate": True, "issues": [], "revised_response": None}
        raise AssertionError(schema_name)


def test_db_and_migrations():
    with tempfile.TemporaryDirectory() as td:
        db = Database(str(Path(td) / "x.db"))
        s = db.load_state()
        s.learner.goals.append("conversation")
        db.save_state(s)
        assert db.load_state().learner.goals == ["conversation"]
        versions = [r["version"] for r in db.conn.execute("SELECT version FROM schema_migrations")]
        assert versions == [1]


def test_agent():
    with tempfile.TemporaryDirectory() as td:
        db = Database(str(Path(td) / "agent.db"))
        agent = BrazilianPortugueseAgent(FakeAdapter(), "fake", db)
        opening = agent.opening_diagnostic()
        assert "Vamos começar." in opening
        answer = agent.respond("Quero aprender cumprimentos.")
        assert "Oi, tudo bem?" in answer
        assert agent.state.current_session.turn_count == 1
        assert "greetings" in agent.state.learner.reinforce


def test_graph_and_scheduler():
    from agent.curriculum import hydrate, next_candidates
    from agent.scheduler import schedule

    graph = hydrate({})
    assert len(graph) >= 10
    assert next_candidates(graph, 5)
    item = ReviewItem(item_id="x", kind="grammar", prompt="teste", due_at="2000-01-01T00:00:00")
    item = schedule(item, 4)
    assert item.interval_days == 1


def test_settings_validation():
    settings = Settings(
        ai_provider="openai",
        state_path="data/learner.db",
        openai_model=None,
    )
    missing = settings.validate_provider_credentials("openai")
    assert "OPENAI_API_KEY" in missing
    assert "OPENAI_MODEL" in missing

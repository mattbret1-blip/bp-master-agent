"""True multi-agent orchestration, tested offline with a fake adapter.

No API keys, no network: the fake returns canned RouteDecision /
specialist outputs / synthesis decisions, and records every call so the
tests can prove each routed specialist got its own structured call.
"""
import sys
import tempfile
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from agent.core import BrazilianPortugueseAgent
from agent.db import Database
from agent.models import AgentDecision
from agent.specialists import SpecialistTeam

ASSESSOR_EVIDENCE = {
    "evidence_id": "assess-e1",
    "domain": "speaking",
    "concept_id": "a1_greetings",
    "evidence": "The learner produced 'Oi, tudo bem?' correctly once.",
    "status": "Observado",
    "interpretation": "One correct production; not durable mastery.",
    "confidence": 0.5,
    "limitation": "Single observation.",
    "mastery_stage": "Recognition",
    "source": "conversation",
}


class FakeMultiAdapter:
    """Canned route + specialist + synthesis decisions.

    The synthesis decision deliberately OMITS the assessor's evidence:
    that proves the team's merge step carries assessor evidence into the
    final decision instead of silently dropping it.
    """

    def __init__(self, specialists=("tutor", "linguist", "assessor"), mode="lesson"):
        self.specialists = list(specialists)
        self.mode = mode
        self.calls = []  # (schema_name, system_prompt, messages)

    def generate_structured(self, system, messages, schema, schema_name):
        self.calls.append((schema_name, system, messages))
        if schema_name == "route_decision":
            return {
                "mode": self.mode,
                "specialists": list(self.specialists),
                "goal": "build a greeting",
                "obstacle": None,
                "context": "everyday conversation",
                "focus": "greetings",
                "reason": "user asks for practice",
            }
        if schema_name == "assessor_output":
            return {
                "contribution": "One correct greeting observed; mastery not established.",
                "evidence": [ASSESSOR_EVIDENCE],
                "state_updates": [],
                "review_candidates": [],
            }
        if schema_name.endswith("_output"):
            return {
                "contribution": f"{schema_name} contribution.",
                "state_updates": [],
                "review_candidates": [],
            }
        if schema_name == "agent_decision":
            return {
                "mode": self.mode,
                "goal": "build a greeting",
                "obstacle": None,
                "context": "everyday conversation",
                "focus": "greetings",
                "next_action": "practice",
                "response": "Synthesized team reply: diga 'Oi, tudo bem?'",
                "evidence": [],
                "state_updates": [],
                "review_candidates": [],
                "research_requests": [],
                "summary": {},
                "certainty_note": "Synthesized from specialist outputs.",
            }
        raise AssertionError(schema_name)

    def schema_names(self):
        return [c[0] for c in self.calls]

    def system_for(self, schema_name):
        return next(system for name, system, _ in self.calls if name == schema_name)


class FakeSingleAdapter:
    """The original single-call path: route + one agent_decision."""

    def __init__(self):
        self.calls = []

    def generate_structured(self, system, messages, schema, schema_name):
        self.calls.append(schema_name)
        if schema_name == "route_decision":
            return {
                "mode": "lesson",
                "specialists": ["tutor"],
                "goal": None,
                "obstacle": None,
                "context": None,
                "focus": None,
                "reason": "single-call path",
            }
        if schema_name == "agent_decision":
            return {
                "mode": "lesson",
                "goal": None,
                "obstacle": None,
                "context": None,
                "focus": None,
                "next_action": "practice",
                "response": "Single-call reply.",
                "evidence": [],
                "state_updates": [],
                "review_candidates": [],
                "research_requests": [],
                "summary": {},
                "certainty_note": "",
            }
        raise AssertionError(schema_name)


def test_each_routed_specialist_invoked_once_with_own_call(monkeypatch):
    adapter = FakeMultiAdapter()
    with tempfile.TemporaryDirectory() as td:
        monkeypatch.setenv("MULTI_AGENT", "true")
        agent = BrazilianPortugueseAgent(
            adapter, "fake", Database(str(Path(td) / "agent.db"))
        )
        agent.respond("Quero aprender cumprimentos.")
    names = adapter.schema_names()
    assert names[0] == "route_decision"
    for specialist in ("tutor", "linguist", "assessor"):
        assert names.count(f"{specialist}_output") == 1, names
    # Manager synthesis runs exactly once, after all specialists.
    assert names.count("agent_decision") == 1
    assert names.index("agent_decision") > names.index("assessor_output")


def test_assessor_evidence_reaches_state_but_no_mastery(monkeypatch):
    adapter = FakeMultiAdapter()
    with tempfile.TemporaryDirectory() as td:
        monkeypatch.setenv("MULTI_AGENT", "true")
        agent = BrazilianPortugueseAgent(
            adapter, "fake", Database(str(Path(td) / "agent.db"))
        )
        agent.respond("Oi, tudo bem?")
    learner = agent.state.learner
    # Evidence survived the synthesis (which omitted it) via the merge.
    assert [e.evidence_id for e in learner.assessment_history] == ["assess-e1"]
    node = learner.competencies["a1_greetings"]
    # Evidence gate: one Observado response at 0.5 confidence adds only
    # 0.08 * 0.5 = 0.04 mastery — far from durable mastery.
    assert node.mastery == pytest.approx(0.04)
    assert node.evidence_count == 1
    assert "a1_greetings" not in learner.mastered
    # No CEFR promotion: the gate needs >= 2 evidence items.
    assert learner.cefr.speaking.level is None
    assert learner.cefr.overall is None


def test_synthesized_decision_is_pydantic_validated(monkeypatch):
    adapter = FakeMultiAdapter()
    with tempfile.TemporaryDirectory() as td:
        monkeypatch.setenv("MULTI_AGENT", "true")
        agent = BrazilianPortugueseAgent(
            adapter, "fake", Database(str(Path(td) / "agent.db"))
        )
        reply = agent.respond("Oi, tudo bem?")
    assert reply == "Synthesized team reply: diga 'Oi, tudo bem?'"
    assert isinstance(agent.state.last_decision, AgentDecision)
    assert agent.state.current_session.turn_count == 1


def test_skill_file_content_reaches_specialist_prompt(monkeypatch):
    adapter = FakeMultiAdapter(
        specialists=("linguist", "culture", "assessor")
    )
    with tempfile.TemporaryDirectory() as td:
        monkeypatch.setenv("MULTI_AGENT", "true")
        agent = BrazilianPortugueseAgent(
            adapter, "fake", Database(str(Path(td) / "agent.db"))
        )
        agent.respond("Explique o subjuntivo.")
    # Distinctive lines from the real skills/*.md files.
    assert "categorical rules" in adapter.system_for("linguist_output")
    assert "without stereotypes" in adapter.system_for("culture_output")
    assert "conservative CEFR gating" in adapter.system_for("assessor_output")


def test_mode_skill_reaches_specialist_prompt(monkeypatch):
    adapter = FakeMultiAdapter(specialists=("tutor",), mode="diagnostic")
    with tempfile.TemporaryDirectory() as td:
        monkeypatch.setenv("MULTI_AGENT", "true")
        agent = BrazilianPortugueseAgent(
            adapter, "fake", Database(str(Path(td) / "agent.db"))
        )
        agent.respond("Quero começar.")
    assert "separate observation from inference" in adapter.system_for("tutor_output")


def test_single_call_path_still_works_when_flag_off(monkeypatch):
    adapter = FakeSingleAdapter()
    with tempfile.TemporaryDirectory() as td:
        monkeypatch.setenv("MULTI_AGENT", "false")
        agent = BrazilianPortugueseAgent(
            adapter, "fake", Database(str(Path(td) / "agent.db"))
        )
        reply = agent.respond("Quero aprender cumprimentos.")
    assert reply == "Single-call reply."
    assert adapter.calls == ["route_decision", "agent_decision"]


def test_missing_skill_files_degrade_gracefully(monkeypatch):
    adapter = FakeMultiAdapter(specialists=("linguist", "assessor"))
    team = SpecialistTeam(adapter, "AGENT", project_root="/nonexistent-root")
    from agent.models import RouteDecision

    decision = team.run(
        RouteDecision(
            mode="lesson", specialists=["linguist", "assessor"], reason="x"
        ),
        {"learner": {}, "session": {}},
        "Oi, tudo bem?",
        [],
    )
    assert isinstance(decision, AgentDecision)
    assert decision.response.startswith("Synthesized team reply")
    assert [e.evidence_id for e in decision.evidence] == ["assess-e1"]


def test_empty_specialist_list_defaults_to_tutor(monkeypatch):
    adapter = FakeMultiAdapter(specialists=())
    with tempfile.TemporaryDirectory() as td:
        monkeypatch.setenv("MULTI_AGENT", "true")
        agent = BrazilianPortugueseAgent(
            adapter, "fake", Database(str(Path(td) / "agent.db"))
        )
        agent.respond("Oi.")
    assert adapter.schema_names().count("tutor_output") == 1
    assert adapter.schema_names().count("agent_decision") == 1

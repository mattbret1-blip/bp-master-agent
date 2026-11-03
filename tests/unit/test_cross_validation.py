"""Synthesize + cross-validate + revalidate loop, tested offline.

No API keys, no network: the fake returns canned route / specialist /
synthesis / validation decisions, and records every call so the tests
can prove the loop's bounds, drops, fallback, and flag behavior.
"""
import sys
import tempfile
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from agent.core import BrazilianPortugueseAgent
from agent.db import Database

KNOWN_EVIDENCE = {
    "evidence_id": "ev-known",
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

UNKNOWN_EVIDENCE = {
    "evidence_id": "ev-unknown",
    "domain": "speaking",
    "concept_id": "no_such_concept",
    "evidence": "Claim about a competency that does not exist.",
    "status": "Observado",
    "interpretation": "Bogus.",
    "confidence": 0.9,
    "limitation": "",
    "mastery_stage": "Recognition",
    "source": "conversation",
}


def _decision(response, evidence, state_updates):
    return {
        "mode": "lesson",
        "goal": "build a greeting",
        "obstacle": None,
        "context": "everyday conversation",
        "focus": "greetings",
        "next_action": "practice",
        "response": response,
        "evidence": evidence,
        "state_updates": state_updates,
        "review_candidates": [],
        "research_requests": [],
        "summary": {},
        "certainty_note": "",
    }


# The initial synthesis: dirty on purpose — unknown-concept evidence, a
# mastery claim contradicted by a recurring error, a malformed CEFR
# proposal, a conflicting CEFR proposal, and response prose claiming
# mastery and C1 that the kept evidence does not support.
DIRTY_UPDATES = [
    {
        "update_type": "add_mastered_candidate",
        "payload": {"concept": "greetings", "evidence_backed": True},
    },
    {
        "update_type": "add_recurring_error",
        "payload": {
            "error_id": "e1", "category": "grammar", "form": "greetings",
            "correction": "", "explanation": "", "count": 1, "impact": 0.5,
        },
    },
    {
        "update_type": "update_cefr",
        "payload": {"domain": "telepathy", "level": "B2",
                    "evidence_count": 3, "confidence": 0.9},
    },
    {
        "update_type": "update_cefr",
        "payload": {"domain": "speaking", "level": "B2",
                    "evidence_count": 3, "confidence": 0.9},
    },
    {
        "update_type": "update_cefr",
        "payload": {"domain": "speaking", "level": "C1",
                    "evidence_count": 3, "confidence": 0.9},
    },
]

DIRTY_DECISION = _decision(
    "Synthesized reply. You have mastered greetings and reached C1.",
    [KNOWN_EVIDENCE, UNKNOWN_EVIDENCE],
    DIRTY_UPDATES,
)

CLEAN_DECISION = _decision(
    "Corrected reply: diga 'Oi, tudo bem?' mais uma vez.",
    [KNOWN_EVIDENCE],
    [
        {
            "update_type": "add_recurring_error",
            "payload": {
                "error_id": "e1", "category": "grammar", "form": "greetings",
                "correction": "", "explanation": "", "count": 1, "impact": 0.5,
            },
        },
    ],
)


class FakeValidatingAdapter:
    """Canned multi-agent turn with a scenario-controlled validator.

    Scenarios for the validation_report call:
    - "pass": first report passes (deterministic drops still apply).
    - "fixable_then_pass": first report fixable, second passes — the
      re-synthesis round repairs the decision.
    - "always_fixable": every report fixable — proves the 2-round bound.
    - "raise": the validation call raises — proves graceful fallback.
    """

    def __init__(self, scenario="pass", specialists=("tutor", "assessor")):
        self.scenario = scenario
        self.specialists = list(specialists)
        self.calls = []  # (schema_name, system_prompt)
        self.synthesis_count = 0
        self.validation_count = 0

    def generate_structured(self, system, messages, schema, schema_name):
        self.calls.append((schema_name, system))
        if schema_name == "route_decision":
            return {
                "mode": "lesson",
                "specialists": list(self.specialists),
                "goal": "build a greeting",
                "obstacle": None,
                "context": "everyday conversation",
                "focus": "greetings",
                "reason": "user asks for practice",
            }
        if schema_name == "assessor_output":
            return {
                "contribution": "One correct greeting observed.",
                "evidence": [KNOWN_EVIDENCE],
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
            self.synthesis_count += 1
            if self.synthesis_count == 1:
                return DIRTY_DECISION
            return CLEAN_DECISION
        if schema_name == "validation_report":
            self.validation_count += 1
            if self.scenario == "raise":
                raise RuntimeError("validator down")
            if self.scenario == "always_fixable":
                return {
                    "verdict": "fixable",
                    "issues": [{
                        "severity": "warning", "category": "style",
                        "detail": "Still imperfect.", "affected_field": "response",
                    }],
                }
            if self.scenario == "fixable_then_pass":
                if self.validation_count == 1:
                    return {
                        "verdict": "fixable",
                        "issues": [{
                            "severity": "warning", "category": "unsupported_claim",
                            "detail": "Response overclaims mastery and C1.",
                            "affected_field": "response",
                        }],
                    }
                return {"verdict": "pass", "issues": []}
            return {"verdict": "pass", "issues": []}
        raise AssertionError(schema_name)

    def schema_names(self):
        return [c[0] for c in self.calls]

    def system_for(self, schema_name, occurrence=0):
        hits = [s for n, s in self.calls if n == schema_name]
        return hits[occurrence]


def _agent(adapter, monkeypatch, multi="true", cross="true"):
    monkeypatch.setenv("MULTI_AGENT", multi)
    monkeypatch.setenv("CROSS_VALIDATE", cross)
    td = tempfile.TemporaryDirectory()
    agent = BrazilianPortugueseAgent(
        adapter, "fake", Database(str(Path(td.name) / "agent.db"))
    )
    agent._td = td  # keep the tempdir alive for the test's duration
    return agent


def test_contradiction_and_unknown_evidence_dropped_not_applied(monkeypatch):
    adapter = FakeValidatingAdapter(scenario="pass")
    agent = _agent(adapter, monkeypatch)
    agent.respond("Oi, tudo bem?")
    learner = agent.state.learner
    # Unknown-concept evidence never reaches the assessment history.
    assert [e.evidence_id for e in learner.assessment_history] == ["ev-known"]
    # Contradiction resolved conservatively: the error (observation)
    # survives, the mastery claim (verdict) is dropped.
    assert "greetings" not in learner.mastered
    assert [e.form for e in learner.recurring_errors] == ["greetings"]
    # Malformed + conflicting CEFR proposals dropped; the kept speaking
    # B2 proposal passes the gate but clamps to one band above none: A1.
    assert learner.cefr.speaking.level == "A1"
    # Validation event logs exactly what was dropped and why.
    events = agent.export()["events"]
    validation = [e for e in events if e["kind"] == "validation"]
    assert len(validation) == 1
    import json as _json
    summary = _json.loads(validation[0]["payload"])
    assert "ev-unknown" in summary["dropped_evidence"]
    assert any("add_mastered_candidate:greetings" in u for u in summary["dropped_updates"])
    assert any("update_cefr:telepathy" in u for u in summary["dropped_updates"])
    assert summary["rounds_used"] == 1


def test_fixable_issue_corrected_by_resynthesis_round(monkeypatch):
    adapter = FakeValidatingAdapter(scenario="fixable_then_pass")
    agent = _agent(adapter, monkeypatch)
    reply = agent.respond("Oi, tudo bem?")
    assert reply == "Corrected reply: diga 'Oi, tudo bem?' mais uma vez."
    assert adapter.synthesis_count == 2  # initial + one re-synthesis
    assert agent.last_validation["rounds_used"] == 2
    assert agent.last_validation["verdict"] == "pass"
    # The repaired decision is what got applied.
    assert [e.evidence_id for e in agent.state.learner.assessment_history] == ["ev-known"]


def test_loop_terminates_after_two_rounds_when_issues_persist(monkeypatch):
    adapter = FakeValidatingAdapter(scenario="always_fixable")
    agent = _agent(adapter, monkeypatch)
    reply = agent.respond("Oi, tudo bem?")
    assert reply  # the turn still completes
    assert adapter.synthesis_count == 2  # never a third round
    assert adapter.validation_count == 2
    assert agent.last_validation["rounds_used"] == 2


def test_validation_failure_falls_back_without_breaking_turn(monkeypatch):
    adapter = FakeValidatingAdapter(scenario="raise")
    agent = _agent(adapter, monkeypatch)
    reply = agent.respond("Oi, tudo bem?")
    assert reply == "Synthesized reply. You have mastered greetings and reached C1."
    assert agent.state.current_session.turn_count == 1
    assert agent.last_validation["fallback"] is True
    events = agent.export()["events"]
    assert any(e["kind"] == "validation_fallback" for e in events)


def test_single_correct_response_still_cannot_grant_mastery(monkeypatch):
    adapter = FakeValidatingAdapter(scenario="pass")
    agent = _agent(adapter, monkeypatch)
    agent.respond("Oi, tudo bem?")
    node = agent.state.learner.competencies["a1_greetings"]
    assert node.mastery == pytest.approx(0.04)
    assert "a1_greetings" not in agent.state.learner.mastered


def test_validator_sees_specialist_contributions(monkeypatch):
    adapter = FakeValidatingAdapter(scenario="pass")
    agent = _agent(adapter, monkeypatch)
    agent.respond("Oi, tudo bem?")
    system = adapter.system_for("validation_report")
    assert "One correct greeting observed." in system
    assert "ev-known" in system


def test_flag_off_multi_agent_on_leaves_behavior_unchanged(monkeypatch):
    adapter = FakeValidatingAdapter(scenario="pass")
    agent = _agent(adapter, monkeypatch, multi="true", cross="false")
    reply = agent.respond("Oi, tudo bem?")
    assert reply.startswith("Synthesized reply.")
    assert "validation_report" not in adapter.schema_names()
    assert agent.last_validation is None
    assert agent.status()["validation"] is None
    # Nothing dropped: pre-validation behavior, verbatim.
    assert [e.evidence_id for e in agent.state.learner.assessment_history] == [
        "ev-known", "ev-unknown",
    ]


def test_flag_on_multi_agent_off_leaves_behavior_unchanged(monkeypatch):
    adapter = FakeValidatingAdapter(scenario="pass")
    agent = _agent(adapter, monkeypatch, multi="false", cross="true")
    # Single-call path needs route + agent_decision only; reuse the
    # dirty decision as the single-call answer.
    reply = agent.respond("Oi, tudo bem?")
    assert "validation_report" not in adapter.schema_names()
    assert agent.last_validation is None


def test_validation_summary_in_status_output(monkeypatch):
    adapter = FakeValidatingAdapter(scenario="fixable_then_pass")
    agent = _agent(adapter, monkeypatch)
    agent.respond("Oi, tudo bem?")
    summary = agent.status()["validation"]
    assert summary["enabled"] is True
    assert summary["rounds_used"] == 2
    assert summary["issues_found"] >= 1
    assert summary["fallback"] is False

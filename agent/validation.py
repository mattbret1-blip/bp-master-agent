"""Synthesize + cross-validate + revalidate loop for the multi-agent path.

Runs AFTER the manager's synthesis and BEFORE state application, only
when ``MULTI_AGENT=true`` and ``CROSS_VALIDATE=true``. Two layers:

1. Deterministic app-code checks (no model involved): evidence must
   reference a known competency, CEFR proposals must be well-formed,
   one turn must not contradict itself (same concept both mastered and
   flagged as a recurring error), and response prose must not claim a
   CEFR level or mastery the decision's own evidence does not support.
2. One structured LLM validation call per round, cross-checking the
   specialist contributions against each other and against the
   learner's evidence record.

Fixable issues trigger ONE re-synthesis round (max 2 synthesis rounds
total). After the final round, only the validated subset is applied:
invalid evidence items and contradictory state updates are dropped and
logged. A validation outage never breaks a tutoring turn: on adapter
error the caller falls back to the pre-validation decision and logs it.

Nothing here writes learner state. It only filters the decision that
``agent.core`` is about to apply through the existing evidence/CEFR
gates, so evidence discipline is unchanged — it can only get stricter.
"""
from __future__ import annotations

import json
import re
from typing import Literal

from pydantic import BaseModel, Field

from .models import AgentDecision, CEFRProfile

CEFR_LEVELS = {"A1", "A2", "B1", "B2", "C1", "C2"}
# CEFRProfile fields minus "overall": a proposal may not target overall
# (it is derived from the four core domains, not set directly).
CEFR_DOMAINS = set(CEFRProfile.model_fields) - {"overall"}

MAX_SYNTHESIS_ROUNDS = 2

_MASTERY_CLAIM = re.compile(
    r"(you have mastered|you've mastered|mastery (achieved|complete)|"
    r"você dominou|domínio completo|você já domina)",
    re.IGNORECASE,
)
_CEFR_TOKEN = re.compile(r"\b(A1|A2|B1|B2|C1|C2)\b")


class ValidationIssue(BaseModel):
    severity: Literal["error", "warning"] = "warning"
    category: str
    detail: str = ""
    affected_field: str = ""


class ValidationReport(BaseModel):
    verdict: Literal["pass", "fixable", "reject"] = "pass"
    issues: list[ValidationIssue] = Field(default_factory=list)


def _norm(text: str) -> str:
    return " ".join(str(text).strip().lower().split())


def deterministic_check(decision: AgentDecision, competencies: dict):
    """Drop invalid/contradictory items from a copy of the decision.

    Returns ``(filtered_decision, issues, dropped)`` where ``dropped``
    is ``{"evidence": [...ids], "updates": [...descriptions]}``.
    The input decision is never mutated.
    """
    filtered = decision.model_copy(deep=True)
    issues: list[ValidationIssue] = []
    dropped = {"evidence": [], "updates": []}

    # 1. Evidence must reference a known competency (or none at all:
    # domain-level observation without a concept_id is allowed).
    kept_evidence = []
    for ev in filtered.evidence:
        if ev.concept_id is not None and ev.concept_id not in competencies:
            issues.append(ValidationIssue(
                severity="error",
                category="unknown_competency",
                detail=f"Evidence references unknown competency {ev.concept_id!r}.",
                affected_field=f"evidence:{ev.evidence_id}",
            ))
            dropped["evidence"].append(ev.evidence_id or ev.concept_id)
        else:
            kept_evidence.append(ev)
    filtered.evidence = kept_evidence

    # 2. CEFR proposals must be well-formed; same-domain conflicts keep
    # only the first proposal.
    kept_updates = []
    seen_cefr: dict[str, str] = {}
    for update in filtered.state_updates:
        if update.update_type == "update_cefr":
            domain = str(update.payload.get("domain", ""))
            level = update.payload.get("level")
            if domain not in CEFR_DOMAINS or level not in CEFR_LEVELS:
                issues.append(ValidationIssue(
                    severity="error",
                    category="malformed_cefr",
                    detail=f"CEFR proposal has invalid domain {domain!r} or level {level!r}.",
                    affected_field=f"update_cefr:{domain}",
                ))
                dropped["updates"].append(f"update_cefr:{domain}")
                continue
            if domain in seen_cefr and seen_cefr[domain] != level:
                issues.append(ValidationIssue(
                    severity="error",
                    category="contradiction",
                    detail=(
                        f"Conflicting CEFR proposals for {domain}: "
                        f"{seen_cefr[domain]} and {level}; keeping the first."
                    ),
                    affected_field=f"update_cefr:{domain}",
                ))
                dropped["updates"].append(f"update_cefr:{domain}:{level}")
                continue
            seen_cefr[domain] = level
        kept_updates.append(update)
    filtered.state_updates = kept_updates

    # 3. One turn must not claim mastery of a concept it also flags as
    # a recurring error. The error (an observation) wins; the mastery
    # claim (a verdict) is dropped.
    mastered = {
        _norm(u.payload.get("concept", ""))
        for u in filtered.state_updates
        if u.update_type == "add_mastered_candidate" and u.payload.get("concept")
    }
    error_forms = [
        _norm(u.payload.get("form", ""))
        for u in filtered.state_updates
        if u.update_type == "add_recurring_error" and u.payload.get("form")
    ]
    contradictory = {
        concept for concept in mastered
        if any(
            concept and (concept in form or form in concept)
            for form in error_forms
        )
    }
    if contradictory:
        kept_updates = []
        for update in filtered.state_updates:
            if (
                update.update_type == "add_mastered_candidate"
                and _norm(update.payload.get("concept", "")) in contradictory
            ):
                concept = update.payload.get("concept", "")
                issues.append(ValidationIssue(
                    severity="error",
                    category="contradiction",
                    detail=(
                        f"Concept {concept!r} is both claimed mastered and "
                        "flagged as a recurring error in one turn; dropping "
                        "the mastery claim."
                    ),
                    affected_field=f"mastered:{concept}",
                ))
                dropped["updates"].append(f"add_mastered_candidate:{concept}")
                continue
            kept_updates.append(update)
        filtered.state_updates = kept_updates

    # 4. Response prose must not claim levels/mastery the decision's
    # own (kept) evidence does not support. These are warnings: prose
    # is fixed by re-synthesis, never rewritten by app code.
    supported_levels = {
        str(u.payload.get("level"))
        for u in filtered.state_updates
        if u.update_type == "update_cefr"
    }
    for token in sorted(set(_CEFR_TOKEN.findall(filtered.response))):
        if token not in supported_levels:
            issues.append(ValidationIssue(
                severity="warning",
                category="unsupported_claim",
                detail=f"Response claims CEFR {token} with no matching CEFR proposal.",
                affected_field="response",
            ))
    backed_mastery = any(
        u.update_type == "add_mastered_candidate"
        and u.payload.get("evidence_backed") is True
        for u in filtered.state_updates
    )
    if _MASTERY_CLAIM.search(filtered.response) and not backed_mastery:
        issues.append(ValidationIssue(
            severity="warning",
            category="unsupported_claim",
            detail="Response claims mastery with no evidence-backed mastery update.",
            affected_field="response",
        ))

    return filtered, issues, dropped


def apply_llm_drops(decision: AgentDecision, issues: list[ValidationIssue]):
    """Drop items an LLM validator flagged as errors with a parseable target.

    ``affected_field`` convention: ``evidence:<evidence_id>`` or
    ``update:<index>`` (index into ``state_updates`` at validation time).
    Anything else (including ``response``) is not dropped by app code;
    it is material for re-synthesis instead. Returns ``(decision, dropped)``
    where ``dropped`` mirrors :func:`deterministic_check`'s shape.
    """
    dropped = {"evidence": [], "updates": []}
    evidence_ids = {
        issue.affected_field.split(":", 1)[1]
        for issue in issues
        if issue.severity == "error" and issue.affected_field.startswith("evidence:")
    }
    update_indices = set()
    for issue in issues:
        if issue.severity != "error" or not issue.affected_field.startswith("update:"):
            continue
        try:
            update_indices.add(int(issue.affected_field.split(":", 1)[1]))
        except ValueError:
            continue
    if evidence_ids:
        kept = []
        for ev in decision.evidence:
            if ev.evidence_id in evidence_ids:
                dropped["evidence"].append(ev.evidence_id)
            else:
                kept.append(ev)
        decision.evidence = kept
    if update_indices:
        kept = []
        for index, update in enumerate(decision.state_updates):
            if index in update_indices:
                dropped["updates"].append(
                    f"llm:{update.update_type}:{index}"
                )
            else:
                kept.append(update)
        decision.state_updates = kept
    return decision, dropped


def strip_claims(decision: AgentDecision) -> AgentDecision:
    """Keep the learner-facing response; drop everything recordable.

    Used when the validator rejects a decision outright: the turn can
    still teach, but nothing unvalidated may touch durable state.
    """
    decision.evidence = []
    decision.state_updates = []
    decision.review_candidates = []
    return decision


class CrossValidator:
    """One structured LLM validation call per round."""

    def __init__(self, adapter, agent_md: str):
        self.adapter = adapter
        self.agent_md = agent_md

    def llm_report(self, decision: AgentDecision, outputs: dict, state: dict) -> ValidationReport:
        learner = state.get("learner", {}) if isinstance(state, dict) else {}
        evidence_record = {
            "assessment_history": learner.get("assessment_history", [])[-20:],
            "cefr": learner.get("cefr", {}),
            "mastered": learner.get("mastered", []),
            "recurring_errors": learner.get("recurring_errors", []),
        }
        system = (
            self.agent_md
            + "\n\nYou are an independent cross-validation reviewer. "
              "Cross-check the specialist contributions against each other "
              "and against the learner's evidence record, then review the "
              "manager's synthesized decision for contradictions, evidence "
              "that does not support the claims made, invented rules or "
              "sources, and assessment leakage. Return only ValidationReport "
              "JSON. Use severity \"error\" only for items that must be "
              "dropped (name the target as evidence:<evidence_id> or "
              "update:<index>); use \"warning\" for prose or judgment issues "
              "a re-synthesis could fix. Verdict \"pass\" means the decision "
              "is sound, \"fixable\" means a re-synthesis could repair it, "
              "\"reject\" means it must not be recorded at all.\n"
              "SPECIALIST OUTPUTS:\n"
            + json.dumps(
                {name: output.model_dump() for name, output in outputs.items()},
                ensure_ascii=False, indent=2,
            )
            + "\nLEARNER EVIDENCE RECORD:\n"
            + json.dumps(evidence_record, ensure_ascii=False, indent=2)
            + "\nSYNTHESIZED DECISION:\n"
            + decision.model_dump_json(indent=2)
        )
        return ValidationReport.model_validate(
            self.adapter.generate_structured(
                system,
                [{"role": "user", "content": "Validate the decision now."}],
                ValidationReport.model_json_schema(),
                "validation_report",
            )
        )


def run_validation_loop(validator, team, route, state, messages,
                        decision: AgentDecision, outputs: dict,
                        competencies: dict):
    """Validate, optionally re-synthesize once, and return the valid subset.

    Returns ``(final_decision, summary)``. Adapter errors propagate to
    the caller, which must fall back to the pre-validation decision and
    log the fallback — a validation outage must never break a turn.
    """
    dropped_evidence: list[str] = []
    dropped_updates: list[str] = []
    issues_found = 0
    rounds = 1
    verdict = "pass"

    decision, det_issues, dropped = deterministic_check(decision, competencies)
    dropped_evidence.extend(dropped["evidence"])
    dropped_updates.extend(dropped["updates"])
    report = validator.llm_report(decision, outputs, state)
    issues = list(det_issues) + list(report.issues)
    issues_found += len(issues)
    verdict = report.verdict
    decision, llm_dropped = apply_llm_drops(decision, report.issues)
    dropped_evidence.extend(llm_dropped["evidence"])
    dropped_updates.extend(llm_dropped["updates"])

    if verdict == "reject":
        decision = strip_claims(decision)
    elif verdict == "fixable" and issues and rounds < MAX_SYNTHESIS_ROUNDS:
        # One bounded re-synthesis round: the manager repairs the
        # decision with the issues in hand; specialists are not re-run.
        decision = team.resynthesize(route, state, messages, outputs, issues)
        rounds = 2
        decision, det_issues, dropped = deterministic_check(decision, competencies)
        dropped_evidence.extend(dropped["evidence"])
        dropped_updates.extend(dropped["updates"])
        report = validator.llm_report(decision, outputs, state)
        issues = list(det_issues) + list(report.issues)
        issues_found += len(issues)
        verdict = report.verdict
        decision, llm_dropped = apply_llm_drops(decision, report.issues)
        dropped_evidence.extend(llm_dropped["evidence"])
        dropped_updates.extend(llm_dropped["updates"])
        if verdict == "reject":
            decision = strip_claims(decision)

    summary = {
        "enabled": True,
        "rounds_used": rounds,
        "verdict": verdict,
        "issues_found": issues_found,
        "dropped_evidence": dropped_evidence,
        "dropped_updates": dropped_updates,
        "fallback": False,
    }
    return decision, summary

from __future__ import annotations
import json
from pathlib import Path

from .models import AgentDecision, Evidence, RouteDecision
from .prompts import ROLES
from .specialist_models import (
    AssessorOutput,
    ConversationOutput,
    CultureOutput,
    LinguistOutput,
    TutorOutput,
)

# Specialist -> skills/<file> loaded into that specialist's prompt.
# Tutor has no dedicated skill file; that is intentional, not an omission
# to paper over — the tutor works from AGENT.md alone.
SPECIALIST_SKILLS: dict[str, str] = {
    "linguist": "linguistics.md",
    "conversation": "conversation.md",
    "culture": "culture.md",
    "assessor": "assessment.md",
}

# Route mode -> skills/<file> appended to specialist and synthesis prompts.
MODE_SKILLS: dict[str, str] = {
    "diagnostic": "diagnostic.md",
    "review": "review.md",
}

SPECIALIST_MODELS = {
    "tutor": TutorOutput,
    "linguist": LinguistOutput,
    "conversation": ConversationOutput,
    "culture": CultureOutput,
    "assessor": AssessorOutput,
}

DEFAULT_SPECIALISTS = ["tutor"]


def load_skill(project_root, filename: str) -> str:
    """Read one skills/*.md file, or return "" when it is missing.

    Missing or unreadable skill files degrade gracefully: the specialist
    still runs from AGENT.md and its role description.
    """
    try:
        return (Path(project_root) / "skills" / filename).read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return ""


class SpecialistTeam:
    """Runs each routed specialist as its own structured model call.

    The old path described specialists inside one LLM call; here each
    specialist gets its own ``adapter.generate_structured`` call with its
    own output schema, and the manager synthesizes those outputs into
    exactly one :class:`AgentDecision`. The synthesized decision is
    validated with the same Pydantic model and applied by the same
    ``agent.core`` state code as the single-call path — no state logic
    is duplicated here.

    Evidence discipline: the manager is instructed to carry the
    assessor's evidence forward verbatim, and the team additionally
    merges in any assessor evidence the synthesis dropped (deduped by
    evidence_id, or by domain + evidence text when no id is given).
    Evidence is observation, not opinion, so dropping it would lose
    learner history; the downstream evidence gate still decides what
    that evidence is worth — a single correct response never grants
    mastery or a CEFR promotion.
    """

    def __init__(self, adapter, agent_md: str, project_root=None):
        self.adapter = adapter
        self.agent_md = agent_md
        self.project_root = (
            Path(project_root)
            if project_root is not None
            else Path(__file__).resolve().parents[1]
        )
        self._skill_cache: dict[str, str] = {}

    def _skill(self, filename: str) -> str:
        if filename not in self._skill_cache:
            self._skill_cache[filename] = load_skill(self.project_root, filename)
        return self._skill_cache[filename]

    def _specialist_prompt(self, name, route, state, mode_skill: str) -> str:
        parts = [self.agent_md]
        parts.append(f"You are the {name} specialist supporting the Master Agent.")
        parts.append(ROLES[name])
        skill_file = SPECIALIST_SKILLS.get(name)
        if skill_file:
            skill_text = self._skill(skill_file)
            if skill_text:
                parts.append(f"SPECIALIST SKILL ({skill_file}):\n{skill_text}")
        if mode_skill:
            parts.append(f"MODE SKILL:\n{mode_skill}")
        parts.append("ROUTE:\n" + json.dumps(route, ensure_ascii=False, indent=2))
        parts.append("CURRENT STATE:\n" + json.dumps(state, ensure_ascii=False, indent=2))
        parts.append(
            f"Return exactly one {SPECIALIST_MODELS[name].__name__} JSON. "
            "The contribution field is prose for the manager to weave into the "
            "learner-facing response. Evidence (assessor only) must be grounded "
            "in the current turn; never equate one correct answer with mastery."
        )
        return "\n\n".join(parts)

    def _run_specialist(self, name, route, state, messages):
        model_cls = SPECIALIST_MODELS[name]
        return model_cls.model_validate(
            self.adapter.generate_structured(
                self._specialist_prompt(
                    name, route, state,
                    self._skill(MODE_SKILLS[route["mode"]])
                    if route.get("mode") in MODE_SKILLS else "",
                ),
                messages,
                model_cls.model_json_schema(),
                f"{name}_output",
            )
        )

    def _synthesize(self, route, state, messages, outputs, mode_skill: str) -> AgentDecision:
        rendered = {
            name: output.model_dump()
            for name, output in outputs.items()
        }
        parts = [
            self.agent_md,
            "You are the manager synthesizing the specialist team into one learner-facing turn.",
            "SPECIALIST OUTPUTS:\n" + json.dumps(rendered, ensure_ascii=False, indent=2),
        ]
        if mode_skill:
            parts.append(f"MODE SKILL:\n{mode_skill}")
        parts.append(
            "Return exactly one AgentDecision JSON. The response field is "
            "learner-facing and must weave the specialists' contributions into "
            "one coherent reply. Carry the assessor's evidence items forward "
            "verbatim in the evidence field; do not invent evidence, and do "
            "not claim mastery the evidence does not support."
        )
        parts.append("ROUTE:\n" + json.dumps(route, ensure_ascii=False, indent=2))
        parts.append("CURRENT STATE:\n" + json.dumps(state, ensure_ascii=False, indent=2))
        return AgentDecision.model_validate(
            self.adapter.generate_structured(
                "\n\n".join(parts),
                messages,
                AgentDecision.model_json_schema(),
                "agent_decision",
            )
        )

    @staticmethod
    def _merge_assessor_evidence(decision: AgentDecision, outputs) -> AgentDecision:
        assessor = outputs.get("assessor")
        if assessor is None:
            return decision
        seen = {
            (ev.evidence_id or f"{ev.domain}::{ev.evidence}")
            for ev in decision.evidence
        }
        for ev in assessor.evidence:
            key = ev.evidence_id or f"{ev.domain}::{ev.evidence}"
            if key not in seen:
                decision.evidence.append(ev)
                seen.add(key)
        return decision

    def run(self, route: RouteDecision, state: dict, user_text: str, history: list) -> AgentDecision:
        """Run the routed specialists, then synthesize one AgentDecision."""
        specialists: list[str] = []
        for name in route.specialists:
            if name in SPECIALIST_MODELS and name not in specialists:
                specialists.append(name)
        if not specialists:
            specialists = list(DEFAULT_SPECIALISTS)

        route_dict = route.model_dump()
        messages = list(history) + [{"role": "user", "content": user_text}]
        mode_skill = (
            self._skill(MODE_SKILLS[route.mode])
            if route.mode in MODE_SKILLS else ""
        )

        outputs = {
            name: self._run_specialist(name, route_dict, state, messages)
            for name in specialists
        }
        decision = self._synthesize(route_dict, state, messages, outputs, mode_skill)
        return self._merge_assessor_evidence(decision, outputs)

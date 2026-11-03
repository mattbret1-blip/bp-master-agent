from __future__ import annotations
import os, time
from pathlib import Path
from .db import Database
from .models import AgentDecision, AgentState, RouteDecision
from .curriculum import hydrate, next_candidates
from .scheduler import due_items
from .prompts import route_prompt, specialist_prompt
from .specialists import SpecialistTeam
from .quality import run_quality_gate
from .validation import CrossValidator, run_validation_loop
from .research import DisabledResearchAdapter, LocalKnowledgeAdapter

INITIAL_OPENING = (
    "Vamos começar. Antes de eu ensinar, vou descobrir como o português brasileiro funciona para você hoje. "
    "Faça o seu melhor; não use tradutor, dicionário ou corretor automático. Se não souber, diga ‘não sei’. "
    "Os resultados iniciais serão provisórios e poderão mudar com mais evidências.\n\n"
    "Vou seguir esta ordem: primeiro verificarei seu objetivo e contexto; depois faremos tarefas de compreensão, "
    "fala, leitura, escrita, gramática, vocabulário, pronúncia, pragmática e cultura. Responda apenas ao que conseguir. "
    "Se uma tarefa não for possível, diga ‘não sei’ ou ‘não consigo fazer agora’; passaremos à próxima sem penalizar você.\n\n"
    "1. Qual é seu principal objetivo com o português brasileiro?\n"
    "2. Em que situações você pretende usar o idioma?\n"
    "3. Você prefere receber instruções em português, inglês ou em uma combinação dos dois?\n"
    "4. Você está usando voz/áudio ou apenas texto?"
)

class BrazilianPortugueseAgent:
    def __init__(self, adapter, provider_name, db=None, research_adapter=None):
        self.adapter = adapter
        self.provider_name = provider_name
        self.db = db or Database(os.getenv("STATE_PATH","data/learner.db"))
        self.state = self.db.load_state()
        root = Path(__file__).resolve().parents[1]
        self.project_root = root
        self.agent_md = (root / "AGENT.md").read_text(encoding="utf-8")
        self.max_history = int(os.getenv("MAX_HISTORY_MESSAGES","24"))
        self.quality_gate = os.getenv("QUALITY_GATE","false").lower() == "true"
        # MULTI_AGENT=true routes through SpecialistTeam (one structured
        # call per specialist + manager synthesis). Default false keeps
        # the original single-call path.
        self.multi_agent = os.getenv("MULTI_AGENT","false").lower() == "true"
        # CROSS_VALIDATE=true enables the synthesize + cross-validate +
        # revalidate loop, but only on the multi-agent path. Default off:
        # with either flag off, behavior is exactly the previous behavior.
        self.cross_validate = os.getenv("CROSS_VALIDATE","false").lower() == "true"
        # Compact summary of the most recent validation run (None when
        # the loop has never run); surfaced via status().
        self.last_validation = None
        self.research_adapter = research_adapter or DisabledResearchAdapter()
        self.state.learner.competencies = hydrate(self.state.learner.competencies)
        self.db.save_state(self.state)

    def opening_diagnostic(self):
        if self.state.current_session.turn_count != 0 or self.state.history:
            return ""
        self.state.current_session.mode = "diagnostic"
        self.state.current_session.stage = "awaiting_initial_diagnostic"
        self.state.history.append({"role":"assistant","content":INITIAL_OPENING})
        self.db.event("diagnostic_opened", {"message": INITIAL_OPENING})
        self.db.save_state(self.state)
        return INITIAL_OPENING

    def _context(self):
        return {
            "learner": self.state.learner.model_dump(),
            "session": self.state.current_session.model_dump(),
            "next_candidates": [x.model_dump() for x in next_candidates(self.state.learner.competencies)],
            "due_reviews": [x.model_dump() for x in due_items(self.state.learner.review_queue, 7)],
            "recent_history": self.state.history[-self.max_history:]
        }

    def respond(self, user_text):
        if user_text == "__INITIALIZE__":
            return self.opening_diagnostic()

        start = time.perf_counter()
        context = self._context()

        route = RouteDecision.model_validate(
            self.adapter.generate_structured(
                route_prompt(self.agent_md, context),
                [{"role":"user","content":user_text}],
                RouteDecision.model_json_schema(),
                "route_decision",
            )
        )

        if self.multi_agent:
            team = SpecialistTeam(
                self.adapter, self.agent_md, self.project_root
            )
            history = self.state.history[-self.max_history:]
            decision, outputs = team.run_detailed(
                route, context, user_text, history,
            )
            if self.cross_validate:
                # Validate AFTER synthesis, BEFORE state application.
                # A validation outage falls back to the pre-validation
                # decision and is logged — it never breaks the turn.
                try:
                    decision, summary = run_validation_loop(
                        CrossValidator(self.adapter, self.agent_md),
                        team, route, context,
                        list(history) + [{"role": "user", "content": user_text}],
                        decision, outputs,
                        self.state.learner.competencies,
                    )
                except Exception as exc:
                    summary = {
                        "enabled": True,
                        "rounds_used": 0,
                        "verdict": "fallback",
                        "issues_found": 0,
                        "dropped_evidence": [],
                        "dropped_updates": [],
                        "fallback": True,
                        "error": str(exc)[:200],
                    }
                    self.db.event("validation_fallback", {"error": str(exc)[:500]})
                self.last_validation = summary
                self.db.event("validation", summary)
        else:
            decision = AgentDecision.model_validate(
                self.adapter.generate_structured(
                    specialist_prompt(self.agent_md, context, route.model_dump()),
                    self.state.history[-self.max_history:] + [{"role":"user","content":user_text}],
                    AgentDecision.model_json_schema(),
                    "agent_decision",
                )
            )

        if self.quality_gate:
            report = run_quality_gate(self.adapter, context, decision)
            self.db.event("quality_gate", report.model_dump())
            if report.revised_response:
                decision.response = report.revised_response

        if decision.research_requests:
            for request in decision.research_requests:
                sources = self.research_adapter.search(request)
                self.state.learner.research_sources.extend(sources)
                self.db.event("research", {
                    "request": request.model_dump(),
                    "sources": [x.model_dump() for x in sources],
                })

        self._apply(route, decision, user_text)
        latency = (time.perf_counter() - start) * 1000
        self.db.run_log(
            self.provider_name, decision.mode, latency,
            len(user_text), len(decision.response),
            route.model_dump(), decision.model_dump()
        )
        self.db.save_state(self.state)
        return decision.response

    def _apply(self, route, decision, user_text):
        self.state.last_route = route
        self.state.last_decision = decision

        self.state.current_session.mode = decision.mode
        self.state.current_session.goal = decision.goal or self.state.current_session.goal
        self.state.current_session.obstacle = decision.obstacle or self.state.current_session.obstacle
        self.state.current_session.context = decision.context or self.state.current_session.context
        self.state.current_session.focus = decision.focus or self.state.current_session.focus
        self.state.current_session.stage = decision.next_action
        self.state.current_session.turn_count += 1

        self.state.history.append({"role":"user","content":user_text})
        self.state.history.append({"role":"assistant","content":decision.response})

        for update in decision.state_updates:
            self._apply_update(update.update_type, update.payload)

        for ev in decision.evidence:
            self.state.learner.assessment_history.append(ev)
            self._apply_evidence(ev)

        for item in decision.review_candidates:
            self.state.learner.review_queue = [
                r for r in self.state.learner.review_queue
                if r.item_id != item.item_id
            ]
            self.state.learner.review_queue.append(item)

        self._refresh_overall_cefr()
        self.db.event("turn", {
            "route": route.model_dump(),
            "decision": decision.model_dump()
        })

    def _apply_update(self, kind, x):
        p = self.state.learner

        if kind == "update_goal" and x.get("value"):
            value = str(x["value"])
            if value not in p.goals:
                p.goals.append(value)

        elif kind == "update_context" and x.get("value"):
            value = str(x["value"])
            if value not in p.contexts:
                p.contexts.append(value)

        elif kind == "update_instruction_language":
            p.instruction_language = x.get("value")

        elif kind == "update_modality":
            p.modality = x.get("value")

        elif kind == "add_reinforce":
            value = str(x.get("concept","")).strip()
            if value and value not in p.reinforce:
                p.reinforce.append(value)

        elif kind == "add_mastered_candidate":
            value = str(x.get("concept","")).strip()
            if value and x.get("evidence_backed") is True and value not in p.mastered:
                p.mastered.append(value)

        elif kind == "add_recurring_error":
            from .models import ErrorItem
            item = ErrorItem.model_validate(x)
            old = next(
                (e for e in p.recurring_errors
                 if e.form == item.form and e.category == item.category),
                None
            )
            if old:
                old.count += 1
                old.impact = max(old.impact, item.impact)
            else:
                p.recurring_errors.append(item)

        elif kind == "add_vocabulary":
            from .models import VocabularyItem
            item = VocabularyItem.model_validate(x)
            old = next((v for v in p.vocabulary if v.term.lower() == item.term.lower()), None)
            if old:
                old.repetitions += 1
            else:
                p.vocabulary.append(item)

        elif kind == "add_review_item":
            from .models import ReviewItem
            item = ReviewItem.model_validate(x)
            p.review_queue = [r for r in p.review_queue if r.item_id != item.item_id]
            p.review_queue.append(item)

        elif kind == "add_assessment_evidence":
            from .models import Evidence
            p.assessment_history.append(Evidence.model_validate(x))

        elif kind == "update_competency":
            cid = x.get("id")
            if cid in p.competencies:
                node = p.competencies[cid]
                node.mastery = max(0, min(1, float(x.get("mastery",node.mastery))))
                node.confidence = max(0, min(1, float(x.get("confidence",node.confidence))))
                node.evidence_count += int(x.get("evidence_increment",1))

        elif kind == "update_cefr":
            self._apply_cefr_proposal(x)

    def _apply_evidence(self, ev):
        if not ev.concept_id or ev.concept_id not in self.state.learner.competencies:
            return
        node = self.state.learner.competencies[ev.concept_id]
        gain = 0.08 if ev.status == "Observado" else 0.03 if ev.status == "Inferido" else 0
        if ev.mastery_stage == "Automaticity":
            gain *= 1.25
        node.mastery = min(1, node.mastery + gain * ev.confidence)
        node.confidence = max(node.confidence, ev.confidence)
        node.evidence_count += 1

    def _apply_cefr_proposal(self, x):
        domain = str(x.get("domain",""))
        proposed = x.get("level")
        profile = self.state.learner.cefr
        target = getattr(profile, domain, None)
        if target is None or proposed not in {"A1","A2","B1","B2","C1","C2"}:
            return

        evidence_count = int(x.get("evidence_count",0))
        confidence = float(x.get("confidence",0))
        # Conservative gate: proposal must carry at least two explicit
        # evidence items and reasonable confidence.
        if evidence_count < 2 or confidence < 0.70:
            return

        order = ["A1","A2","B1","B2","C1","C2"]
        current = order.index(target.level) if target.level in order else -1
        proposed_i = order.index(proposed)
        # Never jump more than one CEFR band per durable update.
        if proposed_i > current + 1:
            proposed_i = current + 1
        target.level = order[proposed_i]
        target.confidence = max(target.confidence, confidence)
        target.evidence_count += evidence_count

    def _refresh_overall_cefr(self):
        core = [
            self.state.learner.cefr.listening,
            self.state.learner.cefr.speaking,
            self.state.learner.cefr.reading,
            self.state.learner.cefr.writing,
        ]
        order = ["A1","A2","B1","B2","C1","C2"]
        if any(x.level is None or x.evidence_count < 2 for x in core):
            self.state.learner.cefr.overall = None
            return
        indices = [order.index(x.level) for x in core]
        self.state.learner.cefr.overall = order[min(indices)]

    def set_provider(self, provider_name, adapter):
        """Swap the model provider without changing learner state."""
        self.provider_name = provider_name
        self.adapter = adapter
        self.db.event("provider_changed", {"provider": provider_name})

    def next_action(self):
        due = due_items(self.state.learner.review_queue, 8)
        if due:
            return {"action":"review","items":[x.model_dump() for x in due]}
        candidates = next_candidates(self.state.learner.competencies, 8)
        if candidates:
            return {"action":"learn_or_practice","candidates":[x.model_dump() for x in candidates]}
        return {"action":"assessment","reason":"No immediate prerequisite-compatible gap dominates."}

    def status(self):
        data = self.state.model_dump()
        # Compact validation summary (None when the loop has never run),
        # so comprehension evaluation stays inspectable from the API/CLI.
        data["validation"] = self.last_validation
        return data

    def export(self):
        return self.db.export_json()

    def reset(self):
        self.db.reset()
        self.state = self.db.load_state()
        self.state.learner.competencies = hydrate({})
        self.db.save_state(self.state)

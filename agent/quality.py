from __future__ import annotations
import json
from .models import QualityReport

def run_quality_gate(adapter, agent_md, state, candidate):
    system = (
        agent_md
        + "\n\nYou are an independent quality-control reviewer. "
          "Return only QualityReport JSON. Review the candidate for incorrect Portuguese, "
          "invented rules/sources, assessment answer leakage, inappropriate correction, "
          "register/region errors, cultural overgeneralization, excessive verbosity, "
          "and failure to meet the learner's goal.\nSTATE:\n"
        + json.dumps(state, ensure_ascii=False, indent=2)
        + "\nCANDIDATE:\n"
        + candidate.response
    )
    return QualityReport.model_validate(
        adapter.generate_structured(
            system,
            [{"role":"user","content":"Review the candidate now."}],
            QualityReport.model_json_schema(),
            "quality_report",
        )
    )

import json
from pathlib import Path

from src.core.models import Analysis, LLMJudgment, Status, Transcript

RUBRIC = json.loads((Path(__file__).parents[2] / "data/rubrics/banking-v1.json").read_text(encoding="utf-8"))
CRITERIA = {item["id"]: item for item in RUBRIC["criteria"]}


def build_analysis(transcript: Transcript, judgment: LLMJudgment, *, agent_id: str,
                   origin: str, llm_provider: str, llm_model: str) -> Analysis:
    expected = set(CRITERIA)
    actual = [f.criterion_id for f in judgment.findings]
    if len(actual) != len(set(actual)) or set(actual) != expected:
        raise ValueError("Evaluation must contain each rubric criterion exactly once")
    segment_ids = {s.segment_id for s in transcript.segments}
    for item in [*judgment.findings, *judgment.coaching]:
        if set(item.evidence_segment_ids) - segment_ids:
            raise ValueError("Evaluation references nonexistent transcript evidence")
    findings = [f.model_copy(deep=True) for f in judgment.findings]
    for finding in findings:
        if transcript.recording_scope == "opening_excerpt" and finding.criterion_id in {"identity", "resolution", "closing"} and finding.status in {Status.PASS, Status.FAIL}:
            finding.status = Status.INSUFFICIENT_EVIDENCE
            finding.explanation = "This opening excerpt ends before this step can be assessed. Review the complete call."
            finding.evidence_segment_ids = []
            finding.suggested_correction = ""
        elif finding.status in {Status.PASS, Status.FAIL} and not finding.evidence_segment_ids:
            finding.status = Status.INSUFFICIENT_EVIDENCE
            finding.explanation = "The model reported an outcome without transcript evidence. Human review is required."
            finding.suggested_correction = ""
    applicable = [f for f in findings if f.status != Status.NOT_APPLICABLE]
    assessable = [f for f in applicable if f.status != Status.INSUFFICIENT_EVIDENCE]
    weight = sum(CRITERIA[f.criterion_id]["weight"] for f in assessable)
    applicable_weight = sum(CRITERIA[f.criterion_id]["weight"] for f in applicable)
    passed_weight = sum(CRITERIA[f.criterion_id]["weight"] for f in assessable if f.status == Status.PASS)
    score = round(100 * passed_weight / weight, 1) if weight else None
    coverage = round(100 * weight / applicable_weight, 1) if applicable_weight else 0.0
    if transcript.recording_scope == "opening_excerpt" and coverage < 50:
        score = None
    critical = any(f.status == Status.FAIL and CRITERIA[f.criterion_id]["critical"] for f in findings)
    uncertain = any(f.status == Status.INSUFFICIENT_EVIDENCE for f in findings)
    unknown_roles = any(s.role == "unknown" for s in transcript.segments)
    priority = "High" if critical else "Medium" if uncertain or unknown_roles or (score is not None and score < 70) else "Low"
    reasons = []
    if critical: reasons.append("Critical criterion failed")
    if uncertain: reasons.append("Evidence is incomplete")
    if transcript.recording_scope == "opening_excerpt": reasons.append("Opening excerpt; full call needed for final QA")
    if unknown_roles: reasons.append("Speaker roles need confirmation")
    if score is not None and score < 70: reasons.append("Low preliminary score")
    return Analysis(call_id=transcript.call_id, agent_id=agent_id, origin=origin,
                    primary_intent=judgment.primary_intent,
                    classification_reason=judgment.classification_reason,
                    findings=findings, coaching=judgment.coaching,
                    score=score, score_coverage=coverage, critical_failure=critical,
                    review_priority=priority, review_reason="; ".join(reasons) or "Routine sampling",
                    transcript=transcript, llm_provider=llm_provider, llm_model=llm_model)

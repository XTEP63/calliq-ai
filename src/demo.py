import json
from pathlib import Path
from datetime import datetime, timezone

from src.core.models import CriterionFinding, Coaching, LLMJudgment, Segment, Status, Transcript
from src.evaluation.scoring import build_analysis
from src.storage.sqlite import Store


# Synthetic scripts and provisional QA judgments created for the demonstration.
# They are not labels from HarperValleyBank or outputs of a live model.
CASES = [
    ("demo-balance-01", "Agent Maya", "Account inquiry", "2026-11-14", [
        ("agent", "Thank you for calling Northstar Bank. This is Maya. How can I help today?"),
        ("customer", "I need to check my checking account balance."),
        ("agent", "Of course. Please confirm the last four digits of your account and your security answer."),
        ("customer", "The last four are 4821, and my answer is cedar."),
        ("agent", "Thank you. Your available balance is 540 dollars. Does that answer your question?"),
        ("customer", "Yes, it does."),
        ("agent", "Is there anything else I can help with? Thank you for calling Northstar Bank."),
    ], ["PASS", "PASS", "PASS", "PASS", "PASS"], "A complete balance inquiry with verification and closing."),
    ("demo-card-02", "Agent Maya", "Card replacement", "2026-11-15", [
        ("agent", "Northstar Bank, this is Maya. How can I help?"),
        ("customer", "I lost my debit card and need a new one."),
        ("agent", "I can replace it. The new card should arrive in five days."),
        ("customer", "What happens to the old card?"),
        ("agent", "It should stop working. Goodbye."),
    ], ["PASS", "FAIL", "PASS", "INSUFFICIENT_EVIDENCE", "FAIL"], "The recording does not show identity verification or a clear confirmation of the lost card procedure."),
    ("demo-hours-03", "Agent Leo", "General information", "2026-11-15", [
        ("agent", "Hello, Northstar Bank. Leo speaking."),
        ("customer", "When does the downtown branch close today?"),
        ("agent", "The downtown branch closes at five this evening."),
        ("customer", "Great, thanks."),
        ("agent", "You're welcome. Anything else I can answer?"),
        ("customer", "No, that's all."),
        ("agent", "Thanks for calling."),
    ], ["PASS", "NOT_APPLICABLE", "PASS", "PASS", "PASS"], "Public branch hours do not require account identity verification."),
    ("demo-payment-04", "Agent Maya", "Payment", "2026-11-16", [
        ("agent", "Northstar Bank, Maya speaking. How may I assist?"),
        ("customer", "Please pay my electricity bill from checking."),
        ("agent", "I understand. Your security phrase first, please."),
        ("customer", "Maple river."),
        ("agent", "I can see your account. I have scheduled the payment."),
        ("customer", "How much was it, and for when?"),
        ("agent", "The system is slow. It should be fine. Bye."),
    ], ["PASS", "PASS", "PASS", "FAIL", "FAIL"], "Amount and date were not confirmed before ending the call."),
    ("demo-transfer-05", "Agent Leo", "Transfer", "2026-11-17", [
        ("agent", "Hello, this is Leo at Northstar Bank. What can I do for you?"),
        ("customer", "I want to move 200 dollars from savings to checking."),
        ("agent", "I can help. Please confirm your security phrase."),
        ("customer", "Blue lantern."),
        ("agent", "I have transferred 200 dollars from savings to checking. Would you like the confirmation number?"),
        ("customer", "Yes, please."),
        ("agent", "The confirmation is 19342. Is there anything else I can help with?"),
    ], ["PASS", "PASS", "PASS", "PASS", "PASS"], "A complete synthetic transfer example."),
    ("demo-escalation-06", "Agent Maya", "Complaint", "2026-11-18", [
        ("customer", "I have called twice and the charge is still there."),
        ("agent", "I am sorry this has taken more than one call. I will review what I can see."),
        ("customer", "Can you remove the charge today?"),
        ("agent", "I cannot confirm that yet. I can send this to our disputes team for review."),
        ("customer", "How will I know what happens?"),
        ("agent", "They should contact you, but I do not have a timeframe."),
    ], ["INSUFFICIENT_EVIDENCE", "INSUFFICIENT_EVIDENCE", "PASS", "INSUFFICIENT_EVIDENCE", "FAIL"], "The beginning may be missing; the next-step timeframe remains unclear."),
]

CRITERION_IDS = ["greeting", "identity", "understanding", "resolution", "closing"]


def demo_analyses():
    analyses = []
    timing_path = Path(__file__).parents[1] / "data/demo/audio_timings.json"
    timings = json.loads(timing_path.read_text(encoding="utf-8")) if timing_path.exists() else {}
    for call_id, agent, intent, day, utterances, statuses, reason in CASES:
        intervals = timings.get(call_id, [[(i-1)*5.0, (i-1)*5.0+4.5] for i in range(1, len(utterances)+1)])
        segments = [Segment(segment_id=f"s{i}", speaker_id=role, role=role, start_seconds=intervals[i-1][0],
                            end_seconds=intervals[i-1][1], text=text)
                    for i, (role, text) in enumerate(utterances, 1)]
        transcript = Transcript(call_id=call_id, source="Synthetic demonstration script", duration_seconds=intervals[-1][1],
                                audio_channels=1, transcription_provider="manual synthetic script",
                                transcription_model="none", speaker_mapping={"agent": "agent", "customer": "customer"},
                                segments=segments)
        findings = []
        for idx, (criterion, status) in enumerate(zip(CRITERION_IDS, statuses)):
            evidence = [segments[min(idx, len(segments)-1)].segment_id]
            explanation = f"Synthetic demo review: {criterion.replace('_', ' ')} is {status.lower().replace('_', ' ')}. {reason}"
            findings.append(CriterionFinding(criterion_id=criterion, status=Status(status), explanation=explanation,
                                             evidence_segment_ids=evidence,
                                             suggested_correction="Confirm this step explicitly with the customer." if status == "FAIL" else ""))
        fail = next((f for f in findings if f.status == Status.FAIL), None)
        coaching = [Coaching(title="Make the next step explicit" if fail else "Maintain clear confirmation",
                             why_it_matters=reason,
                             example_response="Let me confirm the exact next step and timeframe before we finish." if fail else "Have I fully answered your question today?",
                             next_step="Practice a complete closing in the next call." if fail else "Keep confirming the outcome before closing.",
                             evidence_segment_ids=fail.evidence_segment_ids if fail else [segments[-1].segment_id])]
        judgment = LLMJudgment(primary_intent=intent, classification_reason=reason, findings=findings, coaching=coaching)
        analysis = build_analysis(transcript, judgment, agent_id=agent, origin="Synthetic saved demonstration",
                                  llm_provider="none - manually authored demo", llm_model="none")
        analysis.created_at = datetime.fromisoformat(day).replace(tzinfo=timezone.utc).isoformat()
        analyses.append(analysis)
    return analyses


def seed_demo(store: Store):
    for analysis in demo_analyses():
        existing = store.get(analysis.call_id)
        if existing is None or existing.origin.startswith("Synthetic"):
            store.save(analysis)

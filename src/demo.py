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
EVIDENCE = {
    "demo-balance-01": [[1], [3], [3], [5], [7]],
    "demo-card-02": [[1], [1, 3], [3], [3, 5], [5]],
    "demo-hours-03": [[1], [2], [3], [3], [7]],
    "demo-payment-04": [[1], [3], [3], [5, 7], [7]],
    "demo-transfer-05": [[1], [3], [3], [5], [7]],
    "demo-escalation-06": [[1], [], [2], [4, 6], [6]],
}
COACHING = {
    "demo-card-02": ("Verify before replacing a card", "Before I process a replacement, I need to complete identity verification.", "Rehearse the verification step before account changes."),
    "demo-payment-04": ("Confirm payment details", "I have scheduled [verified amount] for [verified date]. Does that match your request?", "Confirm amount and date before ending payment calls."),
    "demo-escalation-06": ("Explain the escalation follow-up", "I will confirm how and when the disputes team will contact you before we finish.", "Give a verified next step and timeframe."),
}
CARD_EXPLANATIONS = {
    "greeting": "Maya identifies the bank and herself, then invites the customer's request.",
    "identity": "The call moves from the lost-card request to a replacement promise without an identity check.",
    "understanding": "Maya acknowledges the replacement request and gives an arrival estimate.",
    "resolution": "The call does not confirm whether the old card was blocked; a reviewer should verify the procedure.",
    "closing": "Maya ends the call without checking for another question or confirming the next step.",
}
CARD_CORRECTIONS = {
    "identity": "Complete identity verification before processing the replacement.",
    "closing": "Ask whether the customer needs anything else and confirm the next step.",
}


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
            evidence = [segments[j-1].segment_id for j in EVIDENCE[call_id][idx]]
            explanation = (CARD_EXPLANATIONS.get(criterion) if call_id == "demo-card-02" else None)
            if not explanation:
                explanation = f"Synthetic demo review: {criterion.replace('_', ' ')} is {status.lower().replace('_', ' ')}. {reason}"
            correction = ""
            if status == "FAIL":
                correction = CARD_CORRECTIONS.get(criterion, "Confirm this step explicitly with the customer.") if call_id == "demo-card-02" else "Confirm this step explicitly with the customer."
            findings.append(CriterionFinding(criterion_id=criterion, status=Status(status), explanation=explanation,
                                             evidence_segment_ids=evidence, suggested_correction=correction))
        fail = next((f for f in findings if f.status == Status.FAIL), None)
        title, example, step = COACHING.get(call_id, ("Maintain clear confirmation", "Have I fully answered your question today?", "Keep confirming the outcome before closing."))
        coaching_evidence = fail.evidence_segment_ids if fail and fail.evidence_segment_ids else [segments[-1].segment_id]
        coaching = [Coaching(title=title,
                             why_it_matters=reason,
                             example_response=example, next_step=step,
                             evidence_segment_ids=coaching_evidence)]
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

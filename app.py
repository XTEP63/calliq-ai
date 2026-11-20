from __future__ import annotations

import json
import hashlib
import os
from datetime import date, datetime, timezone
from pathlib import Path

import streamlit as st

from src.analytics.reports import report_html, summarize
from src.core.models import Transcript
from src.demo import seed_demo
from src.evaluation.scoring import CRITERIA
from src.services.pipeline import confirm_roles, evaluate_transcript, transcribe_audio
from src.storage.sqlite import Store
from src.transcription.manual import parse_manual_transcript

st.set_page_config(page_title="CallIQ | Every Call Counts", page_icon="◉", layout="wide")

for secret_name in ("DEEPGRAM_API_KEY", "GROQ_API_KEY", "TRANSCRIPTION_PROVIDER", "LLM_PROVIDER", "GROQ_MODEL"):
    try:
        if secret_name in st.secrets and not os.getenv(secret_name):
            os.environ[secret_name] = str(st.secrets[secret_name])
    except FileNotFoundError:
        pass

st.markdown("""<style>
.block-container{padding-top:2rem;max-width:1350px}.hero{padding:30px 34px;border-radius:18px;background:linear-gradient(115deg,#143148,#0b5364);margin-bottom:24px}.hero h1{margin:0;color:#fff;font-size:2.5rem}.hero p{color:#ccebf0;font-size:1.1rem;margin:6px 0 0}.badge{display:inline-block;padding:4px 10px;border-radius:30px;background:#134c61;color:#c6f6ff;font-size:.8rem;margin-bottom:10px}.small{color:#9cb4c6;font-size:.9rem}
</style>""", unsafe_allow_html=True)

store = Store(os.getenv("CALLIQ_DB_PATH", "data/calliq.sqlite3"))
seed_demo(store)
all_calls = store.list()

st.markdown('<div class="hero"><span class="badge">CONTACT CENTER INTELLIGENCE</span><h1>CallIQ</h1><p>Every Call Counts. Every Insight Matters.</p></div>', unsafe_allow_html=True)
st.caption("Preliminary AI assessments support human QA. Demo views do not enforce access control. Synthetic examples are labeled throughout.")

page = st.sidebar.radio("Workspace", ["Overview", "Analyze Call", "Agent Dashboard", "Manager Dashboard", "QA Analyst", "Performance Reports", "Architecture & About"])
st.sidebar.divider()
st.sidebar.caption(f"{len(all_calls)} saved evaluations · {sum(c.origin.startswith('Synthetic') for c in all_calls)} synthetic demos")


def result_view(call):
    st.info(f"Source: {call.origin} · Transcript: {call.transcript.transcription_provider} / {call.transcript.transcription_model} · Evaluation: {call.llm_provider} / {call.llm_model}")
    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Quality score", f"{call.score}%" if call.score is not None else "Unscored")
    m2.metric("Score coverage", f"{call.score_coverage}%")
    m3.metric("Review priority", call.review_priority)
    m4.metric("Primary intent", call.primary_intent)
    st.caption("Scores use only assessable criteria. Unknown outcomes reduce coverage, not the score denominator.")
    if call.review_reason != "Routine sampling": st.warning(call.review_reason)
    st.markdown("#### Transcript")
    by_id = {segment.segment_id: segment for segment in call.transcript.segments}
    for segment in call.transcript.segments:
        st.markdown(f"**{segment.start_seconds:05.1f}s · {segment.role.title()} · {segment.segment_id}**  {segment.text}")
    st.markdown("#### Quality rubric")
    for item in call.findings:
        criterion = CRITERIA[item.criterion_id]
        with st.expander(f"{criterion['label']} · {item.status.value} · {criterion['weight']}%", expanded=item.status.value == "FAIL"):
            st.write(item.explanation)
            for segment_id in item.evidence_segment_ids:
                segment = by_id[segment_id]
                st.caption(f"Evidence {segment_id} at {segment.start_seconds:.1f}s: “{segment.text}”")
            if item.suggested_correction: st.write("Suggested correction:", item.suggested_correction)
    st.markdown("#### Coaching")
    for tip in call.coaching:
        st.markdown(f"**{tip.title}** — {tip.why_it_matters}")
        st.write("Example response:", tip.example_response)
        st.caption(f"Next step: {tip.next_step} · Evidence: {', '.join(tip.evidence_segment_ids)}")
    st.download_button("Download evaluation JSON", call.model_dump_json(indent=2), f"{call.call_id}.json", "application/json")


if page == "Overview":
    st.header("From call recordings to actionable coaching")
    st.write("CallIQ transcribes a conversation, applies a configurable QA rubric, verifies cited evidence, and turns findings into coaching and review priorities.")
    stats = summarize(all_calls)
    a, b, c = st.columns(3)
    a.metric("Saved calls", stats["calls"])
    b.metric("Average assessable score", f"{stats['average_score']}%" if stats["average_score"] is not None else "—")
    c.metric("Flagged for QA", stats["flagged"])
    st.caption("These metrics include explicitly synthetic demonstration cases. They are not production KPIs.")
    st.subheader("Demonstration path")
    st.write("Open **Analyze Call** to inspect a saved case or upload mono WAV/MP3. Continue through agent coaching, team metrics, QA review, and a report preview.")

elif page == "Analyze Call":
    st.header("Analyze a conversation")
    demo_tab, corpus_tab, upload_tab, manual_tab = st.tabs(["Saved demonstration", "Public corpus", "Upload and process", "Manual transcript"])
    with demo_tab:
        demos = [c for c in all_calls if c.origin.startswith("Synthetic")]
        chosen = st.selectbox("Synthetic sample", demos, format_func=lambda c: f"{c.call_id} · {c.primary_intent} · {c.agent_id} · {c.review_priority}")
        if chosen:
            recording = Path("data/demo/audio") / f"{chosen.call_id}.mp3"
            if recording.exists():
                st.audio(str(recording))
                st.caption("Synthetic text-to-speech recording; saved transcript and manually authored provisional QA findings.")
            result_view(chosen)
    with corpus_tab:
        corpus_index = Path("data/harpervalley/index.json")
        if corpus_index.exists():
            entries = json.loads(corpus_index.read_text(encoding="utf-8"))
            entry = st.selectbox("HarperValleyBank sample", entries, format_func=lambda x: f"{x['task'].title()} · {x['call_id']}")
            st.caption("Source: Gridspace-Stanford HarperValleyBank, CC BY 4.0. Transcript was human corrected by the dataset authors; no QA score is supplied by the dataset.")
            if entry:
                st.audio(str(Path("data/harpervalley") / entry["audio"]))
                transcript = Transcript.model_validate_json((Path("data/harpervalley") / entry["transcript"]).read_text(encoding="utf-8"))
                for segment in transcript.segments:
                    st.markdown(f"**{segment.start_seconds:05.1f}s · {segment.role.title()}**  {segment.text}")
                saved = st.session_state.get("corpus_analyses", {}).get(entry["call_id"]) or store.get(entry["call_id"])
                if saved:
                    st.markdown("#### Saved evaluation")
                    result_view(saved)
                else:
                    st.caption("No evaluation has been generated for this corpus call.")
                    if st.button("Evaluate this transcript with the configured LLM"):
                        try:
                            agent_id = f"Corpus agent {entry['agent_speaker_id']}"
                            with st.spinner("Evaluating the public corpus transcript…"):
                                analysis, source = evaluate_transcript(transcript, agent_id, store, "Fresh evaluation of public corpus transcript")
                            st.session_state.setdefault("corpus_analyses", {})[entry["call_id"]] = analysis
                            st.success(source)
                            result_view(analysis)
                        except Exception as exc:
                            st.error(f"Evaluation failed: {exc}")
        else:
            st.info("Public corpus files have not been prepared. Run scripts/prepare_harpervalley.py with GitHub CLI and FFmpeg.")
    with upload_tab:
        if not os.getenv("DEEPGRAM_API_KEY") and os.getenv("TRANSCRIPTION_PROVIDER", "deepgram") == "deepgram":
            st.warning("Live transcription needs DEEPGRAM_API_KEY. Saved demonstration cases remain available.")
        if not os.getenv("GROQ_API_KEY") and os.getenv("LLM_PROVIDER", "groq") == "groq":
            st.warning("Live evaluation needs GROQ_API_KEY. You can still inspect saved results.")
        use_sample = st.checkbox("Use bundled 25-second two-speaker sample (HarperValleyBank, CC BY 4.0)")
        if use_sample:
            audio_file_name = "harper-live-25s.mp3"
            audio_bytes = (Path("data/demo/audio") / audio_file_name).read_bytes()
            st.caption("A short excerpt of the public HarperValleyBank card replacement call. Processing it makes fresh API requests.")
        else:
            uploaded = st.file_uploader("Mono WAV or MP3 · up to 20 MB and 15 minutes · authorized recordings only", type=["wav", "mp3"])
            audio_file_name = uploaded.name if uploaded else None
            audio_bytes = uploaded.getvalue() if uploaded else None
        if audio_bytes:
            upload_id = hashlib.sha256(audio_bytes).hexdigest()
            if st.session_state.get("upload_id") != upload_id:
                st.session_state["upload_id"] = upload_id
                st.session_state.pop("transcript", None)
                st.session_state.pop("analysis", None)
            st.audio(audio_bytes, format="audio/mpeg" if audio_file_name.lower().endswith(".mp3") else "audio/wav")
            if st.button("1. Transcribe recording", type="primary"):
                try:
                    with st.spinner("Validating and transcribing…"):
                        transcript, source = transcribe_audio(audio_bytes, audio_file_name, store)
                    st.session_state["transcript"] = transcript
                    st.success(source)
                except Exception as exc:
                    st.error(f"Transcription failed: {exc}")
            transcript = st.session_state.get("transcript")
            if transcript:
                st.caption(f"Transcript: {transcript.transcription_provider} · {transcript.call_id}")
                speakers = sorted({s.speaker_id for s in transcript.segments})
                st.markdown("#### Review the transcript before assigning roles")
                for segment in transcript.segments:
                    st.markdown(f"**{segment.start_seconds:.1f}s · Speaker {segment.speaker_id} · {segment.segment_id}**  {segment.text}")
                roles_uncertain = len(speakers) < 2 or "unknown" in speakers
                if roles_uncertain:
                    st.warning("This transcript does not distinguish two speakers. Agent quality cannot be evaluated reliably. Use a recording with distinct voices or the Manual transcript tab with confirmed roles.")
                agent_speaker = st.selectbox("2. Confirm which speaker is the agent", speakers, disabled=roles_uncertain)
                agent_alias = st.text_input("Agent alias", value="Uploaded agent", disabled=roles_uncertain)
                st.caption("Diarization distinguishes voices but does not identify the agent. Confirm the mapping from the transcript and audio before evaluating.")
                if st.button("3. Evaluate confirmed transcript", disabled=roles_uncertain):
                    try:
                        ready = confirm_roles(transcript, agent_speaker)
                        with st.spinner("Evaluating rubric and checking evidence…"):
                            analysis, source = evaluate_transcript(ready, agent_alias, store)
                        st.session_state["analysis"] = analysis
                        st.success(source)
                    except Exception as exc:
                        st.error(f"Evaluation failed: {exc}")
                if st.session_state.get("analysis"):
                    result_view(st.session_state["analysis"])
    with manual_tab:
        st.caption("Fallback when transcription fails: enter an authorized English transcript with confirmed roles. One turn per line: start|end|agent-or-customer|text (times in seconds). No timestamps or roles are inferred.")
        manual_text = st.text_area("Role-labeled transcript", height=200,
                                   placeholder="0.0|2.5|agent|Thank you for calling. How may I help?\n2.6|4.0|customer|I need to check my balance.")
        manual_id = hashlib.sha256(manual_text.encode("utf-8")).hexdigest()
        if st.session_state.get("manual_id") != manual_id:
            st.session_state["manual_id"] = manual_id
            st.session_state.pop("manual_transcript", None)
            st.session_state.pop("manual_analysis", None)
        if st.button("Validate transcript"):
            try:
                st.session_state["manual_transcript"] = parse_manual_transcript(manual_text)
                st.success("Transcript validated. Review the roles and words before requesting an AI evaluation.")
            except ValueError as exc:
                st.error(str(exc))
        manual_transcript = st.session_state.get("manual_transcript")
        if manual_transcript:
            for segment in manual_transcript.segments:
                st.markdown(f"**{segment.start_seconds:.1f}s · {segment.role.title()} · {segment.segment_id}**  {segment.text}")
            manual_agent = st.text_input("Agent alias for this transcript", value="Manual transcript agent")
            if not os.getenv("GROQ_API_KEY") and os.getenv("LLM_PROVIDER", "groq") == "groq":
                st.warning("AI evaluation needs GROQ_API_KEY. The validated transcript remains available in this session.")
            if st.button("Evaluate validated transcript"):
                try:
                    with st.spinner("Evaluating rubric and checking evidence…"):
                        analysis, source = evaluate_transcript(manual_transcript, manual_agent, store,
                                                               "Fresh evaluation of authorized manual transcript")
                    st.session_state["manual_analysis"] = analysis
                    st.success(source)
                except Exception as exc:
                    st.error(f"Evaluation failed: {exc}")
            if st.session_state.get("manual_analysis"):
                result_view(st.session_state["manual_analysis"])

elif page == "Agent Dashboard":
    st.header("Agent dashboard")
    agents = sorted({c.agent_id for c in all_calls})
    agent = st.selectbox("Agent alias", agents)
    calls = [c for c in all_calls if c.agent_id == agent]
    stats = summarize(calls)
    c1, c2, c3 = st.columns(3)
    c1.metric("Calls reviewed", stats["calls"])
    c2.metric("Average assessable score", f"{stats['average_score']}%" if stats["average_score"] is not None else "—")
    c3.metric("Flagged", stats["flagged"])
    st.line_chart({c.call_id: c.score for c in reversed(calls) if c.score is not None})
    st.write("Recurring opportunities:", ", ".join(f"{CRITERIA[k]['label']} ({v})" for k, v in stats["misses"].most_common()) or "None in saved cases")
    call = st.selectbox("Inspect a call", calls, format_func=lambda c: f"{c.call_id} · {c.primary_intent}")
    if call: result_view(call)

elif page == "Manager Dashboard":
    st.header("Manager dashboard")
    st.caption("Synthetic demonstration team. Agent aliases represent only these sample scripts.")
    for agent in sorted({c.agent_id for c in all_calls}):
        calls = [c for c in all_calls if c.agent_id == agent]
        stats = summarize(calls)
        st.subheader(agent)
        st.write(f"{stats['calls']} calls · average assessable score: {stats['average_score']}% · {stats['flagged']} flagged")
        st.progress((stats["average_score"] or 0)/100)
    st.subheader("Recurring missed criteria")
    misses = summarize(all_calls)["misses"]
    st.bar_chart({CRITERIA[k]["label"]: v for k, v in misses.items()})
    st.dataframe([{"Call": c.call_id, "Agent": c.agent_id, "Intent": c.primary_intent, "Score": c.score, "Priority": c.review_priority, "Source": c.origin} for c in all_calls], hide_index=True, width="stretch")

elif page == "QA Analyst":
    st.header("QA review queue")
    st.caption("Prioritized by critical failures, uncertainty, and low assessable scores. A human reviewer owns the decision. On this public demo, reviews are session-only; enter no private information.")
    queue = sorted(all_calls, key=lambda c: ({"High": 0, "Medium": 1, "Low": 2}[c.review_priority], c.created_at))
    st.dataframe([{"Call": c.call_id, "Priority": c.review_priority, "Reason": c.review_reason, "Agent": c.agent_id, "Score": c.score} for c in queue], hide_index=True, width="stretch")
    call = st.selectbox("Review call", queue, format_func=lambda c: f"{c.review_priority} · {c.call_id}")
    if call:
        result_view(call)
        with st.form("review"):
            reviewer = st.text_input("Reviewer alias")
            decision = st.selectbox("Decision", ["Approved", "Corrected", "Needs follow-up"])
            notes = st.text_area("Correction or review notes")
            if st.form_submit_button("Save review"):
                if reviewer.strip() and notes.strip():
                    if os.getenv("APP_MODE", "online") == "local":
                        store.add_review(call.call_id, reviewer.strip(), decision, notes.strip())
                        st.success("Review saved locally.")
                    else:
                        st.session_state.setdefault("qa_reviews", {}).setdefault(call.call_id, []).append(
                            (reviewer.strip(), decision, notes.strip(), datetime.now(timezone.utc).isoformat()))
                        st.success("Review saved in this browser session.")
                else: st.error("Enter a reviewer alias and notes.")
        reviews = store.reviews(call.call_id) if os.getenv("APP_MODE", "online") == "local" else st.session_state.get("qa_reviews", {}).get(call.call_id, [])
        for reviewer, decision, notes, when in reviews:
            st.caption(f"{when} · {reviewer} · {decision}: {notes}")

elif page == "Performance Reports":
    st.header("Weekly performance report")
    agent = st.selectbox("Agent", sorted({c.agent_id for c in all_calls}))
    period = st.date_input("Reporting period", value=(date(2026, 11, 13), date(2026, 11, 19)))
    if len(period) != 2:
        st.info("Select both start and end dates.")
    else:
        start, end = period
        if start > end:
            st.error("Start date must not exceed end date.")
        else:
            html = report_html(all_calls, agent, start, end)
            st.html(html)
            st.download_button("Download HTML report", html, f"calliq-{agent.lower().replace(' ', '-')}.html", "text/html")
            st.caption("Preview only. CallIQ does not email reports.")

else:
    st.header("Architecture and safeguards")
    st.code("Audio → Deepgram / Faster-Whisper → canonical transcript → Groq / Ollama → evidence validation + Python scoring → SQLite → dashboards + report", language="text")
    st.write("Cloud deployment is stateless for uploaded recordings; the local SQLite file can disappear on Streamlit Community Cloud. Synthetic samples are bundled and reseeded. Durable multiuser storage requires a managed database.")
    st.write("Future AWS path: S3 upload, Step Functions orchestration, Transcribe, Bedrock, Aurora PostgreSQL, CloudWatch, and approved SES delivery.")
    st.write("Production work remains: authentication, role permissions, tenant isolation, encryption, retention, PII redaction, and vendor review. Never use preliminary scores alone for employment decisions.")

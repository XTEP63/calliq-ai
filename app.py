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
from src.services.session import visible_analyses
from src.storage.sqlite import Store
from src.transcription.manual import parse_manual_transcript

st.set_page_config(page_title="CallIQ | Every Call Counts", page_icon="◉", layout="wide", initial_sidebar_state="auto")

for secret_name in ("DEEPGRAM_API_KEY", "GROQ_API_KEY", "TRANSCRIPTION_PROVIDER", "LLM_PROVIDER", "GROQ_MODEL"):
    try:
        if secret_name in st.secrets and not os.getenv(secret_name):
            os.environ[secret_name] = str(st.secrets[secret_name])
    except FileNotFoundError:
        pass

st.markdown("""<style>
.block-container{padding-top:1.3rem;max-width:1240px;padding-bottom:4rem}
.hero{padding:22px 30px;border-radius:18px;background:linear-gradient(115deg,#102B4F 0%,#14365B 72%,#1B416B 100%);margin-bottom:22px;border:1px solid #305476}
.hero h1{margin:1px 0 0;color:#F5F3EE;font-size:2.1rem;letter-spacing:-.035em}.hero p{color:#D5DFE8;font-size:1rem;margin:3px 0 0}
.eyebrow{color:#F07842;font-size:.72rem;font-weight:800;letter-spacing:.15em;text-transform:uppercase}
.guide{border-left:3px solid #F07842;padding:8px 0 8px 17px;margin:12px 0 22px;color:#D5DFE8}
.step{color:#F07842;font-weight:800;font-size:.82rem;letter-spacing:.08em;text-transform:uppercase}
.role-strip{background:#F5F3EE;color:#07182F;border-radius:16px;padding:22px 26px;margin:18px 0 26px}
.role-strip h3{color:#07182F;font-size:1.25rem;margin:0 0 16px}.role-grid{display:grid;grid-template-columns:repeat(3,1fr);gap:22px}
.role-grid strong{display:block;color:#102B4F;margin-bottom:5px}.role-grid span{display:block;line-height:1.45}
div[data-testid="stMetric"]{border:1px solid #305476;border-radius:14px;padding:15px 18px;background:#102B4F}
div[data-testid="stMetricLabel"]{font-weight:650}div[data-testid="stMetricValue"]{color:#F5F3EE}
div[data-testid="stExpander"]{border-color:#305476;border-radius:12px}
div[data-testid="stSidebar"]{border-right:1px solid #305476}
div[data-testid="stSidebar"] div[data-testid="stButton"] button{justify-content:flex-start}
@media(max-width:700px){.hero{padding:18px 20px}.hero h1{font-size:1.8rem}.block-container{padding-top:2rem}.role-grid{grid-template-columns:1fr;gap:14px}}
</style>""", unsafe_allow_html=True)

store = Store(os.getenv("CALLIQ_DB_PATH", "data/calliq.sqlite3"))
seed_demo(store)
all_calls = visible_analyses(store.list(), st.session_state.get("session_analyses", {}))

def go_to(destination: str, analysis_tab: str | None = None) -> None:
    st.session_state["active_page"] = destination
    if analysis_tab:
        st.session_state["analysis_tab_target"] = analysis_tab
        st.session_state["analysis_tab_version"] = st.session_state.get("analysis_tab_version", 0) + 1


page = st.session_state.setdefault("active_page", "Overview")
st.markdown('<div class="hero"><span class="eyebrow">CONTACT CENTER INTELLIGENCE</span><h1>CallIQ</h1><p>Every Call Counts. Every Insight Matters.</p></div>', unsafe_allow_html=True)
st.sidebar.markdown("## CallIQ")
st.sidebar.caption("Quality review and coaching")
st.sidebar.button("Overview", key="nav_overview", icon=":material/home:", type="primary" if page == "Overview" else "tertiary", use_container_width=True, on_click=go_to, args=("Overview",))
st.sidebar.button("Analyze Call", key="nav_analyze", icon=":material/graphic_eq:", type="primary" if page == "Analyze Call" else "tertiary", use_container_width=True, on_click=go_to, args=("Analyze Call",))
with st.sidebar.expander("Dashboards", expanded=page in {"Agent Dashboard", "Manager Dashboard", "QA Analyst"}, icon=":material/dashboard:"):
    for label, destination, icon in (
        ("Agent", "Agent Dashboard", ":material/person:"),
        ("Manager", "Manager Dashboard", ":material/groups:"),
        ("QA Analyst", "QA Analyst", ":material/fact_check:"),
    ):
        st.button(label, key=f"nav_{label.lower().replace(' ', '_')}", icon=icon,
                  type="primary" if page == destination else "tertiary", use_container_width=True,
                  on_click=go_to, args=(destination,))
st.sidebar.button("Performance Reports", key="nav_reports", icon=":material/monitoring:", type="primary" if page == "Performance Reports" else "tertiary", use_container_width=True, on_click=go_to, args=("Performance Reports",))
st.sidebar.button("About", key="nav_about", icon=":material/info:", type="primary" if page == "About" else "tertiary", use_container_width=True, on_click=go_to, args=("About",))
st.sidebar.divider()
st.sidebar.caption("Demo workspace · saved cases are synthetic")
st.sidebar.caption("New analyses remain in this browser session.")


def result_view(call):
    st.markdown(f"### {call.primary_intent}")
    st.caption(f"{call.origin} · {call.agent_id} · {call.call_id}")
    m1, m2, m3 = st.columns(3)
    m1.metric("Preliminary QA score", f"{call.score}%" if call.score is not None else "Unscored")
    m2.metric("Rubric coverage", f"{call.score_coverage}%")
    m3.metric("QA review priority", call.review_priority)
    st.caption("The score uses only assessable checks. Coverage is the share of the rubric supported by this recording.")
    if call.transcript.recording_scope == "opening_excerpt":
        st.info("This clip covers only the start of a call. Later steps are unassessed; a score is withheld below 50% coverage.")
    if call.review_reason != "Routine sampling":
        st.warning(f"Why QA should review this call: {call.review_reason}")
    by_id = {segment.segment_id: segment for segment in call.transcript.segments}
    ordered = sorted(call.findings, key=lambda f: {"FAIL": 0, "INSUFFICIENT_EVIDENCE": 1, "PASS": 2, "NOT_APPLICABLE": 3}[f.status.value])
    if ordered:
        item = ordered[0]
        criterion = CRITERIA[item.criterion_id]
        label = {"PASS": "Passed", "FAIL": "Needs attention", "INSUFFICIENT_EVIDENCE": "Not enough evidence", "NOT_APPLICABLE": "Not applicable"}[item.status.value]
        st.markdown("#### The first finding to review")
        with st.container(border=True):
            st.markdown(f"**{label} · {criterion['label']}**")
            st.write(item.explanation)
            for segment_id in item.evidence_segment_ids:
                segment = by_id[segment_id]
                st.caption(f"Evidence · {segment.start_seconds:.1f}s · {segment.role.title()} · {segment_id}: “{segment.text}”")
            if item.suggested_correction:
                st.write("Suggested correction:", item.suggested_correction)
    st.markdown("#### What to try on the next call")
    for tip in call.coaching:
        with st.container(border=True):
            st.markdown(f"**{tip.title}**")
            st.write(f"Try saying: “{tip.example_response}”")
            st.caption(f"Practice: {tip.next_step} · Evidence: {', '.join(tip.evidence_segment_ids)}")
    if not call.coaching:
        st.caption("No coaching recommendation was generated for this call.")
    with st.expander(f"Remaining rubric checks ({max(0, len(ordered) - 1)})"):
        for item in ordered[1:]:
            criterion = CRITERIA[item.criterion_id]
            label = {"PASS": "Passed", "FAIL": "Needs attention", "INSUFFICIENT_EVIDENCE": "Not enough evidence", "NOT_APPLICABLE": "Not applicable"}[item.status.value]
            st.markdown(f"**{label} · {criterion['label']} · {criterion['weight']}% weight**")
            st.write(item.explanation)
            for segment_id in item.evidence_segment_ids:
                segment = by_id[segment_id]
                st.caption(f"{segment.start_seconds:.1f}s · {segment.role.title()} · {segment_id}: “{segment.text}”")
            st.divider()
    with st.expander("Full transcript"):
        for segment in call.transcript.segments:
            st.markdown(f"**{segment.start_seconds:05.1f}s · {segment.role.title()} · {segment.segment_id}**  {segment.text}")
    with st.expander("Technical details"):
        st.caption(f"Transcription: {call.transcript.transcription_provider} / {call.transcript.transcription_model} · Evaluation: {call.llm_provider} / {call.llm_model}")
        st.caption(f"Rubric version: {call.rubric_version} · Prompt version: {call.prompt_version}")
    st.download_button("Download evaluation JSON", call.model_dump_json(indent=2), f"{call.call_id}.json", "application/json")


if page == "Overview":
    st.header("Review a call. See the evidence. Coach the next one.")
    st.markdown('<div class="guide">Start with a prepared case to understand the full quality loop. New audio analysis is available when you need it.</div>', unsafe_allow_html=True)
    left, right = st.columns([1.25, 1], gap="large")
    with left:
        st.subheader("Explore a saved case")
        st.write("Follow a synthetic card replacement call from transcript evidence to QA priority and a coaching response. Ready immediately; no provider request.")
        st.button("Explore a saved case", key="overview_saved_case", icon=":material/play_arrow:", type="primary", on_click=go_to, args=("Analyze Call", "Saved case"))
    with right:
        st.subheader("Analyze a new call")
        st.write("Use an authorized recording or the bundled public sample. Confirm the agent before evaluation. Transcription and evaluation may use provider credits.")
        st.button("Analyze a new call", key="overview_new_call", icon=":material/graphic_eq:", on_click=go_to, args=("Analyze Call", "New audio analysis"))
    st.divider()
    st.markdown('<div class="role-strip"><h3>One conversation, three useful views</h3><div class="role-grid"><div><strong>Agent</strong><span>A response to practice on the next call.</span></div><div><strong>Manager</strong><span>Patterns to discuss with the team.</span></div><div><strong>QA analyst</strong><span>A queue ordered for human review.</span></div></div></div>', unsafe_allow_html=True)
    st.subheader("Demo workspace status")
    stats = summarize(all_calls)
    a, b, c = st.columns(3)
    a.metric("Visible calls", stats["calls"])
    b.metric("Average assessable score", f"{stats['average_score']}%" if stats["average_score"] is not None else "—")
    c.metric("Flagged for QA", stats["flagged"])
    st.caption("Includes synthetic examples and analyses in this browser session. These are demonstration counts, not production KPIs.")
    st.info("Preliminary AI findings require human QA. Use only public or synthetic recordings in this demo; it has no account access control.")

elif page == "Analyze Call":
    st.header("Analyze a call")
    st.caption("Start with a prepared case, or choose a new analysis path. Provider requests begin only when you press a processing button.")
    tab_labels = ["Saved case", "New audio analysis", "Public corpus", "Manual transcript"]
    target = st.session_state.pop("analysis_tab_target", None)
    tab_version = st.session_state.get("analysis_tab_version", 0)
    demo_tab, upload_tab, corpus_tab, manual_tab = st.tabs(tab_labels, default=target or "Saved case", key=f"analysis_tabs_{tab_version}")
    with demo_tab:
        st.markdown('<p class="step">Start here · instant and free</p>', unsafe_allow_html=True)
        st.write("These six cases have manually authored demo findings. No provider request is made when you inspect them.")
        demos = [c for c in all_calls if c.origin.startswith("Synthetic")]
        default_demo = next((i for i, call in enumerate(demos) if call.call_id == "demo-card-02"), 0)
        chosen = st.selectbox("Choose a scenario", demos, index=default_demo,
                              format_func=lambda c: f"{c.primary_intent} · {c.agent_id} · {c.review_priority} priority")
        if chosen:
            recording = Path("data/demo/audio") / f"{chosen.call_id}.mp3"
            if recording.exists():
                st.audio(str(recording))
                st.caption("Synthetic text-to-speech recording; saved transcript and manually authored provisional QA findings.")
            result_view(chosen)
    with corpus_tab:
        st.write("Listen to a public simulated bank call and inspect its human-corrected transcript. AI evaluation is optional and uses LLM credits.")
        corpus_index = Path("data/harpervalley/index.json")
        if corpus_index.exists():
            entries = json.loads(corpus_index.read_text(encoding="utf-8"))
            entry = st.selectbox("HarperValleyBank sample", entries, format_func=lambda x: f"{x['task'].title()} · {x['call_id']}")
            st.caption("Source: Gridspace-Stanford HarperValleyBank, CC BY 4.0. Transcript was human corrected by the dataset authors; no QA score is supplied by the dataset.")
            if entry:
                st.audio(str(Path("data/harpervalley") / entry["audio"]))
                transcript = Transcript.model_validate_json((Path("data/harpervalley") / entry["transcript"]).read_text(encoding="utf-8"))
                with st.expander("Read the original transcript"):
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
                            st.session_state.setdefault("session_analyses", {})[analysis.call_id] = analysis
                            st.success(source)
                            result_view(analysis)
                        except Exception as exc:
                            st.error(f"Evaluation failed: {exc}")
        else:
            st.info("Public corpus files have not been prepared. Run scripts/prepare_harpervalley.py with GitHub CLI and FFmpeg.")
    with upload_tab:
        st.markdown('<p class="step">Step 1 of 3 · choose audio</p>', unsafe_allow_html=True)
        st.write("Try the bundled public clip or upload an authorized mono WAV/MP3. A provider request starts only when you press **Transcribe recording**.")
        if not os.getenv("DEEPGRAM_API_KEY") and os.getenv("TRANSCRIPTION_PROVIDER", "deepgram") == "deepgram":
            st.warning("Live transcription needs DEEPGRAM_API_KEY. Saved demonstration cases remain available.")
        if not os.getenv("GROQ_API_KEY") and os.getenv("LLM_PROVIDER", "groq") == "groq":
            st.warning("Live evaluation needs GROQ_API_KEY. You can still inspect saved results.")
        use_sample = st.checkbox("Use bundled 25-second two-speaker sample (HarperValleyBank, CC BY 4.0)")
        if use_sample:
            audio_file_name = "harper-live-25s.mp3"
            audio_bytes = (Path("data/demo/audio") / audio_file_name).read_bytes()
            st.info("This 25-second clip contains two voices and only the start of a call. Later QA steps remain unassessed. Transcription and evaluation use provider credits.")
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
            if st.button("Transcribe recording", type="primary"):
                try:
                    with st.spinner("Validating and transcribing…"):
                        transcript, source = transcribe_audio(audio_bytes, audio_file_name, store)
                    if use_sample:
                        transcript = transcript.model_copy(update={"recording_scope": "opening_excerpt", "source": "HarperValleyBank 25-second opening excerpt"})
                    st.session_state["transcript"] = transcript
                    st.success(source)
                except Exception as exc:
                    st.error(f"Transcription failed: {exc}")
            transcript = st.session_state.get("transcript")
            if transcript:
                st.markdown('<p class="step">Step 2 of 3 · confirm the agent</p>', unsafe_allow_html=True)
                st.caption(f"Transcript: {transcript.transcription_provider} · {transcript.call_id}")
                speakers = sorted({s.speaker_id for s in transcript.segments})
                st.markdown("#### Check who said what")
                for segment in transcript.segments:
                    st.markdown(f"**{segment.start_seconds:.1f}s · Speaker {segment.speaker_id} · {segment.segment_id}**  {segment.text}")
                roles_uncertain = len(speakers) < 2 or "unknown" in speakers
                if roles_uncertain:
                    st.warning("This transcript does not distinguish two speakers. Agent quality cannot be evaluated reliably. Use a recording with distinct voices or the Manual transcript tab with confirmed roles.")
                agent_speaker = st.selectbox("Which speaker is the agent?", speakers, disabled=roles_uncertain)
                agent_alias = st.text_input("Agent alias", value="Uploaded agent", disabled=roles_uncertain)
                st.caption("Diarization distinguishes voices but does not identify the agent. Confirm the mapping from the transcript and audio before evaluating.")
                st.markdown('<p class="step">Step 3 of 3 · request QA analysis</p>', unsafe_allow_html=True)
                if st.button("Evaluate confirmed transcript", disabled=roles_uncertain):
                    try:
                        ready = confirm_roles(transcript, agent_speaker)
                        with st.spinner("Evaluating rubric and checking evidence…"):
                            analysis, source = evaluate_transcript(ready, agent_alias, store)
                        st.session_state["analysis"] = analysis
                        st.session_state.setdefault("session_analyses", {})[analysis.call_id] = analysis
                        st.success(source)
                    except Exception as exc:
                        st.error(f"Evaluation failed: {exc}")
                if st.session_state.get("analysis"):
                    result_view(st.session_state["analysis"])
    with manual_tab:
        st.write("Use this fallback when speech recognition is unavailable. Enter only an authorized transcript with real timestamps and confirmed roles.")
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
                    st.session_state.setdefault("session_analyses", {})[analysis.call_id] = analysis
                    st.success(source)
                except Exception as exc:
                    st.error(f"Evaluation failed: {exc}")
            if st.session_state.get("manual_analysis"):
                result_view(st.session_state["manual_analysis"])

elif page == "Agent Dashboard":
    st.header("Agent view")
    st.caption("See your recurring coaching opportunities, then open a call to practice a better response.")
    agents = sorted({c.agent_id for c in all_calls})
    agent = st.selectbox("Choose an agent", agents, index=agents.index("Agent Maya") if "Agent Maya" in agents else 0)
    calls = [c for c in all_calls if c.agent_id == agent]
    stats = summarize(calls)
    c1, c2, c3 = st.columns(3)
    c1.metric("Calls reviewed", stats["calls"])
    c2.metric("Average assessable score", f"{stats['average_score']}%" if stats["average_score"] is not None else "—")
    c3.metric("Flagged", stats["flagged"])
    st.line_chart({c.call_id: c.score for c in reversed(calls) if c.score is not None})
    st.write("**Recurring opportunities:**", ", ".join(f"{CRITERIA[k]['label']} ({v})" for k, v in stats["misses"].most_common()) or "None in visible calls")
    st.markdown("#### Next action: inspect a call and rehearse its coaching response")
    call = st.selectbox("Inspect a call", calls, format_func=lambda c: f"{c.call_id} · {c.primary_intent}")
    if call: result_view(call)

elif page == "Manager Dashboard":
    st.header("Manager view")
    st.caption("Spot repeated quality issues and choose a coaching topic for your team. Demo agents are aliases.")
    team = summarize(all_calls)
    t1, t2, t3 = st.columns(3)
    t1.metric("Visible calls", team["calls"])
    t2.metric("Average assessable score", f"{team['average_score']}%" if team["average_score"] is not None else "—")
    t3.metric("Need QA review", team["flagged"])
    st.subheader("Agent summary")
    rows = []
    for agent in sorted({c.agent_id for c in all_calls}):
        stats = summarize([c for c in all_calls if c.agent_id == agent])
        rows.append({"Agent": agent, "Calls": stats["calls"], "Average score": stats["average_score"], "Flagged": stats["flagged"]})
    st.dataframe(rows, hide_index=True, width="stretch")
    st.subheader("Repeated coaching topics")
    misses = summarize(all_calls)["misses"]
    st.bar_chart({CRITERIA[k]["label"]: v for k, v in misses.items()})
    st.caption("Next action: select a repeated topic and review example calls with a QA analyst before coaching the team.")
    with st.expander("See all calls"):
        st.dataframe([{"Call": c.call_id, "Agent": c.agent_id, "Intent": c.primary_intent, "Score": c.score, "Priority": c.review_priority, "Source": c.origin} for c in all_calls], hide_index=True, width="stretch")

elif page == "QA Analyst":
    st.header("QA review queue")
    st.caption("Open the highest-priority call, check its cited evidence, then approve, correct, or request follow-up. Reviews in this public demo stay in your session; enter no private information.")
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
    st.caption("Preview coaching across multiple calls. Download the report as HTML; no email is sent.")
    agent = st.selectbox("Agent", sorted({c.agent_id for c in all_calls}))
    period = st.date_input("Reporting period", value=(date(2026, 11, 13), date.today()))
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
    st.header("How CallIQ works")
    st.write("CallIQ is a post-call QA prototype. It turns audio into a transcript, asks a model for structured findings, checks cited segments, and calculates the rubric score in Python.")
    st.code("Audio → Deepgram / Faster-Whisper → canonical transcript → Groq / Ollama → evidence validation + Python scoring → SQLite → dashboards + report", language="text")
    st.write("Cloud deployment is stateless for uploaded recordings; the local SQLite file can disappear on Streamlit Community Cloud. Synthetic samples are bundled and reseeded. Durable multiuser storage requires a managed database.")
    st.write("Future AWS path: S3 upload, Step Functions orchestration, Transcribe, Bedrock, Aurora PostgreSQL, CloudWatch, and approved SES delivery.")
    st.write("Production work remains: authentication, role permissions, tenant isolation, encryption, retention, PII redaction, and vendor review. Never use preliminary scores alone for employment decisions.")

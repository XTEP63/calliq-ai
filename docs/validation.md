# Validation record

- Environment: Windows 11, Python 3.14.3, Git 2.53.0, FFmpeg available.
- `python -m pytest -q`: 6 passed (2026-11-19). This includes manual transcript validation and public-session isolation.
- Streamlit `AppTest`: Overview, Analyze Call, Agent Dashboard, Manager Dashboard, QA Analyst, Performance Reports, and Architecture & About loaded without script exceptions (2026-11-19).
- Four synthetic MP3 recordings generated using Windows System.Speech and FFmpeg. Eight public corpus calls prepared with source attribution.
- Streamlit Community Cloud deployed from `XTEP63/calliq-ai` main. `https://calliq-ai.streamlit.app/` opened and rendered Overview, saved analysis with corrected transcript evidence, the public corpus, Manager Dashboard, QA Analyst queue, and report preview. An independent HTTP request without browser cookies returned 200 (2026-11-19).
- Live Deepgram/Groq processing was not exercised because API keys were absent. Upload UI shows the missing-key messages. No paid API requests were made.
- Manual transcript fallback tab loads in Streamlit `AppTest` without exceptions. Live provider verification remains pending until the newly configured Secrets are checked and API usage is authorized.

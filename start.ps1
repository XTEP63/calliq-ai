param([switch]$Local)
$ErrorActionPreference = 'Stop'
if ($Local) {
  $env:TRANSCRIPTION_PROVIDER = 'faster-whisper'
  $env:LLM_PROVIDER = 'ollama'
}
python -m streamlit run app.py

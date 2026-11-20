param([switch]$Local)
$ErrorActionPreference = 'Stop'
if ($Local) {
  $env:APP_MODE = 'local'
  $env:TRANSCRIPTION_PROVIDER = 'faster-whisper'
  $env:LLM_PROVIDER = 'ollama'
}
python -m streamlit run app.py

param([Parameter(Mandatory=$true)][string]$InputJson, [Parameter(Mandatory=$true)][string]$OutputDir)
$ErrorActionPreference = 'Stop'
Add-Type -AssemblyName System.Speech
$synth = New-Object System.Speech.Synthesis.SpeechSynthesizer
$segments = Get-Content -LiteralPath $InputJson -Raw | ConvertFrom-Json
foreach ($segment in $segments) {
  $synth.Rate = if ($segment.role -eq 'agent') { 1 } else { -1 }
  $synth.SetOutputToWaveFile((Join-Path $OutputDir ($segment.id + '.wav')))
  $synth.Speak([string]$segment.text)
  $synth.SetOutputToNull()
}

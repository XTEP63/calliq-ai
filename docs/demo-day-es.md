# Guía para presentar CallIQ

## Ruta recomendada: Streamlit público

Abre [calliq-ai.streamlit.app](https://calliq-ai.streamlit.app/) antes de entrar a la sala y conserva una pestaña con la app ya cargada. Usa pantalla compartida a 100% de zoom y prueba el audio. La app pública es la ruta recomendada: no requiere instalar nada en la máquina del evento y tiene los Secrets configurados en Streamlit Cloud.

1. En **Overview**, explica el problema y anuncia que verán una llamada que exige atención de QA.
2. Ve a **Analyze Call → Saved demonstration**. El caso predeterminado es **Card replacement · Agent Maya · High priority**. Es sintético y sus hallazgos fueron escritos para la demo; no consume APIs.
3. Reproduce unos segundos del audio. Muestra la prioridad, abre **Needs attention · Identity verification**, lee el segmento citado y enseña la sugerencia de coaching. Explica que el puntaje sale de un rubric calculado en Python, no de una cifra inventada por el modelo.
4. Ve a **Agent Dashboard**, elige **Agent Maya** y enseña sus llamadas e historial. Luego ve a **Manager Dashboard** para mostrar resumen por agente y temas repetidos.
5. Ve a **QA Analyst** y selecciona la llamada marcada. Demuestra que una persona puede aprobar o corregir el hallazgo; las notas de la demo pública solo viven en esa sesión. Evita escribir datos privados.
6. Ve a **Performance Reports**, selecciona **Agent Maya** y muestra la vista previa. El HTML se puede descargar; CallIQ no manda correos.

Esta ruta es suficiente si el Wi-Fi del evento es lento, un proveedor falla o no quieres gastar créditos. Mantén abierta también la presentación PPTX en PowerPoint local.

## Extensión opcional: análisis nuevo con APIs

Usa **Analyze Call → Upload and process** y marca **Use bundled 25-second two-speaker sample**. No uses las grabaciones sintéticas TTS para demostrar diarización: ambas voces se generaron con un solo motor de voz. Pulsa **Transcribe recording**, revisa los segmentos y confirma que el agente es **Speaker 0** solo si el transcript de esa ejecución lo respalda. Después pulsa **Evaluate confirmed transcript**. Son dos solicitudes externas, una a Deepgram y otra a Groq, que pueden consumir créditos o generar cargos. Comprueba el saldo y la autorización antes de ejecutarlas de nuevo.

El clip público termina a los 25 segundos. Por eso verificación, resolución y cierre pueden quedar como **Not enough evidence** y el puntaje puede figurar **Unscored**. Eso demuestra un control importante: CallIQ no convierte ausencia de audio en un fallo confirmado. Si la API tarda, vuelve a **Saved demonstration** sin esperar en silencio.

## Alternativa local

La app pública es suficiente. Usa la alternativa local solo si ya la probaste en la máquina que presentarás:

```powershell
cd C:\Users\esteb\apps\call-iq
python -m venv .venv       # solo la primera vez
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt  # solo la primera vez
.\start.ps1
```

Haz la instalación antes de la presentación, no frente al público. Abre `http://localhost:8501`. Así se ejecuta la misma app y los seis casos precargados funcionan sin claves. Para procesar una llamada nueva desde localhost debes configurar **en esa terminal** `DEEPGRAM_API_KEY` y `GROQ_API_KEY`; los Secrets de Streamlit Cloud no se copian a tu computadora. No pegues las claves en diapositivas, archivos versionados ni el chat.

`./start.ps1 -Local` activa Faster-Whisper y Ollama, que siguen experimentales. La diarización local no está implementada: una grabación nueva no permite confirmar al agente con suficiente fiabilidad. Para una demo sin Internet, usa los casos guardados o el transcript manual autorizado, y no prometas un flujo de audio nuevo totalmente offline.

## Plan de contingencia de 30 segundos

Si se cae Streamlit, abre `http://localhost:8501` si ya estaba levantado. Si tampoco está disponible, continúa con el PPTX y describe el caso **Card replacement**: una verificación no confirmada activa revisión QA, el segmento explica el hallazgo y el agente recibe una respuesta sugerida. Nunca muestres una evaluación sintética como si fuera resultado de una API en vivo.

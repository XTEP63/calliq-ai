# CallIQ presentation script

**Target length:** about 9 minutes, including a 90-second product demonstration. Two presenters can split the lines below. For a solo presentation, read both parts in sequence. Pause after the question on slide 2 and after the live demonstration.

## Slide 1 — CallIQ

**Presenter A:** Good morning. Imagine that your contact center handled thousands of conversations yesterday. How many of those conversations can your quality team actually review today?

**Presenter B:** We built CallIQ to help teams turn calls into evidence, coaching, and a clear queue for human review. Our principle is simple: every call counts, and every insight should lead to action.

## Slide 2 — The blind spot

**Presenter A:** Most quality programs rely on a small sample of manual reviews. The problem is not that reviewers lack skill. The problem is that listening, scoring, and documenting each call takes time. A randomly missed call can contain an avoidable process error or a coaching opportunity.

**Presenter B:** Our question was: can we help a QA team see where to look first, while keeping people accountable for the final decision?

## Slide 3 — Who feels the cost

**Presenter A:** The agent gets feedback late and often cannot connect it to a precise moment. The manager sees a team score but struggles to identify repeated behaviors. The QA analyst spends time finding the calls that deserve attention.

**Presenter B:** One conversation can affect all three people. CallIQ gives each of them a different view of the same evidence.

## Slide 4 — One call, structured evidence

**Presenter B:** Here is the workflow. We start with a mono recording or a verified transcript. Speech recognition returns timestamped turns. A person confirms which speaker is the agent. The language model classifies the call and proposes findings using segment IDs.

**Presenter A:** Then ordinary Python code validates those IDs and calculates the rubric score. That separation matters: the model explains what it sees, while deterministic rules calculate the score and flag critical findings.

## Slide 5 — Uncertainty stays visible

**Presenter B:** Consider a 25-second opening excerpt. We may hear the greeting and the customer request, but the recording ends before the agent can finish the procedure. We should not call the missing closing a confirmed failure.

**Presenter A:** CallIQ marks those later steps as insufficient evidence and shows score coverage. If coverage is too low, it withholds the score. Human QA can then request the complete call.

## Slide 6 — Feedback becomes coaching

**Presenter A:** A useful evaluation should help the next conversation, not just label the last one. CallIQ shows the transcript moment, the finding, a concrete alternative response, and a next step to practice.

**Presenter B:** Across several calls, the agent view shows recurring opportunities. The manager view shows team patterns. The weekly report turns those patterns into coaching goals.

## Slide 7 — Live product demonstration

**Presenter B:** Let me show the reliable path. I will open the saved card replacement case. This is a synthetic demonstration case, so it loads instantly and makes no API request.

**Presenter A:** Notice the high review priority. Open the identity verification finding and point to the exact cited turn. Then show the suggested correction. Move to the manager view to see the repeated topics and to the QA queue to see where a reviewer would start.

**Presenter B:** If time and provider credits allow, we can also transcribe a public two-speaker recording live, confirm the agent, and request a new model evaluation. We will keep that optional because the main product story should not depend on network latency.

## Slide 8 — The market already validates the need

**Presenter A:** Established platforms such as NICE, CallMiner, and Observe.AI offer automated quality management, analytics, and coaching. Some also provide real-time guidance and broad channel coverage. This is an active category, not an empty market.

**Presenter B:** CallIQ is a focused pilot. Its current design emphasizes traceable transcript segments, visible uncertainty, deterministic rubric math, and provider adapters that can be exchanged. We are not claiming enterprise-scale coverage or a feature advantage over those mature suites today.

## Slide 9 — What works today

**Presenter B:** The MVP is public. We have a working upload and transcription path, speaker confirmation, structured evaluation, evidence checks, deterministic scoring, stakeholder views, and a weekly report preview. We also include ready-made synthetic cases and an attributed public corpus for a reliable demonstration.

**Presenter A:** The live pipeline has been tested end to end on a public clip. The complete quality workflow still needs production controls before use with real customer data.

## Slide 10 — The path to enterprise use

**Presenter B:** The next stage is a controlled pilot: agreed policy rubrics, calibration against human reviewers, measured precision and recall for QA flags, secure data handling, and integration with contact center systems.

**Presenter A:** At enterprise scale we would add identity and role controls, tenant isolation, retention policies, and approved infrastructure. AI findings would remain advisory until a human reviewer confirms them.

## Slide 11 — Close

**Presenter A:** We are asking for a small, measured pilot with a QA team, not a blind rollout. Give us an approved set of calls and a reviewer baseline, and we can test whether CallIQ helps people find the right calls and coach the right behaviors.

**Presenter B:** CallIQ makes every reviewed call more useful. Thank you. We would be happy to take questions.

## Short answers for likely questions

**Is the score generated by the LLM?** No. The LLM returns structured findings; Python applies rubric weights and calculates the score.

**What if the recording is incomplete?** CallIQ marks unobservable steps as insufficient evidence and shows coverage. An opening excerpt with low coverage is unscored.

**Is this ready for customer data?** No. The current public demo uses synthetic and public simulated calls. Production requires access controls, retention, privacy review, and QA calibration.

**How is this different from established suites?** Our near-term position is a transparent, modular pilot that can be adapted to a team's rubric and providers. We do not claim functionality the current MVP has not demonstrated.

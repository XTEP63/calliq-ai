# CallIQ — solo presentation script

**Format:** one presenter, about 7–8 minutes. The slides tell the complete story without a live product demo. The card replacement example is a synthetic, manually prepared demonstration case in the current MVP; it is not a measured customer result or a live model response.

## Slide 1 — CallIQ

Good morning. I want to start with a simple question: if your contact center handled thousands of conversations yesterday, which of those conversations will actually change how your team works tomorrow?

CallIQ is an AI-assisted quality and coaching platform for contact centers. It turns a conversation into a reviewable finding, a practical coaching step, and a clearer priority for the QA team.

## Slide 2 — The blind spot

Quality teams do valuable work, but listening to, scoring, and documenting a call takes time. So they often review a sample. A call outside that sample may contain a missed procedure, a customer concern, or a moment where an agent needed support.

The opportunity is to help reviewers find the right conversations sooner and make each review more useful.

## Slide 3 — Three people, one gap

Think about the three people around a call. An agent needs feedback tied to something they actually said. A manager needs to see repeated behavior across a team. A QA analyst needs to know which call deserves attention first.

They do not need three disconnected reports. They need different decisions grounded in the same conversation.

## Slide 4 — The call

Let me show you a small example. This is a synthetic card replacement conversation built into our demo. A customer says, “I lost my debit card and need a new one.” Maya replies that she can replace it and gives an arrival estimate. Then the customer asks what happens to the old card, and Maya ends the call with “It should stop working. Goodbye.”

On a quick listen, this may sound like a routine service interaction. But the exact words matter. Where was identity verification? Was the old card actually blocked? Did the customer get a clear resolution? This is where a quality review becomes useful.

## Slide 5 — What CallIQ would surface

In this prepared demo review, CallIQ flags identity verification for human attention. The finding points to the opening and the replacement promise, where no verification is heard. It marks the procedure outcome as insufficient evidence: the call does not confirm that the old card was blocked. The closing is also weak.

The preliminary score is 42.9 percent with 70 percent rubric coverage, and the call is placed at high QA priority. Those numbers are not the whole story. The value is that a reviewer can inspect the cited turns, confirm or correct the finding, and see exactly why the case rose to the top.

## Slide 6 — Turn a finding into coaching

The next step is not simply telling Maya she failed. CallIQ suggests a response she can practice: “Before I process a replacement, I need to complete identity verification.”

That creates a practical loop. The agent sees a specific improvement. The manager can watch for the same behavior across calls. QA can spend time on the calls that need judgment. With more reviewed calls, a weekly report can summarize repeated coaching opportunities.

## Slide 7 — How the product works

Under the hood, the workflow is straightforward. Start with a recording or a transcript. Transcription produces speaker turns. A person confirms who the agent is. The evaluation proposes a call category and rubric findings with transcript segment IDs. Python checks those references and calculates the weighted score.

That design keeps the evidence visible. If the recording is incomplete, CallIQ can mark a criterion as insufficient evidence and show score coverage. A human reviewer remains responsible for the final quality decision.

## Slide 8 — Why CallIQ

Contact center analytics is an established category. NICE, CallMiner, and Observe.AI offer broad quality and coaching products. Our near-term entry point is deliberately focused: a transparent post-call QA workflow that a team can pilot against its own rubric.

What we want to prove is a connected chain: from a specific turn in a call, to a reviewable finding, to a coaching action, to a pattern across calls. We also designed the provider layer so transcription and language models can change as requirements change. Those choices support a controlled pilot; they are not a claim that this MVP has more features than mature suites.

## Slide 9 — What is real today

The MVP already supports saved synthetic cases, a public demo, a tested transcription and evaluation path, evidence checks, deterministic scoring, agent and manager views, a QA queue, and a weekly report preview.

The next step before real customer data is equally clear: approved access controls, privacy and retention rules, calibration with human reviewers, and contact center integration. We want to measure the product in a safe, realistic setting before making enterprise claims.

## Slide 10 — The pilot

So here is the pilot we propose: use an approved set of calls and an existing human QA baseline. Then ask three concrete questions. Can the team find important calls sooner? Do cited transcript moments make reviews faster and clearer? Does repeated coaching help agents improve over time?

If we cannot show those changes, we will know what to fix. If we can, we will have evidence for the next stage of investment.

## Slide 11 — Close

CallIQ starts with one conversation, but the goal is a stronger quality loop across the team. Every call can reveal something; the value comes when that insight helps a person make a better decision.

We are asking for a small, human-reviewed pilot with a QA team and approved calls. Thank you. I would welcome your questions.

## Short answers for likely questions

**Did an AI model produce the example on slides 4–5?** No. It is a synthetic saved case with manually authored provisional findings. The separate live evaluation path has been tested, but the presentation does not depend on a network call.

**Does the model set the score?** No. It proposes structured findings; Python validates evidence references and calculates rubric weights.

**What if part of a recording is missing?** The reviewer sees insufficient-evidence criteria and score coverage. Low coverage can withhold a score.

**Is the public MVP ready for real customer recordings?** No. Production use needs access controls, data-handling approval, human calibration, and monitoring.

**How is CallIQ different from established suites?** The near-term proposition is an adaptable, evidence-first pilot focused on post-call QA and coaching. We would test its value against a human baseline rather than claim superiority without evidence.

**What if a live demo is requested after the talk?** Open the saved synthetic card replacement case first. Only run a new transcription and evaluation if the format, connection, and approved provider credits permit it. This is optional and outside the slide narrative.

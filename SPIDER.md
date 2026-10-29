# JARVIS MARK 2 is SPIDER

Spider coordinates public-source research, real subprocess tool jobs, evidence
routing and durable review lessons. It has no brokerage order interface.

## Real hierarchy

Spider / Mark 2 supervisor → repository task groups → three actual subprocess
workers per repository: license metadata check, static source review and
candidate readiness. Eight repository records produce 24 worker processes;
at most two run concurrently. Groups are task containers, not extra processes.
Each launched worker records its PID, start/end timestamps and actual result.
Queued tasks are not described as running; a dead supervisor is detected.

The office shows the eight named review roles separately from the process
tree. Six external AI providers have saved web reviews, not unattended API
connections. Tool workers support those review tasks; they are not Claude,
Grok or other model instances and were not spawned by those providers.
Qwen stays the existing VPS analyst. No new process is installed on the VPS.

## What flows through Spider

- Public GitHub source status → Spider → compiled research context.
- Saved reviewer summaries → Spider → compiled research context.
- Real subprocess results → Spider → compiled research context.
- Existing read-only Mark 1 monitor → Spider → local display.
- Compiled context → Spider → local display.

The local SQLite router persists deduplicated envelopes with source, target,
kind, receipt time, payload and SHA256 fingerprint. Receipt time is NOT the
time an external AI generated its review. The packet inspector exposes this
distinction. Trace animates an actual recorded envelope; new delivery pulses
are driven by newly received hub records, not a fabricated conversation.

The local context/packet database may contain demo monitor data and must stay
local. It is ignored by Git. Only the public-source child-worker results and
review lessons are included in cloud outputs.

## Learning each review

Cloud research cycles run the real worker fleet, persist its results and update
`data/review-lessons.json`. Findings have source/commit/rule provenance, first
and last observed timestamps, review counts and open status. UI polling does
not inflate review counts. This is operational evidence memory, not LLM weight
training. No finding automatically changes risk, promotes a strategy or trades.

The office's Run Child Workers button dispatches another bounded local evidence
review through Spider. The scheduled GitHub workflow runs these same review
tools in the cloud independently of the Mac when the deployed cycle runs.

Native MT5 compilation, signal parity and profitability are still unverified.
The worker reports those missing requirements rather than inventing results.

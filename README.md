# JARVIS MARK 2 — independent EA research worker

Mark 2's identity is **SPIDER**, the research coordinator and data router.
See [SPIDER.md](SPIDER.md) for real worker hierarchy, message routing and
review lessons. Its named AI reviewers are distinct from actual tool processes.

Mission: discover public MT5 EA source, retain reproducible source evidence,
review code heuristics, and create isolated tester-only EA variants.
Independent process, folder, state and journal. No Mark 1 runtime imports.

## Current limits

This is a deterministic autonomous worker, not a separately connected LLM.
It does not trade, buy EAs, create accounts, or transfer funds. GitHub public
read-only API needs no user account; rate-limit failures are recorded. External
source is stored as inert JSON, never executed or automatically trusted.
Repository stars do not rank profit. No verified best EA exists yet.

Three generated long-only MA/H1-trend EA variants inherit the existing
unproven JARVIS tester baseline. Source is generated and hashed; compilation,
native MT5 testing and forward-demo evaluation are NOT completed. No new
backtest was launched. Every generated EA refuses to initialize outside the
MT5 Strategy Tester. No automatic promotion into Mark 1 or trading terminals.

## Reuse-first extension

An additional candidate reuses the actual BUY/SELL signal functions from
geraked/metatrader5 `Experts/3MACD.mq5` at pinned commit
`d3eb29c382acf715727d5cd6a0414151e821fc2d`. The upstream source, MIT license
and SHA256 provenance are retained. `reuse.py` extracts the signal functions
and removes order execution; the generated adapter only prints signal events
inside the Strategy Tester. It does not reuse EAUtils, grids or stock risk
defaults. Reverse=true is preserved explicitly. It is NOT compiled,
profit-tested or replay-verified against upstream yet.

Six external AI web reviews were received and checked; see [AI-TEAM.md](AI-TEAM.md).
These are session consultations, not unattended cloud API integrations.

## Operation

Python 3 standard library only. `python agent.py --once` runs one research
cycle; `python agent.py` runs independent hourly research plus a local dashboard
on `127.0.0.1:8766`. Logs and source evidence are in `data/`; generated source
and hashes are in `generated/`. No account data or passwords belong here.
The local process stops when its host stops. User selected free cloud and is
concerned about VPS load: DO NOT deploy this worker onto the trading VPS.
Cloud deployment is active: first cloud run completed successfully on 29 Oct
2026 at 22:46 MYT. No Mark 2 process is installed on the trading VPS.

## Prepared free cloud workflow

The GitHub Actions workflow runs hourly or manually, independently
of Mac and Mark 1. It is restricted to a PUBLIC repository and a standard
Ubuntu runner; private jobs are skipped. No paid APIs, artifacts, large runner
or subscriptions. Only project code, public source analysis and generated own
EA are published. Raw downloaded external source is ignored. Each run has an
eight-minute limit and retains a bounded repository registry. GitHub schedule
can be delayed or disabled by GitHub; it is not an always-on service.

First cloud run verified: https://github.com/tw7c42sb8m-oss/jarvis-mark2/actions/runs/40894740797
The persisted `data/status.json` confirms `runtime: GITHUB_ACTIONS`, six
repositories reviewed, three tester-only variants generated, zero research
errors and zero broker orders. The three Python worker tests also passed in
the cloud. This verifies software operation, not EA profitability.

Cloud schedule is hourly at minute 23 (MYT). GitHub may delay schedules. Mac and trading VPS are not required
for these cloud cycles. Native MT5 compilation and performance evaluation
remain pending; no backtest or broker trading is launched by this worker.

Public GitHub API: https://docs.github.com/en/rest/search/search
MT5 tester: https://www.metatrader5.com/en/terminal/help/algotrading/testing
Forward optimization: https://www.metatrader5.com/en/terminal/help/algotrading/strategy_optimization

# JARVIS MARK 2 — independent EA research worker

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

## Operation

Python 3 standard library only. `python agent.py --once` runs one research
cycle; `python agent.py` runs independent hourly research plus a local dashboard
on `127.0.0.1:8766`. Logs and source evidence are in `data/`; generated source
and hashes are in `generated/`. No account data or passwords belong here.
The local process stops when its host stops. User selected free cloud and is
concerned about VPS load: DO NOT deploy this worker onto the trading VPS.
Cloud deployment is not yet done; storage alone does not run the agent.

## Prepared free cloud workflow

The GitHub Actions workflow runs every six hours or manually, independently
of Mac and Mark 1. It is restricted to a PUBLIC repository and a standard
Ubuntu runner; private jobs are skipped. No paid APIs, artifacts, large runner
or subscriptions. Only project code, public source analysis and generated own
EA are published. Raw downloaded external source is ignored. Each run has an
eight-minute limit and retains a bounded repository registry. GitHub schedule
can be delayed or disabled by GitHub; it is not an always-on service.

Deployment is being verified. A successful Actions run and its persisted
`data/status.json` with `runtime: GITHUB_ACTIONS` establish the first cloud
cycle; source files alone do not establish that the worker is running.

Public GitHub API: https://docs.github.com/en/rest/search/search
MT5 tester: https://www.metatrader5.com/en/terminal/help/algotrading/testing
Forward optimization: https://www.metatrader5.com/en/terminal/help/algotrading/strategy_optimization

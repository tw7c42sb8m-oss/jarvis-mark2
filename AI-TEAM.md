# Mark 2 research team — 29 October 2026

| AI | Role | Verified involvement in this update |
| --- | --- | --- |
| Codex | Source verification, implementation, test and cloud deployment | Coordinator |
| Claude | Dependency and implementation review | Web review received |
| Kimi | Reuse experiments and additional source discovery | Web review received |
| Grok | Critical assessment of defaults and reported performance | Web review received; overstatements challenged |
| DeepSeek | MQL5 buffers, reversal and signal parity review | Web review received in Safari; indexing correction sent |
| Gemini | Independent adapter and rejection-criteria review | Free anonymous web review received |
| Perplexity | Primary-source discovery and source categories | Free anonymous web review received |
| Qwen | Existing bounded Mark 1 analyst | Existing VPS role only; not queried or changed by this update |

These are research/coding assistants, not evidence of a profitable trading
strategy. All six external web consultations used the same generic public-code
brief and different reviewer roles. No brokerage credentials, account numbers,
private trade ledger, purchases, or paid API were used.

The cloud worker is a deterministic scheduled researcher. It does not call
these websites, train an LLM, hold their browser sessions, or automatically
obey their replies. Web liaison was performed during this session; it is not
an unattended API integration.

## Adopted findings

- Reuse the pinned MIT 3MACD signal functions from geraked/metatrader5.
- Preserve the upstream copyright and full MIT license.
- Exclude EAUtils, grid, order routing, account state, and stock risk defaults.
- Keep all candidate compilation and signal replay separate from Mark 1.
- Preserve the upstream `Reverse=true` convention in a single direction flip.
- Require complete copied buffers, closed-bar reads and later signal parity
  checks. MT5 compilation and parity checks have NOT been completed.
- Keep EA31337 as an architectural reference; its recursive framework and
  GPL code are not copied into this adapter.

## Corrections and rejected claims

- DeepSeek initially assigned shift 2 to copied array index 0 irrespective of
  array indexing. Rejected: `CopyBuffer` start position, physical order and
  logical `ArraySetAsSeries` indexing are separate. The adapter preserves
  start=0, dynamic series arrays and signal references at indices >=1.
  Primary documentation: https://www.mql5.com/en/docs/series/copybuffer and
  https://www.mql5.com/en/docs/array/arraysetasseries .
- Grok called configurable input defaults hard-coded behavior and inferred
  that every reported curve necessarily reflected martingale recovery.
  Neither inference is justified without the settings behind each report.
  A grid is not synonymous with martingale. Correction requested.
- AI agreement is not independent validation when reviewers receive the
  same supplied facts. Source checks and native replay evidence remain
  necessary. No claim of profitability has been adopted.
- Perplexity described additional components as MIT, but GitHub metadata
  did not establish a clear license for two suggestions. No code copied.

## Sources considered

1. https://github.com/geraked/metatrader5 — chosen signal source, MIT.
   Pinned commit d3eb29c382acf715727d5cd6a0414151e821fc2d.
   3MACD uses built-in iMACD; DHLAOS has custom-indicator dependencies.
2. https://github.com/EA31337/EA31337 — GPL-3.0 multi-strategy framework;
   reference only, no framework execution or code integration.
3. https://github.com/sibvic/mq5-templates — MIT metadata verified;
   template research shortlist, individual snippets not audited yet.
4. https://github.com/EarnForex/PositionSizer — position-sizing utility,
   not proof of an autonomous entry strategy; no code integrated.
5. https://github.com/RicardoBarato/xauusd-mt5-expert-advisor — GPL-3.0
   metadata verified; source research shortlist only.
6. https://github.com/zephyrrr/MLEA — no clear root license established,
   last metadata update 2013; no copying or execution.
7. https://github.com/moko-jumbie/pine-to-mql5-ea — repository exists,
   license unconfirmed by metadata; no copying or execution.
8. https://github.com/abebr/awesome-mql5-expert-advisors — repository exists,
   GitHub license metadata NOASSERTION; no copying or execution.

No source is declared the best-performing EA. Public reports have not been
replicated on the user's broker, and no new backtest or broker trade ran.

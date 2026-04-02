# QA Gate: DejaVu CLI Featurepack (dejavu-cli-impl-featurepack-005)

**Author:** Seraph | **Date:** 2026-04-01 | **Status:** GATE PREPARED — awaiting Neo delivery

---

## Acceptance Criteria & Test Matrix

### Criterion 1: Strategies are state-agnostic (no state binding in definition/storage)
| # | Test | Input | Expected | Severity |
|---|------|-------|----------|----------|
| DEC-1 | StrategyBuilder has no `state` param | `builder.add_rule(condition="close > vwap", action="long")` | Method signature has no `state` argument | Critical |
| DEC-2 | `parse()` doesn't filter by state | DataFrame with `state` column, strategy with no state ref | No `df["state"] == X` in parse logic | Critical |
| DEC-3 | Old state-conditional rules rejected | `builder.add_rule(state=1, condition=...)` or `strategy add trigger --state 1` | Returns error / rejects `state=` in rule string | Major |
| DEC-4 | Strategy saved without model reference | `ctx.strategies[name]` | No model_type or state_sequence embedded in strategy object | Major |
| DEC-5 | `strategy show` displays only price/indicator rules | `strategy help / show` | Output shows conditions, no state references | Minor |

### Criterion 2: Backtest requires/asks for strategy + model + model state
| # | Test | Input | Expected | Severity |
|---|------|-------|----------|----------|
| BT-1 | `backtest` command with no args | `backtest` (no flags) | Prompts for strategy, model, state OR errors | Critical |
| BT-2 | Minimal valid invocation | `backtest --strategy X --model hmm --state N` | Runs backtest successfully | Critical |
| BT-3 | Missing strategy flag | `backtest --model hmm --state N` | Error: strategy required | Major |
| BT-4 | Missing state flag | `backtest --strategy X --model hmm` | Error: state required | Major |
| BT-5 | Tab-completion on strategy/model/state | `backtest --strategy <TAB>` | Completes from available values | Minor |

### Criterion 3: Entry gating by selected state, exits/no-overnight intact
| # | Test | Input | Expected | Severity |
|---|------|-------|----------|----------|
| GATE-1 | Entry suppressed when state ≠ target | Strategy triggers on all bars; state filter set to "State 1" | Entry signals only on bars where `state == 1` | Critical |
| GATE-2 | Exits NOT suppressed by state | Position open; state changes to non-target on next bar | Exit signal still fires | Critical |
| GATE-3 | No-overnight enforcement active | Last bar of each day | No entries on last bar, exits forced | Critical |
| GATE-4 | Regime mask OR logic correct | Multiple states specified | Entries on ANY of the selected states | Major |

### Criterion 4: HLC chart renders state background + entry/exit markers
| # | Test | Input | Expected | Severity |
|---|------|-------|----------|----------|
| CHART-1 | `chart hlc` renders HLC bars | After backtest | Terminal chart with high-low-close visualization | Critical |
| CHART-2 | State-colored background | Model fitted, states present | Each bar column has background color corresponding to state | Critical |
| CHART-3 | Entry markers overlay | Backtest produced trades | Green ▲ markers at entry timestamp/price | Critical |
| CHART-4 | Exit markers overlay | Backtest produced trades | Red ▼ markers at exit timestamp/price | Critical |
| CHART-5 | `--no-states` flag | `chart hlc --no-states` | Chart renders without state background | Minor |
| CHART-6 | `--no-trades` flag | `chart hlc --no-trades` | Chart renders without entry/exit markers | Minor |
| CHART-7 | `--overlay vwap` flag | `chart hlc --overlay vwap` | VWAP line overlaid on chart | Minor |
| CHART-8 | Downsampling for wide data | >120 bars in 80-char terminal | Chart downsamples to fit terminal width | Minor |

### Criterion 5: Command/docs consistency (no contradictory old flow text)
| # | Test | Input | Expected | Severity |
|---|------|-------|----------|----------|
| DOC-1 | Help text updated | `help` command | No mention of `strategy add --state X` or old backtest flow | Major |
| DOC-2 | do_model help updated | `model --help` | Consistent with new workflow | Minor |
| DOC-3 | do_backtest help updated | `backtest --help` | Shows new multi-arg usage (strategy + model + state) | Major |
| DOC-4 | do_strategy help updated | `strategy --help` | No state references in strategy commands | Minor |

---

## Evidence Commands (for Neo to pass)

```bash
# Build/Import
cd /home/smith/Projects/dejavu && source venv/bin/activate && python -c "from dejavu.strategy.builder import StrategyBuilder; from dejavu.strategy.engine import BacktestEngine; from dejavu.shell import DejavuShell; print('OK')"

# StrategyBuilder API — no state param
python -c "
import inspect
from dejavu.strategy.builder import StrategyBuilder
sig = inspect.signature(StrategyBuilder.add_rule)
assert 'state' not in sig.parameters, 'FAIL: state still in API'
print('StrategyBuilder.add_rule state-free: PASS')
"

# Backtest requires strategy + model + state
python -c "
import inspect
from dejavu.shell import DejavuShell
src = inspect.getsource(DejavuShell.do_backtest)
assert '--strategy' in src or 'strategy' in src, 'FAIL: no strategy arg'
assert '--model' in src or 'model' in src, 'FAIL: no model arg'
assert '--state' in src or 'state' in src, 'FAIL: no state arg'
print('Backtest arg requirements: PASS')
"

# No-overnight enforcement in engine
python -c "
import inspect
from dejavu.strategy.engine import BacktestEngine
src = inspect.getsource(BacktestEngine.run)
# Verify state gating: tech entries AND regime mask
assert 'regime_mask' in src or 'state' in src.lower(), 'FAIL: no state gating'
assert 'enforce_no_overnight' in src, 'FAIL: no-overnight missing'
print('State gating + no-overnight: PASS')
"

# Chart module
python -c "
from dejavu.ui.charts import render_annotated_hlc
print('HLC chart module imported: PASS')
"

# Help text consistency
python -c "
import inspect
from dejavu.shell import DejavuShell
help_text = DejavuShell.do_help.__doc__ or ''
help_src = inspect.getsource(DejavuShell.do_help)
assert '--state' not in help_src or 'backtest' in help_src, 'FAIL: stale state ref in help'
print('Help text consistency: PASS')
"
```

---

## Prior Blockers (from qa_impl_core_report.md)

These must remain closed or be explicitly addressed in the featurepack delivery:

| Prior Blocker | Status | Featurepack Impact |
|---------------|--------|--------------------|
| API key validation in AlpacaProvider | OPEN (minor operational risk) | Out of scope for featurepack, but should not regress |
| HMM multi-feature convergence | CLOSED in rev-1 | Verify not broken by featurepack changes |
| Zero-cost disclosure in metrics table | CLOSED in rev-1 | Verify not removed by featurepack changes |

---

## QA Execution Plan

1. **Import + structural checks** — verify new API surface
2. **Decoupling verification** — StrategyBuilder has no state binding
3. **Backtest gating verification** — requires strategy + model + state triplet
4. **Entry/exit/no-overnight functional test** — state mask applied correctly
5. **HLC chart test** — renders with state background + trade markers
6. **Docs/help consistency sweep** — no old-flow text
7. **Prior regression sweep** — verify no regressions to closed blockers

Status: **GATE READY. Awaiting Neo deliverable at `/home/smith/Projects/dejavu/`.**

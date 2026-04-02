# DejaVu v2 - CLI Framework

Interactive quantitative research workstation for intraday regime discovery and strategy validation.

## Prerequisites
- Python 3.11+

## Installation

```bash
cd /home/smith/Projects/dejavu
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

## Running the CLI

```bash
python3 -m dejavu
```

## Current Flow

1. Load intraday data:
   ```bash
   use AAPL --range 10d --freq 5m
   ```
   Alpaca IEX is primary when keys are configured; `yahooquery` is the fallback.

2. Fit a model:
   ```bash
   model hmm --states 3
   ```
   The CLI stores inferred states separately from strategies.

3. Create a state-agnostic strategy:
   ```bash
   strategy new momentum_breakout --rule "close > vwap and rel_vol > 1.5" --action long
   strategy add momentum_breakout --rule "close < prev_close" --action exit
   ```

4. Bind strategy + model + state at backtest time:
   ```bash
   backtest --strategy momentum_breakout --model hmm --state 2
   ```
   You can also pass a state label instead of a numeric state id.

5. Render the annotated HLC chart:
   ```bash
   chart hlc --overlay vwap
   ```
   The chart shows HLC bars, state-colored backgrounds, and entry/exit markers from the most recent backtest.

## Notes
- Strategies must be state-agnostic. Any rule containing `state` is rejected.
- Backtest reporting explicitly assumes zero slippage and zero commission.
- `show trades` prints the latest trade table from the most recent backtest.

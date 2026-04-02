import logging
from typing import Dict, Any, Tuple

import pandas as pd
import vectorbt as vbt

from dejavu.strategy.builder import StrategyBuilder

logger = logging.getLogger(__name__)


class BacktestEngine:
    def __init__(self, data: pd.DataFrame, builder: StrategyBuilder):
        self.data = data
        self.builder = builder

    def enforce_no_overnight(self, entries: pd.Series, exits: pd.Series) -> Tuple[pd.Series, pd.Series]:
        logger.debug("Enforcing no-overnight policy")
        is_last_bar = pd.Series(False, index=self.data.index)
        dates = self.data.index.date
        for date_value in pd.Series(dates).unique():
            day_mask = dates == date_value
            day_index = self.data.index[day_mask]
            if len(day_index) > 0:
                is_last_bar.loc[day_index[-1]] = True
        entries = entries & ~is_last_bar
        exits = exits | is_last_bar
        return entries.astype(bool), exits.astype(bool)

    def run(self, model_states: pd.Series, target_state: int) -> Tuple[vbt.Portfolio, Dict[str, pd.Series]]:
        logger.info("Running vectorbt backtest engine")
        tech_entries, tech_exits = self.builder.evaluate(self.data)
        regime_mask = (model_states == target_state)
        entries = tech_entries & regime_mask
        exits = tech_exits.copy()
        entries, exits = self.enforce_no_overnight(entries, exits)
        logger.info("Executing backtest with ZERO slippage and ZERO commission (Default MVP Behavior)")
        portfolio = vbt.Portfolio.from_signals(
            self.data["close"],
            entries=entries,
            exits=exits,
            fees=0.0,
            slippage=0.0,
            freq="5m",
        )
        return portfolio, {
            "tech_entries": tech_entries,
            "tech_exits": tech_exits,
            "regime_mask": regime_mask,
            "entries": entries,
            "exits": exits,
        }

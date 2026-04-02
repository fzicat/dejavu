from typing import Optional, Dict, Any
import pandas as pd


class SessionContext:
    def __init__(self):
        self.active_ticker: Optional[str] = None
        self.active_timeframe: Optional[str] = None
        self.data: Optional[pd.DataFrame] = None
        self.active_model: Optional[str] = None
        self.model_params: Dict[str, Any] = {}
        self.state_sequence: Optional[pd.Series] = None
        self.fitted_models: Dict[str, Dict[str, Any]] = {}
        self.active_strategy: Optional[str] = None
        self.strategies: Dict[str, Any] = {}
        self.backtest_results: Optional[Any] = None
        self.last_backtest: Optional[Dict[str, Any]] = None

    def status(self) -> Dict[str, Any]:
        return {
            "Ticker": self.active_ticker or "None",
            "Timeframe": self.active_timeframe or "None",
            "Data Rows": len(self.data) if self.data is not None else 0,
            "Active Model": self.active_model or "None",
            "Fitted Models": ", ".join(self.fitted_models.keys()) if self.fitted_models else "None",
            "Active Strategy": self.active_strategy or "None",
        }

    def clear(self):
        self.__init__()

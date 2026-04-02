import pandas as pd
import numpy as np
import logging
from dejavu.models.base import BaseModel

logger = logging.getLogger(__name__)

class LSTMModel(BaseModel):
    def fit(self, df: pd.DataFrame) -> None:
        logger.info(f"Fitting LSTM with params: {self.params}")
        # Phase 2 TODO: Implement PyTorch LSTM training loop
        self.is_fitted = True

    def infer_states(self, df: pd.DataFrame) -> pd.Series:
        logger.info(f"Inferring states with LSTM")
        # Random states between 0 and 2
        states = np.random.randint(0, 3, len(df))
        return pd.Series(states, index=df.index, name="state")

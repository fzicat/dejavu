import pandas as pd
import numpy as np
import logging
from hmmlearn.hmm import GaussianHMM
from dejavu.models.base import BaseModel

logger = logging.getLogger(__name__)

class GaussianHMMModel(BaseModel):
    def _extract_features(self, df: pd.DataFrame) -> np.ndarray:
        # Calculate log returns
        log_ret = np.log(df['close'] / df['close'].shift(1)).fillna(0)
        
        # Realized volatility
        realized_vol = log_ret.rolling(window=10).std().fillna(log_ret.std())
        
        # VWAP deviation (distance from VWAP as %)
        vwap_dev = ((df['close'] - df['vwap']) / df['vwap']).fillna(0)
        
        # Relative Volume (already calculated in features.py)
        rel_vol = df.get('rel_vol', pd.Series(1.0, index=df.index)).fillna(1.0)
        
        # Normalize features
        log_ret_norm = (log_ret - log_ret.mean()) / (log_ret.std() + 1e-8)
        vol_norm = (realized_vol - realized_vol.mean()) / (realized_vol.std() + 1e-8)
        vwap_dev_norm = (vwap_dev - vwap_dev.mean()) / (vwap_dev.std() + 1e-8)
        rel_vol_norm = (rel_vol - rel_vol.mean()) / (rel_vol.std() + 1e-8)
        
        X = np.column_stack([
            log_ret_norm.values,
            vol_norm.values,
            vwap_dev_norm.values,
            rel_vol_norm.values
        ])
        
        return X

    def fit(self, df: pd.DataFrame) -> None:
        logger.info(f"Fitting HMM with params: {self.params}")
        self.n_states = int(self.params.get('states', 3))
        
        # Reproducible random state for stability
        self.model = GaussianHMM(
            n_components=self.n_states, 
            covariance_type="diag", 
            n_iter=200, 
            random_state=42
        )
        
        X = self._extract_features(df)
        self.model.fit(X)
        self.is_fitted = True

    def infer_states(self, df: pd.DataFrame) -> pd.Series:
        logger.info(f"Inferring states with HMM (Static Inference)")
        if not self.is_fitted:
            self.fit(df)
            
        X = self._extract_features(df)
        states = self.model.predict(X)
        
        # Label states by their characteristics
        df_copy = df.copy()
        df_copy['state'] = states
        df_copy['returns'] = df_copy['close'].pct_change()
        
        # Group by state to get statistics
        stats = df_copy.groupby('state')['returns'].agg(['mean', 'std'])
        self.state_labels = {}
        
        global_vol = df_copy['returns'].std()
        
        for state in range(self.n_states):
            if state in stats.index:
                mean_ret = stats.loc[state, 'mean']
                vol = stats.loc[state, 'std']
                
                direction = "Bullish" if mean_ret > 0.0001 else ("Bearish" if mean_ret < -0.0001 else "Neutral")
                vol_label = "High Vol" if vol > global_vol else "Low Vol"
                
                self.state_labels[state] = f"{direction} / {vol_label}"
            else:
                self.state_labels[state] = "Unknown"
                
        # Attach labels to context dynamically if needed by the UI
        return pd.Series(states, index=df.index, name="state")

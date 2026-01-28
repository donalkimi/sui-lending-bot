from abc import ABC, abstractmethod
from datetime import datetime
from typing import Tuple
import pandas as pd
import sys
import os

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from data.refresh_pipeline import refresh_pipeline
from dashboard.dashboard_utils import load_historical_snapshot


class DataLoader(ABC):
    """Abstract base class for loading dashboard data from different sources"""

    @abstractmethod
    def load_data(self) -> Tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame,
                                   pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame, datetime]:
        """
        Load data and return 11-tuple:
        (lend_rates, borrow_rates, collateral_ratios, prices,
         lend_rewards, borrow_rewards, available_borrow, borrow_fees, borrow_weights, liquidation_thresholds, timestamp)

        All DataFrames must have identical structure:
        - 'Token' column (e.g., 'USDC', 'SUI')
        - 'Contract' column (token contract address)
        - Protocol columns (e.g., 'Navi', 'AlphaFi', 'Suilend')
        """
        pass

    @property
    @abstractmethod
    def timestamp(self) -> datetime:
        """Return the timestamp of the loaded data"""
        pass

    @property
    @abstractmethod
    def is_live(self) -> bool:
        """Return True if this is live data, False if historical"""
        pass


class UnifiedDataLoader(DataLoader):
    """
    Unified data loader that loads historical snapshots from the database.

    This loader is used for both "latest" and historical data - there is no distinction.
    When user clicks "Get Live Data", refresh_pipeline() is called externally (in streamlit_app.py),
    which creates a new snapshot in the database. This loader then loads that snapshot.
    """

    def __init__(self, timestamp: str):
        """
        Args:
            timestamp: Timestamp string from database (REQUIRED, never None)
        """
        assert timestamp is not None, "timestamp must not be None - use explicit button to call refresh_pipeline()"

        self._timestamp_str = timestamp
        # Parse to datetime for display purposes
        self._timestamp = pd.to_datetime(timestamp)
        self._data = None

    def load_data(self) -> Tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame,
                                   pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame, datetime]:
        """Load snapshot from database at the specified timestamp"""
        result = load_historical_snapshot(self._timestamp_str)

        if result is None or len(result) != 10:
            raise ValueError(f"load_historical_snapshot() did not return expected 10 DataFrames for timestamp {self._timestamp_str}")

        (lend_rates, borrow_rates, collateral_ratios, prices,
         lend_rewards, borrow_rewards, available_borrow, borrow_fees, borrow_weights, liquidation_thresholds) = result

        return (lend_rates, borrow_rates, collateral_ratios, prices,
                lend_rewards, borrow_rewards, available_borrow, borrow_fees, borrow_weights, liquidation_thresholds, self._timestamp)

    @property
    def timestamp(self) -> datetime:
        return self._timestamp

    @property
    def is_live(self) -> bool:
        # All data is now "historical" - even the latest timestamp
        # Return True if this is the most recent snapshot for backward compatibility
        # (This property will be removed in a later phase)
        return False


class HistoricalDataLoader(DataLoader):
    """
    DEPRECATED: Use UnifiedDataLoader instead.

    Loads historical data from rates_snapshot table via load_historical_snapshot()
    """

    def __init__(self, timestamp: str):
        """
        Args:
            timestamp: Timestamp string from database (not datetime object)
        """
        self._timestamp_str = timestamp
        # Parse to datetime for display purposes
        self._timestamp = pd.to_datetime(timestamp)
        self._data = None

    def load_data(self) -> Tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame,
                                   pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame, datetime]:
        """Load historical snapshot from database"""
        # Pass string timestamp to load_historical_snapshot
        result = load_historical_snapshot(self._timestamp_str)

        if result is None or len(result) != 10:
            raise ValueError(f"load_historical_snapshot() did not return expected 10 DataFrames for timestamp {self._timestamp_str}")

        (lend_rates, borrow_rates, collateral_ratios, prices,
         lend_rewards, borrow_rewards, available_borrow, borrow_fees, borrow_weights, liquidation_thresholds) = result

        return (lend_rates, borrow_rates, collateral_ratios, prices,
                lend_rewards, borrow_rewards, available_borrow, borrow_fees, borrow_weights, liquidation_thresholds, self._timestamp)

    @property
    def timestamp(self) -> datetime:
        return self._timestamp

    @property
    def is_live(self) -> bool:
        return False

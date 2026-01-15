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
                                   pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame, datetime]:
        """
        Load data and return 9-tuple:
        (lend_rates, borrow_rates, collateral_ratios, prices,
         lend_rewards, borrow_rewards, available_borrow, borrow_fees, timestamp)

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


class LiveDataLoader(DataLoader):
    """Loads live data from protocol APIs via refresh_pipeline()"""

    def __init__(self):
        self._timestamp = None
        self._data = None

    def load_data(self) -> Tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame,
                                   pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame, datetime]:
        """Fetch live data from protocol APIs"""
        # Call refresh_pipeline with Slack notifications disabled (dashboard refreshes should be silent)
        result = refresh_pipeline(send_slack_notifications=False)

        if result is None:
            raise ValueError("refresh_pipeline() returned None")

        # Extract data from RefreshResult dataclass
        lend_rates = result.lend_rates
        borrow_rates = result.borrow_rates
        collateral_ratios = result.collateral_ratios
        prices = result.prices
        lend_rewards = result.lend_rewards
        borrow_rewards = result.borrow_rewards
        available_borrow = result.available_borrow
        borrow_fees = result.borrow_fees

        # Use timestamp from result
        self._timestamp = result.timestamp

        return (lend_rates, borrow_rates, collateral_ratios, prices,
                lend_rewards, borrow_rewards, available_borrow, borrow_fees, self._timestamp)

    @property
    def timestamp(self) -> datetime:
        return self._timestamp or datetime.now()

    @property
    def is_live(self) -> bool:
        return True


class HistoricalDataLoader(DataLoader):
    """Loads historical data from rates_snapshot table via load_historical_snapshot()"""

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
                                   pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame, datetime]:
        """Load historical snapshot from database"""
        # Pass string timestamp to load_historical_snapshot
        result = load_historical_snapshot(self._timestamp_str)

        if result is None or len(result) != 8:
            raise ValueError(f"load_historical_snapshot() did not return expected 8 DataFrames for timestamp {self._timestamp_str}")

        (lend_rates, borrow_rates, collateral_ratios, prices,
         lend_rewards, borrow_rewards, available_borrow, borrow_fees) = result

        return (lend_rates, borrow_rates, collateral_ratios, prices,
                lend_rewards, borrow_rewards, available_borrow, borrow_fees, self._timestamp)

    @property
    def timestamp(self) -> datetime:
        return self._timestamp

    @property
    def is_live(self) -> bool:
        return False

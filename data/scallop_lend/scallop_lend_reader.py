from typing import Tuple
import pandas as pd
from data.scallop_shared.scallop_base_reader import (
    ScallopBaseReader,
    ScallopReaderConfig,
)


class ScallopLendReader(ScallopBaseReader):
    """
    Scallop lending-only protocol reader.

    Zeros out collateral factors because Scallop lent assets cannot be used
    as collateral while earning interest.
    """

    def get_all_data(self) -> Tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
        lend_df, borrow_df, coll_df = super().get_all_data()

        # Zero out collateral factors (can't use lent assets as collateral)
        coll_df["Collateralization_factor"] = 0.0
        coll_df["Liquidation_threshold"] = 0.0

        print("\t\t(ScallopLend: collateral factors set to 0)")
        return lend_df, borrow_df, coll_df


# Example usage
if __name__ == "__main__":
    config = ScallopReaderConfig(
        node_script_path="data/scallop_shared/scallop_reader-sdk.mjs"
    )
    reader = ScallopLendReader(config)

    lend_df, borrow_df, collateral_df = reader.get_all_data()

    print("\n" + "=" * 80)
    print("SCALLOP LEND - LENDING RATES (including rewards):")
    print("=" * 80)
    with pd.option_context("display.max_rows", None, "display.max_columns", None):
        print(lend_df)

    print("\n" + "=" * 80)
    print("SCALLOP LEND - COLLATERAL RATIOS (should be 0.0):")
    print("=" * 80)
    with pd.option_context("display.max_rows", None, "display.max_columns", None):
        print(collateral_df)

    print("\n" + "=" * 80)
    print("VERIFICATION:")
    print("=" * 80)
    print(
        f"Unique collateral factors: {collateral_df['Collateralization_factor'].unique()}"
    )
    print(
        f"Unique liquidation thresholds: {collateral_df['Liquidation_threshold'].unique()}"
    )

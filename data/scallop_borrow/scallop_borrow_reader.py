from typing import Tuple
import pandas as pd
from data.scallop_shared.scallop_base_reader import (
    ScallopBaseReader,
    ScallopReaderConfig,
)


class ScallopBorrowReader(ScallopBaseReader):
    """
    Scallop borrowing-only protocol reader.

    Zeros out lending APRs because Scallop collateral assets do not earn
    interest while being borrowed against.
    """

    def get_all_data(self) -> Tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
        lend_df, borrow_df, coll_df = super().get_all_data()

        # Zero out lending APRs (no interest earned on collateral)
        lend_df["Supply_base_apr"] = 0.0
        lend_df["Supply_reward_apr"] = 0.0
        lend_df["Supply_apr"] = 0.0

        print("\t\t(ScallopBorrow: lending APRs set to 0)")
        return lend_df, borrow_df, coll_df


# Example usage
if __name__ == "__main__":
    config = ScallopReaderConfig(
        node_script_path="data/scallop_shared/scallop_reader-sdk.mjs"
    )
    reader = ScallopBorrowReader(config)

    lend_df, borrow_df, collateral_df = reader.get_all_data()

    print("\n" + "=" * 80)
    print("SCALLOP BORROW - LENDING RATES (should be 0.0):")
    print("=" * 80)
    with pd.option_context("display.max_rows", None, "display.max_columns", None):
        print(lend_df)

    print("\n" + "=" * 80)
    print("SCALLOP BORROW - BORROW RATES:")
    print("=" * 80)
    with pd.option_context("display.max_rows", None, "display.max_columns", None):
        print(borrow_df)

    print("\n" + "=" * 80)
    print("SCALLOP BORROW - COLLATERAL RATIOS (should be non-zero):")
    print("=" * 80)
    with pd.option_context("display.max_rows", None, "display.max_columns", None):
        print(collateral_df)

    print("\n" + "=" * 80)
    print("VERIFICATION:")
    print("=" * 80)
    print(f"Unique supply APRs: {lend_df['Supply_apr'].unique()}")
    print(f"Unique supply base APRs: {lend_df['Supply_base_apr'].unique()}")
    print(f"Unique supply reward APRs: {lend_df['Supply_reward_apr'].unique()}")

import { GenericArg } from "../../_framework/util";
import { Transaction, TransactionArgument, TransactionObjectInput } from "@mysten/sui/transactions";
export interface SetArgs {
    builder: TransactionObjectInput;
    field: GenericArg;
    value: GenericArg;
}
export declare function set(tx: Transaction, typeArgs: [string, string], args: SetArgs): import("@mysten/sui/transactions").TransactionResult;
export declare function destroy(tx: Transaction, config: TransactionObjectInput): import("@mysten/sui/transactions").TransactionResult;
export declare function from(tx: Transaction, config: TransactionObjectInput): import("@mysten/sui/transactions").TransactionResult;
export interface SetSpreadFeeBpsArgs {
    builder: TransactionObjectInput;
    spreadFeeBps: bigint | TransactionArgument;
}
export declare function setSpreadFeeBps(tx: Transaction, args: SetSpreadFeeBpsArgs): import("@mysten/sui/transactions").TransactionResult;
export declare function spreadFee(tx: Transaction, config: TransactionObjectInput): import("@mysten/sui/transactions").TransactionResult;
export declare function borrowFee(tx: Transaction, config: TransactionObjectInput): import("@mysten/sui/transactions").TransactionResult;
export declare function borrowLimit(tx: Transaction, config: TransactionObjectInput): import("@mysten/sui/transactions").TransactionResult;
export declare function borrowLimitUsd(tx: Transaction, config: TransactionObjectInput): import("@mysten/sui/transactions").TransactionResult;
export declare function borrowWeight(tx: Transaction, config: TransactionObjectInput): import("@mysten/sui/transactions").TransactionResult;
export declare function build(tx: Transaction, builder: TransactionObjectInput): import("@mysten/sui/transactions").TransactionResult;
export interface CalculateAprArgs {
    config: TransactionObjectInput;
    curUtil: TransactionObjectInput;
}
export declare function calculateApr(tx: Transaction, args: CalculateAprArgs): import("@mysten/sui/transactions").TransactionResult;
export interface CalculateSupplyAprArgs {
    config: TransactionObjectInput;
    curUtil: TransactionObjectInput;
    borrowApr: TransactionObjectInput;
}
export declare function calculateSupplyApr(tx: Transaction, args: CalculateSupplyAprArgs): import("@mysten/sui/transactions").TransactionResult;
export declare function closeLtv(tx: Transaction, config: TransactionObjectInput): import("@mysten/sui/transactions").TransactionResult;
export interface CreateReserveConfigArgs {
    openLtvPct: number | TransactionArgument;
    closeLtvPct: number | TransactionArgument;
    maxCloseLtvPct: number | TransactionArgument;
    borrowWeightBps: bigint | TransactionArgument;
    depositLimit: bigint | TransactionArgument;
    borrowLimit: bigint | TransactionArgument;
    liquidationBonusBps: bigint | TransactionArgument;
    maxLiquidationBonusBps: bigint | TransactionArgument;
    depositLimitUsd: bigint | TransactionArgument;
    borrowLimitUsd: bigint | TransactionArgument;
    borrowFeeBps: bigint | TransactionArgument;
    spreadFeeBps: bigint | TransactionArgument;
    protocolLiquidationFeeBps: bigint | TransactionArgument;
    interestRateUtils: Array<number | TransactionArgument> | TransactionArgument;
    interestRateAprs: Array<bigint | TransactionArgument> | TransactionArgument;
    isolated: boolean | TransactionArgument;
    openAttributedBorrowLimitUsd: bigint | TransactionArgument;
    closeAttributedBorrowLimitUsd: bigint | TransactionArgument;
}
export declare function createReserveConfig(tx: Transaction, args: CreateReserveConfigArgs): import("@mysten/sui/transactions").TransactionResult;
export declare function depositLimit(tx: Transaction, config: TransactionObjectInput): import("@mysten/sui/transactions").TransactionResult;
export declare function depositLimitUsd(tx: Transaction, config: TransactionObjectInput): import("@mysten/sui/transactions").TransactionResult;
export declare function isolated(tx: Transaction, config: TransactionObjectInput): import("@mysten/sui/transactions").TransactionResult;
export declare function liquidationBonus(tx: Transaction, config: TransactionObjectInput): import("@mysten/sui/transactions").TransactionResult;
export declare function openLtv(tx: Transaction, config: TransactionObjectInput): import("@mysten/sui/transactions").TransactionResult;
export declare function protocolLiquidationFee(tx: Transaction, config: TransactionObjectInput): import("@mysten/sui/transactions").TransactionResult;
export interface SetBorrowFeeBpsArgs {
    builder: TransactionObjectInput;
    borrowFeeBps: bigint | TransactionArgument;
}
export declare function setBorrowFeeBps(tx: Transaction, args: SetBorrowFeeBpsArgs): import("@mysten/sui/transactions").TransactionResult;
export interface SetBorrowLimitArgs {
    builder: TransactionObjectInput;
    borrowLimit: bigint | TransactionArgument;
}
export declare function setBorrowLimit(tx: Transaction, args: SetBorrowLimitArgs): import("@mysten/sui/transactions").TransactionResult;
export interface SetBorrowLimitUsdArgs {
    builder: TransactionObjectInput;
    borrowLimitUsd: bigint | TransactionArgument;
}
export declare function setBorrowLimitUsd(tx: Transaction, args: SetBorrowLimitUsdArgs): import("@mysten/sui/transactions").TransactionResult;
export interface SetBorrowWeightBpsArgs {
    builder: TransactionObjectInput;
    borrowWeightBps: bigint | TransactionArgument;
}
export declare function setBorrowWeightBps(tx: Transaction, args: SetBorrowWeightBpsArgs): import("@mysten/sui/transactions").TransactionResult;
export interface SetCloseAttributedBorrowLimitUsdArgs {
    builder: TransactionObjectInput;
    closeAttributedBorrowLimitUsd: bigint | TransactionArgument;
}
export declare function setCloseAttributedBorrowLimitUsd(tx: Transaction, args: SetCloseAttributedBorrowLimitUsdArgs): import("@mysten/sui/transactions").TransactionResult;
export interface SetCloseLtvPctArgs {
    builder: TransactionObjectInput;
    closeLtvPct: number | TransactionArgument;
}
export declare function setCloseLtvPct(tx: Transaction, args: SetCloseLtvPctArgs): import("@mysten/sui/transactions").TransactionResult;
export interface SetDepositLimitArgs {
    builder: TransactionObjectInput;
    depositLimit: bigint | TransactionArgument;
}
export declare function setDepositLimit(tx: Transaction, args: SetDepositLimitArgs): import("@mysten/sui/transactions").TransactionResult;
export interface SetDepositLimitUsdArgs {
    builder: TransactionObjectInput;
    depositLimitUsd: bigint | TransactionArgument;
}
export declare function setDepositLimitUsd(tx: Transaction, args: SetDepositLimitUsdArgs): import("@mysten/sui/transactions").TransactionResult;
export interface SetInterestRateAprsArgs {
    builder: TransactionObjectInput;
    interestRateAprs: Array<bigint | TransactionArgument> | TransactionArgument;
}
export declare function setInterestRateAprs(tx: Transaction, args: SetInterestRateAprsArgs): import("@mysten/sui/transactions").TransactionResult;
export interface SetInterestRateUtilsArgs {
    builder: TransactionObjectInput;
    interestRateUtils: Array<number | TransactionArgument> | TransactionArgument;
}
export declare function setInterestRateUtils(tx: Transaction, args: SetInterestRateUtilsArgs): import("@mysten/sui/transactions").TransactionResult;
export interface SetIsolatedArgs {
    builder: TransactionObjectInput;
    isolated: boolean | TransactionArgument;
}
export declare function setIsolated(tx: Transaction, args: SetIsolatedArgs): import("@mysten/sui/transactions").TransactionResult;
export interface SetLiquidationBonusBpsArgs {
    builder: TransactionObjectInput;
    liquidationBonusBps: bigint | TransactionArgument;
}
export declare function setLiquidationBonusBps(tx: Transaction, args: SetLiquidationBonusBpsArgs): import("@mysten/sui/transactions").TransactionResult;
export interface SetMaxCloseLtvPctArgs {
    builder: TransactionObjectInput;
    maxCloseLtvPct: number | TransactionArgument;
}
export declare function setMaxCloseLtvPct(tx: Transaction, args: SetMaxCloseLtvPctArgs): import("@mysten/sui/transactions").TransactionResult;
export interface SetMaxLiquidationBonusBpsArgs {
    builder: TransactionObjectInput;
    maxLiquidationBonusBps: bigint | TransactionArgument;
}
export declare function setMaxLiquidationBonusBps(tx: Transaction, args: SetMaxLiquidationBonusBpsArgs): import("@mysten/sui/transactions").TransactionResult;
export interface SetOpenAttributedBorrowLimitUsdArgs {
    builder: TransactionObjectInput;
    openAttributedBorrowLimitUsd: bigint | TransactionArgument;
}
export declare function setOpenAttributedBorrowLimitUsd(tx: Transaction, args: SetOpenAttributedBorrowLimitUsdArgs): import("@mysten/sui/transactions").TransactionResult;
export interface SetOpenLtvPctArgs {
    builder: TransactionObjectInput;
    openLtvPct: number | TransactionArgument;
}
export declare function setOpenLtvPct(tx: Transaction, args: SetOpenLtvPctArgs): import("@mysten/sui/transactions").TransactionResult;
export interface SetProtocolLiquidationFeeBpsArgs {
    builder: TransactionObjectInput;
    protocolLiquidationFeeBps: bigint | TransactionArgument;
}
export declare function setProtocolLiquidationFeeBps(tx: Transaction, args: SetProtocolLiquidationFeeBpsArgs): import("@mysten/sui/transactions").TransactionResult;
export declare function validateReserveConfig(tx: Transaction, config: TransactionObjectInput): import("@mysten/sui/transactions").TransactionResult;
export interface ValidateUtilsAndAprsArgs {
    utils: Array<number | TransactionArgument> | TransactionArgument;
    aprs: Array<bigint | TransactionArgument> | TransactionArgument;
}
export declare function validateUtilsAndAprs(tx: Transaction, args: ValidateUtilsAndAprsArgs): import("@mysten/sui/transactions").TransactionResult;

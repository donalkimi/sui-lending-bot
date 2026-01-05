import { Transaction, TransactionArgument, TransactionObjectInput } from "@mysten/sui/transactions";
export interface BorrowArgs {
    lendingMarket: TransactionObjectInput;
    reserveArrayIndex: bigint | TransactionArgument;
    obligationOwnerCap: TransactionObjectInput;
    clock: TransactionObjectInput;
    amount: bigint | TransactionArgument;
}
export declare function borrow(tx: Transaction, typeArgs: [string, string], args: BorrowArgs): import("@mysten/sui/transactions").TransactionResult;
export interface MigrateArgs {
    lendingMarketOwnerCap: TransactionObjectInput;
    lendingMarket: TransactionObjectInput;
}
export declare function migrate(tx: Transaction, typeArg: string, args: MigrateArgs): import("@mysten/sui/transactions").TransactionResult;
export declare function init(tx: Transaction, otw: TransactionObjectInput): import("@mysten/sui/transactions").TransactionResult;
export interface ClaimFeesArgs {
    lendingMarket: TransactionObjectInput;
    reserveArrayIndex: bigint | TransactionArgument;
    systemState: TransactionObjectInput;
}
export declare function claimFees(tx: Transaction, typeArgs: [string, string], args: ClaimFeesArgs): import("@mysten/sui/transactions").TransactionResult;
export interface AddPoolRewardArgs {
    lendingMarketOwnerCap: TransactionObjectInput;
    lendingMarket: TransactionObjectInput;
    reserveArrayIndex: bigint | TransactionArgument;
    isDepositReward: boolean | TransactionArgument;
    rewards: TransactionObjectInput;
    startTimeMs: bigint | TransactionArgument;
    endTimeMs: bigint | TransactionArgument;
    clock: TransactionObjectInput;
}
export declare function addPoolReward(tx: Transaction, typeArgs: [string, string], args: AddPoolRewardArgs): import("@mysten/sui/transactions").TransactionResult;
export interface CancelPoolRewardArgs {
    lendingMarketOwnerCap: TransactionObjectInput;
    lendingMarket: TransactionObjectInput;
    reserveArrayIndex: bigint | TransactionArgument;
    isDepositReward: boolean | TransactionArgument;
    rewardIndex: bigint | TransactionArgument;
    clock: TransactionObjectInput;
}
export declare function cancelPoolReward(tx: Transaction, typeArgs: [string, string], args: CancelPoolRewardArgs): import("@mysten/sui/transactions").TransactionResult;
export interface ClaimRewardsArgs {
    lendingMarket: TransactionObjectInput;
    cap: TransactionObjectInput;
    clock: TransactionObjectInput;
    reserveId: bigint | TransactionArgument;
    rewardIndex: bigint | TransactionArgument;
    isDepositReward: boolean | TransactionArgument;
}
export declare function claimRewards(tx: Transaction, typeArgs: [string, string], args: ClaimRewardsArgs): import("@mysten/sui/transactions").TransactionResult;
export interface ClosePoolRewardArgs {
    lendingMarketOwnerCap: TransactionObjectInput;
    lendingMarket: TransactionObjectInput;
    reserveArrayIndex: bigint | TransactionArgument;
    isDepositReward: boolean | TransactionArgument;
    rewardIndex: bigint | TransactionArgument;
    clock: TransactionObjectInput;
}
export declare function closePoolReward(tx: Transaction, typeArgs: [string, string], args: ClosePoolRewardArgs): import("@mysten/sui/transactions").TransactionResult;
export declare function reserve(tx: Transaction, typeArgs: [string, string], lendingMarket: TransactionObjectInput): import("@mysten/sui/transactions").TransactionResult;
export interface CompoundInterestArgs {
    lendingMarket: TransactionObjectInput;
    reserveArrayIndex: bigint | TransactionArgument;
    clock: TransactionObjectInput;
}
export declare function compoundInterest(tx: Transaction, typeArg: string, args: CompoundInterestArgs): import("@mysten/sui/transactions").TransactionResult;
export interface DepositLiquidityAndMintCtokensArgs {
    lendingMarket: TransactionObjectInput;
    reserveArrayIndex: bigint | TransactionArgument;
    clock: TransactionObjectInput;
    deposit: TransactionObjectInput;
}
export declare function depositLiquidityAndMintCtokens(tx: Transaction, typeArgs: [string, string], args: DepositLiquidityAndMintCtokensArgs): import("@mysten/sui/transactions").TransactionResult;
export interface FulfillLiquidityRequestArgs {
    lendingMarket: TransactionObjectInput;
    reserveArrayIndex: bigint | TransactionArgument;
    liquidityRequest: TransactionObjectInput;
}
export declare function fulfillLiquidityRequest(tx: Transaction, typeArgs: [string, string], args: FulfillLiquidityRequestArgs): import("@mysten/sui/transactions").TransactionResult;
export interface InitStakerArgs {
    lendingMarket: TransactionObjectInput;
    lendingMarketOwnerCap: TransactionObjectInput;
    suiReserveArrayIndex: bigint | TransactionArgument;
    treasuryCap: TransactionObjectInput;
}
export declare function initStaker(tx: Transaction, typeArgs: [string, string], args: InitStakerArgs): import("@mysten/sui/transactions").TransactionResult;
export interface MaxBorrowAmountArgs {
    rateLimiter: TransactionObjectInput;
    obligation: TransactionObjectInput;
    reserve: TransactionObjectInput;
    clock: TransactionObjectInput;
}
export declare function maxBorrowAmount(tx: Transaction, typeArg: string, args: MaxBorrowAmountArgs): import("@mysten/sui/transactions").TransactionResult;
export interface RebalanceStakerArgs {
    lendingMarket: TransactionObjectInput;
    suiReserveArrayIndex: bigint | TransactionArgument;
    systemState: TransactionObjectInput;
}
export declare function rebalanceStaker(tx: Transaction, typeArg: string, args: RebalanceStakerArgs): import("@mysten/sui/transactions").TransactionResult;
export interface UnstakeSuiFromStakerArgs {
    lendingMarket: TransactionObjectInput;
    suiReserveArrayIndex: bigint | TransactionArgument;
    liquidityRequest: TransactionObjectInput;
    systemState: TransactionObjectInput;
}
export declare function unstakeSuiFromStaker(tx: Transaction, typeArg: string, args: UnstakeSuiFromStakerArgs): import("@mysten/sui/transactions").TransactionResult;
export interface UpdateReserveConfigArgs {
    lendingMarketOwnerCap: TransactionObjectInput;
    lendingMarket: TransactionObjectInput;
    reserveArrayIndex: bigint | TransactionArgument;
    config: TransactionObjectInput;
}
export declare function updateReserveConfig(tx: Transaction, typeArgs: [string, string], args: UpdateReserveConfigArgs): import("@mysten/sui/transactions").TransactionResult;
export interface WithdrawCtokensArgs {
    lendingMarket: TransactionObjectInput;
    reserveArrayIndex: bigint | TransactionArgument;
    obligationOwnerCap: TransactionObjectInput;
    clock: TransactionObjectInput;
    amount: bigint | TransactionArgument;
}
export declare function withdrawCtokens(tx: Transaction, typeArgs: [string, string], args: WithdrawCtokensArgs): import("@mysten/sui/transactions").TransactionResult;
export interface ObligationArgs {
    lendingMarket: TransactionObjectInput;
    obligationId: string | TransactionArgument;
}
export declare function obligation(tx: Transaction, typeArg: string, args: ObligationArgs): import("@mysten/sui/transactions").TransactionResult;
export declare function createObligation(tx: Transaction, typeArg: string, lendingMarket: TransactionObjectInput): import("@mysten/sui/transactions").TransactionResult;
export declare function reserveArrayIndex(tx: Transaction, typeArgs: [string, string], lendingMarket: TransactionObjectInput): import("@mysten/sui/transactions").TransactionResult;
export interface ForgiveArgs {
    lendingMarketOwnerCap: TransactionObjectInput;
    lendingMarket: TransactionObjectInput;
    reserveArrayIndex: bigint | TransactionArgument;
    obligationId: string | TransactionArgument;
    clock: TransactionObjectInput;
    maxForgiveAmount: bigint | TransactionArgument;
}
export declare function forgive(tx: Transaction, typeArgs: [string, string], args: ForgiveArgs): import("@mysten/sui/transactions").TransactionResult;
export interface LiquidateArgs {
    lendingMarket: TransactionObjectInput;
    obligationId: string | TransactionArgument;
    repayReserveArrayIndex: bigint | TransactionArgument;
    withdrawReserveArrayIndex: bigint | TransactionArgument;
    clock: TransactionObjectInput;
    repayCoins: TransactionObjectInput;
}
export declare function liquidate(tx: Transaction, typeArgs: [string, string, string], args: LiquidateArgs): import("@mysten/sui/transactions").TransactionResult;
export declare function reserves(tx: Transaction, typeArg: string, lendingMarket: TransactionObjectInput): import("@mysten/sui/transactions").TransactionResult;
export interface MaxWithdrawAmountArgs {
    rateLimiter: TransactionObjectInput;
    obligation: TransactionObjectInput;
    reserve: TransactionObjectInput;
    clock: TransactionObjectInput;
}
export declare function maxWithdrawAmount(tx: Transaction, typeArg: string, args: MaxWithdrawAmountArgs): import("@mysten/sui/transactions").TransactionResult;
export interface RepayArgs {
    lendingMarket: TransactionObjectInput;
    reserveArrayIndex: bigint | TransactionArgument;
    obligationId: string | TransactionArgument;
    clock: TransactionObjectInput;
    maxRepayCoins: TransactionObjectInput;
}
export declare function repay(tx: Transaction, typeArgs: [string, string], args: RepayArgs): import("@mysten/sui/transactions").TransactionResult;
export declare function obligationId(tx: Transaction, typeArg: string, cap: TransactionObjectInput): import("@mysten/sui/transactions").TransactionResult;
export interface AddReserveArgs {
    lendingMarketOwnerCap: TransactionObjectInput;
    lendingMarket: TransactionObjectInput;
    priceInfo: TransactionObjectInput;
    config: TransactionObjectInput;
    coinMetadata: TransactionObjectInput;
    clock: TransactionObjectInput;
}
export declare function addReserve(tx: Transaction, typeArgs: [string, string], args: AddReserveArgs): import("@mysten/sui/transactions").TransactionResult;
export interface BorrowRequestArgs {
    lendingMarket: TransactionObjectInput;
    reserveArrayIndex: bigint | TransactionArgument;
    obligationOwnerCap: TransactionObjectInput;
    clock: TransactionObjectInput;
    amount: bigint | TransactionArgument;
}
export declare function borrowRequest(tx: Transaction, typeArgs: [string, string], args: BorrowRequestArgs): import("@mysten/sui/transactions").TransactionResult;
export interface ChangeReservePriceFeedArgs {
    lendingMarketOwnerCap: TransactionObjectInput;
    lendingMarket: TransactionObjectInput;
    reserveArrayIndex: bigint | TransactionArgument;
    priceInfoObj: TransactionObjectInput;
    clock: TransactionObjectInput;
}
export declare function changeReservePriceFeed(tx: Transaction, typeArgs: [string, string], args: ChangeReservePriceFeedArgs): import("@mysten/sui/transactions").TransactionResult;
export interface ClaimRewardsAndDepositArgs {
    lendingMarket: TransactionObjectInput;
    obligationId: string | TransactionArgument;
    clock: TransactionObjectInput;
    rewardReserveId: bigint | TransactionArgument;
    rewardIndex: bigint | TransactionArgument;
    isDepositReward: boolean | TransactionArgument;
    depositReserveId: bigint | TransactionArgument;
}
export declare function claimRewardsAndDeposit(tx: Transaction, typeArgs: [string, string], args: ClaimRewardsAndDepositArgs): import("@mysten/sui/transactions").TransactionResult;
export interface ClaimRewardsByObligationIdArgs {
    lendingMarket: TransactionObjectInput;
    obligationId: string | TransactionArgument;
    clock: TransactionObjectInput;
    reserveId: bigint | TransactionArgument;
    rewardIndex: bigint | TransactionArgument;
    isDepositReward: boolean | TransactionArgument;
    failIfRewardPeriodNotOver: boolean | TransactionArgument;
}
export declare function claimRewardsByObligationId(tx: Transaction, typeArgs: [string, string], args: ClaimRewardsByObligationIdArgs): import("@mysten/sui/transactions").TransactionResult;
export declare function createLendingMarket(tx: Transaction, typeArg: string): import("@mysten/sui/transactions").TransactionResult;
export interface DepositCtokensIntoObligationArgs {
    lendingMarket: TransactionObjectInput;
    reserveArrayIndex: bigint | TransactionArgument;
    obligationOwnerCap: TransactionObjectInput;
    clock: TransactionObjectInput;
    deposit: TransactionObjectInput;
}
export declare function depositCtokensIntoObligation(tx: Transaction, typeArgs: [string, string], args: DepositCtokensIntoObligationArgs): import("@mysten/sui/transactions").TransactionResult;
export interface DepositCtokensIntoObligationByIdArgs {
    lendingMarket: TransactionObjectInput;
    reserveArrayIndex: bigint | TransactionArgument;
    obligationId: string | TransactionArgument;
    clock: TransactionObjectInput;
    deposit: TransactionObjectInput;
}
export declare function depositCtokensIntoObligationById(tx: Transaction, typeArgs: [string, string], args: DepositCtokensIntoObligationByIdArgs): import("@mysten/sui/transactions").TransactionResult;
export declare function feeReceiver(tx: Transaction, typeArg: string, lendingMarket: TransactionObjectInput): import("@mysten/sui/transactions").TransactionResult;
export interface NewObligationOwnerCapArgs {
    lendingMarketOwnerCap: TransactionObjectInput;
    lendingMarket: TransactionObjectInput;
    obligationId: string | TransactionArgument;
}
export declare function newObligationOwnerCap(tx: Transaction, typeArg: string, args: NewObligationOwnerCapArgs): import("@mysten/sui/transactions").TransactionResult;
export declare function rateLimiterExemptionAmount(tx: Transaction, typeArgs: [string, string], exemption: TransactionObjectInput): import("@mysten/sui/transactions").TransactionResult;
export interface RedeemCtokensAndWithdrawLiquidityArgs {
    lendingMarket: TransactionObjectInput;
    reserveArrayIndex: bigint | TransactionArgument;
    clock: TransactionObjectInput;
    ctokens: TransactionObjectInput;
    rateLimiterExemption: TransactionObjectInput | TransactionArgument | null;
}
export declare function redeemCtokensAndWithdrawLiquidity(tx: Transaction, typeArgs: [string, string], args: RedeemCtokensAndWithdrawLiquidityArgs): import("@mysten/sui/transactions").TransactionResult;
export interface RedeemCtokensAndWithdrawLiquidityRequestArgs {
    lendingMarket: TransactionObjectInput;
    reserveArrayIndex: bigint | TransactionArgument;
    clock: TransactionObjectInput;
    ctokens: TransactionObjectInput;
    rateLimiterExemption: TransactionObjectInput | TransactionArgument | null;
}
export declare function redeemCtokensAndWithdrawLiquidityRequest(tx: Transaction, typeArgs: [string, string], args: RedeemCtokensAndWithdrawLiquidityRequestArgs): import("@mysten/sui/transactions").TransactionResult;
export interface RefreshReservePriceArgs {
    lendingMarket: TransactionObjectInput;
    reserveArrayIndex: bigint | TransactionArgument;
    clock: TransactionObjectInput;
    priceInfo: TransactionObjectInput;
}
export declare function refreshReservePrice(tx: Transaction, typeArg: string, args: RefreshReservePriceArgs): import("@mysten/sui/transactions").TransactionResult;
export interface SetFeeReceiversArgs {
    lendingMarketOwnerCap: TransactionObjectInput;
    lendingMarket: TransactionObjectInput;
    receivers: Array<string | TransactionArgument> | TransactionArgument;
    weights: Array<bigint | TransactionArgument> | TransactionArgument;
}
export declare function setFeeReceivers(tx: Transaction, typeArg: string, args: SetFeeReceiversArgs): import("@mysten/sui/transactions").TransactionResult;
export interface UpdateRateLimiterConfigArgs {
    lendingMarketOwnerCap: TransactionObjectInput;
    lendingMarket: TransactionObjectInput;
    clock: TransactionObjectInput;
    config: TransactionObjectInput;
}
export declare function updateRateLimiterConfig(tx: Transaction, typeArg: string, args: UpdateRateLimiterConfigArgs): import("@mysten/sui/transactions").TransactionResult;

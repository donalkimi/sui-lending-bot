import { SuiClient, SuiEvent } from "@mysten/sui/client";
type TypeName = {
    name: string;
};
type Decimal = {
    value: string;
};
type address = string;
type u64 = string;
export declare enum SuilendEventType {
    InterestUpdateEvent = "InterestUpdateEvent",
    ReserveAssetDataEvent = "ReserveAssetDataEvent",
    MintEvent = "MintEvent",
    RedeemEvent = "RedeemEvent",
    DepositEvent = "DepositEvent",
    WithdrawEvent = "WithdrawEvent",
    BorrowEvent = "BorrowEvent",
    RepayEvent = "RepayEvent",
    LiquidateEvent = "LiquidateEvent",
    ClaimRewardEvent = "ClaimRewardEvent",
    ObligationDataEvent = "ObligationDataEvent"
}
export declare enum SuilendTransactionModule {
    LendingMarket = "lending_market",
    Reserve = "reserve"
}
declare class TypedParamsSuiEvent<T> {
    event: SuiEvent;
    constructor(event: SuiEvent);
    params(): T;
    isType(module: SuilendTransactionModule, eventType: SuilendEventType): boolean;
}
export declare class GenericSuilendEvent extends TypedParamsSuiEvent<object> {
}
export declare class InterestUpdateEvent extends TypedParamsSuiEvent<{
    lending_market_id: address;
    coin_type: TypeName;
    reserve_id: address;
    cumulative_borrow_rate: Decimal;
    available_amount: u64;
    borrowed_amount: Decimal;
    unclaimed_spread_fees: Decimal;
    ctoken_supply: u64;
    borrow_interest_paid: Decimal;
    spread_fee: Decimal;
    supply_interest_earned: Decimal;
    borrow_interest_paid_usd_estimate: Decimal;
    protocol_fee_usd_estimate: Decimal;
    supply_interest_earned_usd_estimate: Decimal;
}> {
}
export declare class ReserveAssetDataEvent extends TypedParamsSuiEvent<{
    lending_market_id: address;
    coin_type: TypeName;
    reserve_id: address;
    available_amount: Decimal;
    supply_amount: Decimal;
    borrowed_amount: Decimal;
    available_amount_usd_estimate: Decimal;
    supply_amount_usd_estimate: Decimal;
    borrowed_amount_usd_estimate: Decimal;
    borrow_apr: Decimal;
    supply_apr: Decimal;
    ctoken_supply: u64;
    cumulative_borrow_rate: Decimal;
    price: Decimal;
    smoothed_price: Decimal;
    price_last_update_timestamp_s: u64;
}> {
}
export declare class MintEvent extends TypedParamsSuiEvent<{
    lending_market_id: address;
    coin_type: TypeName;
    reserve_id: address;
    liquidity_amount: u64;
    ctoken_amount: u64;
}> {
}
export declare class RedeemEvent extends TypedParamsSuiEvent<{
    lending_market_id: address;
    coin_type: TypeName;
    reserve_id: address;
    ctoken_amount: u64;
    liquidity_amount: u64;
}> {
}
export declare class DepositEvent extends TypedParamsSuiEvent<{
    lending_market_id: address;
    coin_type: TypeName;
    reserve_id: address;
    obligation_id: address;
    ctoken_amount: u64;
}> {
}
export declare class WithdrawEvent extends TypedParamsSuiEvent<{
    lending_market_id: address;
    coin_type: TypeName;
    reserve_id: address;
    obligation_id: address;
    ctoken_amount: u64;
}> {
}
export declare class BorrowEvent extends TypedParamsSuiEvent<{
    lending_market_id: address;
    coin_type: TypeName;
    reserve_id: address;
    obligation_id: address;
    liquidity_amount: u64;
    origination_fee_amount: u64;
}> {
}
export declare class RepayEvent extends TypedParamsSuiEvent<{
    lending_market_id: address;
    coin_type: TypeName;
    reserve_id: address;
    obligation_id: address;
    liquidity_amount: u64;
}> {
}
export declare class LiquidateEvent extends TypedParamsSuiEvent<{
    lending_market_id: address;
    repay_reserve_id: address;
    withdraw_reserve_id: address;
    obligation_id: address;
    repay_coin_type: TypeName;
    withdraw_coin_type: TypeName;
    repay_amount: u64;
    withdraw_amount: u64;
    protocol_fee_amount: u64;
    liquidator_bonus_amount: u64;
}> {
}
export declare class ClaimRewardEvent extends TypedParamsSuiEvent<{
    lending_market_id: address;
    reserve_id: address;
    obligation_id: address;
    is_deposit_reward: boolean;
    pool_reward_id: address;
    coin_type: TypeName;
    liquidity_amount: u64;
}> {
}
export declare class ObligationDataEvent extends TypedParamsSuiEvent<{
    lending_market_id: address;
    obligation_id: address;
    deposits: {
        coin_type: TypeName;
        reserve_array_index: u64;
        deposited_ctoken_amount: u64;
        market_value: Decimal;
        user_reward_manager_index: u64;
        attributed_borrow_value: Decimal;
    }[];
    borrows: {
        coin_type: TypeName;
        reserve_array_index: u64;
        borrowed_amount: Decimal;
        cumulative_borrow_rate: Decimal;
        market_value: Decimal;
        user_reward_manager_index: u64;
    }[];
    deposited_value_usd: Decimal;
    allowed_borrow_value_usd: Decimal;
    unhealthy_borrow_value_usd: Decimal;
    super_unhealthy_borrow_value_usd: Decimal;
    unweighted_borrowed_value_usd: Decimal;
    weighted_borrowed_value_usd: Decimal;
    weighted_borrowed_value_upper_bound_usd: Decimal;
    borrowing_isolated_asset: boolean;
    bad_debt_usd: Decimal;
    closable: boolean;
}> {
}
export declare function getEvents(client: SuiClient, digest: string): Promise<GenericSuilendEvent[]>;
export declare function getRedeemEvent(client: SuiClient, digest: string): Promise<RedeemEvent | null>;
export {};

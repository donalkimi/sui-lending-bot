"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
exports.borrow = borrow;
exports.migrate = migrate;
exports.init = init;
exports.claimFees = claimFees;
exports.addPoolReward = addPoolReward;
exports.cancelPoolReward = cancelPoolReward;
exports.claimRewards = claimRewards;
exports.closePoolReward = closePoolReward;
exports.reserve = reserve;
exports.compoundInterest = compoundInterest;
exports.depositLiquidityAndMintCtokens = depositLiquidityAndMintCtokens;
exports.fulfillLiquidityRequest = fulfillLiquidityRequest;
exports.initStaker = initStaker;
exports.maxBorrowAmount = maxBorrowAmount;
exports.rebalanceStaker = rebalanceStaker;
exports.unstakeSuiFromStaker = unstakeSuiFromStaker;
exports.updateReserveConfig = updateReserveConfig;
exports.withdrawCtokens = withdrawCtokens;
exports.obligation = obligation;
exports.createObligation = createObligation;
exports.reserveArrayIndex = reserveArrayIndex;
exports.forgive = forgive;
exports.liquidate = liquidate;
exports.reserves = reserves;
exports.maxWithdrawAmount = maxWithdrawAmount;
exports.repay = repay;
exports.obligationId = obligationId;
exports.addReserve = addReserve;
exports.borrowRequest = borrowRequest;
exports.changeReservePriceFeed = changeReservePriceFeed;
exports.claimRewardsAndDeposit = claimRewardsAndDeposit;
exports.claimRewardsByObligationId = claimRewardsByObligationId;
exports.createLendingMarket = createLendingMarket;
exports.depositCtokensIntoObligation = depositCtokensIntoObligation;
exports.depositCtokensIntoObligationById = depositCtokensIntoObligationById;
exports.feeReceiver = feeReceiver;
exports.newObligationOwnerCap = newObligationOwnerCap;
exports.rateLimiterExemptionAmount = rateLimiterExemptionAmount;
exports.redeemCtokensAndWithdrawLiquidity = redeemCtokensAndWithdrawLiquidity;
exports.redeemCtokensAndWithdrawLiquidityRequest = redeemCtokensAndWithdrawLiquidityRequest;
exports.refreshReservePrice = refreshReservePrice;
exports.setFeeReceivers = setFeeReceivers;
exports.updateRateLimiterConfig = updateRateLimiterConfig;
const __1 = require("..");
const structs_1 = require("../../_dependencies/source/0x2/object/structs");
const util_1 = require("../../_framework/util");
const structs_2 = require("./structs");
function borrow(tx, typeArgs, args) {
    return tx.moveCall({
        target: `${__1.PUBLISHED_AT}::lending_market::borrow`,
        typeArguments: typeArgs,
        arguments: [
            (0, util_1.obj)(tx, args.lendingMarket),
            (0, util_1.pure)(tx, args.reserveArrayIndex, `u64`),
            (0, util_1.obj)(tx, args.obligationOwnerCap),
            (0, util_1.obj)(tx, args.clock),
            (0, util_1.pure)(tx, args.amount, `u64`),
        ],
    });
}
function migrate(tx, typeArg, args) {
    return tx.moveCall({
        target: `${__1.PUBLISHED_AT}::lending_market::migrate`,
        typeArguments: [typeArg],
        arguments: [
            (0, util_1.obj)(tx, args.lendingMarketOwnerCap),
            (0, util_1.obj)(tx, args.lendingMarket),
        ],
    });
}
function init(tx, otw) {
    return tx.moveCall({
        target: `${__1.PUBLISHED_AT}::lending_market::init`,
        arguments: [(0, util_1.obj)(tx, otw)],
    });
}
function claimFees(tx, typeArgs, args) {
    return tx.moveCall({
        target: `${__1.PUBLISHED_AT}::lending_market::claim_fees`,
        typeArguments: typeArgs,
        arguments: [
            (0, util_1.obj)(tx, args.lendingMarket),
            (0, util_1.pure)(tx, args.reserveArrayIndex, `u64`),
            (0, util_1.obj)(tx, args.systemState),
        ],
    });
}
function addPoolReward(tx, typeArgs, args) {
    return tx.moveCall({
        target: `${__1.PUBLISHED_AT}::lending_market::add_pool_reward`,
        typeArguments: typeArgs,
        arguments: [
            (0, util_1.obj)(tx, args.lendingMarketOwnerCap),
            (0, util_1.obj)(tx, args.lendingMarket),
            (0, util_1.pure)(tx, args.reserveArrayIndex, `u64`),
            (0, util_1.pure)(tx, args.isDepositReward, `bool`),
            (0, util_1.obj)(tx, args.rewards),
            (0, util_1.pure)(tx, args.startTimeMs, `u64`),
            (0, util_1.pure)(tx, args.endTimeMs, `u64`),
            (0, util_1.obj)(tx, args.clock),
        ],
    });
}
function cancelPoolReward(tx, typeArgs, args) {
    return tx.moveCall({
        target: `${__1.PUBLISHED_AT}::lending_market::cancel_pool_reward`,
        typeArguments: typeArgs,
        arguments: [
            (0, util_1.obj)(tx, args.lendingMarketOwnerCap),
            (0, util_1.obj)(tx, args.lendingMarket),
            (0, util_1.pure)(tx, args.reserveArrayIndex, `u64`),
            (0, util_1.pure)(tx, args.isDepositReward, `bool`),
            (0, util_1.pure)(tx, args.rewardIndex, `u64`),
            (0, util_1.obj)(tx, args.clock),
        ],
    });
}
function claimRewards(tx, typeArgs, args) {
    return tx.moveCall({
        target: `${__1.PUBLISHED_AT}::lending_market::claim_rewards`,
        typeArguments: typeArgs,
        arguments: [
            (0, util_1.obj)(tx, args.lendingMarket),
            (0, util_1.obj)(tx, args.cap),
            (0, util_1.obj)(tx, args.clock),
            (0, util_1.pure)(tx, args.reserveId, `u64`),
            (0, util_1.pure)(tx, args.rewardIndex, `u64`),
            (0, util_1.pure)(tx, args.isDepositReward, `bool`),
        ],
    });
}
function closePoolReward(tx, typeArgs, args) {
    return tx.moveCall({
        target: `${__1.PUBLISHED_AT}::lending_market::close_pool_reward`,
        typeArguments: typeArgs,
        arguments: [
            (0, util_1.obj)(tx, args.lendingMarketOwnerCap),
            (0, util_1.obj)(tx, args.lendingMarket),
            (0, util_1.pure)(tx, args.reserveArrayIndex, `u64`),
            (0, util_1.pure)(tx, args.isDepositReward, `bool`),
            (0, util_1.pure)(tx, args.rewardIndex, `u64`),
            (0, util_1.obj)(tx, args.clock),
        ],
    });
}
function reserve(tx, typeArgs, lendingMarket) {
    return tx.moveCall({
        target: `${__1.PUBLISHED_AT}::lending_market::reserve`,
        typeArguments: typeArgs,
        arguments: [(0, util_1.obj)(tx, lendingMarket)],
    });
}
function compoundInterest(tx, typeArg, args) {
    return tx.moveCall({
        target: `${__1.PUBLISHED_AT}::lending_market::compound_interest`,
        typeArguments: [typeArg],
        arguments: [
            (0, util_1.obj)(tx, args.lendingMarket),
            (0, util_1.pure)(tx, args.reserveArrayIndex, `u64`),
            (0, util_1.obj)(tx, args.clock),
        ],
    });
}
function depositLiquidityAndMintCtokens(tx, typeArgs, args) {
    return tx.moveCall({
        target: `${__1.PUBLISHED_AT}::lending_market::deposit_liquidity_and_mint_ctokens`,
        typeArguments: typeArgs,
        arguments: [
            (0, util_1.obj)(tx, args.lendingMarket),
            (0, util_1.pure)(tx, args.reserveArrayIndex, `u64`),
            (0, util_1.obj)(tx, args.clock),
            (0, util_1.obj)(tx, args.deposit),
        ],
    });
}
function fulfillLiquidityRequest(tx, typeArgs, args) {
    return tx.moveCall({
        target: `${__1.PUBLISHED_AT}::lending_market::fulfill_liquidity_request`,
        typeArguments: typeArgs,
        arguments: [
            (0, util_1.obj)(tx, args.lendingMarket),
            (0, util_1.pure)(tx, args.reserveArrayIndex, `u64`),
            (0, util_1.obj)(tx, args.liquidityRequest),
        ],
    });
}
function initStaker(tx, typeArgs, args) {
    return tx.moveCall({
        target: `${__1.PUBLISHED_AT}::lending_market::init_staker`,
        typeArguments: typeArgs,
        arguments: [
            (0, util_1.obj)(tx, args.lendingMarket),
            (0, util_1.obj)(tx, args.lendingMarketOwnerCap),
            (0, util_1.pure)(tx, args.suiReserveArrayIndex, `u64`),
            (0, util_1.obj)(tx, args.treasuryCap),
        ],
    });
}
function maxBorrowAmount(tx, typeArg, args) {
    return tx.moveCall({
        target: `${__1.PUBLISHED_AT}::lending_market::max_borrow_amount`,
        typeArguments: [typeArg],
        arguments: [
            (0, util_1.obj)(tx, args.rateLimiter),
            (0, util_1.obj)(tx, args.obligation),
            (0, util_1.obj)(tx, args.reserve),
            (0, util_1.obj)(tx, args.clock),
        ],
    });
}
function rebalanceStaker(tx, typeArg, args) {
    return tx.moveCall({
        target: `${__1.PUBLISHED_AT}::lending_market::rebalance_staker`,
        typeArguments: [typeArg],
        arguments: [
            (0, util_1.obj)(tx, args.lendingMarket),
            (0, util_1.pure)(tx, args.suiReserveArrayIndex, `u64`),
            (0, util_1.obj)(tx, args.systemState),
        ],
    });
}
function unstakeSuiFromStaker(tx, typeArg, args) {
    return tx.moveCall({
        target: `${__1.PUBLISHED_AT}::lending_market::unstake_sui_from_staker`,
        typeArguments: [typeArg],
        arguments: [
            (0, util_1.obj)(tx, args.lendingMarket),
            (0, util_1.pure)(tx, args.suiReserveArrayIndex, `u64`),
            (0, util_1.obj)(tx, args.liquidityRequest),
            (0, util_1.obj)(tx, args.systemState),
        ],
    });
}
function updateReserveConfig(tx, typeArgs, args) {
    return tx.moveCall({
        target: `${__1.PUBLISHED_AT}::lending_market::update_reserve_config`,
        typeArguments: typeArgs,
        arguments: [
            (0, util_1.obj)(tx, args.lendingMarketOwnerCap),
            (0, util_1.obj)(tx, args.lendingMarket),
            (0, util_1.pure)(tx, args.reserveArrayIndex, `u64`),
            (0, util_1.obj)(tx, args.config),
        ],
    });
}
function withdrawCtokens(tx, typeArgs, args) {
    return tx.moveCall({
        target: `${__1.PUBLISHED_AT}::lending_market::withdraw_ctokens`,
        typeArguments: typeArgs,
        arguments: [
            (0, util_1.obj)(tx, args.lendingMarket),
            (0, util_1.pure)(tx, args.reserveArrayIndex, `u64`),
            (0, util_1.obj)(tx, args.obligationOwnerCap),
            (0, util_1.obj)(tx, args.clock),
            (0, util_1.pure)(tx, args.amount, `u64`),
        ],
    });
}
function obligation(tx, typeArg, args) {
    return tx.moveCall({
        target: `${__1.PUBLISHED_AT}::lending_market::obligation`,
        typeArguments: [typeArg],
        arguments: [
            (0, util_1.obj)(tx, args.lendingMarket),
            (0, util_1.pure)(tx, args.obligationId, `${structs_1.ID.$typeName}`),
        ],
    });
}
function createObligation(tx, typeArg, lendingMarket) {
    return tx.moveCall({
        target: `${__1.PUBLISHED_AT}::lending_market::create_obligation`,
        typeArguments: [typeArg],
        arguments: [(0, util_1.obj)(tx, lendingMarket)],
    });
}
function reserveArrayIndex(tx, typeArgs, lendingMarket) {
    return tx.moveCall({
        target: `${__1.PUBLISHED_AT}::lending_market::reserve_array_index`,
        typeArguments: typeArgs,
        arguments: [(0, util_1.obj)(tx, lendingMarket)],
    });
}
function forgive(tx, typeArgs, args) {
    return tx.moveCall({
        target: `${__1.PUBLISHED_AT}::lending_market::forgive`,
        typeArguments: typeArgs,
        arguments: [
            (0, util_1.obj)(tx, args.lendingMarketOwnerCap),
            (0, util_1.obj)(tx, args.lendingMarket),
            (0, util_1.pure)(tx, args.reserveArrayIndex, `u64`),
            (0, util_1.pure)(tx, args.obligationId, `${structs_1.ID.$typeName}`),
            (0, util_1.obj)(tx, args.clock),
            (0, util_1.pure)(tx, args.maxForgiveAmount, `u64`),
        ],
    });
}
function liquidate(tx, typeArgs, args) {
    return tx.moveCall({
        target: `${__1.PUBLISHED_AT}::lending_market::liquidate`,
        typeArguments: typeArgs,
        arguments: [
            (0, util_1.obj)(tx, args.lendingMarket),
            (0, util_1.pure)(tx, args.obligationId, `${structs_1.ID.$typeName}`),
            (0, util_1.pure)(tx, args.repayReserveArrayIndex, `u64`),
            (0, util_1.pure)(tx, args.withdrawReserveArrayIndex, `u64`),
            (0, util_1.obj)(tx, args.clock),
            (0, util_1.obj)(tx, args.repayCoins),
        ],
    });
}
function reserves(tx, typeArg, lendingMarket) {
    return tx.moveCall({
        target: `${__1.PUBLISHED_AT}::lending_market::reserves`,
        typeArguments: [typeArg],
        arguments: [(0, util_1.obj)(tx, lendingMarket)],
    });
}
function maxWithdrawAmount(tx, typeArg, args) {
    return tx.moveCall({
        target: `${__1.PUBLISHED_AT}::lending_market::max_withdraw_amount`,
        typeArguments: [typeArg],
        arguments: [
            (0, util_1.obj)(tx, args.rateLimiter),
            (0, util_1.obj)(tx, args.obligation),
            (0, util_1.obj)(tx, args.reserve),
            (0, util_1.obj)(tx, args.clock),
        ],
    });
}
function repay(tx, typeArgs, args) {
    return tx.moveCall({
        target: `${__1.PUBLISHED_AT}::lending_market::repay`,
        typeArguments: typeArgs,
        arguments: [
            (0, util_1.obj)(tx, args.lendingMarket),
            (0, util_1.pure)(tx, args.reserveArrayIndex, `u64`),
            (0, util_1.pure)(tx, args.obligationId, `${structs_1.ID.$typeName}`),
            (0, util_1.obj)(tx, args.clock),
            (0, util_1.obj)(tx, args.maxRepayCoins),
        ],
    });
}
function obligationId(tx, typeArg, cap) {
    return tx.moveCall({
        target: `${__1.PUBLISHED_AT}::lending_market::obligation_id`,
        typeArguments: [typeArg],
        arguments: [(0, util_1.obj)(tx, cap)],
    });
}
function addReserve(tx, typeArgs, args) {
    return tx.moveCall({
        target: `${__1.PUBLISHED_AT}::lending_market::add_reserve`,
        typeArguments: typeArgs,
        arguments: [
            (0, util_1.obj)(tx, args.lendingMarketOwnerCap),
            (0, util_1.obj)(tx, args.lendingMarket),
            (0, util_1.obj)(tx, args.priceInfo),
            (0, util_1.obj)(tx, args.config),
            (0, util_1.obj)(tx, args.coinMetadata),
            (0, util_1.obj)(tx, args.clock),
        ],
    });
}
function borrowRequest(tx, typeArgs, args) {
    return tx.moveCall({
        target: `${__1.PUBLISHED_AT}::lending_market::borrow_request`,
        typeArguments: typeArgs,
        arguments: [
            (0, util_1.obj)(tx, args.lendingMarket),
            (0, util_1.pure)(tx, args.reserveArrayIndex, `u64`),
            (0, util_1.obj)(tx, args.obligationOwnerCap),
            (0, util_1.obj)(tx, args.clock),
            (0, util_1.pure)(tx, args.amount, `u64`),
        ],
    });
}
function changeReservePriceFeed(tx, typeArgs, args) {
    return tx.moveCall({
        target: `${__1.PUBLISHED_AT}::lending_market::change_reserve_price_feed`,
        typeArguments: typeArgs,
        arguments: [
            (0, util_1.obj)(tx, args.lendingMarketOwnerCap),
            (0, util_1.obj)(tx, args.lendingMarket),
            (0, util_1.pure)(tx, args.reserveArrayIndex, `u64`),
            (0, util_1.obj)(tx, args.priceInfoObj),
            (0, util_1.obj)(tx, args.clock),
        ],
    });
}
function claimRewardsAndDeposit(tx, typeArgs, args) {
    return tx.moveCall({
        target: `${__1.PUBLISHED_AT}::lending_market::claim_rewards_and_deposit`,
        typeArguments: typeArgs,
        arguments: [
            (0, util_1.obj)(tx, args.lendingMarket),
            (0, util_1.pure)(tx, args.obligationId, `${structs_1.ID.$typeName}`),
            (0, util_1.obj)(tx, args.clock),
            (0, util_1.pure)(tx, args.rewardReserveId, `u64`),
            (0, util_1.pure)(tx, args.rewardIndex, `u64`),
            (0, util_1.pure)(tx, args.isDepositReward, `bool`),
            (0, util_1.pure)(tx, args.depositReserveId, `u64`),
        ],
    });
}
function claimRewardsByObligationId(tx, typeArgs, args) {
    return tx.moveCall({
        target: `${__1.PUBLISHED_AT}::lending_market::claim_rewards_by_obligation_id`,
        typeArguments: typeArgs,
        arguments: [
            (0, util_1.obj)(tx, args.lendingMarket),
            (0, util_1.pure)(tx, args.obligationId, `${structs_1.ID.$typeName}`),
            (0, util_1.obj)(tx, args.clock),
            (0, util_1.pure)(tx, args.reserveId, `u64`),
            (0, util_1.pure)(tx, args.rewardIndex, `u64`),
            (0, util_1.pure)(tx, args.isDepositReward, `bool`),
            (0, util_1.pure)(tx, args.failIfRewardPeriodNotOver, `bool`),
        ],
    });
}
function createLendingMarket(tx, typeArg) {
    return tx.moveCall({
        target: `${__1.PUBLISHED_AT}::lending_market::create_lending_market`,
        typeArguments: [typeArg],
        arguments: [],
    });
}
function depositCtokensIntoObligation(tx, typeArgs, args) {
    return tx.moveCall({
        target: `${__1.PUBLISHED_AT}::lending_market::deposit_ctokens_into_obligation`,
        typeArguments: typeArgs,
        arguments: [
            (0, util_1.obj)(tx, args.lendingMarket),
            (0, util_1.pure)(tx, args.reserveArrayIndex, `u64`),
            (0, util_1.obj)(tx, args.obligationOwnerCap),
            (0, util_1.obj)(tx, args.clock),
            (0, util_1.obj)(tx, args.deposit),
        ],
    });
}
function depositCtokensIntoObligationById(tx, typeArgs, args) {
    return tx.moveCall({
        target: `${__1.PUBLISHED_AT}::lending_market::deposit_ctokens_into_obligation_by_id`,
        typeArguments: typeArgs,
        arguments: [
            (0, util_1.obj)(tx, args.lendingMarket),
            (0, util_1.pure)(tx, args.reserveArrayIndex, `u64`),
            (0, util_1.pure)(tx, args.obligationId, `${structs_1.ID.$typeName}`),
            (0, util_1.obj)(tx, args.clock),
            (0, util_1.obj)(tx, args.deposit),
        ],
    });
}
function feeReceiver(tx, typeArg, lendingMarket) {
    return tx.moveCall({
        target: `${__1.PUBLISHED_AT}::lending_market::fee_receiver`,
        typeArguments: [typeArg],
        arguments: [(0, util_1.obj)(tx, lendingMarket)],
    });
}
function newObligationOwnerCap(tx, typeArg, args) {
    return tx.moveCall({
        target: `${__1.PUBLISHED_AT}::lending_market::new_obligation_owner_cap`,
        typeArguments: [typeArg],
        arguments: [
            (0, util_1.obj)(tx, args.lendingMarketOwnerCap),
            (0, util_1.obj)(tx, args.lendingMarket),
            (0, util_1.pure)(tx, args.obligationId, `${structs_1.ID.$typeName}`),
        ],
    });
}
function rateLimiterExemptionAmount(tx, typeArgs, exemption) {
    return tx.moveCall({
        target: `${__1.PUBLISHED_AT}::lending_market::rate_limiter_exemption_amount`,
        typeArguments: typeArgs,
        arguments: [(0, util_1.obj)(tx, exemption)],
    });
}
function redeemCtokensAndWithdrawLiquidity(tx, typeArgs, args) {
    return tx.moveCall({
        target: `${__1.PUBLISHED_AT}::lending_market::redeem_ctokens_and_withdraw_liquidity`,
        typeArguments: typeArgs,
        arguments: [
            (0, util_1.obj)(tx, args.lendingMarket),
            (0, util_1.pure)(tx, args.reserveArrayIndex, `u64`),
            (0, util_1.obj)(tx, args.clock),
            (0, util_1.obj)(tx, args.ctokens),
            (0, util_1.option)(tx, `${structs_2.RateLimiterExemption.$typeName}<${typeArgs[0]}, ${typeArgs[1]}>`, args.rateLimiterExemption),
        ],
    });
}
function redeemCtokensAndWithdrawLiquidityRequest(tx, typeArgs, args) {
    return tx.moveCall({
        target: `${__1.PUBLISHED_AT}::lending_market::redeem_ctokens_and_withdraw_liquidity_request`,
        typeArguments: typeArgs,
        arguments: [
            (0, util_1.obj)(tx, args.lendingMarket),
            (0, util_1.pure)(tx, args.reserveArrayIndex, `u64`),
            (0, util_1.obj)(tx, args.clock),
            (0, util_1.obj)(tx, args.ctokens),
            (0, util_1.option)(tx, `${structs_2.RateLimiterExemption.$typeName}<${typeArgs[0]}, ${typeArgs[1]}>`, args.rateLimiterExemption),
        ],
    });
}
function refreshReservePrice(tx, typeArg, args) {
    return tx.moveCall({
        target: `${__1.PUBLISHED_AT}::lending_market::refresh_reserve_price`,
        typeArguments: [typeArg],
        arguments: [
            (0, util_1.obj)(tx, args.lendingMarket),
            (0, util_1.pure)(tx, args.reserveArrayIndex, `u64`),
            (0, util_1.obj)(tx, args.clock),
            (0, util_1.obj)(tx, args.priceInfo),
        ],
    });
}
function setFeeReceivers(tx, typeArg, args) {
    return tx.moveCall({
        target: `${__1.PUBLISHED_AT}::lending_market::set_fee_receivers`,
        typeArguments: [typeArg],
        arguments: [
            (0, util_1.obj)(tx, args.lendingMarketOwnerCap),
            (0, util_1.obj)(tx, args.lendingMarket),
            (0, util_1.pure)(tx, args.receivers, `vector<address>`),
            (0, util_1.pure)(tx, args.weights, `vector<u64>`),
        ],
    });
}
function updateRateLimiterConfig(tx, typeArg, args) {
    return tx.moveCall({
        target: `${__1.PUBLISHED_AT}::lending_market::update_rate_limiter_config`,
        typeArguments: [typeArg],
        arguments: [
            (0, util_1.obj)(tx, args.lendingMarketOwnerCap),
            (0, util_1.obj)(tx, args.lendingMarket),
            (0, util_1.obj)(tx, args.clock),
            (0, util_1.obj)(tx, args.config),
        ],
    });
}

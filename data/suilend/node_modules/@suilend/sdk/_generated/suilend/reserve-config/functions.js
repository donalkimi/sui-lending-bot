"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
exports.set = set;
exports.destroy = destroy;
exports.from = from;
exports.setSpreadFeeBps = setSpreadFeeBps;
exports.spreadFee = spreadFee;
exports.borrowFee = borrowFee;
exports.borrowLimit = borrowLimit;
exports.borrowLimitUsd = borrowLimitUsd;
exports.borrowWeight = borrowWeight;
exports.build = build;
exports.calculateApr = calculateApr;
exports.calculateSupplyApr = calculateSupplyApr;
exports.closeLtv = closeLtv;
exports.createReserveConfig = createReserveConfig;
exports.depositLimit = depositLimit;
exports.depositLimitUsd = depositLimitUsd;
exports.isolated = isolated;
exports.liquidationBonus = liquidationBonus;
exports.openLtv = openLtv;
exports.protocolLiquidationFee = protocolLiquidationFee;
exports.setBorrowFeeBps = setBorrowFeeBps;
exports.setBorrowLimit = setBorrowLimit;
exports.setBorrowLimitUsd = setBorrowLimitUsd;
exports.setBorrowWeightBps = setBorrowWeightBps;
exports.setCloseAttributedBorrowLimitUsd = setCloseAttributedBorrowLimitUsd;
exports.setCloseLtvPct = setCloseLtvPct;
exports.setDepositLimit = setDepositLimit;
exports.setDepositLimitUsd = setDepositLimitUsd;
exports.setInterestRateAprs = setInterestRateAprs;
exports.setInterestRateUtils = setInterestRateUtils;
exports.setIsolated = setIsolated;
exports.setLiquidationBonusBps = setLiquidationBonusBps;
exports.setMaxCloseLtvPct = setMaxCloseLtvPct;
exports.setMaxLiquidationBonusBps = setMaxLiquidationBonusBps;
exports.setOpenAttributedBorrowLimitUsd = setOpenAttributedBorrowLimitUsd;
exports.setOpenLtvPct = setOpenLtvPct;
exports.setProtocolLiquidationFeeBps = setProtocolLiquidationFeeBps;
exports.validateReserveConfig = validateReserveConfig;
exports.validateUtilsAndAprs = validateUtilsAndAprs;
const __1 = require("..");
const util_1 = require("../../_framework/util");
function set(tx, typeArgs, args) {
    return tx.moveCall({
        target: `${__1.PUBLISHED_AT}::reserve_config::set`,
        typeArguments: typeArgs,
        arguments: [
            (0, util_1.obj)(tx, args.builder),
            (0, util_1.generic)(tx, `${typeArgs[0]}`, args.field),
            (0, util_1.generic)(tx, `${typeArgs[1]}`, args.value),
        ],
    });
}
function destroy(tx, config) {
    return tx.moveCall({
        target: `${__1.PUBLISHED_AT}::reserve_config::destroy`,
        arguments: [(0, util_1.obj)(tx, config)],
    });
}
function from(tx, config) {
    return tx.moveCall({
        target: `${__1.PUBLISHED_AT}::reserve_config::from`,
        arguments: [(0, util_1.obj)(tx, config)],
    });
}
function setSpreadFeeBps(tx, args) {
    return tx.moveCall({
        target: `${__1.PUBLISHED_AT}::reserve_config::set_spread_fee_bps`,
        arguments: [(0, util_1.obj)(tx, args.builder), (0, util_1.pure)(tx, args.spreadFeeBps, `u64`)],
    });
}
function spreadFee(tx, config) {
    return tx.moveCall({
        target: `${__1.PUBLISHED_AT}::reserve_config::spread_fee`,
        arguments: [(0, util_1.obj)(tx, config)],
    });
}
function borrowFee(tx, config) {
    return tx.moveCall({
        target: `${__1.PUBLISHED_AT}::reserve_config::borrow_fee`,
        arguments: [(0, util_1.obj)(tx, config)],
    });
}
function borrowLimit(tx, config) {
    return tx.moveCall({
        target: `${__1.PUBLISHED_AT}::reserve_config::borrow_limit`,
        arguments: [(0, util_1.obj)(tx, config)],
    });
}
function borrowLimitUsd(tx, config) {
    return tx.moveCall({
        target: `${__1.PUBLISHED_AT}::reserve_config::borrow_limit_usd`,
        arguments: [(0, util_1.obj)(tx, config)],
    });
}
function borrowWeight(tx, config) {
    return tx.moveCall({
        target: `${__1.PUBLISHED_AT}::reserve_config::borrow_weight`,
        arguments: [(0, util_1.obj)(tx, config)],
    });
}
function build(tx, builder) {
    return tx.moveCall({
        target: `${__1.PUBLISHED_AT}::reserve_config::build`,
        arguments: [(0, util_1.obj)(tx, builder)],
    });
}
function calculateApr(tx, args) {
    return tx.moveCall({
        target: `${__1.PUBLISHED_AT}::reserve_config::calculate_apr`,
        arguments: [(0, util_1.obj)(tx, args.config), (0, util_1.obj)(tx, args.curUtil)],
    });
}
function calculateSupplyApr(tx, args) {
    return tx.moveCall({
        target: `${__1.PUBLISHED_AT}::reserve_config::calculate_supply_apr`,
        arguments: [
            (0, util_1.obj)(tx, args.config),
            (0, util_1.obj)(tx, args.curUtil),
            (0, util_1.obj)(tx, args.borrowApr),
        ],
    });
}
function closeLtv(tx, config) {
    return tx.moveCall({
        target: `${__1.PUBLISHED_AT}::reserve_config::close_ltv`,
        arguments: [(0, util_1.obj)(tx, config)],
    });
}
function createReserveConfig(tx, args) {
    return tx.moveCall({
        target: `${__1.PUBLISHED_AT}::reserve_config::create_reserve_config`,
        arguments: [
            (0, util_1.pure)(tx, args.openLtvPct, `u8`),
            (0, util_1.pure)(tx, args.closeLtvPct, `u8`),
            (0, util_1.pure)(tx, args.maxCloseLtvPct, `u8`),
            (0, util_1.pure)(tx, args.borrowWeightBps, `u64`),
            (0, util_1.pure)(tx, args.depositLimit, `u64`),
            (0, util_1.pure)(tx, args.borrowLimit, `u64`),
            (0, util_1.pure)(tx, args.liquidationBonusBps, `u64`),
            (0, util_1.pure)(tx, args.maxLiquidationBonusBps, `u64`),
            (0, util_1.pure)(tx, args.depositLimitUsd, `u64`),
            (0, util_1.pure)(tx, args.borrowLimitUsd, `u64`),
            (0, util_1.pure)(tx, args.borrowFeeBps, `u64`),
            (0, util_1.pure)(tx, args.spreadFeeBps, `u64`),
            (0, util_1.pure)(tx, args.protocolLiquidationFeeBps, `u64`),
            (0, util_1.pure)(tx, args.interestRateUtils, `vector<u8>`),
            (0, util_1.pure)(tx, args.interestRateAprs, `vector<u64>`),
            (0, util_1.pure)(tx, args.isolated, `bool`),
            (0, util_1.pure)(tx, args.openAttributedBorrowLimitUsd, `u64`),
            (0, util_1.pure)(tx, args.closeAttributedBorrowLimitUsd, `u64`),
        ],
    });
}
function depositLimit(tx, config) {
    return tx.moveCall({
        target: `${__1.PUBLISHED_AT}::reserve_config::deposit_limit`,
        arguments: [(0, util_1.obj)(tx, config)],
    });
}
function depositLimitUsd(tx, config) {
    return tx.moveCall({
        target: `${__1.PUBLISHED_AT}::reserve_config::deposit_limit_usd`,
        arguments: [(0, util_1.obj)(tx, config)],
    });
}
function isolated(tx, config) {
    return tx.moveCall({
        target: `${__1.PUBLISHED_AT}::reserve_config::isolated`,
        arguments: [(0, util_1.obj)(tx, config)],
    });
}
function liquidationBonus(tx, config) {
    return tx.moveCall({
        target: `${__1.PUBLISHED_AT}::reserve_config::liquidation_bonus`,
        arguments: [(0, util_1.obj)(tx, config)],
    });
}
function openLtv(tx, config) {
    return tx.moveCall({
        target: `${__1.PUBLISHED_AT}::reserve_config::open_ltv`,
        arguments: [(0, util_1.obj)(tx, config)],
    });
}
function protocolLiquidationFee(tx, config) {
    return tx.moveCall({
        target: `${__1.PUBLISHED_AT}::reserve_config::protocol_liquidation_fee`,
        arguments: [(0, util_1.obj)(tx, config)],
    });
}
function setBorrowFeeBps(tx, args) {
    return tx.moveCall({
        target: `${__1.PUBLISHED_AT}::reserve_config::set_borrow_fee_bps`,
        arguments: [(0, util_1.obj)(tx, args.builder), (0, util_1.pure)(tx, args.borrowFeeBps, `u64`)],
    });
}
function setBorrowLimit(tx, args) {
    return tx.moveCall({
        target: `${__1.PUBLISHED_AT}::reserve_config::set_borrow_limit`,
        arguments: [(0, util_1.obj)(tx, args.builder), (0, util_1.pure)(tx, args.borrowLimit, `u64`)],
    });
}
function setBorrowLimitUsd(tx, args) {
    return tx.moveCall({
        target: `${__1.PUBLISHED_AT}::reserve_config::set_borrow_limit_usd`,
        arguments: [(0, util_1.obj)(tx, args.builder), (0, util_1.pure)(tx, args.borrowLimitUsd, `u64`)],
    });
}
function setBorrowWeightBps(tx, args) {
    return tx.moveCall({
        target: `${__1.PUBLISHED_AT}::reserve_config::set_borrow_weight_bps`,
        arguments: [(0, util_1.obj)(tx, args.builder), (0, util_1.pure)(tx, args.borrowWeightBps, `u64`)],
    });
}
function setCloseAttributedBorrowLimitUsd(tx, args) {
    return tx.moveCall({
        target: `${__1.PUBLISHED_AT}::reserve_config::set_close_attributed_borrow_limit_usd`,
        arguments: [
            (0, util_1.obj)(tx, args.builder),
            (0, util_1.pure)(tx, args.closeAttributedBorrowLimitUsd, `u64`),
        ],
    });
}
function setCloseLtvPct(tx, args) {
    return tx.moveCall({
        target: `${__1.PUBLISHED_AT}::reserve_config::set_close_ltv_pct`,
        arguments: [(0, util_1.obj)(tx, args.builder), (0, util_1.pure)(tx, args.closeLtvPct, `u8`)],
    });
}
function setDepositLimit(tx, args) {
    return tx.moveCall({
        target: `${__1.PUBLISHED_AT}::reserve_config::set_deposit_limit`,
        arguments: [(0, util_1.obj)(tx, args.builder), (0, util_1.pure)(tx, args.depositLimit, `u64`)],
    });
}
function setDepositLimitUsd(tx, args) {
    return tx.moveCall({
        target: `${__1.PUBLISHED_AT}::reserve_config::set_deposit_limit_usd`,
        arguments: [(0, util_1.obj)(tx, args.builder), (0, util_1.pure)(tx, args.depositLimitUsd, `u64`)],
    });
}
function setInterestRateAprs(tx, args) {
    return tx.moveCall({
        target: `${__1.PUBLISHED_AT}::reserve_config::set_interest_rate_aprs`,
        arguments: [
            (0, util_1.obj)(tx, args.builder),
            (0, util_1.pure)(tx, args.interestRateAprs, `vector<u64>`),
        ],
    });
}
function setInterestRateUtils(tx, args) {
    return tx.moveCall({
        target: `${__1.PUBLISHED_AT}::reserve_config::set_interest_rate_utils`,
        arguments: [
            (0, util_1.obj)(tx, args.builder),
            (0, util_1.pure)(tx, args.interestRateUtils, `vector<u8>`),
        ],
    });
}
function setIsolated(tx, args) {
    return tx.moveCall({
        target: `${__1.PUBLISHED_AT}::reserve_config::set_isolated`,
        arguments: [(0, util_1.obj)(tx, args.builder), (0, util_1.pure)(tx, args.isolated, `bool`)],
    });
}
function setLiquidationBonusBps(tx, args) {
    return tx.moveCall({
        target: `${__1.PUBLISHED_AT}::reserve_config::set_liquidation_bonus_bps`,
        arguments: [
            (0, util_1.obj)(tx, args.builder),
            (0, util_1.pure)(tx, args.liquidationBonusBps, `u64`),
        ],
    });
}
function setMaxCloseLtvPct(tx, args) {
    return tx.moveCall({
        target: `${__1.PUBLISHED_AT}::reserve_config::set_max_close_ltv_pct`,
        arguments: [(0, util_1.obj)(tx, args.builder), (0, util_1.pure)(tx, args.maxCloseLtvPct, `u8`)],
    });
}
function setMaxLiquidationBonusBps(tx, args) {
    return tx.moveCall({
        target: `${__1.PUBLISHED_AT}::reserve_config::set_max_liquidation_bonus_bps`,
        arguments: [
            (0, util_1.obj)(tx, args.builder),
            (0, util_1.pure)(tx, args.maxLiquidationBonusBps, `u64`),
        ],
    });
}
function setOpenAttributedBorrowLimitUsd(tx, args) {
    return tx.moveCall({
        target: `${__1.PUBLISHED_AT}::reserve_config::set_open_attributed_borrow_limit_usd`,
        arguments: [
            (0, util_1.obj)(tx, args.builder),
            (0, util_1.pure)(tx, args.openAttributedBorrowLimitUsd, `u64`),
        ],
    });
}
function setOpenLtvPct(tx, args) {
    return tx.moveCall({
        target: `${__1.PUBLISHED_AT}::reserve_config::set_open_ltv_pct`,
        arguments: [(0, util_1.obj)(tx, args.builder), (0, util_1.pure)(tx, args.openLtvPct, `u8`)],
    });
}
function setProtocolLiquidationFeeBps(tx, args) {
    return tx.moveCall({
        target: `${__1.PUBLISHED_AT}::reserve_config::set_protocol_liquidation_fee_bps`,
        arguments: [
            (0, util_1.obj)(tx, args.builder),
            (0, util_1.pure)(tx, args.protocolLiquidationFeeBps, `u64`),
        ],
    });
}
function validateReserveConfig(tx, config) {
    return tx.moveCall({
        target: `${__1.PUBLISHED_AT}::reserve_config::validate_reserve_config`,
        arguments: [(0, util_1.obj)(tx, config)],
    });
}
function validateUtilsAndAprs(tx, args) {
    return tx.moveCall({
        target: `${__1.PUBLISHED_AT}::reserve_config::validate_utils_and_aprs`,
        arguments: [
            (0, util_1.pure)(tx, args.utils, `vector<u8>`),
            (0, util_1.pure)(tx, args.aprs, `vector<u64>`),
        ],
    });
}

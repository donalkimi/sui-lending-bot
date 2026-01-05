"use strict";
var __createBinding = (this && this.__createBinding) || (Object.create ? (function(o, m, k, k2) {
    if (k2 === undefined) k2 = k;
    var desc = Object.getOwnPropertyDescriptor(m, k);
    if (!desc || ("get" in desc ? !m.__esModule : desc.writable || desc.configurable)) {
      desc = { enumerable: true, get: function() { return m[k]; } };
    }
    Object.defineProperty(o, k2, desc);
}) : (function(o, m, k, k2) {
    if (k2 === undefined) k2 = k;
    o[k2] = m[k];
}));
var __setModuleDefault = (this && this.__setModuleDefault) || (Object.create ? (function(o, v) {
    Object.defineProperty(o, "default", { enumerable: true, value: v });
}) : function(o, v) {
    o["default"] = v;
});
var __importStar = (this && this.__importStar) || (function () {
    var ownKeys = function(o) {
        ownKeys = Object.getOwnPropertyNames || function (o) {
            var ar = [];
            for (var k in o) if (Object.prototype.hasOwnProperty.call(o, k)) ar[ar.length] = k;
            return ar;
        };
        return ownKeys(o);
    };
    return function (mod) {
        if (mod && mod.__esModule) return mod;
        var result = {};
        if (mod != null) for (var k = ownKeys(mod), i = 0; i < k.length; i++) if (k[i] !== "default") __createBinding(result, mod, k[i]);
        __setModuleDefault(result, mod);
        return result;
    };
})();
var __importDefault = (this && this.__importDefault) || function (mod) {
    return (mod && mod.__esModule) ? mod : { "default": mod };
};
Object.defineProperty(exports, "__esModule", { value: true });
exports.parsePoolReward = exports.parsePoolRewardManager = exports.parseReserveConfig = exports.parseReserve = void 0;
const utils_1 = require("@mysten/sui/utils");
const bignumber_js_1 = __importDefault(require("bignumber.js"));
const uuid_1 = require("uuid");
const constants_1 = require("../lib/constants");
const utils_2 = require("../utils");
const simulate = __importStar(require("../utils/simulate"));
const parseReserve = (reserve, coinMetadataMap) => {
    const config = (0, exports.parseReserveConfig)(reserve);
    const $typeName = reserve.$typeName;
    const id = reserve.id;
    const arrayIndex = BigInt(reserve.arrayIndex);
    const coinType = (0, utils_1.normalizeStructTag)(reserve.coinType.name);
    const coinMetadata = coinMetadataMap[coinType];
    const mintDecimals = reserve.mintDecimals;
    const priceIdentifier = `0x${(0, utils_2.toHexString)(reserve.priceIdentifier.bytes)}`;
    const price = new bignumber_js_1.default(reserve.price.value.toString()).div(constants_1.WAD);
    const smoothedPrice = new bignumber_js_1.default(reserve.smoothedPrice.value.toString()).div(constants_1.WAD);
    const minPrice = bignumber_js_1.default.min(price, smoothedPrice);
    const maxPrice = bignumber_js_1.default.max(price, smoothedPrice);
    const priceLastUpdateTimestampS = reserve.priceLastUpdateTimestampS;
    const availableAmount = new bignumber_js_1.default(reserve.availableAmount.toString()).div(10 ** mintDecimals);
    const ctokenSupply = new bignumber_js_1.default(reserve.ctokenSupply.toString()).div(10 ** mintDecimals);
    const borrowedAmount = new bignumber_js_1.default(reserve.borrowedAmount.value.toString())
        .div(constants_1.WAD)
        .div(10 ** mintDecimals);
    const cumulativeBorrowRate = new bignumber_js_1.default(reserve.cumulativeBorrowRate.value.toString()).div(constants_1.WAD);
    const interestLastUpdateTimestampS = reserve.interestLastUpdateTimestampS;
    const unclaimedSpreadFees = new bignumber_js_1.default(reserve.unclaimedSpreadFees.value.toString())
        .div(constants_1.WAD)
        .div(10 ** mintDecimals);
    const attributedBorrowValue = new bignumber_js_1.default(reserve.attributedBorrowValue.value.toString());
    const depositsPoolRewardManager = (0, exports.parsePoolRewardManager)(reserve.depositsPoolRewardManager, coinMetadataMap);
    const borrowsPoolRewardManager = (0, exports.parsePoolRewardManager)(reserve.borrowsPoolRewardManager, coinMetadataMap);
    // Custom
    const availableAmountUsd = availableAmount.times(price);
    const borrowedAmountUsd = borrowedAmount.times(price);
    const depositedAmount = borrowedAmount.plus(availableAmount);
    const depositedAmountUsd = depositedAmount.times(price);
    const cTokenExchangeRate = simulate.cTokenRatio(reserve);
    const borrowAprPercent = simulate.calculateBorrowAprPercent(reserve);
    const depositAprPercent = simulate.calculateDepositAprPercent(reserve);
    const utilizationPercent = simulate.calculateUtilizationPercent(reserve);
    const symbol = coinMetadata.symbol;
    const name = coinMetadata.name;
    const iconUrl = coinMetadata.iconUrl;
    const description = coinMetadata.description;
    return {
        config,
        $typeName,
        id,
        arrayIndex,
        coinType,
        mintDecimals,
        priceIdentifier,
        price,
        smoothedPrice,
        minPrice,
        maxPrice,
        priceLastUpdateTimestampS,
        availableAmount,
        ctokenSupply,
        borrowedAmount,
        cumulativeBorrowRate,
        interestLastUpdateTimestampS,
        unclaimedSpreadFees,
        attributedBorrowValue,
        depositsPoolRewardManager,
        borrowsPoolRewardManager,
        availableAmountUsd,
        borrowedAmountUsd,
        depositedAmount,
        depositedAmountUsd,
        cTokenExchangeRate,
        borrowAprPercent,
        depositAprPercent,
        utilizationPercent,
        token: Object.assign({ coinType }, coinMetadata),
        /**
         * @deprecated since version 1.1.19. Use `token.symbol` instead.
         */
        symbol,
        /**
         * @deprecated since version 1.1.19. Use `token.name` instead.
         */
        name,
        /**
         * @deprecated since version 1.1.19. Use `token.iconUrl` instead.
         */
        iconUrl,
        /**
         * @deprecated since version 1.1.19. Use `token.description` instead.
         */
        description,
        /**
         * @deprecated since version 1.0.3. Use `depositedAmount` instead.
         */
        totalDeposits: depositedAmount,
    };
};
exports.parseReserve = parseReserve;
const parseReserveConfig = (reserve) => {
    const config = reserve.config.element;
    if (!config)
        throw new Error("Reserve config not found");
    const mintDecimals = reserve.mintDecimals;
    const $typeName = config.$typeName;
    const openLtvPct = config.openLtvPct;
    const closeLtvPct = config.closeLtvPct;
    const maxCloseLtvPct = config.maxCloseLtvPct;
    const borrowWeightBps = (0, bignumber_js_1.default)(config.borrowWeightBps.toString());
    const depositLimit = new bignumber_js_1.default(config.depositLimit.toString()).div(10 ** mintDecimals);
    const borrowLimit = new bignumber_js_1.default(config.borrowLimit.toString()).div(10 ** mintDecimals);
    const liquidationBonusBps = Number(config.liquidationBonusBps.toString());
    const maxLiquidationBonusBps = Number(config.maxLiquidationBonusBps.toString());
    const depositLimitUsd = new bignumber_js_1.default(config.depositLimitUsd.toString());
    const borrowLimitUsd = new bignumber_js_1.default(config.borrowLimitUsd.toString());
    const borrowFeeBps = Number(config.borrowFeeBps.toString());
    const spreadFeeBps = Number(config.spreadFeeBps.toString());
    const protocolLiquidationFeeBps = Number(config.protocolLiquidationFeeBps.toString());
    const isolated = config.isolated;
    const openAttributedBorrowLimitUsd = Number(config.openAttributedBorrowLimitUsd.toString());
    const closeAttributedBorrowLimitUsd = Number(config.closeAttributedBorrowLimitUsd.toString());
    // additionalFields
    const interestRate = config.interestRateUtils.map((util, index) => ({
        id: (0, uuid_1.v4)(),
        utilPercent: new bignumber_js_1.default(util.toString()),
        aprPercent: new bignumber_js_1.default(config.interestRateAprs[index].toString()).div(100),
    }));
    return {
        $typeName,
        openLtvPct,
        closeLtvPct,
        maxCloseLtvPct,
        borrowWeightBps,
        depositLimit,
        borrowLimit,
        liquidationBonusBps,
        maxLiquidationBonusBps,
        depositLimitUsd,
        borrowLimitUsd,
        borrowFeeBps,
        spreadFeeBps,
        protocolLiquidationFeeBps,
        isolated,
        openAttributedBorrowLimitUsd,
        closeAttributedBorrowLimitUsd,
        // additionalFields,
        interestRate,
    };
};
exports.parseReserveConfig = parseReserveConfig;
const parsePoolRewardManager = (poolRewardManager, coinMetadataMap) => {
    const $typeName = poolRewardManager.$typeName;
    const id = poolRewardManager.id;
    const totalShares = poolRewardManager.totalShares;
    const poolRewards = poolRewardManager.poolRewards
        .map((pr, index) => (0, exports.parsePoolReward)(pr, index, coinMetadataMap))
        .filter(Boolean);
    const lastUpdateTimeMs = poolRewardManager.lastUpdateTimeMs;
    return {
        $typeName,
        id,
        totalShares,
        poolRewards,
        lastUpdateTimeMs,
    };
};
exports.parsePoolRewardManager = parsePoolRewardManager;
const parsePoolReward = (poolReward, rewardIndex, coinMetadataMap) => {
    if (!poolReward)
        return null;
    const $typeName = poolReward.$typeName;
    const id = poolReward.id;
    const poolRewardManagerId = poolReward.poolRewardManagerId;
    const coinType = (0, utils_1.normalizeStructTag)(poolReward.coinType.name);
    const coinMetadata = coinMetadataMap[coinType];
    const mintDecimals = coinMetadata.decimals;
    const startTimeMs = Number(poolReward.startTimeMs);
    const endTimeMs = Number(poolReward.endTimeMs);
    const totalRewards = new bignumber_js_1.default(poolReward.totalRewards.toString()).div(10 ** coinMetadata.decimals);
    const allocatedRewards = new bignumber_js_1.default(poolReward.allocatedRewards.value.toString())
        .div(constants_1.WAD)
        .div(10 ** coinMetadata.decimals);
    const cumulativeRewardsPerShare = new bignumber_js_1.default(poolReward.cumulativeRewardsPerShare.value.toString())
        .div(constants_1.WAD)
        .div(10 ** coinMetadata.decimals);
    const numUserRewardManagers = poolReward.numUserRewardManagers;
    // additionalFields
    // Custom
    const symbol = coinMetadata.symbol;
    return {
        $typeName,
        id,
        poolRewardManagerId,
        coinType,
        startTimeMs,
        endTimeMs,
        totalRewards,
        allocatedRewards,
        cumulativeRewardsPerShare,
        numUserRewardManagers,
        rewardIndex,
        symbol,
        mintDecimals,
    };
};
exports.parsePoolReward = parsePoolReward;

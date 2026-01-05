import { CoinMetadata } from "@mysten/sui/client";
import BigNumber from "bignumber.js";
import { PoolReward, PoolRewardManager } from "../_generated/suilend/liquidity-mining/structs";
import { Reserve } from "../_generated/suilend/reserve/structs";
export type ParsedReserve = ReturnType<typeof parseReserve>;
export type ParsedReserveConfig = ReturnType<typeof parseReserveConfig>;
export type ParsedPoolRewardManager = ReturnType<typeof parsePoolRewardManager>;
export type ParsedPoolReward = NonNullable<ReturnType<typeof parsePoolReward>>;
export declare const parseReserve: (reserve: Reserve<string>, coinMetadataMap: Record<string, CoinMetadata>) => {
    config: {
        $typeName: string;
        openLtvPct: number;
        closeLtvPct: number;
        maxCloseLtvPct: number;
        borrowWeightBps: BigNumber;
        depositLimit: BigNumber;
        borrowLimit: BigNumber;
        liquidationBonusBps: number;
        maxLiquidationBonusBps: number;
        depositLimitUsd: BigNumber;
        borrowLimitUsd: BigNumber;
        borrowFeeBps: number;
        spreadFeeBps: number;
        protocolLiquidationFeeBps: number;
        isolated: boolean;
        openAttributedBorrowLimitUsd: number;
        closeAttributedBorrowLimitUsd: number;
        interestRate: {
            id: string;
            utilPercent: BigNumber;
            aprPercent: BigNumber;
        }[];
    };
    $typeName: string;
    id: string;
    arrayIndex: bigint;
    coinType: string;
    mintDecimals: number;
    priceIdentifier: string;
    price: BigNumber;
    smoothedPrice: BigNumber;
    minPrice: BigNumber;
    maxPrice: BigNumber;
    priceLastUpdateTimestampS: bigint;
    availableAmount: BigNumber;
    ctokenSupply: BigNumber;
    borrowedAmount: BigNumber;
    cumulativeBorrowRate: BigNumber;
    interestLastUpdateTimestampS: bigint;
    unclaimedSpreadFees: BigNumber;
    attributedBorrowValue: BigNumber;
    depositsPoolRewardManager: {
        $typeName: string;
        id: string;
        totalShares: bigint;
        poolRewards: {
            $typeName: string;
            id: string;
            poolRewardManagerId: string;
            coinType: string;
            startTimeMs: number;
            endTimeMs: number;
            totalRewards: BigNumber;
            allocatedRewards: BigNumber;
            cumulativeRewardsPerShare: BigNumber;
            numUserRewardManagers: bigint;
            rewardIndex: number;
            symbol: string;
            mintDecimals: number;
        }[];
        lastUpdateTimeMs: bigint;
    };
    borrowsPoolRewardManager: {
        $typeName: string;
        id: string;
        totalShares: bigint;
        poolRewards: {
            $typeName: string;
            id: string;
            poolRewardManagerId: string;
            coinType: string;
            startTimeMs: number;
            endTimeMs: number;
            totalRewards: BigNumber;
            allocatedRewards: BigNumber;
            cumulativeRewardsPerShare: BigNumber;
            numUserRewardManagers: bigint;
            rewardIndex: number;
            symbol: string;
            mintDecimals: number;
        }[];
        lastUpdateTimeMs: bigint;
    };
    availableAmountUsd: BigNumber;
    borrowedAmountUsd: BigNumber;
    depositedAmount: BigNumber;
    depositedAmountUsd: BigNumber;
    cTokenExchangeRate: BigNumber;
    borrowAprPercent: BigNumber;
    depositAprPercent: BigNumber;
    utilizationPercent: BigNumber;
    token: {
        decimals: number;
        description: string;
        iconUrl?: string | null;
        id?: string | null;
        name: string;
        symbol: string;
        coinType: string;
    };
    /**
     * @deprecated since version 1.1.19. Use `token.symbol` instead.
     */
    symbol: string;
    /**
     * @deprecated since version 1.1.19. Use `token.name` instead.
     */
    name: string;
    /**
     * @deprecated since version 1.1.19. Use `token.iconUrl` instead.
     */
    iconUrl: string | null | undefined;
    /**
     * @deprecated since version 1.1.19. Use `token.description` instead.
     */
    description: string;
    /**
     * @deprecated since version 1.0.3. Use `depositedAmount` instead.
     */
    totalDeposits: BigNumber;
};
export declare const parseReserveConfig: (reserve: Reserve<string>) => {
    $typeName: string;
    openLtvPct: number;
    closeLtvPct: number;
    maxCloseLtvPct: number;
    borrowWeightBps: BigNumber;
    depositLimit: BigNumber;
    borrowLimit: BigNumber;
    liquidationBonusBps: number;
    maxLiquidationBonusBps: number;
    depositLimitUsd: BigNumber;
    borrowLimitUsd: BigNumber;
    borrowFeeBps: number;
    spreadFeeBps: number;
    protocolLiquidationFeeBps: number;
    isolated: boolean;
    openAttributedBorrowLimitUsd: number;
    closeAttributedBorrowLimitUsd: number;
    interestRate: {
        id: string;
        utilPercent: BigNumber;
        aprPercent: BigNumber;
    }[];
};
export declare const parsePoolRewardManager: (poolRewardManager: PoolRewardManager, coinMetadataMap: Record<string, CoinMetadata>) => {
    $typeName: string;
    id: string;
    totalShares: bigint;
    poolRewards: {
        $typeName: string;
        id: string;
        poolRewardManagerId: string;
        coinType: string;
        startTimeMs: number;
        endTimeMs: number;
        totalRewards: BigNumber;
        allocatedRewards: BigNumber;
        cumulativeRewardsPerShare: BigNumber;
        numUserRewardManagers: bigint;
        rewardIndex: number;
        symbol: string;
        mintDecimals: number;
    }[];
    lastUpdateTimeMs: bigint;
};
export declare const parsePoolReward: (poolReward: PoolReward | null, rewardIndex: number, coinMetadataMap: Record<string, CoinMetadata>) => {
    $typeName: string;
    id: string;
    poolRewardManagerId: string;
    coinType: string;
    startTimeMs: number;
    endTimeMs: number;
    totalRewards: BigNumber;
    allocatedRewards: BigNumber;
    cumulativeRewardsPerShare: BigNumber;
    numUserRewardManagers: bigint;
    rewardIndex: number;
    symbol: string;
    mintDecimals: number;
} | null;

import { SuiPriceServiceConnection } from "@pythnetwork/pyth-sui-js";
import BigNumber from "bignumber.js";
import { Decimal } from "../_generated/suilend/decimal/structs";
import { PoolRewardManager, UserRewardManager } from "../_generated/suilend/liquidity-mining/structs";
import { Borrow, Obligation } from "../_generated/suilend/obligation/structs";
import { Reserve } from "../_generated/suilend/reserve/structs";
/**
 * @deprecated since version 1.0.8. Use `calculateUtilizationPercent` instead.
 */
export declare const calculateUtilizationRate: (reserve: Reserve<string>) => BigNumber;
export declare const calculateUtilizationPercent: (reserve: Reserve<string>) => BigNumber;
/**
 * @deprecated since version 1.0.8. Use `calculateBorrowAprPercent` instead.
 */
export declare const calculateBorrowApr: (reserve: Reserve<string>) => BigNumber;
export declare const calculateBorrowAprPercent: (reserve: Reserve<string>) => BigNumber;
/**
 * @deprecated since version 1.0.8. Use `calculateDepositAprPercent` instead.
 */
export declare const calculateSupplyApr: (reserve: Reserve<string>) => BigNumber;
export declare const calculateDepositAprPercent: (reserve: Reserve<string>) => BigNumber;
export declare const compoundReserveInterest: (reserve: Reserve<string>, nowS: number) => Reserve<string>;
export declare const updatePoolRewardsManager: (manager: PoolRewardManager, nowMs: number) => PoolRewardManager;
export declare const refreshReservePrice: (reserves: Reserve<string>[], pythConnection: SuiPriceServiceConnection) => Promise<Reserve<string>[]>;
export declare const updateUserRewardManager: (poolManager: PoolRewardManager, userRewardManager: UserRewardManager, nowMs: number) => UserRewardManager;
export declare const refreshObligation: (unrefreshedObligation: Obligation<string>, refreshedReserves: Reserve<string>[]) => Obligation<string>;
export declare const numberToDecimal: (value: number) => Decimal;
export declare const stringToDecimal: (value: string) => Decimal;
export declare const decimalToBigNumber: (value: Decimal) => BigNumber;
export declare const getCTokenMarketValue: (reserve: Reserve<string>, depositedCTokenAmount: BigNumber) => BigNumber;
export declare const getCTokenMarketValueLowerBound: (reserve: Reserve<string>, depositedCTokenAmount: BigNumber) => BigNumber;
export declare const cTokenRatio: (reserve: Reserve<string>) => BigNumber;
export declare const totalSupply: (reserve: Reserve<string>) => BigNumber;
export declare const compoundDebt: (borrow: Borrow, reserve: Reserve<string>) => Borrow;

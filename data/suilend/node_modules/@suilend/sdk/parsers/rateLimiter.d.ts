import BigNumber from "bignumber.js";
import { RateLimiter } from "../_generated/suilend/rate-limiter/structs";
export type ParsedRateLimiter = ReturnType<typeof parseRateLimiter>;
export type ParsedRateLimiterConfig = ReturnType<typeof parseRateLimiterConfig>;
export declare const parseRateLimiter: (rateLimiter: RateLimiter, nowS: number) => {
    config: {
        windowDuration: bigint;
        maxOutflow: bigint;
    };
    $typeName: string;
    prevQty: bigint;
    windowStart: bigint;
    curQty: bigint;
    remainingOutflow: BigNumber;
};
export declare const parseRateLimiterConfig: (rateLimiter: RateLimiter) => {
    windowDuration: bigint;
    maxOutflow: bigint;
};

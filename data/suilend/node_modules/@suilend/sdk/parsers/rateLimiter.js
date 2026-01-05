"use strict";
var __importDefault = (this && this.__importDefault) || function (mod) {
    return (mod && mod.__esModule) ? mod : { "default": mod };
};
Object.defineProperty(exports, "__esModule", { value: true });
exports.parseRateLimiterConfig = exports.parseRateLimiter = void 0;
const bignumber_js_1 = __importDefault(require("bignumber.js"));
const constants_1 = require("../lib/constants");
const parseRateLimiter = (rateLimiter, nowS) => {
    const config = (0, exports.parseRateLimiterConfig)(rateLimiter);
    const $typeName = rateLimiter.$typeName;
    const prevQty = rateLimiter.prevQty.value;
    const windowStart = rateLimiter.windowStart;
    const curQty = rateLimiter.curQty.value;
    // Custom
    const prevWeight = new bignumber_js_1.default(config.windowDuration.toString())
        .minus((BigInt(nowS) - windowStart + BigInt(1)).toString())
        .div(config.windowDuration.toString());
    const currentOutflow = prevWeight
        .times(new bignumber_js_1.default(prevQty.toString()))
        .plus(new bignumber_js_1.default(curQty.toString()))
        .div(constants_1.WAD);
    const remainingOutflow = currentOutflow.gt(config.maxOutflow.toString())
        ? new bignumber_js_1.default(0)
        : new bignumber_js_1.default(config.maxOutflow.toString()).minus(currentOutflow);
    return {
        config,
        $typeName,
        prevQty,
        windowStart,
        curQty,
        remainingOutflow,
    };
};
exports.parseRateLimiter = parseRateLimiter;
const parseRateLimiterConfig = (rateLimiter) => {
    const config = rateLimiter.config;
    if (!config)
        throw new Error("Rate limiter config not found");
    const windowDuration = config.windowDuration;
    const maxOutflow = config.maxOutflow;
    return {
        windowDuration,
        maxOutflow,
    };
};
exports.parseRateLimiterConfig = parseRateLimiterConfig;

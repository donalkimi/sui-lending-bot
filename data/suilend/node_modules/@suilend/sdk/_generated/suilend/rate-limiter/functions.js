"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
exports.new_ = new_;
exports.currentOutflow = currentOutflow;
exports.newConfig = newConfig;
exports.processQty = processQty;
exports.remainingOutflow = remainingOutflow;
exports.updateInternal = updateInternal;
const __1 = require("..");
const util_1 = require("../../_framework/util");
function new_(tx, args) {
    return tx.moveCall({
        target: `${__1.PUBLISHED_AT}::rate_limiter::new`,
        arguments: [(0, util_1.obj)(tx, args.config), (0, util_1.pure)(tx, args.curTime, `u64`)],
    });
}
function currentOutflow(tx, args) {
    return tx.moveCall({
        target: `${__1.PUBLISHED_AT}::rate_limiter::current_outflow`,
        arguments: [(0, util_1.obj)(tx, args.rateLimiter), (0, util_1.pure)(tx, args.curTime, `u64`)],
    });
}
function newConfig(tx, args) {
    return tx.moveCall({
        target: `${__1.PUBLISHED_AT}::rate_limiter::new_config`,
        arguments: [
            (0, util_1.pure)(tx, args.windowDuration, `u64`),
            (0, util_1.pure)(tx, args.maxOutflow, `u64`),
        ],
    });
}
function processQty(tx, args) {
    return tx.moveCall({
        target: `${__1.PUBLISHED_AT}::rate_limiter::process_qty`,
        arguments: [
            (0, util_1.obj)(tx, args.rateLimiter),
            (0, util_1.pure)(tx, args.curTime, `u64`),
            (0, util_1.obj)(tx, args.qty),
        ],
    });
}
function remainingOutflow(tx, args) {
    return tx.moveCall({
        target: `${__1.PUBLISHED_AT}::rate_limiter::remaining_outflow`,
        arguments: [(0, util_1.obj)(tx, args.rateLimiter), (0, util_1.pure)(tx, args.curTime, `u64`)],
    });
}
function updateInternal(tx, args) {
    return tx.moveCall({
        target: `${__1.PUBLISHED_AT}::rate_limiter::update_internal`,
        arguments: [(0, util_1.obj)(tx, args.rateLimiter), (0, util_1.pure)(tx, args.curTime, `u64`)],
    });
}

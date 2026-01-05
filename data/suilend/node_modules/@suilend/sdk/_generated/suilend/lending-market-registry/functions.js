"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
exports.init = init;
exports.createLendingMarket = createLendingMarket;
const __1 = require("..");
const util_1 = require("../../_framework/util");
function init(tx) {
    return tx.moveCall({
        target: `${__1.PUBLISHED_AT}::lending_market_registry::init`,
        arguments: [],
    });
}
function createLendingMarket(tx, typeArg, registry) {
    return tx.moveCall({
        target: `${__1.PUBLISHED_AT}::lending_market_registry::create_lending_market`,
        typeArguments: [typeArg],
        arguments: [(0, util_1.obj)(tx, registry)],
    });
}

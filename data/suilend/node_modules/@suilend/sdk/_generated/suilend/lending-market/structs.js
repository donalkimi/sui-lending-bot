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
var __awaiter = (this && this.__awaiter) || function (thisArg, _arguments, P, generator) {
    function adopt(value) { return value instanceof P ? value : new P(function (resolve) { resolve(value); }); }
    return new (P || (P = Promise))(function (resolve, reject) {
        function fulfilled(value) { try { step(generator.next(value)); } catch (e) { reject(e); } }
        function rejected(value) { try { step(generator["throw"](value)); } catch (e) { reject(e); } }
        function step(result) { result.done ? resolve(result.value) : adopt(result.value).then(fulfilled, rejected); }
        step((generator = generator.apply(thisArg, _arguments || [])).next());
    });
};
Object.defineProperty(exports, "__esModule", { value: true });
exports.WithdrawEvent = exports.RepayEvent = exports.RateLimiterExemption = exports.ObligationOwnerCap = exports.LiquidateEvent = exports.LendingMarketOwnerCap = exports.LendingMarket = exports.LENDING_MARKET = exports.ForgiveEvent = exports.FeeReceiversKey = exports.FeeReceivers = exports.DepositEvent = exports.ClaimRewardEvent = exports.BorrowEvent = exports.RedeemEvent = exports.MintEvent = void 0;
exports.isMintEvent = isMintEvent;
exports.isRedeemEvent = isRedeemEvent;
exports.isBorrowEvent = isBorrowEvent;
exports.isClaimRewardEvent = isClaimRewardEvent;
exports.isDepositEvent = isDepositEvent;
exports.isFeeReceivers = isFeeReceivers;
exports.isFeeReceiversKey = isFeeReceiversKey;
exports.isForgiveEvent = isForgiveEvent;
exports.isLENDING_MARKET = isLENDING_MARKET;
exports.isLendingMarket = isLendingMarket;
exports.isLendingMarketOwnerCap = isLendingMarketOwnerCap;
exports.isLiquidateEvent = isLiquidateEvent;
exports.isObligationOwnerCap = isObligationOwnerCap;
exports.isRateLimiterExemption = isRateLimiterExemption;
exports.isRepayEvent = isRepayEvent;
exports.isWithdrawEvent = isWithdrawEvent;
const reified = __importStar(require("../../_framework/reified"));
const structs_1 = require("../../_dependencies/source/0x1/type-name/structs");
const structs_2 = require("../../_dependencies/source/0x2/object-table/structs");
const structs_3 = require("../../_dependencies/source/0x2/object/structs");
const reified_1 = require("../../_framework/reified");
const util_1 = require("../../_framework/util");
const structs_4 = require("../decimal/structs");
const index_1 = require("../index");
const structs_5 = require("../obligation/structs");
const structs_6 = require("../rate-limiter/structs");
const structs_7 = require("../reserve/structs");
const bcs_1 = require("@mysten/sui/bcs");
const utils_1 = require("@mysten/sui/utils");
/* ============================== MintEvent =============================== */
function isMintEvent(type) {
    type = (0, util_1.compressSuiType)(type);
    return type === `${index_1.PKG_V1}::lending_market::MintEvent`;
}
class MintEvent {
    constructor(typeArgs, fields) {
        this.__StructClass = true;
        this.$typeName = MintEvent.$typeName;
        this.$isPhantom = MintEvent.$isPhantom;
        this.$fullTypeName = (0, util_1.composeSuiType)(MintEvent.$typeName, ...typeArgs);
        this.$typeArgs = typeArgs;
        this.lendingMarketId = fields.lendingMarketId;
        this.coinType = fields.coinType;
        this.reserveId = fields.reserveId;
        this.liquidityAmount = fields.liquidityAmount;
        this.ctokenAmount = fields.ctokenAmount;
    }
    static reified() {
        return {
            typeName: MintEvent.$typeName,
            fullTypeName: (0, util_1.composeSuiType)(MintEvent.$typeName, ...[]),
            typeArgs: [],
            isPhantom: MintEvent.$isPhantom,
            reifiedTypeArgs: [],
            fromFields: (fields) => MintEvent.fromFields(fields),
            fromFieldsWithTypes: (item) => MintEvent.fromFieldsWithTypes(item),
            fromBcs: (data) => MintEvent.fromBcs(data),
            bcs: MintEvent.bcs,
            fromJSONField: (field) => MintEvent.fromJSONField(field),
            fromJSON: (json) => MintEvent.fromJSON(json),
            fromSuiParsedData: (content) => MintEvent.fromSuiParsedData(content),
            fromSuiObjectData: (content) => MintEvent.fromSuiObjectData(content),
            fetch: (client, id) => __awaiter(this, void 0, void 0, function* () { return MintEvent.fetch(client, id); }),
            new: (fields) => {
                return new MintEvent([], fields);
            },
            kind: "StructClassReified",
        };
    }
    static get r() {
        return MintEvent.reified();
    }
    static phantom() {
        return (0, reified_1.phantom)(MintEvent.reified());
    }
    static get p() {
        return MintEvent.phantom();
    }
    static get bcs() {
        return bcs_1.bcs.struct("MintEvent", {
            lending_market_id: bcs_1.bcs
                .bytes(32)
                .transform({
                input: (val) => (0, utils_1.fromHEX)(val),
                output: (val) => (0, utils_1.toHEX)(val),
            }),
            coin_type: structs_1.TypeName.bcs,
            reserve_id: bcs_1.bcs
                .bytes(32)
                .transform({
                input: (val) => (0, utils_1.fromHEX)(val),
                output: (val) => (0, utils_1.toHEX)(val),
            }),
            liquidity_amount: bcs_1.bcs.u64(),
            ctoken_amount: bcs_1.bcs.u64(),
        });
    }
    static fromFields(fields) {
        return MintEvent.reified().new({
            lendingMarketId: (0, reified_1.decodeFromFields)("address", fields.lending_market_id),
            coinType: (0, reified_1.decodeFromFields)(structs_1.TypeName.reified(), fields.coin_type),
            reserveId: (0, reified_1.decodeFromFields)("address", fields.reserve_id),
            liquidityAmount: (0, reified_1.decodeFromFields)("u64", fields.liquidity_amount),
            ctokenAmount: (0, reified_1.decodeFromFields)("u64", fields.ctoken_amount),
        });
    }
    static fromFieldsWithTypes(item) {
        if (!isMintEvent(item.type)) {
            throw new Error("not a MintEvent type");
        }
        return MintEvent.reified().new({
            lendingMarketId: (0, reified_1.decodeFromFieldsWithTypes)("address", item.fields.lending_market_id),
            coinType: (0, reified_1.decodeFromFieldsWithTypes)(structs_1.TypeName.reified(), item.fields.coin_type),
            reserveId: (0, reified_1.decodeFromFieldsWithTypes)("address", item.fields.reserve_id),
            liquidityAmount: (0, reified_1.decodeFromFieldsWithTypes)("u64", item.fields.liquidity_amount),
            ctokenAmount: (0, reified_1.decodeFromFieldsWithTypes)("u64", item.fields.ctoken_amount),
        });
    }
    static fromBcs(data) {
        return MintEvent.fromFields(MintEvent.bcs.parse(data));
    }
    toJSONField() {
        return {
            lendingMarketId: this.lendingMarketId,
            coinType: this.coinType.toJSONField(),
            reserveId: this.reserveId,
            liquidityAmount: this.liquidityAmount.toString(),
            ctokenAmount: this.ctokenAmount.toString(),
        };
    }
    toJSON() {
        return Object.assign({ $typeName: this.$typeName, $typeArgs: this.$typeArgs }, this.toJSONField());
    }
    static fromJSONField(field) {
        return MintEvent.reified().new({
            lendingMarketId: (0, reified_1.decodeFromJSONField)("address", field.lendingMarketId),
            coinType: (0, reified_1.decodeFromJSONField)(structs_1.TypeName.reified(), field.coinType),
            reserveId: (0, reified_1.decodeFromJSONField)("address", field.reserveId),
            liquidityAmount: (0, reified_1.decodeFromJSONField)("u64", field.liquidityAmount),
            ctokenAmount: (0, reified_1.decodeFromJSONField)("u64", field.ctokenAmount),
        });
    }
    static fromJSON(json) {
        if (json.$typeName !== MintEvent.$typeName) {
            throw new Error("not a WithTwoGenerics json object");
        }
        return MintEvent.fromJSONField(json);
    }
    static fromSuiParsedData(content) {
        if (content.dataType !== "moveObject") {
            throw new Error("not an object");
        }
        if (!isMintEvent(content.type)) {
            throw new Error(`object at ${content.fields.id} is not a MintEvent object`);
        }
        return MintEvent.fromFieldsWithTypes(content);
    }
    static fromSuiObjectData(data) {
        if (data.bcs) {
            if (data.bcs.dataType !== "moveObject" || !isMintEvent(data.bcs.type)) {
                throw new Error(`object at is not a MintEvent object`);
            }
            return MintEvent.fromBcs((0, utils_1.fromB64)(data.bcs.bcsBytes));
        }
        if (data.content) {
            return MintEvent.fromSuiParsedData(data.content);
        }
        throw new Error("Both `bcs` and `content` fields are missing from the data. Include `showBcs` or `showContent` in the request.");
    }
    static fetch(client, id) {
        return __awaiter(this, void 0, void 0, function* () {
            var _a, _b;
            const res = yield client.getObject({ id, options: { showBcs: true } });
            if (res.error) {
                throw new Error(`error fetching MintEvent object at id ${id}: ${res.error.code}`);
            }
            if (((_b = (_a = res.data) === null || _a === void 0 ? void 0 : _a.bcs) === null || _b === void 0 ? void 0 : _b.dataType) !== "moveObject" ||
                !isMintEvent(res.data.bcs.type)) {
                throw new Error(`object at id ${id} is not a MintEvent object`);
            }
            return MintEvent.fromSuiObjectData(res.data);
        });
    }
}
exports.MintEvent = MintEvent;
MintEvent.$typeName = `${index_1.PKG_V1}::lending_market::MintEvent`;
MintEvent.$numTypeParams = 0;
MintEvent.$isPhantom = [];
/* ============================== RedeemEvent =============================== */
function isRedeemEvent(type) {
    type = (0, util_1.compressSuiType)(type);
    return type === `${index_1.PKG_V1}::lending_market::RedeemEvent`;
}
class RedeemEvent {
    constructor(typeArgs, fields) {
        this.__StructClass = true;
        this.$typeName = RedeemEvent.$typeName;
        this.$isPhantom = RedeemEvent.$isPhantom;
        this.$fullTypeName = (0, util_1.composeSuiType)(RedeemEvent.$typeName, ...typeArgs);
        this.$typeArgs = typeArgs;
        this.lendingMarketId = fields.lendingMarketId;
        this.coinType = fields.coinType;
        this.reserveId = fields.reserveId;
        this.ctokenAmount = fields.ctokenAmount;
        this.liquidityAmount = fields.liquidityAmount;
    }
    static reified() {
        return {
            typeName: RedeemEvent.$typeName,
            fullTypeName: (0, util_1.composeSuiType)(RedeemEvent.$typeName, ...[]),
            typeArgs: [],
            isPhantom: RedeemEvent.$isPhantom,
            reifiedTypeArgs: [],
            fromFields: (fields) => RedeemEvent.fromFields(fields),
            fromFieldsWithTypes: (item) => RedeemEvent.fromFieldsWithTypes(item),
            fromBcs: (data) => RedeemEvent.fromBcs(data),
            bcs: RedeemEvent.bcs,
            fromJSONField: (field) => RedeemEvent.fromJSONField(field),
            fromJSON: (json) => RedeemEvent.fromJSON(json),
            fromSuiParsedData: (content) => RedeemEvent.fromSuiParsedData(content),
            fromSuiObjectData: (content) => RedeemEvent.fromSuiObjectData(content),
            fetch: (client, id) => __awaiter(this, void 0, void 0, function* () { return RedeemEvent.fetch(client, id); }),
            new: (fields) => {
                return new RedeemEvent([], fields);
            },
            kind: "StructClassReified",
        };
    }
    static get r() {
        return RedeemEvent.reified();
    }
    static phantom() {
        return (0, reified_1.phantom)(RedeemEvent.reified());
    }
    static get p() {
        return RedeemEvent.phantom();
    }
    static get bcs() {
        return bcs_1.bcs.struct("RedeemEvent", {
            lending_market_id: bcs_1.bcs
                .bytes(32)
                .transform({
                input: (val) => (0, utils_1.fromHEX)(val),
                output: (val) => (0, utils_1.toHEX)(val),
            }),
            coin_type: structs_1.TypeName.bcs,
            reserve_id: bcs_1.bcs
                .bytes(32)
                .transform({
                input: (val) => (0, utils_1.fromHEX)(val),
                output: (val) => (0, utils_1.toHEX)(val),
            }),
            ctoken_amount: bcs_1.bcs.u64(),
            liquidity_amount: bcs_1.bcs.u64(),
        });
    }
    static fromFields(fields) {
        return RedeemEvent.reified().new({
            lendingMarketId: (0, reified_1.decodeFromFields)("address", fields.lending_market_id),
            coinType: (0, reified_1.decodeFromFields)(structs_1.TypeName.reified(), fields.coin_type),
            reserveId: (0, reified_1.decodeFromFields)("address", fields.reserve_id),
            ctokenAmount: (0, reified_1.decodeFromFields)("u64", fields.ctoken_amount),
            liquidityAmount: (0, reified_1.decodeFromFields)("u64", fields.liquidity_amount),
        });
    }
    static fromFieldsWithTypes(item) {
        if (!isRedeemEvent(item.type)) {
            throw new Error("not a RedeemEvent type");
        }
        return RedeemEvent.reified().new({
            lendingMarketId: (0, reified_1.decodeFromFieldsWithTypes)("address", item.fields.lending_market_id),
            coinType: (0, reified_1.decodeFromFieldsWithTypes)(structs_1.TypeName.reified(), item.fields.coin_type),
            reserveId: (0, reified_1.decodeFromFieldsWithTypes)("address", item.fields.reserve_id),
            ctokenAmount: (0, reified_1.decodeFromFieldsWithTypes)("u64", item.fields.ctoken_amount),
            liquidityAmount: (0, reified_1.decodeFromFieldsWithTypes)("u64", item.fields.liquidity_amount),
        });
    }
    static fromBcs(data) {
        return RedeemEvent.fromFields(RedeemEvent.bcs.parse(data));
    }
    toJSONField() {
        return {
            lendingMarketId: this.lendingMarketId,
            coinType: this.coinType.toJSONField(),
            reserveId: this.reserveId,
            ctokenAmount: this.ctokenAmount.toString(),
            liquidityAmount: this.liquidityAmount.toString(),
        };
    }
    toJSON() {
        return Object.assign({ $typeName: this.$typeName, $typeArgs: this.$typeArgs }, this.toJSONField());
    }
    static fromJSONField(field) {
        return RedeemEvent.reified().new({
            lendingMarketId: (0, reified_1.decodeFromJSONField)("address", field.lendingMarketId),
            coinType: (0, reified_1.decodeFromJSONField)(structs_1.TypeName.reified(), field.coinType),
            reserveId: (0, reified_1.decodeFromJSONField)("address", field.reserveId),
            ctokenAmount: (0, reified_1.decodeFromJSONField)("u64", field.ctokenAmount),
            liquidityAmount: (0, reified_1.decodeFromJSONField)("u64", field.liquidityAmount),
        });
    }
    static fromJSON(json) {
        if (json.$typeName !== RedeemEvent.$typeName) {
            throw new Error("not a WithTwoGenerics json object");
        }
        return RedeemEvent.fromJSONField(json);
    }
    static fromSuiParsedData(content) {
        if (content.dataType !== "moveObject") {
            throw new Error("not an object");
        }
        if (!isRedeemEvent(content.type)) {
            throw new Error(`object at ${content.fields.id} is not a RedeemEvent object`);
        }
        return RedeemEvent.fromFieldsWithTypes(content);
    }
    static fromSuiObjectData(data) {
        if (data.bcs) {
            if (data.bcs.dataType !== "moveObject" || !isRedeemEvent(data.bcs.type)) {
                throw new Error(`object at is not a RedeemEvent object`);
            }
            return RedeemEvent.fromBcs((0, utils_1.fromB64)(data.bcs.bcsBytes));
        }
        if (data.content) {
            return RedeemEvent.fromSuiParsedData(data.content);
        }
        throw new Error("Both `bcs` and `content` fields are missing from the data. Include `showBcs` or `showContent` in the request.");
    }
    static fetch(client, id) {
        return __awaiter(this, void 0, void 0, function* () {
            var _a, _b;
            const res = yield client.getObject({ id, options: { showBcs: true } });
            if (res.error) {
                throw new Error(`error fetching RedeemEvent object at id ${id}: ${res.error.code}`);
            }
            if (((_b = (_a = res.data) === null || _a === void 0 ? void 0 : _a.bcs) === null || _b === void 0 ? void 0 : _b.dataType) !== "moveObject" ||
                !isRedeemEvent(res.data.bcs.type)) {
                throw new Error(`object at id ${id} is not a RedeemEvent object`);
            }
            return RedeemEvent.fromSuiObjectData(res.data);
        });
    }
}
exports.RedeemEvent = RedeemEvent;
RedeemEvent.$typeName = `${index_1.PKG_V1}::lending_market::RedeemEvent`;
RedeemEvent.$numTypeParams = 0;
RedeemEvent.$isPhantom = [];
/* ============================== BorrowEvent =============================== */
function isBorrowEvent(type) {
    type = (0, util_1.compressSuiType)(type);
    return type === `${index_1.PKG_V1}::lending_market::BorrowEvent`;
}
class BorrowEvent {
    constructor(typeArgs, fields) {
        this.__StructClass = true;
        this.$typeName = BorrowEvent.$typeName;
        this.$isPhantom = BorrowEvent.$isPhantom;
        this.$fullTypeName = (0, util_1.composeSuiType)(BorrowEvent.$typeName, ...typeArgs);
        this.$typeArgs = typeArgs;
        this.lendingMarketId = fields.lendingMarketId;
        this.coinType = fields.coinType;
        this.reserveId = fields.reserveId;
        this.obligationId = fields.obligationId;
        this.liquidityAmount = fields.liquidityAmount;
        this.originationFeeAmount = fields.originationFeeAmount;
    }
    static reified() {
        return {
            typeName: BorrowEvent.$typeName,
            fullTypeName: (0, util_1.composeSuiType)(BorrowEvent.$typeName, ...[]),
            typeArgs: [],
            isPhantom: BorrowEvent.$isPhantom,
            reifiedTypeArgs: [],
            fromFields: (fields) => BorrowEvent.fromFields(fields),
            fromFieldsWithTypes: (item) => BorrowEvent.fromFieldsWithTypes(item),
            fromBcs: (data) => BorrowEvent.fromBcs(data),
            bcs: BorrowEvent.bcs,
            fromJSONField: (field) => BorrowEvent.fromJSONField(field),
            fromJSON: (json) => BorrowEvent.fromJSON(json),
            fromSuiParsedData: (content) => BorrowEvent.fromSuiParsedData(content),
            fromSuiObjectData: (content) => BorrowEvent.fromSuiObjectData(content),
            fetch: (client, id) => __awaiter(this, void 0, void 0, function* () { return BorrowEvent.fetch(client, id); }),
            new: (fields) => {
                return new BorrowEvent([], fields);
            },
            kind: "StructClassReified",
        };
    }
    static get r() {
        return BorrowEvent.reified();
    }
    static phantom() {
        return (0, reified_1.phantom)(BorrowEvent.reified());
    }
    static get p() {
        return BorrowEvent.phantom();
    }
    static get bcs() {
        return bcs_1.bcs.struct("BorrowEvent", {
            lending_market_id: bcs_1.bcs
                .bytes(32)
                .transform({
                input: (val) => (0, utils_1.fromHEX)(val),
                output: (val) => (0, utils_1.toHEX)(val),
            }),
            coin_type: structs_1.TypeName.bcs,
            reserve_id: bcs_1.bcs
                .bytes(32)
                .transform({
                input: (val) => (0, utils_1.fromHEX)(val),
                output: (val) => (0, utils_1.toHEX)(val),
            }),
            obligation_id: bcs_1.bcs
                .bytes(32)
                .transform({
                input: (val) => (0, utils_1.fromHEX)(val),
                output: (val) => (0, utils_1.toHEX)(val),
            }),
            liquidity_amount: bcs_1.bcs.u64(),
            origination_fee_amount: bcs_1.bcs.u64(),
        });
    }
    static fromFields(fields) {
        return BorrowEvent.reified().new({
            lendingMarketId: (0, reified_1.decodeFromFields)("address", fields.lending_market_id),
            coinType: (0, reified_1.decodeFromFields)(structs_1.TypeName.reified(), fields.coin_type),
            reserveId: (0, reified_1.decodeFromFields)("address", fields.reserve_id),
            obligationId: (0, reified_1.decodeFromFields)("address", fields.obligation_id),
            liquidityAmount: (0, reified_1.decodeFromFields)("u64", fields.liquidity_amount),
            originationFeeAmount: (0, reified_1.decodeFromFields)("u64", fields.origination_fee_amount),
        });
    }
    static fromFieldsWithTypes(item) {
        if (!isBorrowEvent(item.type)) {
            throw new Error("not a BorrowEvent type");
        }
        return BorrowEvent.reified().new({
            lendingMarketId: (0, reified_1.decodeFromFieldsWithTypes)("address", item.fields.lending_market_id),
            coinType: (0, reified_1.decodeFromFieldsWithTypes)(structs_1.TypeName.reified(), item.fields.coin_type),
            reserveId: (0, reified_1.decodeFromFieldsWithTypes)("address", item.fields.reserve_id),
            obligationId: (0, reified_1.decodeFromFieldsWithTypes)("address", item.fields.obligation_id),
            liquidityAmount: (0, reified_1.decodeFromFieldsWithTypes)("u64", item.fields.liquidity_amount),
            originationFeeAmount: (0, reified_1.decodeFromFieldsWithTypes)("u64", item.fields.origination_fee_amount),
        });
    }
    static fromBcs(data) {
        return BorrowEvent.fromFields(BorrowEvent.bcs.parse(data));
    }
    toJSONField() {
        return {
            lendingMarketId: this.lendingMarketId,
            coinType: this.coinType.toJSONField(),
            reserveId: this.reserveId,
            obligationId: this.obligationId,
            liquidityAmount: this.liquidityAmount.toString(),
            originationFeeAmount: this.originationFeeAmount.toString(),
        };
    }
    toJSON() {
        return Object.assign({ $typeName: this.$typeName, $typeArgs: this.$typeArgs }, this.toJSONField());
    }
    static fromJSONField(field) {
        return BorrowEvent.reified().new({
            lendingMarketId: (0, reified_1.decodeFromJSONField)("address", field.lendingMarketId),
            coinType: (0, reified_1.decodeFromJSONField)(structs_1.TypeName.reified(), field.coinType),
            reserveId: (0, reified_1.decodeFromJSONField)("address", field.reserveId),
            obligationId: (0, reified_1.decodeFromJSONField)("address", field.obligationId),
            liquidityAmount: (0, reified_1.decodeFromJSONField)("u64", field.liquidityAmount),
            originationFeeAmount: (0, reified_1.decodeFromJSONField)("u64", field.originationFeeAmount),
        });
    }
    static fromJSON(json) {
        if (json.$typeName !== BorrowEvent.$typeName) {
            throw new Error("not a WithTwoGenerics json object");
        }
        return BorrowEvent.fromJSONField(json);
    }
    static fromSuiParsedData(content) {
        if (content.dataType !== "moveObject") {
            throw new Error("not an object");
        }
        if (!isBorrowEvent(content.type)) {
            throw new Error(`object at ${content.fields.id} is not a BorrowEvent object`);
        }
        return BorrowEvent.fromFieldsWithTypes(content);
    }
    static fromSuiObjectData(data) {
        if (data.bcs) {
            if (data.bcs.dataType !== "moveObject" || !isBorrowEvent(data.bcs.type)) {
                throw new Error(`object at is not a BorrowEvent object`);
            }
            return BorrowEvent.fromBcs((0, utils_1.fromB64)(data.bcs.bcsBytes));
        }
        if (data.content) {
            return BorrowEvent.fromSuiParsedData(data.content);
        }
        throw new Error("Both `bcs` and `content` fields are missing from the data. Include `showBcs` or `showContent` in the request.");
    }
    static fetch(client, id) {
        return __awaiter(this, void 0, void 0, function* () {
            var _a, _b;
            const res = yield client.getObject({ id, options: { showBcs: true } });
            if (res.error) {
                throw new Error(`error fetching BorrowEvent object at id ${id}: ${res.error.code}`);
            }
            if (((_b = (_a = res.data) === null || _a === void 0 ? void 0 : _a.bcs) === null || _b === void 0 ? void 0 : _b.dataType) !== "moveObject" ||
                !isBorrowEvent(res.data.bcs.type)) {
                throw new Error(`object at id ${id} is not a BorrowEvent object`);
            }
            return BorrowEvent.fromSuiObjectData(res.data);
        });
    }
}
exports.BorrowEvent = BorrowEvent;
BorrowEvent.$typeName = `${index_1.PKG_V1}::lending_market::BorrowEvent`;
BorrowEvent.$numTypeParams = 0;
BorrowEvent.$isPhantom = [];
/* ============================== ClaimRewardEvent =============================== */
function isClaimRewardEvent(type) {
    type = (0, util_1.compressSuiType)(type);
    return type === `${index_1.PKG_V1}::lending_market::ClaimRewardEvent`;
}
class ClaimRewardEvent {
    constructor(typeArgs, fields) {
        this.__StructClass = true;
        this.$typeName = ClaimRewardEvent.$typeName;
        this.$isPhantom = ClaimRewardEvent.$isPhantom;
        this.$fullTypeName = (0, util_1.composeSuiType)(ClaimRewardEvent.$typeName, ...typeArgs);
        this.$typeArgs = typeArgs;
        this.lendingMarketId = fields.lendingMarketId;
        this.reserveId = fields.reserveId;
        this.obligationId = fields.obligationId;
        this.isDepositReward = fields.isDepositReward;
        this.poolRewardId = fields.poolRewardId;
        this.coinType = fields.coinType;
        this.liquidityAmount = fields.liquidityAmount;
    }
    static reified() {
        return {
            typeName: ClaimRewardEvent.$typeName,
            fullTypeName: (0, util_1.composeSuiType)(ClaimRewardEvent.$typeName, ...[]),
            typeArgs: [],
            isPhantom: ClaimRewardEvent.$isPhantom,
            reifiedTypeArgs: [],
            fromFields: (fields) => ClaimRewardEvent.fromFields(fields),
            fromFieldsWithTypes: (item) => ClaimRewardEvent.fromFieldsWithTypes(item),
            fromBcs: (data) => ClaimRewardEvent.fromBcs(data),
            bcs: ClaimRewardEvent.bcs,
            fromJSONField: (field) => ClaimRewardEvent.fromJSONField(field),
            fromJSON: (json) => ClaimRewardEvent.fromJSON(json),
            fromSuiParsedData: (content) => ClaimRewardEvent.fromSuiParsedData(content),
            fromSuiObjectData: (content) => ClaimRewardEvent.fromSuiObjectData(content),
            fetch: (client, id) => __awaiter(this, void 0, void 0, function* () { return ClaimRewardEvent.fetch(client, id); }),
            new: (fields) => {
                return new ClaimRewardEvent([], fields);
            },
            kind: "StructClassReified",
        };
    }
    static get r() {
        return ClaimRewardEvent.reified();
    }
    static phantom() {
        return (0, reified_1.phantom)(ClaimRewardEvent.reified());
    }
    static get p() {
        return ClaimRewardEvent.phantom();
    }
    static get bcs() {
        return bcs_1.bcs.struct("ClaimRewardEvent", {
            lending_market_id: bcs_1.bcs
                .bytes(32)
                .transform({
                input: (val) => (0, utils_1.fromHEX)(val),
                output: (val) => (0, utils_1.toHEX)(val),
            }),
            reserve_id: bcs_1.bcs
                .bytes(32)
                .transform({
                input: (val) => (0, utils_1.fromHEX)(val),
                output: (val) => (0, utils_1.toHEX)(val),
            }),
            obligation_id: bcs_1.bcs
                .bytes(32)
                .transform({
                input: (val) => (0, utils_1.fromHEX)(val),
                output: (val) => (0, utils_1.toHEX)(val),
            }),
            is_deposit_reward: bcs_1.bcs.bool(),
            pool_reward_id: bcs_1.bcs
                .bytes(32)
                .transform({
                input: (val) => (0, utils_1.fromHEX)(val),
                output: (val) => (0, utils_1.toHEX)(val),
            }),
            coin_type: structs_1.TypeName.bcs,
            liquidity_amount: bcs_1.bcs.u64(),
        });
    }
    static fromFields(fields) {
        return ClaimRewardEvent.reified().new({
            lendingMarketId: (0, reified_1.decodeFromFields)("address", fields.lending_market_id),
            reserveId: (0, reified_1.decodeFromFields)("address", fields.reserve_id),
            obligationId: (0, reified_1.decodeFromFields)("address", fields.obligation_id),
            isDepositReward: (0, reified_1.decodeFromFields)("bool", fields.is_deposit_reward),
            poolRewardId: (0, reified_1.decodeFromFields)("address", fields.pool_reward_id),
            coinType: (0, reified_1.decodeFromFields)(structs_1.TypeName.reified(), fields.coin_type),
            liquidityAmount: (0, reified_1.decodeFromFields)("u64", fields.liquidity_amount),
        });
    }
    static fromFieldsWithTypes(item) {
        if (!isClaimRewardEvent(item.type)) {
            throw new Error("not a ClaimRewardEvent type");
        }
        return ClaimRewardEvent.reified().new({
            lendingMarketId: (0, reified_1.decodeFromFieldsWithTypes)("address", item.fields.lending_market_id),
            reserveId: (0, reified_1.decodeFromFieldsWithTypes)("address", item.fields.reserve_id),
            obligationId: (0, reified_1.decodeFromFieldsWithTypes)("address", item.fields.obligation_id),
            isDepositReward: (0, reified_1.decodeFromFieldsWithTypes)("bool", item.fields.is_deposit_reward),
            poolRewardId: (0, reified_1.decodeFromFieldsWithTypes)("address", item.fields.pool_reward_id),
            coinType: (0, reified_1.decodeFromFieldsWithTypes)(structs_1.TypeName.reified(), item.fields.coin_type),
            liquidityAmount: (0, reified_1.decodeFromFieldsWithTypes)("u64", item.fields.liquidity_amount),
        });
    }
    static fromBcs(data) {
        return ClaimRewardEvent.fromFields(ClaimRewardEvent.bcs.parse(data));
    }
    toJSONField() {
        return {
            lendingMarketId: this.lendingMarketId,
            reserveId: this.reserveId,
            obligationId: this.obligationId,
            isDepositReward: this.isDepositReward,
            poolRewardId: this.poolRewardId,
            coinType: this.coinType.toJSONField(),
            liquidityAmount: this.liquidityAmount.toString(),
        };
    }
    toJSON() {
        return Object.assign({ $typeName: this.$typeName, $typeArgs: this.$typeArgs }, this.toJSONField());
    }
    static fromJSONField(field) {
        return ClaimRewardEvent.reified().new({
            lendingMarketId: (0, reified_1.decodeFromJSONField)("address", field.lendingMarketId),
            reserveId: (0, reified_1.decodeFromJSONField)("address", field.reserveId),
            obligationId: (0, reified_1.decodeFromJSONField)("address", field.obligationId),
            isDepositReward: (0, reified_1.decodeFromJSONField)("bool", field.isDepositReward),
            poolRewardId: (0, reified_1.decodeFromJSONField)("address", field.poolRewardId),
            coinType: (0, reified_1.decodeFromJSONField)(structs_1.TypeName.reified(), field.coinType),
            liquidityAmount: (0, reified_1.decodeFromJSONField)("u64", field.liquidityAmount),
        });
    }
    static fromJSON(json) {
        if (json.$typeName !== ClaimRewardEvent.$typeName) {
            throw new Error("not a WithTwoGenerics json object");
        }
        return ClaimRewardEvent.fromJSONField(json);
    }
    static fromSuiParsedData(content) {
        if (content.dataType !== "moveObject") {
            throw new Error("not an object");
        }
        if (!isClaimRewardEvent(content.type)) {
            throw new Error(`object at ${content.fields.id} is not a ClaimRewardEvent object`);
        }
        return ClaimRewardEvent.fromFieldsWithTypes(content);
    }
    static fromSuiObjectData(data) {
        if (data.bcs) {
            if (data.bcs.dataType !== "moveObject" ||
                !isClaimRewardEvent(data.bcs.type)) {
                throw new Error(`object at is not a ClaimRewardEvent object`);
            }
            return ClaimRewardEvent.fromBcs((0, utils_1.fromB64)(data.bcs.bcsBytes));
        }
        if (data.content) {
            return ClaimRewardEvent.fromSuiParsedData(data.content);
        }
        throw new Error("Both `bcs` and `content` fields are missing from the data. Include `showBcs` or `showContent` in the request.");
    }
    static fetch(client, id) {
        return __awaiter(this, void 0, void 0, function* () {
            var _a, _b;
            const res = yield client.getObject({ id, options: { showBcs: true } });
            if (res.error) {
                throw new Error(`error fetching ClaimRewardEvent object at id ${id}: ${res.error.code}`);
            }
            if (((_b = (_a = res.data) === null || _a === void 0 ? void 0 : _a.bcs) === null || _b === void 0 ? void 0 : _b.dataType) !== "moveObject" ||
                !isClaimRewardEvent(res.data.bcs.type)) {
                throw new Error(`object at id ${id} is not a ClaimRewardEvent object`);
            }
            return ClaimRewardEvent.fromSuiObjectData(res.data);
        });
    }
}
exports.ClaimRewardEvent = ClaimRewardEvent;
ClaimRewardEvent.$typeName = `${index_1.PKG_V1}::lending_market::ClaimRewardEvent`;
ClaimRewardEvent.$numTypeParams = 0;
ClaimRewardEvent.$isPhantom = [];
/* ============================== DepositEvent =============================== */
function isDepositEvent(type) {
    type = (0, util_1.compressSuiType)(type);
    return type === `${index_1.PKG_V1}::lending_market::DepositEvent`;
}
class DepositEvent {
    constructor(typeArgs, fields) {
        this.__StructClass = true;
        this.$typeName = DepositEvent.$typeName;
        this.$isPhantom = DepositEvent.$isPhantom;
        this.$fullTypeName = (0, util_1.composeSuiType)(DepositEvent.$typeName, ...typeArgs);
        this.$typeArgs = typeArgs;
        this.lendingMarketId = fields.lendingMarketId;
        this.coinType = fields.coinType;
        this.reserveId = fields.reserveId;
        this.obligationId = fields.obligationId;
        this.ctokenAmount = fields.ctokenAmount;
    }
    static reified() {
        return {
            typeName: DepositEvent.$typeName,
            fullTypeName: (0, util_1.composeSuiType)(DepositEvent.$typeName, ...[]),
            typeArgs: [],
            isPhantom: DepositEvent.$isPhantom,
            reifiedTypeArgs: [],
            fromFields: (fields) => DepositEvent.fromFields(fields),
            fromFieldsWithTypes: (item) => DepositEvent.fromFieldsWithTypes(item),
            fromBcs: (data) => DepositEvent.fromBcs(data),
            bcs: DepositEvent.bcs,
            fromJSONField: (field) => DepositEvent.fromJSONField(field),
            fromJSON: (json) => DepositEvent.fromJSON(json),
            fromSuiParsedData: (content) => DepositEvent.fromSuiParsedData(content),
            fromSuiObjectData: (content) => DepositEvent.fromSuiObjectData(content),
            fetch: (client, id) => __awaiter(this, void 0, void 0, function* () { return DepositEvent.fetch(client, id); }),
            new: (fields) => {
                return new DepositEvent([], fields);
            },
            kind: "StructClassReified",
        };
    }
    static get r() {
        return DepositEvent.reified();
    }
    static phantom() {
        return (0, reified_1.phantom)(DepositEvent.reified());
    }
    static get p() {
        return DepositEvent.phantom();
    }
    static get bcs() {
        return bcs_1.bcs.struct("DepositEvent", {
            lending_market_id: bcs_1.bcs
                .bytes(32)
                .transform({
                input: (val) => (0, utils_1.fromHEX)(val),
                output: (val) => (0, utils_1.toHEX)(val),
            }),
            coin_type: structs_1.TypeName.bcs,
            reserve_id: bcs_1.bcs
                .bytes(32)
                .transform({
                input: (val) => (0, utils_1.fromHEX)(val),
                output: (val) => (0, utils_1.toHEX)(val),
            }),
            obligation_id: bcs_1.bcs
                .bytes(32)
                .transform({
                input: (val) => (0, utils_1.fromHEX)(val),
                output: (val) => (0, utils_1.toHEX)(val),
            }),
            ctoken_amount: bcs_1.bcs.u64(),
        });
    }
    static fromFields(fields) {
        return DepositEvent.reified().new({
            lendingMarketId: (0, reified_1.decodeFromFields)("address", fields.lending_market_id),
            coinType: (0, reified_1.decodeFromFields)(structs_1.TypeName.reified(), fields.coin_type),
            reserveId: (0, reified_1.decodeFromFields)("address", fields.reserve_id),
            obligationId: (0, reified_1.decodeFromFields)("address", fields.obligation_id),
            ctokenAmount: (0, reified_1.decodeFromFields)("u64", fields.ctoken_amount),
        });
    }
    static fromFieldsWithTypes(item) {
        if (!isDepositEvent(item.type)) {
            throw new Error("not a DepositEvent type");
        }
        return DepositEvent.reified().new({
            lendingMarketId: (0, reified_1.decodeFromFieldsWithTypes)("address", item.fields.lending_market_id),
            coinType: (0, reified_1.decodeFromFieldsWithTypes)(structs_1.TypeName.reified(), item.fields.coin_type),
            reserveId: (0, reified_1.decodeFromFieldsWithTypes)("address", item.fields.reserve_id),
            obligationId: (0, reified_1.decodeFromFieldsWithTypes)("address", item.fields.obligation_id),
            ctokenAmount: (0, reified_1.decodeFromFieldsWithTypes)("u64", item.fields.ctoken_amount),
        });
    }
    static fromBcs(data) {
        return DepositEvent.fromFields(DepositEvent.bcs.parse(data));
    }
    toJSONField() {
        return {
            lendingMarketId: this.lendingMarketId,
            coinType: this.coinType.toJSONField(),
            reserveId: this.reserveId,
            obligationId: this.obligationId,
            ctokenAmount: this.ctokenAmount.toString(),
        };
    }
    toJSON() {
        return Object.assign({ $typeName: this.$typeName, $typeArgs: this.$typeArgs }, this.toJSONField());
    }
    static fromJSONField(field) {
        return DepositEvent.reified().new({
            lendingMarketId: (0, reified_1.decodeFromJSONField)("address", field.lendingMarketId),
            coinType: (0, reified_1.decodeFromJSONField)(structs_1.TypeName.reified(), field.coinType),
            reserveId: (0, reified_1.decodeFromJSONField)("address", field.reserveId),
            obligationId: (0, reified_1.decodeFromJSONField)("address", field.obligationId),
            ctokenAmount: (0, reified_1.decodeFromJSONField)("u64", field.ctokenAmount),
        });
    }
    static fromJSON(json) {
        if (json.$typeName !== DepositEvent.$typeName) {
            throw new Error("not a WithTwoGenerics json object");
        }
        return DepositEvent.fromJSONField(json);
    }
    static fromSuiParsedData(content) {
        if (content.dataType !== "moveObject") {
            throw new Error("not an object");
        }
        if (!isDepositEvent(content.type)) {
            throw new Error(`object at ${content.fields.id} is not a DepositEvent object`);
        }
        return DepositEvent.fromFieldsWithTypes(content);
    }
    static fromSuiObjectData(data) {
        if (data.bcs) {
            if (data.bcs.dataType !== "moveObject" ||
                !isDepositEvent(data.bcs.type)) {
                throw new Error(`object at is not a DepositEvent object`);
            }
            return DepositEvent.fromBcs((0, utils_1.fromB64)(data.bcs.bcsBytes));
        }
        if (data.content) {
            return DepositEvent.fromSuiParsedData(data.content);
        }
        throw new Error("Both `bcs` and `content` fields are missing from the data. Include `showBcs` or `showContent` in the request.");
    }
    static fetch(client, id) {
        return __awaiter(this, void 0, void 0, function* () {
            var _a, _b;
            const res = yield client.getObject({ id, options: { showBcs: true } });
            if (res.error) {
                throw new Error(`error fetching DepositEvent object at id ${id}: ${res.error.code}`);
            }
            if (((_b = (_a = res.data) === null || _a === void 0 ? void 0 : _a.bcs) === null || _b === void 0 ? void 0 : _b.dataType) !== "moveObject" ||
                !isDepositEvent(res.data.bcs.type)) {
                throw new Error(`object at id ${id} is not a DepositEvent object`);
            }
            return DepositEvent.fromSuiObjectData(res.data);
        });
    }
}
exports.DepositEvent = DepositEvent;
DepositEvent.$typeName = `${index_1.PKG_V1}::lending_market::DepositEvent`;
DepositEvent.$numTypeParams = 0;
DepositEvent.$isPhantom = [];
/* ============================== FeeReceivers =============================== */
function isFeeReceivers(type) {
    type = (0, util_1.compressSuiType)(type);
    return type === `${index_1.PKG_V10}::lending_market::FeeReceivers`;
}
class FeeReceivers {
    constructor(typeArgs, fields) {
        this.__StructClass = true;
        this.$typeName = FeeReceivers.$typeName;
        this.$isPhantom = FeeReceivers.$isPhantom;
        this.$fullTypeName = (0, util_1.composeSuiType)(FeeReceivers.$typeName, ...typeArgs);
        this.$typeArgs = typeArgs;
        this.receivers = fields.receivers;
        this.weights = fields.weights;
        this.totalWeight = fields.totalWeight;
    }
    static reified() {
        return {
            typeName: FeeReceivers.$typeName,
            fullTypeName: (0, util_1.composeSuiType)(FeeReceivers.$typeName, ...[]),
            typeArgs: [],
            isPhantom: FeeReceivers.$isPhantom,
            reifiedTypeArgs: [],
            fromFields: (fields) => FeeReceivers.fromFields(fields),
            fromFieldsWithTypes: (item) => FeeReceivers.fromFieldsWithTypes(item),
            fromBcs: (data) => FeeReceivers.fromBcs(data),
            bcs: FeeReceivers.bcs,
            fromJSONField: (field) => FeeReceivers.fromJSONField(field),
            fromJSON: (json) => FeeReceivers.fromJSON(json),
            fromSuiParsedData: (content) => FeeReceivers.fromSuiParsedData(content),
            fromSuiObjectData: (content) => FeeReceivers.fromSuiObjectData(content),
            fetch: (client, id) => __awaiter(this, void 0, void 0, function* () { return FeeReceivers.fetch(client, id); }),
            new: (fields) => {
                return new FeeReceivers([], fields);
            },
            kind: "StructClassReified",
        };
    }
    static get r() {
        return FeeReceivers.reified();
    }
    static phantom() {
        return (0, reified_1.phantom)(FeeReceivers.reified());
    }
    static get p() {
        return FeeReceivers.phantom();
    }
    static get bcs() {
        return bcs_1.bcs.struct("FeeReceivers", {
            receivers: bcs_1.bcs.vector(bcs_1.bcs
                .bytes(32)
                .transform({
                input: (val) => (0, utils_1.fromHEX)(val),
                output: (val) => (0, utils_1.toHEX)(val),
            })),
            weights: bcs_1.bcs.vector(bcs_1.bcs.u64()),
            total_weight: bcs_1.bcs.u64(),
        });
    }
    static fromFields(fields) {
        return FeeReceivers.reified().new({
            receivers: (0, reified_1.decodeFromFields)(reified.vector("address"), fields.receivers),
            weights: (0, reified_1.decodeFromFields)(reified.vector("u64"), fields.weights),
            totalWeight: (0, reified_1.decodeFromFields)("u64", fields.total_weight),
        });
    }
    static fromFieldsWithTypes(item) {
        if (!isFeeReceivers(item.type)) {
            throw new Error("not a FeeReceivers type");
        }
        return FeeReceivers.reified().new({
            receivers: (0, reified_1.decodeFromFieldsWithTypes)(reified.vector("address"), item.fields.receivers),
            weights: (0, reified_1.decodeFromFieldsWithTypes)(reified.vector("u64"), item.fields.weights),
            totalWeight: (0, reified_1.decodeFromFieldsWithTypes)("u64", item.fields.total_weight),
        });
    }
    static fromBcs(data) {
        return FeeReceivers.fromFields(FeeReceivers.bcs.parse(data));
    }
    toJSONField() {
        return {
            receivers: (0, reified_1.fieldToJSON)(`vector<address>`, this.receivers),
            weights: (0, reified_1.fieldToJSON)(`vector<u64>`, this.weights),
            totalWeight: this.totalWeight.toString(),
        };
    }
    toJSON() {
        return Object.assign({ $typeName: this.$typeName, $typeArgs: this.$typeArgs }, this.toJSONField());
    }
    static fromJSONField(field) {
        return FeeReceivers.reified().new({
            receivers: (0, reified_1.decodeFromJSONField)(reified.vector("address"), field.receivers),
            weights: (0, reified_1.decodeFromJSONField)(reified.vector("u64"), field.weights),
            totalWeight: (0, reified_1.decodeFromJSONField)("u64", field.totalWeight),
        });
    }
    static fromJSON(json) {
        if (json.$typeName !== FeeReceivers.$typeName) {
            throw new Error("not a WithTwoGenerics json object");
        }
        return FeeReceivers.fromJSONField(json);
    }
    static fromSuiParsedData(content) {
        if (content.dataType !== "moveObject") {
            throw new Error("not an object");
        }
        if (!isFeeReceivers(content.type)) {
            throw new Error(`object at ${content.fields.id} is not a FeeReceivers object`);
        }
        return FeeReceivers.fromFieldsWithTypes(content);
    }
    static fromSuiObjectData(data) {
        if (data.bcs) {
            if (data.bcs.dataType !== "moveObject" ||
                !isFeeReceivers(data.bcs.type)) {
                throw new Error(`object at is not a FeeReceivers object`);
            }
            return FeeReceivers.fromBcs((0, utils_1.fromB64)(data.bcs.bcsBytes));
        }
        if (data.content) {
            return FeeReceivers.fromSuiParsedData(data.content);
        }
        throw new Error("Both `bcs` and `content` fields are missing from the data. Include `showBcs` or `showContent` in the request.");
    }
    static fetch(client, id) {
        return __awaiter(this, void 0, void 0, function* () {
            var _a, _b;
            const res = yield client.getObject({ id, options: { showBcs: true } });
            if (res.error) {
                throw new Error(`error fetching FeeReceivers object at id ${id}: ${res.error.code}`);
            }
            if (((_b = (_a = res.data) === null || _a === void 0 ? void 0 : _a.bcs) === null || _b === void 0 ? void 0 : _b.dataType) !== "moveObject" ||
                !isFeeReceivers(res.data.bcs.type)) {
                throw new Error(`object at id ${id} is not a FeeReceivers object`);
            }
            return FeeReceivers.fromSuiObjectData(res.data);
        });
    }
}
exports.FeeReceivers = FeeReceivers;
FeeReceivers.$typeName = `${index_1.PKG_V10}::lending_market::FeeReceivers`;
FeeReceivers.$numTypeParams = 0;
FeeReceivers.$isPhantom = [];
/* ============================== FeeReceiversKey =============================== */
function isFeeReceiversKey(type) {
    type = (0, util_1.compressSuiType)(type);
    return type === `${index_1.PKG_V10}::lending_market::FeeReceiversKey`;
}
class FeeReceiversKey {
    constructor(typeArgs, fields) {
        this.__StructClass = true;
        this.$typeName = FeeReceiversKey.$typeName;
        this.$isPhantom = FeeReceiversKey.$isPhantom;
        this.$fullTypeName = (0, util_1.composeSuiType)(FeeReceiversKey.$typeName, ...typeArgs);
        this.$typeArgs = typeArgs;
        this.dummyField = fields.dummyField;
    }
    static reified() {
        return {
            typeName: FeeReceiversKey.$typeName,
            fullTypeName: (0, util_1.composeSuiType)(FeeReceiversKey.$typeName, ...[]),
            typeArgs: [],
            isPhantom: FeeReceiversKey.$isPhantom,
            reifiedTypeArgs: [],
            fromFields: (fields) => FeeReceiversKey.fromFields(fields),
            fromFieldsWithTypes: (item) => FeeReceiversKey.fromFieldsWithTypes(item),
            fromBcs: (data) => FeeReceiversKey.fromBcs(data),
            bcs: FeeReceiversKey.bcs,
            fromJSONField: (field) => FeeReceiversKey.fromJSONField(field),
            fromJSON: (json) => FeeReceiversKey.fromJSON(json),
            fromSuiParsedData: (content) => FeeReceiversKey.fromSuiParsedData(content),
            fromSuiObjectData: (content) => FeeReceiversKey.fromSuiObjectData(content),
            fetch: (client, id) => __awaiter(this, void 0, void 0, function* () { return FeeReceiversKey.fetch(client, id); }),
            new: (fields) => {
                return new FeeReceiversKey([], fields);
            },
            kind: "StructClassReified",
        };
    }
    static get r() {
        return FeeReceiversKey.reified();
    }
    static phantom() {
        return (0, reified_1.phantom)(FeeReceiversKey.reified());
    }
    static get p() {
        return FeeReceiversKey.phantom();
    }
    static get bcs() {
        return bcs_1.bcs.struct("FeeReceiversKey", {
            dummy_field: bcs_1.bcs.bool(),
        });
    }
    static fromFields(fields) {
        return FeeReceiversKey.reified().new({
            dummyField: (0, reified_1.decodeFromFields)("bool", fields.dummy_field),
        });
    }
    static fromFieldsWithTypes(item) {
        if (!isFeeReceiversKey(item.type)) {
            throw new Error("not a FeeReceiversKey type");
        }
        return FeeReceiversKey.reified().new({
            dummyField: (0, reified_1.decodeFromFieldsWithTypes)("bool", item.fields.dummy_field),
        });
    }
    static fromBcs(data) {
        return FeeReceiversKey.fromFields(FeeReceiversKey.bcs.parse(data));
    }
    toJSONField() {
        return {
            dummyField: this.dummyField,
        };
    }
    toJSON() {
        return Object.assign({ $typeName: this.$typeName, $typeArgs: this.$typeArgs }, this.toJSONField());
    }
    static fromJSONField(field) {
        return FeeReceiversKey.reified().new({
            dummyField: (0, reified_1.decodeFromJSONField)("bool", field.dummyField),
        });
    }
    static fromJSON(json) {
        if (json.$typeName !== FeeReceiversKey.$typeName) {
            throw new Error("not a WithTwoGenerics json object");
        }
        return FeeReceiversKey.fromJSONField(json);
    }
    static fromSuiParsedData(content) {
        if (content.dataType !== "moveObject") {
            throw new Error("not an object");
        }
        if (!isFeeReceiversKey(content.type)) {
            throw new Error(`object at ${content.fields.id} is not a FeeReceiversKey object`);
        }
        return FeeReceiversKey.fromFieldsWithTypes(content);
    }
    static fromSuiObjectData(data) {
        if (data.bcs) {
            if (data.bcs.dataType !== "moveObject" ||
                !isFeeReceiversKey(data.bcs.type)) {
                throw new Error(`object at is not a FeeReceiversKey object`);
            }
            return FeeReceiversKey.fromBcs((0, utils_1.fromB64)(data.bcs.bcsBytes));
        }
        if (data.content) {
            return FeeReceiversKey.fromSuiParsedData(data.content);
        }
        throw new Error("Both `bcs` and `content` fields are missing from the data. Include `showBcs` or `showContent` in the request.");
    }
    static fetch(client, id) {
        return __awaiter(this, void 0, void 0, function* () {
            var _a, _b;
            const res = yield client.getObject({ id, options: { showBcs: true } });
            if (res.error) {
                throw new Error(`error fetching FeeReceiversKey object at id ${id}: ${res.error.code}`);
            }
            if (((_b = (_a = res.data) === null || _a === void 0 ? void 0 : _a.bcs) === null || _b === void 0 ? void 0 : _b.dataType) !== "moveObject" ||
                !isFeeReceiversKey(res.data.bcs.type)) {
                throw new Error(`object at id ${id} is not a FeeReceiversKey object`);
            }
            return FeeReceiversKey.fromSuiObjectData(res.data);
        });
    }
}
exports.FeeReceiversKey = FeeReceiversKey;
FeeReceiversKey.$typeName = `${index_1.PKG_V10}::lending_market::FeeReceiversKey`;
FeeReceiversKey.$numTypeParams = 0;
FeeReceiversKey.$isPhantom = [];
/* ============================== ForgiveEvent =============================== */
function isForgiveEvent(type) {
    type = (0, util_1.compressSuiType)(type);
    return type === `${index_1.PKG_V1}::lending_market::ForgiveEvent`;
}
class ForgiveEvent {
    constructor(typeArgs, fields) {
        this.__StructClass = true;
        this.$typeName = ForgiveEvent.$typeName;
        this.$isPhantom = ForgiveEvent.$isPhantom;
        this.$fullTypeName = (0, util_1.composeSuiType)(ForgiveEvent.$typeName, ...typeArgs);
        this.$typeArgs = typeArgs;
        this.lendingMarketId = fields.lendingMarketId;
        this.coinType = fields.coinType;
        this.reserveId = fields.reserveId;
        this.obligationId = fields.obligationId;
        this.liquidityAmount = fields.liquidityAmount;
    }
    static reified() {
        return {
            typeName: ForgiveEvent.$typeName,
            fullTypeName: (0, util_1.composeSuiType)(ForgiveEvent.$typeName, ...[]),
            typeArgs: [],
            isPhantom: ForgiveEvent.$isPhantom,
            reifiedTypeArgs: [],
            fromFields: (fields) => ForgiveEvent.fromFields(fields),
            fromFieldsWithTypes: (item) => ForgiveEvent.fromFieldsWithTypes(item),
            fromBcs: (data) => ForgiveEvent.fromBcs(data),
            bcs: ForgiveEvent.bcs,
            fromJSONField: (field) => ForgiveEvent.fromJSONField(field),
            fromJSON: (json) => ForgiveEvent.fromJSON(json),
            fromSuiParsedData: (content) => ForgiveEvent.fromSuiParsedData(content),
            fromSuiObjectData: (content) => ForgiveEvent.fromSuiObjectData(content),
            fetch: (client, id) => __awaiter(this, void 0, void 0, function* () { return ForgiveEvent.fetch(client, id); }),
            new: (fields) => {
                return new ForgiveEvent([], fields);
            },
            kind: "StructClassReified",
        };
    }
    static get r() {
        return ForgiveEvent.reified();
    }
    static phantom() {
        return (0, reified_1.phantom)(ForgiveEvent.reified());
    }
    static get p() {
        return ForgiveEvent.phantom();
    }
    static get bcs() {
        return bcs_1.bcs.struct("ForgiveEvent", {
            lending_market_id: bcs_1.bcs
                .bytes(32)
                .transform({
                input: (val) => (0, utils_1.fromHEX)(val),
                output: (val) => (0, utils_1.toHEX)(val),
            }),
            coin_type: structs_1.TypeName.bcs,
            reserve_id: bcs_1.bcs
                .bytes(32)
                .transform({
                input: (val) => (0, utils_1.fromHEX)(val),
                output: (val) => (0, utils_1.toHEX)(val),
            }),
            obligation_id: bcs_1.bcs
                .bytes(32)
                .transform({
                input: (val) => (0, utils_1.fromHEX)(val),
                output: (val) => (0, utils_1.toHEX)(val),
            }),
            liquidity_amount: bcs_1.bcs.u64(),
        });
    }
    static fromFields(fields) {
        return ForgiveEvent.reified().new({
            lendingMarketId: (0, reified_1.decodeFromFields)("address", fields.lending_market_id),
            coinType: (0, reified_1.decodeFromFields)(structs_1.TypeName.reified(), fields.coin_type),
            reserveId: (0, reified_1.decodeFromFields)("address", fields.reserve_id),
            obligationId: (0, reified_1.decodeFromFields)("address", fields.obligation_id),
            liquidityAmount: (0, reified_1.decodeFromFields)("u64", fields.liquidity_amount),
        });
    }
    static fromFieldsWithTypes(item) {
        if (!isForgiveEvent(item.type)) {
            throw new Error("not a ForgiveEvent type");
        }
        return ForgiveEvent.reified().new({
            lendingMarketId: (0, reified_1.decodeFromFieldsWithTypes)("address", item.fields.lending_market_id),
            coinType: (0, reified_1.decodeFromFieldsWithTypes)(structs_1.TypeName.reified(), item.fields.coin_type),
            reserveId: (0, reified_1.decodeFromFieldsWithTypes)("address", item.fields.reserve_id),
            obligationId: (0, reified_1.decodeFromFieldsWithTypes)("address", item.fields.obligation_id),
            liquidityAmount: (0, reified_1.decodeFromFieldsWithTypes)("u64", item.fields.liquidity_amount),
        });
    }
    static fromBcs(data) {
        return ForgiveEvent.fromFields(ForgiveEvent.bcs.parse(data));
    }
    toJSONField() {
        return {
            lendingMarketId: this.lendingMarketId,
            coinType: this.coinType.toJSONField(),
            reserveId: this.reserveId,
            obligationId: this.obligationId,
            liquidityAmount: this.liquidityAmount.toString(),
        };
    }
    toJSON() {
        return Object.assign({ $typeName: this.$typeName, $typeArgs: this.$typeArgs }, this.toJSONField());
    }
    static fromJSONField(field) {
        return ForgiveEvent.reified().new({
            lendingMarketId: (0, reified_1.decodeFromJSONField)("address", field.lendingMarketId),
            coinType: (0, reified_1.decodeFromJSONField)(structs_1.TypeName.reified(), field.coinType),
            reserveId: (0, reified_1.decodeFromJSONField)("address", field.reserveId),
            obligationId: (0, reified_1.decodeFromJSONField)("address", field.obligationId),
            liquidityAmount: (0, reified_1.decodeFromJSONField)("u64", field.liquidityAmount),
        });
    }
    static fromJSON(json) {
        if (json.$typeName !== ForgiveEvent.$typeName) {
            throw new Error("not a WithTwoGenerics json object");
        }
        return ForgiveEvent.fromJSONField(json);
    }
    static fromSuiParsedData(content) {
        if (content.dataType !== "moveObject") {
            throw new Error("not an object");
        }
        if (!isForgiveEvent(content.type)) {
            throw new Error(`object at ${content.fields.id} is not a ForgiveEvent object`);
        }
        return ForgiveEvent.fromFieldsWithTypes(content);
    }
    static fromSuiObjectData(data) {
        if (data.bcs) {
            if (data.bcs.dataType !== "moveObject" ||
                !isForgiveEvent(data.bcs.type)) {
                throw new Error(`object at is not a ForgiveEvent object`);
            }
            return ForgiveEvent.fromBcs((0, utils_1.fromB64)(data.bcs.bcsBytes));
        }
        if (data.content) {
            return ForgiveEvent.fromSuiParsedData(data.content);
        }
        throw new Error("Both `bcs` and `content` fields are missing from the data. Include `showBcs` or `showContent` in the request.");
    }
    static fetch(client, id) {
        return __awaiter(this, void 0, void 0, function* () {
            var _a, _b;
            const res = yield client.getObject({ id, options: { showBcs: true } });
            if (res.error) {
                throw new Error(`error fetching ForgiveEvent object at id ${id}: ${res.error.code}`);
            }
            if (((_b = (_a = res.data) === null || _a === void 0 ? void 0 : _a.bcs) === null || _b === void 0 ? void 0 : _b.dataType) !== "moveObject" ||
                !isForgiveEvent(res.data.bcs.type)) {
                throw new Error(`object at id ${id} is not a ForgiveEvent object`);
            }
            return ForgiveEvent.fromSuiObjectData(res.data);
        });
    }
}
exports.ForgiveEvent = ForgiveEvent;
ForgiveEvent.$typeName = `${index_1.PKG_V1}::lending_market::ForgiveEvent`;
ForgiveEvent.$numTypeParams = 0;
ForgiveEvent.$isPhantom = [];
/* ============================== LENDING_MARKET =============================== */
function isLENDING_MARKET(type) {
    type = (0, util_1.compressSuiType)(type);
    return type === `${index_1.PKG_V1}::lending_market::LENDING_MARKET`;
}
class LENDING_MARKET {
    constructor(typeArgs, fields) {
        this.__StructClass = true;
        this.$typeName = LENDING_MARKET.$typeName;
        this.$isPhantom = LENDING_MARKET.$isPhantom;
        this.$fullTypeName = (0, util_1.composeSuiType)(LENDING_MARKET.$typeName, ...typeArgs);
        this.$typeArgs = typeArgs;
        this.dummyField = fields.dummyField;
    }
    static reified() {
        return {
            typeName: LENDING_MARKET.$typeName,
            fullTypeName: (0, util_1.composeSuiType)(LENDING_MARKET.$typeName, ...[]),
            typeArgs: [],
            isPhantom: LENDING_MARKET.$isPhantom,
            reifiedTypeArgs: [],
            fromFields: (fields) => LENDING_MARKET.fromFields(fields),
            fromFieldsWithTypes: (item) => LENDING_MARKET.fromFieldsWithTypes(item),
            fromBcs: (data) => LENDING_MARKET.fromBcs(data),
            bcs: LENDING_MARKET.bcs,
            fromJSONField: (field) => LENDING_MARKET.fromJSONField(field),
            fromJSON: (json) => LENDING_MARKET.fromJSON(json),
            fromSuiParsedData: (content) => LENDING_MARKET.fromSuiParsedData(content),
            fromSuiObjectData: (content) => LENDING_MARKET.fromSuiObjectData(content),
            fetch: (client, id) => __awaiter(this, void 0, void 0, function* () { return LENDING_MARKET.fetch(client, id); }),
            new: (fields) => {
                return new LENDING_MARKET([], fields);
            },
            kind: "StructClassReified",
        };
    }
    static get r() {
        return LENDING_MARKET.reified();
    }
    static phantom() {
        return (0, reified_1.phantom)(LENDING_MARKET.reified());
    }
    static get p() {
        return LENDING_MARKET.phantom();
    }
    static get bcs() {
        return bcs_1.bcs.struct("LENDING_MARKET", {
            dummy_field: bcs_1.bcs.bool(),
        });
    }
    static fromFields(fields) {
        return LENDING_MARKET.reified().new({
            dummyField: (0, reified_1.decodeFromFields)("bool", fields.dummy_field),
        });
    }
    static fromFieldsWithTypes(item) {
        if (!isLENDING_MARKET(item.type)) {
            throw new Error("not a LENDING_MARKET type");
        }
        return LENDING_MARKET.reified().new({
            dummyField: (0, reified_1.decodeFromFieldsWithTypes)("bool", item.fields.dummy_field),
        });
    }
    static fromBcs(data) {
        return LENDING_MARKET.fromFields(LENDING_MARKET.bcs.parse(data));
    }
    toJSONField() {
        return {
            dummyField: this.dummyField,
        };
    }
    toJSON() {
        return Object.assign({ $typeName: this.$typeName, $typeArgs: this.$typeArgs }, this.toJSONField());
    }
    static fromJSONField(field) {
        return LENDING_MARKET.reified().new({
            dummyField: (0, reified_1.decodeFromJSONField)("bool", field.dummyField),
        });
    }
    static fromJSON(json) {
        if (json.$typeName !== LENDING_MARKET.$typeName) {
            throw new Error("not a WithTwoGenerics json object");
        }
        return LENDING_MARKET.fromJSONField(json);
    }
    static fromSuiParsedData(content) {
        if (content.dataType !== "moveObject") {
            throw new Error("not an object");
        }
        if (!isLENDING_MARKET(content.type)) {
            throw new Error(`object at ${content.fields.id} is not a LENDING_MARKET object`);
        }
        return LENDING_MARKET.fromFieldsWithTypes(content);
    }
    static fromSuiObjectData(data) {
        if (data.bcs) {
            if (data.bcs.dataType !== "moveObject" ||
                !isLENDING_MARKET(data.bcs.type)) {
                throw new Error(`object at is not a LENDING_MARKET object`);
            }
            return LENDING_MARKET.fromBcs((0, utils_1.fromB64)(data.bcs.bcsBytes));
        }
        if (data.content) {
            return LENDING_MARKET.fromSuiParsedData(data.content);
        }
        throw new Error("Both `bcs` and `content` fields are missing from the data. Include `showBcs` or `showContent` in the request.");
    }
    static fetch(client, id) {
        return __awaiter(this, void 0, void 0, function* () {
            var _a, _b;
            const res = yield client.getObject({ id, options: { showBcs: true } });
            if (res.error) {
                throw new Error(`error fetching LENDING_MARKET object at id ${id}: ${res.error.code}`);
            }
            if (((_b = (_a = res.data) === null || _a === void 0 ? void 0 : _a.bcs) === null || _b === void 0 ? void 0 : _b.dataType) !== "moveObject" ||
                !isLENDING_MARKET(res.data.bcs.type)) {
                throw new Error(`object at id ${id} is not a LENDING_MARKET object`);
            }
            return LENDING_MARKET.fromSuiObjectData(res.data);
        });
    }
}
exports.LENDING_MARKET = LENDING_MARKET;
LENDING_MARKET.$typeName = `${index_1.PKG_V1}::lending_market::LENDING_MARKET`;
LENDING_MARKET.$numTypeParams = 0;
LENDING_MARKET.$isPhantom = [];
/* ============================== LendingMarket =============================== */
function isLendingMarket(type) {
    type = (0, util_1.compressSuiType)(type);
    return type.startsWith(`${index_1.PKG_V1}::lending_market::LendingMarket` + "<");
}
class LendingMarket {
    constructor(typeArgs, fields) {
        this.__StructClass = true;
        this.$typeName = LendingMarket.$typeName;
        this.$isPhantom = LendingMarket.$isPhantom;
        this.$fullTypeName = (0, util_1.composeSuiType)(LendingMarket.$typeName, ...typeArgs);
        this.$typeArgs = typeArgs;
        this.id = fields.id;
        this.version = fields.version;
        this.reserves = fields.reserves;
        this.obligations = fields.obligations;
        this.rateLimiter = fields.rateLimiter;
        this.feeReceiver = fields.feeReceiver;
        this.badDebtUsd = fields.badDebtUsd;
        this.badDebtLimitUsd = fields.badDebtLimitUsd;
    }
    static reified(P) {
        return {
            typeName: LendingMarket.$typeName,
            fullTypeName: (0, util_1.composeSuiType)(LendingMarket.$typeName, ...[(0, reified_1.extractType)(P)]),
            typeArgs: [(0, reified_1.extractType)(P)],
            isPhantom: LendingMarket.$isPhantom,
            reifiedTypeArgs: [P],
            fromFields: (fields) => LendingMarket.fromFields(P, fields),
            fromFieldsWithTypes: (item) => LendingMarket.fromFieldsWithTypes(P, item),
            fromBcs: (data) => LendingMarket.fromBcs(P, data),
            bcs: LendingMarket.bcs,
            fromJSONField: (field) => LendingMarket.fromJSONField(P, field),
            fromJSON: (json) => LendingMarket.fromJSON(P, json),
            fromSuiParsedData: (content) => LendingMarket.fromSuiParsedData(P, content),
            fromSuiObjectData: (content) => LendingMarket.fromSuiObjectData(P, content),
            fetch: (client, id) => __awaiter(this, void 0, void 0, function* () { return LendingMarket.fetch(client, P, id); }),
            new: (fields) => {
                return new LendingMarket([(0, reified_1.extractType)(P)], fields);
            },
            kind: "StructClassReified",
        };
    }
    static get r() {
        return LendingMarket.reified;
    }
    static phantom(P) {
        return (0, reified_1.phantom)(LendingMarket.reified(P));
    }
    static get p() {
        return LendingMarket.phantom;
    }
    static get bcs() {
        return bcs_1.bcs.struct("LendingMarket", {
            id: structs_3.UID.bcs,
            version: bcs_1.bcs.u64(),
            reserves: bcs_1.bcs.vector(structs_7.Reserve.bcs),
            obligations: structs_2.ObjectTable.bcs,
            rate_limiter: structs_6.RateLimiter.bcs,
            fee_receiver: bcs_1.bcs
                .bytes(32)
                .transform({
                input: (val) => (0, utils_1.fromHEX)(val),
                output: (val) => (0, utils_1.toHEX)(val),
            }),
            bad_debt_usd: structs_4.Decimal.bcs,
            bad_debt_limit_usd: structs_4.Decimal.bcs,
        });
    }
    static fromFields(typeArg, fields) {
        return LendingMarket.reified(typeArg).new({
            id: (0, reified_1.decodeFromFields)(structs_3.UID.reified(), fields.id),
            version: (0, reified_1.decodeFromFields)("u64", fields.version),
            reserves: (0, reified_1.decodeFromFields)(reified.vector(structs_7.Reserve.reified(typeArg)), fields.reserves),
            obligations: (0, reified_1.decodeFromFields)(structs_2.ObjectTable.reified(reified.phantom(structs_3.ID.reified()), reified.phantom(structs_5.Obligation.reified(typeArg))), fields.obligations),
            rateLimiter: (0, reified_1.decodeFromFields)(structs_6.RateLimiter.reified(), fields.rate_limiter),
            feeReceiver: (0, reified_1.decodeFromFields)("address", fields.fee_receiver),
            badDebtUsd: (0, reified_1.decodeFromFields)(structs_4.Decimal.reified(), fields.bad_debt_usd),
            badDebtLimitUsd: (0, reified_1.decodeFromFields)(structs_4.Decimal.reified(), fields.bad_debt_limit_usd),
        });
    }
    static fromFieldsWithTypes(typeArg, item) {
        if (!isLendingMarket(item.type)) {
            throw new Error("not a LendingMarket type");
        }
        (0, reified_1.assertFieldsWithTypesArgsMatch)(item, [typeArg]);
        return LendingMarket.reified(typeArg).new({
            id: (0, reified_1.decodeFromFieldsWithTypes)(structs_3.UID.reified(), item.fields.id),
            version: (0, reified_1.decodeFromFieldsWithTypes)("u64", item.fields.version),
            reserves: (0, reified_1.decodeFromFieldsWithTypes)(reified.vector(structs_7.Reserve.reified(typeArg)), item.fields.reserves),
            obligations: (0, reified_1.decodeFromFieldsWithTypes)(structs_2.ObjectTable.reified(reified.phantom(structs_3.ID.reified()), reified.phantom(structs_5.Obligation.reified(typeArg))), item.fields.obligations),
            rateLimiter: (0, reified_1.decodeFromFieldsWithTypes)(structs_6.RateLimiter.reified(), item.fields.rate_limiter),
            feeReceiver: (0, reified_1.decodeFromFieldsWithTypes)("address", item.fields.fee_receiver),
            badDebtUsd: (0, reified_1.decodeFromFieldsWithTypes)(structs_4.Decimal.reified(), item.fields.bad_debt_usd),
            badDebtLimitUsd: (0, reified_1.decodeFromFieldsWithTypes)(structs_4.Decimal.reified(), item.fields.bad_debt_limit_usd),
        });
    }
    static fromBcs(typeArg, data) {
        return LendingMarket.fromFields(typeArg, LendingMarket.bcs.parse(data));
    }
    toJSONField() {
        return {
            id: this.id,
            version: this.version.toString(),
            reserves: (0, reified_1.fieldToJSON)(`vector<${structs_7.Reserve.$typeName}<${this.$typeArgs[0]}>>`, this.reserves),
            obligations: this.obligations.toJSONField(),
            rateLimiter: this.rateLimiter.toJSONField(),
            feeReceiver: this.feeReceiver,
            badDebtUsd: this.badDebtUsd.toJSONField(),
            badDebtLimitUsd: this.badDebtLimitUsd.toJSONField(),
        };
    }
    toJSON() {
        return Object.assign({ $typeName: this.$typeName, $typeArgs: this.$typeArgs }, this.toJSONField());
    }
    static fromJSONField(typeArg, field) {
        return LendingMarket.reified(typeArg).new({
            id: (0, reified_1.decodeFromJSONField)(structs_3.UID.reified(), field.id),
            version: (0, reified_1.decodeFromJSONField)("u64", field.version),
            reserves: (0, reified_1.decodeFromJSONField)(reified.vector(structs_7.Reserve.reified(typeArg)), field.reserves),
            obligations: (0, reified_1.decodeFromJSONField)(structs_2.ObjectTable.reified(reified.phantom(structs_3.ID.reified()), reified.phantom(structs_5.Obligation.reified(typeArg))), field.obligations),
            rateLimiter: (0, reified_1.decodeFromJSONField)(structs_6.RateLimiter.reified(), field.rateLimiter),
            feeReceiver: (0, reified_1.decodeFromJSONField)("address", field.feeReceiver),
            badDebtUsd: (0, reified_1.decodeFromJSONField)(structs_4.Decimal.reified(), field.badDebtUsd),
            badDebtLimitUsd: (0, reified_1.decodeFromJSONField)(structs_4.Decimal.reified(), field.badDebtLimitUsd),
        });
    }
    static fromJSON(typeArg, json) {
        if (json.$typeName !== LendingMarket.$typeName) {
            throw new Error("not a WithTwoGenerics json object");
        }
        (0, reified_1.assertReifiedTypeArgsMatch)((0, util_1.composeSuiType)(LendingMarket.$typeName, (0, reified_1.extractType)(typeArg)), json.$typeArgs, [typeArg]);
        return LendingMarket.fromJSONField(typeArg, json);
    }
    static fromSuiParsedData(typeArg, content) {
        if (content.dataType !== "moveObject") {
            throw new Error("not an object");
        }
        if (!isLendingMarket(content.type)) {
            throw new Error(`object at ${content.fields.id} is not a LendingMarket object`);
        }
        return LendingMarket.fromFieldsWithTypes(typeArg, content);
    }
    static fromSuiObjectData(typeArg, data) {
        if (data.bcs) {
            if (data.bcs.dataType !== "moveObject" ||
                !isLendingMarket(data.bcs.type)) {
                throw new Error(`object at is not a LendingMarket object`);
            }
            const gotTypeArgs = (0, util_1.parseTypeName)(data.bcs.type).typeArgs;
            if (gotTypeArgs.length !== 1) {
                throw new Error(`type argument mismatch: expected 1 type argument but got '${gotTypeArgs.length}'`);
            }
            const gotTypeArg = (0, util_1.compressSuiType)(gotTypeArgs[0]);
            const expectedTypeArg = (0, util_1.compressSuiType)((0, reified_1.extractType)(typeArg));
            if (gotTypeArg !== (0, util_1.compressSuiType)((0, reified_1.extractType)(typeArg))) {
                throw new Error(`type argument mismatch: expected '${expectedTypeArg}' but got '${gotTypeArg}'`);
            }
            return LendingMarket.fromBcs(typeArg, (0, utils_1.fromB64)(data.bcs.bcsBytes));
        }
        if (data.content) {
            return LendingMarket.fromSuiParsedData(typeArg, data.content);
        }
        throw new Error("Both `bcs` and `content` fields are missing from the data. Include `showBcs` or `showContent` in the request.");
    }
    static fetch(client, typeArg, id) {
        return __awaiter(this, void 0, void 0, function* () {
            var _a, _b;
            const res = yield client.getObject({ id, options: { showBcs: true } });
            if (res.error) {
                throw new Error(`error fetching LendingMarket object at id ${id}: ${res.error.code}`);
            }
            if (((_b = (_a = res.data) === null || _a === void 0 ? void 0 : _a.bcs) === null || _b === void 0 ? void 0 : _b.dataType) !== "moveObject" ||
                !isLendingMarket(res.data.bcs.type)) {
                throw new Error(`object at id ${id} is not a LendingMarket object`);
            }
            return LendingMarket.fromSuiObjectData(typeArg, res.data);
        });
    }
}
exports.LendingMarket = LendingMarket;
LendingMarket.$typeName = `${index_1.PKG_V1}::lending_market::LendingMarket`;
LendingMarket.$numTypeParams = 1;
LendingMarket.$isPhantom = [true];
/* ============================== LendingMarketOwnerCap =============================== */
function isLendingMarketOwnerCap(type) {
    type = (0, util_1.compressSuiType)(type);
    return type.startsWith(`${index_1.PKG_V1}::lending_market::LendingMarketOwnerCap` + "<");
}
class LendingMarketOwnerCap {
    constructor(typeArgs, fields) {
        this.__StructClass = true;
        this.$typeName = LendingMarketOwnerCap.$typeName;
        this.$isPhantom = LendingMarketOwnerCap.$isPhantom;
        this.$fullTypeName = (0, util_1.composeSuiType)(LendingMarketOwnerCap.$typeName, ...typeArgs);
        this.$typeArgs = typeArgs;
        this.id = fields.id;
        this.lendingMarketId = fields.lendingMarketId;
    }
    static reified(P) {
        return {
            typeName: LendingMarketOwnerCap.$typeName,
            fullTypeName: (0, util_1.composeSuiType)(LendingMarketOwnerCap.$typeName, ...[(0, reified_1.extractType)(P)]),
            typeArgs: [(0, reified_1.extractType)(P)],
            isPhantom: LendingMarketOwnerCap.$isPhantom,
            reifiedTypeArgs: [P],
            fromFields: (fields) => LendingMarketOwnerCap.fromFields(P, fields),
            fromFieldsWithTypes: (item) => LendingMarketOwnerCap.fromFieldsWithTypes(P, item),
            fromBcs: (data) => LendingMarketOwnerCap.fromBcs(P, data),
            bcs: LendingMarketOwnerCap.bcs,
            fromJSONField: (field) => LendingMarketOwnerCap.fromJSONField(P, field),
            fromJSON: (json) => LendingMarketOwnerCap.fromJSON(P, json),
            fromSuiParsedData: (content) => LendingMarketOwnerCap.fromSuiParsedData(P, content),
            fromSuiObjectData: (content) => LendingMarketOwnerCap.fromSuiObjectData(P, content),
            fetch: (client, id) => __awaiter(this, void 0, void 0, function* () { return LendingMarketOwnerCap.fetch(client, P, id); }),
            new: (fields) => {
                return new LendingMarketOwnerCap([(0, reified_1.extractType)(P)], fields);
            },
            kind: "StructClassReified",
        };
    }
    static get r() {
        return LendingMarketOwnerCap.reified;
    }
    static phantom(P) {
        return (0, reified_1.phantom)(LendingMarketOwnerCap.reified(P));
    }
    static get p() {
        return LendingMarketOwnerCap.phantom;
    }
    static get bcs() {
        return bcs_1.bcs.struct("LendingMarketOwnerCap", {
            id: structs_3.UID.bcs,
            lending_market_id: structs_3.ID.bcs,
        });
    }
    static fromFields(typeArg, fields) {
        return LendingMarketOwnerCap.reified(typeArg).new({
            id: (0, reified_1.decodeFromFields)(structs_3.UID.reified(), fields.id),
            lendingMarketId: (0, reified_1.decodeFromFields)(structs_3.ID.reified(), fields.lending_market_id),
        });
    }
    static fromFieldsWithTypes(typeArg, item) {
        if (!isLendingMarketOwnerCap(item.type)) {
            throw new Error("not a LendingMarketOwnerCap type");
        }
        (0, reified_1.assertFieldsWithTypesArgsMatch)(item, [typeArg]);
        return LendingMarketOwnerCap.reified(typeArg).new({
            id: (0, reified_1.decodeFromFieldsWithTypes)(structs_3.UID.reified(), item.fields.id),
            lendingMarketId: (0, reified_1.decodeFromFieldsWithTypes)(structs_3.ID.reified(), item.fields.lending_market_id),
        });
    }
    static fromBcs(typeArg, data) {
        return LendingMarketOwnerCap.fromFields(typeArg, LendingMarketOwnerCap.bcs.parse(data));
    }
    toJSONField() {
        return {
            id: this.id,
            lendingMarketId: this.lendingMarketId,
        };
    }
    toJSON() {
        return Object.assign({ $typeName: this.$typeName, $typeArgs: this.$typeArgs }, this.toJSONField());
    }
    static fromJSONField(typeArg, field) {
        return LendingMarketOwnerCap.reified(typeArg).new({
            id: (0, reified_1.decodeFromJSONField)(structs_3.UID.reified(), field.id),
            lendingMarketId: (0, reified_1.decodeFromJSONField)(structs_3.ID.reified(), field.lendingMarketId),
        });
    }
    static fromJSON(typeArg, json) {
        if (json.$typeName !== LendingMarketOwnerCap.$typeName) {
            throw new Error("not a WithTwoGenerics json object");
        }
        (0, reified_1.assertReifiedTypeArgsMatch)((0, util_1.composeSuiType)(LendingMarketOwnerCap.$typeName, (0, reified_1.extractType)(typeArg)), json.$typeArgs, [typeArg]);
        return LendingMarketOwnerCap.fromJSONField(typeArg, json);
    }
    static fromSuiParsedData(typeArg, content) {
        if (content.dataType !== "moveObject") {
            throw new Error("not an object");
        }
        if (!isLendingMarketOwnerCap(content.type)) {
            throw new Error(`object at ${content.fields.id} is not a LendingMarketOwnerCap object`);
        }
        return LendingMarketOwnerCap.fromFieldsWithTypes(typeArg, content);
    }
    static fromSuiObjectData(typeArg, data) {
        if (data.bcs) {
            if (data.bcs.dataType !== "moveObject" ||
                !isLendingMarketOwnerCap(data.bcs.type)) {
                throw new Error(`object at is not a LendingMarketOwnerCap object`);
            }
            const gotTypeArgs = (0, util_1.parseTypeName)(data.bcs.type).typeArgs;
            if (gotTypeArgs.length !== 1) {
                throw new Error(`type argument mismatch: expected 1 type argument but got '${gotTypeArgs.length}'`);
            }
            const gotTypeArg = (0, util_1.compressSuiType)(gotTypeArgs[0]);
            const expectedTypeArg = (0, util_1.compressSuiType)((0, reified_1.extractType)(typeArg));
            if (gotTypeArg !== (0, util_1.compressSuiType)((0, reified_1.extractType)(typeArg))) {
                throw new Error(`type argument mismatch: expected '${expectedTypeArg}' but got '${gotTypeArg}'`);
            }
            return LendingMarketOwnerCap.fromBcs(typeArg, (0, utils_1.fromB64)(data.bcs.bcsBytes));
        }
        if (data.content) {
            return LendingMarketOwnerCap.fromSuiParsedData(typeArg, data.content);
        }
        throw new Error("Both `bcs` and `content` fields are missing from the data. Include `showBcs` or `showContent` in the request.");
    }
    static fetch(client, typeArg, id) {
        return __awaiter(this, void 0, void 0, function* () {
            var _a, _b;
            const res = yield client.getObject({ id, options: { showBcs: true } });
            if (res.error) {
                throw new Error(`error fetching LendingMarketOwnerCap object at id ${id}: ${res.error.code}`);
            }
            if (((_b = (_a = res.data) === null || _a === void 0 ? void 0 : _a.bcs) === null || _b === void 0 ? void 0 : _b.dataType) !== "moveObject" ||
                !isLendingMarketOwnerCap(res.data.bcs.type)) {
                throw new Error(`object at id ${id} is not a LendingMarketOwnerCap object`);
            }
            return LendingMarketOwnerCap.fromSuiObjectData(typeArg, res.data);
        });
    }
}
exports.LendingMarketOwnerCap = LendingMarketOwnerCap;
LendingMarketOwnerCap.$typeName = `${index_1.PKG_V1}::lending_market::LendingMarketOwnerCap`;
LendingMarketOwnerCap.$numTypeParams = 1;
LendingMarketOwnerCap.$isPhantom = [true];
/* ============================== LiquidateEvent =============================== */
function isLiquidateEvent(type) {
    type = (0, util_1.compressSuiType)(type);
    return type === `${index_1.PKG_V1}::lending_market::LiquidateEvent`;
}
class LiquidateEvent {
    constructor(typeArgs, fields) {
        this.__StructClass = true;
        this.$typeName = LiquidateEvent.$typeName;
        this.$isPhantom = LiquidateEvent.$isPhantom;
        this.$fullTypeName = (0, util_1.composeSuiType)(LiquidateEvent.$typeName, ...typeArgs);
        this.$typeArgs = typeArgs;
        this.lendingMarketId = fields.lendingMarketId;
        this.repayReserveId = fields.repayReserveId;
        this.withdrawReserveId = fields.withdrawReserveId;
        this.obligationId = fields.obligationId;
        this.repayCoinType = fields.repayCoinType;
        this.withdrawCoinType = fields.withdrawCoinType;
        this.repayAmount = fields.repayAmount;
        this.withdrawAmount = fields.withdrawAmount;
        this.protocolFeeAmount = fields.protocolFeeAmount;
        this.liquidatorBonusAmount = fields.liquidatorBonusAmount;
    }
    static reified() {
        return {
            typeName: LiquidateEvent.$typeName,
            fullTypeName: (0, util_1.composeSuiType)(LiquidateEvent.$typeName, ...[]),
            typeArgs: [],
            isPhantom: LiquidateEvent.$isPhantom,
            reifiedTypeArgs: [],
            fromFields: (fields) => LiquidateEvent.fromFields(fields),
            fromFieldsWithTypes: (item) => LiquidateEvent.fromFieldsWithTypes(item),
            fromBcs: (data) => LiquidateEvent.fromBcs(data),
            bcs: LiquidateEvent.bcs,
            fromJSONField: (field) => LiquidateEvent.fromJSONField(field),
            fromJSON: (json) => LiquidateEvent.fromJSON(json),
            fromSuiParsedData: (content) => LiquidateEvent.fromSuiParsedData(content),
            fromSuiObjectData: (content) => LiquidateEvent.fromSuiObjectData(content),
            fetch: (client, id) => __awaiter(this, void 0, void 0, function* () { return LiquidateEvent.fetch(client, id); }),
            new: (fields) => {
                return new LiquidateEvent([], fields);
            },
            kind: "StructClassReified",
        };
    }
    static get r() {
        return LiquidateEvent.reified();
    }
    static phantom() {
        return (0, reified_1.phantom)(LiquidateEvent.reified());
    }
    static get p() {
        return LiquidateEvent.phantom();
    }
    static get bcs() {
        return bcs_1.bcs.struct("LiquidateEvent", {
            lending_market_id: bcs_1.bcs
                .bytes(32)
                .transform({
                input: (val) => (0, utils_1.fromHEX)(val),
                output: (val) => (0, utils_1.toHEX)(val),
            }),
            repay_reserve_id: bcs_1.bcs
                .bytes(32)
                .transform({
                input: (val) => (0, utils_1.fromHEX)(val),
                output: (val) => (0, utils_1.toHEX)(val),
            }),
            withdraw_reserve_id: bcs_1.bcs
                .bytes(32)
                .transform({
                input: (val) => (0, utils_1.fromHEX)(val),
                output: (val) => (0, utils_1.toHEX)(val),
            }),
            obligation_id: bcs_1.bcs
                .bytes(32)
                .transform({
                input: (val) => (0, utils_1.fromHEX)(val),
                output: (val) => (0, utils_1.toHEX)(val),
            }),
            repay_coin_type: structs_1.TypeName.bcs,
            withdraw_coin_type: structs_1.TypeName.bcs,
            repay_amount: bcs_1.bcs.u64(),
            withdraw_amount: bcs_1.bcs.u64(),
            protocol_fee_amount: bcs_1.bcs.u64(),
            liquidator_bonus_amount: bcs_1.bcs.u64(),
        });
    }
    static fromFields(fields) {
        return LiquidateEvent.reified().new({
            lendingMarketId: (0, reified_1.decodeFromFields)("address", fields.lending_market_id),
            repayReserveId: (0, reified_1.decodeFromFields)("address", fields.repay_reserve_id),
            withdrawReserveId: (0, reified_1.decodeFromFields)("address", fields.withdraw_reserve_id),
            obligationId: (0, reified_1.decodeFromFields)("address", fields.obligation_id),
            repayCoinType: (0, reified_1.decodeFromFields)(structs_1.TypeName.reified(), fields.repay_coin_type),
            withdrawCoinType: (0, reified_1.decodeFromFields)(structs_1.TypeName.reified(), fields.withdraw_coin_type),
            repayAmount: (0, reified_1.decodeFromFields)("u64", fields.repay_amount),
            withdrawAmount: (0, reified_1.decodeFromFields)("u64", fields.withdraw_amount),
            protocolFeeAmount: (0, reified_1.decodeFromFields)("u64", fields.protocol_fee_amount),
            liquidatorBonusAmount: (0, reified_1.decodeFromFields)("u64", fields.liquidator_bonus_amount),
        });
    }
    static fromFieldsWithTypes(item) {
        if (!isLiquidateEvent(item.type)) {
            throw new Error("not a LiquidateEvent type");
        }
        return LiquidateEvent.reified().new({
            lendingMarketId: (0, reified_1.decodeFromFieldsWithTypes)("address", item.fields.lending_market_id),
            repayReserveId: (0, reified_1.decodeFromFieldsWithTypes)("address", item.fields.repay_reserve_id),
            withdrawReserveId: (0, reified_1.decodeFromFieldsWithTypes)("address", item.fields.withdraw_reserve_id),
            obligationId: (0, reified_1.decodeFromFieldsWithTypes)("address", item.fields.obligation_id),
            repayCoinType: (0, reified_1.decodeFromFieldsWithTypes)(structs_1.TypeName.reified(), item.fields.repay_coin_type),
            withdrawCoinType: (0, reified_1.decodeFromFieldsWithTypes)(structs_1.TypeName.reified(), item.fields.withdraw_coin_type),
            repayAmount: (0, reified_1.decodeFromFieldsWithTypes)("u64", item.fields.repay_amount),
            withdrawAmount: (0, reified_1.decodeFromFieldsWithTypes)("u64", item.fields.withdraw_amount),
            protocolFeeAmount: (0, reified_1.decodeFromFieldsWithTypes)("u64", item.fields.protocol_fee_amount),
            liquidatorBonusAmount: (0, reified_1.decodeFromFieldsWithTypes)("u64", item.fields.liquidator_bonus_amount),
        });
    }
    static fromBcs(data) {
        return LiquidateEvent.fromFields(LiquidateEvent.bcs.parse(data));
    }
    toJSONField() {
        return {
            lendingMarketId: this.lendingMarketId,
            repayReserveId: this.repayReserveId,
            withdrawReserveId: this.withdrawReserveId,
            obligationId: this.obligationId,
            repayCoinType: this.repayCoinType.toJSONField(),
            withdrawCoinType: this.withdrawCoinType.toJSONField(),
            repayAmount: this.repayAmount.toString(),
            withdrawAmount: this.withdrawAmount.toString(),
            protocolFeeAmount: this.protocolFeeAmount.toString(),
            liquidatorBonusAmount: this.liquidatorBonusAmount.toString(),
        };
    }
    toJSON() {
        return Object.assign({ $typeName: this.$typeName, $typeArgs: this.$typeArgs }, this.toJSONField());
    }
    static fromJSONField(field) {
        return LiquidateEvent.reified().new({
            lendingMarketId: (0, reified_1.decodeFromJSONField)("address", field.lendingMarketId),
            repayReserveId: (0, reified_1.decodeFromJSONField)("address", field.repayReserveId),
            withdrawReserveId: (0, reified_1.decodeFromJSONField)("address", field.withdrawReserveId),
            obligationId: (0, reified_1.decodeFromJSONField)("address", field.obligationId),
            repayCoinType: (0, reified_1.decodeFromJSONField)(structs_1.TypeName.reified(), field.repayCoinType),
            withdrawCoinType: (0, reified_1.decodeFromJSONField)(structs_1.TypeName.reified(), field.withdrawCoinType),
            repayAmount: (0, reified_1.decodeFromJSONField)("u64", field.repayAmount),
            withdrawAmount: (0, reified_1.decodeFromJSONField)("u64", field.withdrawAmount),
            protocolFeeAmount: (0, reified_1.decodeFromJSONField)("u64", field.protocolFeeAmount),
            liquidatorBonusAmount: (0, reified_1.decodeFromJSONField)("u64", field.liquidatorBonusAmount),
        });
    }
    static fromJSON(json) {
        if (json.$typeName !== LiquidateEvent.$typeName) {
            throw new Error("not a WithTwoGenerics json object");
        }
        return LiquidateEvent.fromJSONField(json);
    }
    static fromSuiParsedData(content) {
        if (content.dataType !== "moveObject") {
            throw new Error("not an object");
        }
        if (!isLiquidateEvent(content.type)) {
            throw new Error(`object at ${content.fields.id} is not a LiquidateEvent object`);
        }
        return LiquidateEvent.fromFieldsWithTypes(content);
    }
    static fromSuiObjectData(data) {
        if (data.bcs) {
            if (data.bcs.dataType !== "moveObject" ||
                !isLiquidateEvent(data.bcs.type)) {
                throw new Error(`object at is not a LiquidateEvent object`);
            }
            return LiquidateEvent.fromBcs((0, utils_1.fromB64)(data.bcs.bcsBytes));
        }
        if (data.content) {
            return LiquidateEvent.fromSuiParsedData(data.content);
        }
        throw new Error("Both `bcs` and `content` fields are missing from the data. Include `showBcs` or `showContent` in the request.");
    }
    static fetch(client, id) {
        return __awaiter(this, void 0, void 0, function* () {
            var _a, _b;
            const res = yield client.getObject({ id, options: { showBcs: true } });
            if (res.error) {
                throw new Error(`error fetching LiquidateEvent object at id ${id}: ${res.error.code}`);
            }
            if (((_b = (_a = res.data) === null || _a === void 0 ? void 0 : _a.bcs) === null || _b === void 0 ? void 0 : _b.dataType) !== "moveObject" ||
                !isLiquidateEvent(res.data.bcs.type)) {
                throw new Error(`object at id ${id} is not a LiquidateEvent object`);
            }
            return LiquidateEvent.fromSuiObjectData(res.data);
        });
    }
}
exports.LiquidateEvent = LiquidateEvent;
LiquidateEvent.$typeName = `${index_1.PKG_V1}::lending_market::LiquidateEvent`;
LiquidateEvent.$numTypeParams = 0;
LiquidateEvent.$isPhantom = [];
/* ============================== ObligationOwnerCap =============================== */
function isObligationOwnerCap(type) {
    type = (0, util_1.compressSuiType)(type);
    return type.startsWith(`${index_1.PKG_V1}::lending_market::ObligationOwnerCap` + "<");
}
class ObligationOwnerCap {
    constructor(typeArgs, fields) {
        this.__StructClass = true;
        this.$typeName = ObligationOwnerCap.$typeName;
        this.$isPhantom = ObligationOwnerCap.$isPhantom;
        this.$fullTypeName = (0, util_1.composeSuiType)(ObligationOwnerCap.$typeName, ...typeArgs);
        this.$typeArgs = typeArgs;
        this.id = fields.id;
        this.obligationId = fields.obligationId;
    }
    static reified(P) {
        return {
            typeName: ObligationOwnerCap.$typeName,
            fullTypeName: (0, util_1.composeSuiType)(ObligationOwnerCap.$typeName, ...[(0, reified_1.extractType)(P)]),
            typeArgs: [(0, reified_1.extractType)(P)],
            isPhantom: ObligationOwnerCap.$isPhantom,
            reifiedTypeArgs: [P],
            fromFields: (fields) => ObligationOwnerCap.fromFields(P, fields),
            fromFieldsWithTypes: (item) => ObligationOwnerCap.fromFieldsWithTypes(P, item),
            fromBcs: (data) => ObligationOwnerCap.fromBcs(P, data),
            bcs: ObligationOwnerCap.bcs,
            fromJSONField: (field) => ObligationOwnerCap.fromJSONField(P, field),
            fromJSON: (json) => ObligationOwnerCap.fromJSON(P, json),
            fromSuiParsedData: (content) => ObligationOwnerCap.fromSuiParsedData(P, content),
            fromSuiObjectData: (content) => ObligationOwnerCap.fromSuiObjectData(P, content),
            fetch: (client, id) => __awaiter(this, void 0, void 0, function* () { return ObligationOwnerCap.fetch(client, P, id); }),
            new: (fields) => {
                return new ObligationOwnerCap([(0, reified_1.extractType)(P)], fields);
            },
            kind: "StructClassReified",
        };
    }
    static get r() {
        return ObligationOwnerCap.reified;
    }
    static phantom(P) {
        return (0, reified_1.phantom)(ObligationOwnerCap.reified(P));
    }
    static get p() {
        return ObligationOwnerCap.phantom;
    }
    static get bcs() {
        return bcs_1.bcs.struct("ObligationOwnerCap", {
            id: structs_3.UID.bcs,
            obligation_id: structs_3.ID.bcs,
        });
    }
    static fromFields(typeArg, fields) {
        return ObligationOwnerCap.reified(typeArg).new({
            id: (0, reified_1.decodeFromFields)(structs_3.UID.reified(), fields.id),
            obligationId: (0, reified_1.decodeFromFields)(structs_3.ID.reified(), fields.obligation_id),
        });
    }
    static fromFieldsWithTypes(typeArg, item) {
        if (!isObligationOwnerCap(item.type)) {
            throw new Error("not a ObligationOwnerCap type");
        }
        (0, reified_1.assertFieldsWithTypesArgsMatch)(item, [typeArg]);
        return ObligationOwnerCap.reified(typeArg).new({
            id: (0, reified_1.decodeFromFieldsWithTypes)(structs_3.UID.reified(), item.fields.id),
            obligationId: (0, reified_1.decodeFromFieldsWithTypes)(structs_3.ID.reified(), item.fields.obligation_id),
        });
    }
    static fromBcs(typeArg, data) {
        return ObligationOwnerCap.fromFields(typeArg, ObligationOwnerCap.bcs.parse(data));
    }
    toJSONField() {
        return {
            id: this.id,
            obligationId: this.obligationId,
        };
    }
    toJSON() {
        return Object.assign({ $typeName: this.$typeName, $typeArgs: this.$typeArgs }, this.toJSONField());
    }
    static fromJSONField(typeArg, field) {
        return ObligationOwnerCap.reified(typeArg).new({
            id: (0, reified_1.decodeFromJSONField)(structs_3.UID.reified(), field.id),
            obligationId: (0, reified_1.decodeFromJSONField)(structs_3.ID.reified(), field.obligationId),
        });
    }
    static fromJSON(typeArg, json) {
        if (json.$typeName !== ObligationOwnerCap.$typeName) {
            throw new Error("not a WithTwoGenerics json object");
        }
        (0, reified_1.assertReifiedTypeArgsMatch)((0, util_1.composeSuiType)(ObligationOwnerCap.$typeName, (0, reified_1.extractType)(typeArg)), json.$typeArgs, [typeArg]);
        return ObligationOwnerCap.fromJSONField(typeArg, json);
    }
    static fromSuiParsedData(typeArg, content) {
        if (content.dataType !== "moveObject") {
            throw new Error("not an object");
        }
        if (!isObligationOwnerCap(content.type)) {
            throw new Error(`object at ${content.fields.id} is not a ObligationOwnerCap object`);
        }
        return ObligationOwnerCap.fromFieldsWithTypes(typeArg, content);
    }
    static fromSuiObjectData(typeArg, data) {
        if (data.bcs) {
            if (data.bcs.dataType !== "moveObject" ||
                !isObligationOwnerCap(data.bcs.type)) {
                throw new Error(`object at is not a ObligationOwnerCap object`);
            }
            const gotTypeArgs = (0, util_1.parseTypeName)(data.bcs.type).typeArgs;
            if (gotTypeArgs.length !== 1) {
                throw new Error(`type argument mismatch: expected 1 type argument but got '${gotTypeArgs.length}'`);
            }
            const gotTypeArg = (0, util_1.compressSuiType)(gotTypeArgs[0]);
            const expectedTypeArg = (0, util_1.compressSuiType)((0, reified_1.extractType)(typeArg));
            if (gotTypeArg !== (0, util_1.compressSuiType)((0, reified_1.extractType)(typeArg))) {
                throw new Error(`type argument mismatch: expected '${expectedTypeArg}' but got '${gotTypeArg}'`);
            }
            return ObligationOwnerCap.fromBcs(typeArg, (0, utils_1.fromB64)(data.bcs.bcsBytes));
        }
        if (data.content) {
            return ObligationOwnerCap.fromSuiParsedData(typeArg, data.content);
        }
        throw new Error("Both `bcs` and `content` fields are missing from the data. Include `showBcs` or `showContent` in the request.");
    }
    static fetch(client, typeArg, id) {
        return __awaiter(this, void 0, void 0, function* () {
            var _a, _b;
            const res = yield client.getObject({ id, options: { showBcs: true } });
            if (res.error) {
                throw new Error(`error fetching ObligationOwnerCap object at id ${id}: ${res.error.code}`);
            }
            if (((_b = (_a = res.data) === null || _a === void 0 ? void 0 : _a.bcs) === null || _b === void 0 ? void 0 : _b.dataType) !== "moveObject" ||
                !isObligationOwnerCap(res.data.bcs.type)) {
                throw new Error(`object at id ${id} is not a ObligationOwnerCap object`);
            }
            return ObligationOwnerCap.fromSuiObjectData(typeArg, res.data);
        });
    }
}
exports.ObligationOwnerCap = ObligationOwnerCap;
ObligationOwnerCap.$typeName = `${index_1.PKG_V1}::lending_market::ObligationOwnerCap`;
ObligationOwnerCap.$numTypeParams = 1;
ObligationOwnerCap.$isPhantom = [true];
/* ============================== RateLimiterExemption =============================== */
function isRateLimiterExemption(type) {
    type = (0, util_1.compressSuiType)(type);
    return type.startsWith(`${index_1.PKG_V1}::lending_market::RateLimiterExemption` + "<");
}
class RateLimiterExemption {
    constructor(typeArgs, fields) {
        this.__StructClass = true;
        this.$typeName = RateLimiterExemption.$typeName;
        this.$isPhantom = RateLimiterExemption.$isPhantom;
        this.$fullTypeName = (0, util_1.composeSuiType)(RateLimiterExemption.$typeName, ...typeArgs);
        this.$typeArgs = typeArgs;
        this.amount = fields.amount;
    }
    static reified(P, T) {
        return {
            typeName: RateLimiterExemption.$typeName,
            fullTypeName: (0, util_1.composeSuiType)(RateLimiterExemption.$typeName, ...[(0, reified_1.extractType)(P), (0, reified_1.extractType)(T)]),
            typeArgs: [(0, reified_1.extractType)(P), (0, reified_1.extractType)(T)],
            isPhantom: RateLimiterExemption.$isPhantom,
            reifiedTypeArgs: [P, T],
            fromFields: (fields) => RateLimiterExemption.fromFields([P, T], fields),
            fromFieldsWithTypes: (item) => RateLimiterExemption.fromFieldsWithTypes([P, T], item),
            fromBcs: (data) => RateLimiterExemption.fromBcs([P, T], data),
            bcs: RateLimiterExemption.bcs,
            fromJSONField: (field) => RateLimiterExemption.fromJSONField([P, T], field),
            fromJSON: (json) => RateLimiterExemption.fromJSON([P, T], json),
            fromSuiParsedData: (content) => RateLimiterExemption.fromSuiParsedData([P, T], content),
            fromSuiObjectData: (content) => RateLimiterExemption.fromSuiObjectData([P, T], content),
            fetch: (client, id) => __awaiter(this, void 0, void 0, function* () { return RateLimiterExemption.fetch(client, [P, T], id); }),
            new: (fields) => {
                return new RateLimiterExemption([(0, reified_1.extractType)(P), (0, reified_1.extractType)(T)], fields);
            },
            kind: "StructClassReified",
        };
    }
    static get r() {
        return RateLimiterExemption.reified;
    }
    static phantom(P, T) {
        return (0, reified_1.phantom)(RateLimiterExemption.reified(P, T));
    }
    static get p() {
        return RateLimiterExemption.phantom;
    }
    static get bcs() {
        return bcs_1.bcs.struct("RateLimiterExemption", {
            amount: bcs_1.bcs.u64(),
        });
    }
    static fromFields(typeArgs, fields) {
        return RateLimiterExemption.reified(typeArgs[0], typeArgs[1]).new({
            amount: (0, reified_1.decodeFromFields)("u64", fields.amount),
        });
    }
    static fromFieldsWithTypes(typeArgs, item) {
        if (!isRateLimiterExemption(item.type)) {
            throw new Error("not a RateLimiterExemption type");
        }
        (0, reified_1.assertFieldsWithTypesArgsMatch)(item, typeArgs);
        return RateLimiterExemption.reified(typeArgs[0], typeArgs[1]).new({
            amount: (0, reified_1.decodeFromFieldsWithTypes)("u64", item.fields.amount),
        });
    }
    static fromBcs(typeArgs, data) {
        return RateLimiterExemption.fromFields(typeArgs, RateLimiterExemption.bcs.parse(data));
    }
    toJSONField() {
        return {
            amount: this.amount.toString(),
        };
    }
    toJSON() {
        return Object.assign({ $typeName: this.$typeName, $typeArgs: this.$typeArgs }, this.toJSONField());
    }
    static fromJSONField(typeArgs, field) {
        return RateLimiterExemption.reified(typeArgs[0], typeArgs[1]).new({
            amount: (0, reified_1.decodeFromJSONField)("u64", field.amount),
        });
    }
    static fromJSON(typeArgs, json) {
        if (json.$typeName !== RateLimiterExemption.$typeName) {
            throw new Error("not a WithTwoGenerics json object");
        }
        (0, reified_1.assertReifiedTypeArgsMatch)((0, util_1.composeSuiType)(RateLimiterExemption.$typeName, ...typeArgs.map(reified_1.extractType)), json.$typeArgs, typeArgs);
        return RateLimiterExemption.fromJSONField(typeArgs, json);
    }
    static fromSuiParsedData(typeArgs, content) {
        if (content.dataType !== "moveObject") {
            throw new Error("not an object");
        }
        if (!isRateLimiterExemption(content.type)) {
            throw new Error(`object at ${content.fields.id} is not a RateLimiterExemption object`);
        }
        return RateLimiterExemption.fromFieldsWithTypes(typeArgs, content);
    }
    static fromSuiObjectData(typeArgs, data) {
        if (data.bcs) {
            if (data.bcs.dataType !== "moveObject" ||
                !isRateLimiterExemption(data.bcs.type)) {
                throw new Error(`object at is not a RateLimiterExemption object`);
            }
            const gotTypeArgs = (0, util_1.parseTypeName)(data.bcs.type).typeArgs;
            if (gotTypeArgs.length !== 2) {
                throw new Error(`type argument mismatch: expected 2 type arguments but got ${gotTypeArgs.length}`);
            }
            for (let i = 0; i < 2; i++) {
                const gotTypeArg = (0, util_1.compressSuiType)(gotTypeArgs[i]);
                const expectedTypeArg = (0, util_1.compressSuiType)((0, reified_1.extractType)(typeArgs[i]));
                if (gotTypeArg !== expectedTypeArg) {
                    throw new Error(`type argument mismatch at position ${i}: expected '${expectedTypeArg}' but got '${gotTypeArg}'`);
                }
            }
            return RateLimiterExemption.fromBcs(typeArgs, (0, utils_1.fromB64)(data.bcs.bcsBytes));
        }
        if (data.content) {
            return RateLimiterExemption.fromSuiParsedData(typeArgs, data.content);
        }
        throw new Error("Both `bcs` and `content` fields are missing from the data. Include `showBcs` or `showContent` in the request.");
    }
    static fetch(client, typeArgs, id) {
        return __awaiter(this, void 0, void 0, function* () {
            var _a, _b;
            const res = yield client.getObject({ id, options: { showBcs: true } });
            if (res.error) {
                throw new Error(`error fetching RateLimiterExemption object at id ${id}: ${res.error.code}`);
            }
            if (((_b = (_a = res.data) === null || _a === void 0 ? void 0 : _a.bcs) === null || _b === void 0 ? void 0 : _b.dataType) !== "moveObject" ||
                !isRateLimiterExemption(res.data.bcs.type)) {
                throw new Error(`object at id ${id} is not a RateLimiterExemption object`);
            }
            return RateLimiterExemption.fromSuiObjectData(typeArgs, res.data);
        });
    }
}
exports.RateLimiterExemption = RateLimiterExemption;
RateLimiterExemption.$typeName = `${index_1.PKG_V1}::lending_market::RateLimiterExemption`;
RateLimiterExemption.$numTypeParams = 2;
RateLimiterExemption.$isPhantom = [true, true];
/* ============================== RepayEvent =============================== */
function isRepayEvent(type) {
    type = (0, util_1.compressSuiType)(type);
    return type === `${index_1.PKG_V1}::lending_market::RepayEvent`;
}
class RepayEvent {
    constructor(typeArgs, fields) {
        this.__StructClass = true;
        this.$typeName = RepayEvent.$typeName;
        this.$isPhantom = RepayEvent.$isPhantom;
        this.$fullTypeName = (0, util_1.composeSuiType)(RepayEvent.$typeName, ...typeArgs);
        this.$typeArgs = typeArgs;
        this.lendingMarketId = fields.lendingMarketId;
        this.coinType = fields.coinType;
        this.reserveId = fields.reserveId;
        this.obligationId = fields.obligationId;
        this.liquidityAmount = fields.liquidityAmount;
    }
    static reified() {
        return {
            typeName: RepayEvent.$typeName,
            fullTypeName: (0, util_1.composeSuiType)(RepayEvent.$typeName, ...[]),
            typeArgs: [],
            isPhantom: RepayEvent.$isPhantom,
            reifiedTypeArgs: [],
            fromFields: (fields) => RepayEvent.fromFields(fields),
            fromFieldsWithTypes: (item) => RepayEvent.fromFieldsWithTypes(item),
            fromBcs: (data) => RepayEvent.fromBcs(data),
            bcs: RepayEvent.bcs,
            fromJSONField: (field) => RepayEvent.fromJSONField(field),
            fromJSON: (json) => RepayEvent.fromJSON(json),
            fromSuiParsedData: (content) => RepayEvent.fromSuiParsedData(content),
            fromSuiObjectData: (content) => RepayEvent.fromSuiObjectData(content),
            fetch: (client, id) => __awaiter(this, void 0, void 0, function* () { return RepayEvent.fetch(client, id); }),
            new: (fields) => {
                return new RepayEvent([], fields);
            },
            kind: "StructClassReified",
        };
    }
    static get r() {
        return RepayEvent.reified();
    }
    static phantom() {
        return (0, reified_1.phantom)(RepayEvent.reified());
    }
    static get p() {
        return RepayEvent.phantom();
    }
    static get bcs() {
        return bcs_1.bcs.struct("RepayEvent", {
            lending_market_id: bcs_1.bcs
                .bytes(32)
                .transform({
                input: (val) => (0, utils_1.fromHEX)(val),
                output: (val) => (0, utils_1.toHEX)(val),
            }),
            coin_type: structs_1.TypeName.bcs,
            reserve_id: bcs_1.bcs
                .bytes(32)
                .transform({
                input: (val) => (0, utils_1.fromHEX)(val),
                output: (val) => (0, utils_1.toHEX)(val),
            }),
            obligation_id: bcs_1.bcs
                .bytes(32)
                .transform({
                input: (val) => (0, utils_1.fromHEX)(val),
                output: (val) => (0, utils_1.toHEX)(val),
            }),
            liquidity_amount: bcs_1.bcs.u64(),
        });
    }
    static fromFields(fields) {
        return RepayEvent.reified().new({
            lendingMarketId: (0, reified_1.decodeFromFields)("address", fields.lending_market_id),
            coinType: (0, reified_1.decodeFromFields)(structs_1.TypeName.reified(), fields.coin_type),
            reserveId: (0, reified_1.decodeFromFields)("address", fields.reserve_id),
            obligationId: (0, reified_1.decodeFromFields)("address", fields.obligation_id),
            liquidityAmount: (0, reified_1.decodeFromFields)("u64", fields.liquidity_amount),
        });
    }
    static fromFieldsWithTypes(item) {
        if (!isRepayEvent(item.type)) {
            throw new Error("not a RepayEvent type");
        }
        return RepayEvent.reified().new({
            lendingMarketId: (0, reified_1.decodeFromFieldsWithTypes)("address", item.fields.lending_market_id),
            coinType: (0, reified_1.decodeFromFieldsWithTypes)(structs_1.TypeName.reified(), item.fields.coin_type),
            reserveId: (0, reified_1.decodeFromFieldsWithTypes)("address", item.fields.reserve_id),
            obligationId: (0, reified_1.decodeFromFieldsWithTypes)("address", item.fields.obligation_id),
            liquidityAmount: (0, reified_1.decodeFromFieldsWithTypes)("u64", item.fields.liquidity_amount),
        });
    }
    static fromBcs(data) {
        return RepayEvent.fromFields(RepayEvent.bcs.parse(data));
    }
    toJSONField() {
        return {
            lendingMarketId: this.lendingMarketId,
            coinType: this.coinType.toJSONField(),
            reserveId: this.reserveId,
            obligationId: this.obligationId,
            liquidityAmount: this.liquidityAmount.toString(),
        };
    }
    toJSON() {
        return Object.assign({ $typeName: this.$typeName, $typeArgs: this.$typeArgs }, this.toJSONField());
    }
    static fromJSONField(field) {
        return RepayEvent.reified().new({
            lendingMarketId: (0, reified_1.decodeFromJSONField)("address", field.lendingMarketId),
            coinType: (0, reified_1.decodeFromJSONField)(structs_1.TypeName.reified(), field.coinType),
            reserveId: (0, reified_1.decodeFromJSONField)("address", field.reserveId),
            obligationId: (0, reified_1.decodeFromJSONField)("address", field.obligationId),
            liquidityAmount: (0, reified_1.decodeFromJSONField)("u64", field.liquidityAmount),
        });
    }
    static fromJSON(json) {
        if (json.$typeName !== RepayEvent.$typeName) {
            throw new Error("not a WithTwoGenerics json object");
        }
        return RepayEvent.fromJSONField(json);
    }
    static fromSuiParsedData(content) {
        if (content.dataType !== "moveObject") {
            throw new Error("not an object");
        }
        if (!isRepayEvent(content.type)) {
            throw new Error(`object at ${content.fields.id} is not a RepayEvent object`);
        }
        return RepayEvent.fromFieldsWithTypes(content);
    }
    static fromSuiObjectData(data) {
        if (data.bcs) {
            if (data.bcs.dataType !== "moveObject" || !isRepayEvent(data.bcs.type)) {
                throw new Error(`object at is not a RepayEvent object`);
            }
            return RepayEvent.fromBcs((0, utils_1.fromB64)(data.bcs.bcsBytes));
        }
        if (data.content) {
            return RepayEvent.fromSuiParsedData(data.content);
        }
        throw new Error("Both `bcs` and `content` fields are missing from the data. Include `showBcs` or `showContent` in the request.");
    }
    static fetch(client, id) {
        return __awaiter(this, void 0, void 0, function* () {
            var _a, _b;
            const res = yield client.getObject({ id, options: { showBcs: true } });
            if (res.error) {
                throw new Error(`error fetching RepayEvent object at id ${id}: ${res.error.code}`);
            }
            if (((_b = (_a = res.data) === null || _a === void 0 ? void 0 : _a.bcs) === null || _b === void 0 ? void 0 : _b.dataType) !== "moveObject" ||
                !isRepayEvent(res.data.bcs.type)) {
                throw new Error(`object at id ${id} is not a RepayEvent object`);
            }
            return RepayEvent.fromSuiObjectData(res.data);
        });
    }
}
exports.RepayEvent = RepayEvent;
RepayEvent.$typeName = `${index_1.PKG_V1}::lending_market::RepayEvent`;
RepayEvent.$numTypeParams = 0;
RepayEvent.$isPhantom = [];
/* ============================== WithdrawEvent =============================== */
function isWithdrawEvent(type) {
    type = (0, util_1.compressSuiType)(type);
    return type === `${index_1.PKG_V1}::lending_market::WithdrawEvent`;
}
class WithdrawEvent {
    constructor(typeArgs, fields) {
        this.__StructClass = true;
        this.$typeName = WithdrawEvent.$typeName;
        this.$isPhantom = WithdrawEvent.$isPhantom;
        this.$fullTypeName = (0, util_1.composeSuiType)(WithdrawEvent.$typeName, ...typeArgs);
        this.$typeArgs = typeArgs;
        this.lendingMarketId = fields.lendingMarketId;
        this.coinType = fields.coinType;
        this.reserveId = fields.reserveId;
        this.obligationId = fields.obligationId;
        this.ctokenAmount = fields.ctokenAmount;
    }
    static reified() {
        return {
            typeName: WithdrawEvent.$typeName,
            fullTypeName: (0, util_1.composeSuiType)(WithdrawEvent.$typeName, ...[]),
            typeArgs: [],
            isPhantom: WithdrawEvent.$isPhantom,
            reifiedTypeArgs: [],
            fromFields: (fields) => WithdrawEvent.fromFields(fields),
            fromFieldsWithTypes: (item) => WithdrawEvent.fromFieldsWithTypes(item),
            fromBcs: (data) => WithdrawEvent.fromBcs(data),
            bcs: WithdrawEvent.bcs,
            fromJSONField: (field) => WithdrawEvent.fromJSONField(field),
            fromJSON: (json) => WithdrawEvent.fromJSON(json),
            fromSuiParsedData: (content) => WithdrawEvent.fromSuiParsedData(content),
            fromSuiObjectData: (content) => WithdrawEvent.fromSuiObjectData(content),
            fetch: (client, id) => __awaiter(this, void 0, void 0, function* () { return WithdrawEvent.fetch(client, id); }),
            new: (fields) => {
                return new WithdrawEvent([], fields);
            },
            kind: "StructClassReified",
        };
    }
    static get r() {
        return WithdrawEvent.reified();
    }
    static phantom() {
        return (0, reified_1.phantom)(WithdrawEvent.reified());
    }
    static get p() {
        return WithdrawEvent.phantom();
    }
    static get bcs() {
        return bcs_1.bcs.struct("WithdrawEvent", {
            lending_market_id: bcs_1.bcs
                .bytes(32)
                .transform({
                input: (val) => (0, utils_1.fromHEX)(val),
                output: (val) => (0, utils_1.toHEX)(val),
            }),
            coin_type: structs_1.TypeName.bcs,
            reserve_id: bcs_1.bcs
                .bytes(32)
                .transform({
                input: (val) => (0, utils_1.fromHEX)(val),
                output: (val) => (0, utils_1.toHEX)(val),
            }),
            obligation_id: bcs_1.bcs
                .bytes(32)
                .transform({
                input: (val) => (0, utils_1.fromHEX)(val),
                output: (val) => (0, utils_1.toHEX)(val),
            }),
            ctoken_amount: bcs_1.bcs.u64(),
        });
    }
    static fromFields(fields) {
        return WithdrawEvent.reified().new({
            lendingMarketId: (0, reified_1.decodeFromFields)("address", fields.lending_market_id),
            coinType: (0, reified_1.decodeFromFields)(structs_1.TypeName.reified(), fields.coin_type),
            reserveId: (0, reified_1.decodeFromFields)("address", fields.reserve_id),
            obligationId: (0, reified_1.decodeFromFields)("address", fields.obligation_id),
            ctokenAmount: (0, reified_1.decodeFromFields)("u64", fields.ctoken_amount),
        });
    }
    static fromFieldsWithTypes(item) {
        if (!isWithdrawEvent(item.type)) {
            throw new Error("not a WithdrawEvent type");
        }
        return WithdrawEvent.reified().new({
            lendingMarketId: (0, reified_1.decodeFromFieldsWithTypes)("address", item.fields.lending_market_id),
            coinType: (0, reified_1.decodeFromFieldsWithTypes)(structs_1.TypeName.reified(), item.fields.coin_type),
            reserveId: (0, reified_1.decodeFromFieldsWithTypes)("address", item.fields.reserve_id),
            obligationId: (0, reified_1.decodeFromFieldsWithTypes)("address", item.fields.obligation_id),
            ctokenAmount: (0, reified_1.decodeFromFieldsWithTypes)("u64", item.fields.ctoken_amount),
        });
    }
    static fromBcs(data) {
        return WithdrawEvent.fromFields(WithdrawEvent.bcs.parse(data));
    }
    toJSONField() {
        return {
            lendingMarketId: this.lendingMarketId,
            coinType: this.coinType.toJSONField(),
            reserveId: this.reserveId,
            obligationId: this.obligationId,
            ctokenAmount: this.ctokenAmount.toString(),
        };
    }
    toJSON() {
        return Object.assign({ $typeName: this.$typeName, $typeArgs: this.$typeArgs }, this.toJSONField());
    }
    static fromJSONField(field) {
        return WithdrawEvent.reified().new({
            lendingMarketId: (0, reified_1.decodeFromJSONField)("address", field.lendingMarketId),
            coinType: (0, reified_1.decodeFromJSONField)(structs_1.TypeName.reified(), field.coinType),
            reserveId: (0, reified_1.decodeFromJSONField)("address", field.reserveId),
            obligationId: (0, reified_1.decodeFromJSONField)("address", field.obligationId),
            ctokenAmount: (0, reified_1.decodeFromJSONField)("u64", field.ctokenAmount),
        });
    }
    static fromJSON(json) {
        if (json.$typeName !== WithdrawEvent.$typeName) {
            throw new Error("not a WithTwoGenerics json object");
        }
        return WithdrawEvent.fromJSONField(json);
    }
    static fromSuiParsedData(content) {
        if (content.dataType !== "moveObject") {
            throw new Error("not an object");
        }
        if (!isWithdrawEvent(content.type)) {
            throw new Error(`object at ${content.fields.id} is not a WithdrawEvent object`);
        }
        return WithdrawEvent.fromFieldsWithTypes(content);
    }
    static fromSuiObjectData(data) {
        if (data.bcs) {
            if (data.bcs.dataType !== "moveObject" ||
                !isWithdrawEvent(data.bcs.type)) {
                throw new Error(`object at is not a WithdrawEvent object`);
            }
            return WithdrawEvent.fromBcs((0, utils_1.fromB64)(data.bcs.bcsBytes));
        }
        if (data.content) {
            return WithdrawEvent.fromSuiParsedData(data.content);
        }
        throw new Error("Both `bcs` and `content` fields are missing from the data. Include `showBcs` or `showContent` in the request.");
    }
    static fetch(client, id) {
        return __awaiter(this, void 0, void 0, function* () {
            var _a, _b;
            const res = yield client.getObject({ id, options: { showBcs: true } });
            if (res.error) {
                throw new Error(`error fetching WithdrawEvent object at id ${id}: ${res.error.code}`);
            }
            if (((_b = (_a = res.data) === null || _a === void 0 ? void 0 : _a.bcs) === null || _b === void 0 ? void 0 : _b.dataType) !== "moveObject" ||
                !isWithdrawEvent(res.data.bcs.type)) {
                throw new Error(`object at id ${id} is not a WithdrawEvent object`);
            }
            return WithdrawEvent.fromSuiObjectData(res.data);
        });
    }
}
exports.WithdrawEvent = WithdrawEvent;
WithdrawEvent.$typeName = `${index_1.PKG_V1}::lending_market::WithdrawEvent`;
WithdrawEvent.$numTypeParams = 0;
WithdrawEvent.$isPhantom = [];

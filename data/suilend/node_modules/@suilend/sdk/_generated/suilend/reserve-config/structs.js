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
exports.ReserveConfigBuilder = exports.ReserveConfig = void 0;
exports.isReserveConfig = isReserveConfig;
exports.isReserveConfigBuilder = isReserveConfigBuilder;
const reified = __importStar(require("../../_framework/reified"));
const structs_1 = require("../../_dependencies/source/0x2/bag/structs");
const reified_1 = require("../../_framework/reified");
const util_1 = require("../../_framework/util");
const index_1 = require("../index");
const bcs_1 = require("@mysten/sui/bcs");
const utils_1 = require("@mysten/sui/utils");
/* ============================== ReserveConfig =============================== */
function isReserveConfig(type) {
    type = (0, util_1.compressSuiType)(type);
    return type === `${index_1.PKG_V1}::reserve_config::ReserveConfig`;
}
class ReserveConfig {
    constructor(typeArgs, fields) {
        this.__StructClass = true;
        this.$typeName = ReserveConfig.$typeName;
        this.$isPhantom = ReserveConfig.$isPhantom;
        this.$fullTypeName = (0, util_1.composeSuiType)(ReserveConfig.$typeName, ...typeArgs);
        this.$typeArgs = typeArgs;
        this.openLtvPct = fields.openLtvPct;
        this.closeLtvPct = fields.closeLtvPct;
        this.maxCloseLtvPct = fields.maxCloseLtvPct;
        this.borrowWeightBps = fields.borrowWeightBps;
        this.depositLimit = fields.depositLimit;
        this.borrowLimit = fields.borrowLimit;
        this.liquidationBonusBps = fields.liquidationBonusBps;
        this.maxLiquidationBonusBps = fields.maxLiquidationBonusBps;
        this.depositLimitUsd = fields.depositLimitUsd;
        this.borrowLimitUsd = fields.borrowLimitUsd;
        this.interestRateUtils = fields.interestRateUtils;
        this.interestRateAprs = fields.interestRateAprs;
        this.borrowFeeBps = fields.borrowFeeBps;
        this.spreadFeeBps = fields.spreadFeeBps;
        this.protocolLiquidationFeeBps = fields.protocolLiquidationFeeBps;
        this.isolated = fields.isolated;
        this.openAttributedBorrowLimitUsd = fields.openAttributedBorrowLimitUsd;
        this.closeAttributedBorrowLimitUsd = fields.closeAttributedBorrowLimitUsd;
        this.additionalFields = fields.additionalFields;
    }
    static reified() {
        return {
            typeName: ReserveConfig.$typeName,
            fullTypeName: (0, util_1.composeSuiType)(ReserveConfig.$typeName, ...[]),
            typeArgs: [],
            isPhantom: ReserveConfig.$isPhantom,
            reifiedTypeArgs: [],
            fromFields: (fields) => ReserveConfig.fromFields(fields),
            fromFieldsWithTypes: (item) => ReserveConfig.fromFieldsWithTypes(item),
            fromBcs: (data) => ReserveConfig.fromBcs(data),
            bcs: ReserveConfig.bcs,
            fromJSONField: (field) => ReserveConfig.fromJSONField(field),
            fromJSON: (json) => ReserveConfig.fromJSON(json),
            fromSuiParsedData: (content) => ReserveConfig.fromSuiParsedData(content),
            fromSuiObjectData: (content) => ReserveConfig.fromSuiObjectData(content),
            fetch: (client, id) => __awaiter(this, void 0, void 0, function* () { return ReserveConfig.fetch(client, id); }),
            new: (fields) => {
                return new ReserveConfig([], fields);
            },
            kind: "StructClassReified",
        };
    }
    static get r() {
        return ReserveConfig.reified();
    }
    static phantom() {
        return (0, reified_1.phantom)(ReserveConfig.reified());
    }
    static get p() {
        return ReserveConfig.phantom();
    }
    static get bcs() {
        return bcs_1.bcs.struct("ReserveConfig", {
            open_ltv_pct: bcs_1.bcs.u8(),
            close_ltv_pct: bcs_1.bcs.u8(),
            max_close_ltv_pct: bcs_1.bcs.u8(),
            borrow_weight_bps: bcs_1.bcs.u64(),
            deposit_limit: bcs_1.bcs.u64(),
            borrow_limit: bcs_1.bcs.u64(),
            liquidation_bonus_bps: bcs_1.bcs.u64(),
            max_liquidation_bonus_bps: bcs_1.bcs.u64(),
            deposit_limit_usd: bcs_1.bcs.u64(),
            borrow_limit_usd: bcs_1.bcs.u64(),
            interest_rate_utils: bcs_1.bcs.vector(bcs_1.bcs.u8()),
            interest_rate_aprs: bcs_1.bcs.vector(bcs_1.bcs.u64()),
            borrow_fee_bps: bcs_1.bcs.u64(),
            spread_fee_bps: bcs_1.bcs.u64(),
            protocol_liquidation_fee_bps: bcs_1.bcs.u64(),
            isolated: bcs_1.bcs.bool(),
            open_attributed_borrow_limit_usd: bcs_1.bcs.u64(),
            close_attributed_borrow_limit_usd: bcs_1.bcs.u64(),
            additional_fields: structs_1.Bag.bcs,
        });
    }
    static fromFields(fields) {
        return ReserveConfig.reified().new({
            openLtvPct: (0, reified_1.decodeFromFields)("u8", fields.open_ltv_pct),
            closeLtvPct: (0, reified_1.decodeFromFields)("u8", fields.close_ltv_pct),
            maxCloseLtvPct: (0, reified_1.decodeFromFields)("u8", fields.max_close_ltv_pct),
            borrowWeightBps: (0, reified_1.decodeFromFields)("u64", fields.borrow_weight_bps),
            depositLimit: (0, reified_1.decodeFromFields)("u64", fields.deposit_limit),
            borrowLimit: (0, reified_1.decodeFromFields)("u64", fields.borrow_limit),
            liquidationBonusBps: (0, reified_1.decodeFromFields)("u64", fields.liquidation_bonus_bps),
            maxLiquidationBonusBps: (0, reified_1.decodeFromFields)("u64", fields.max_liquidation_bonus_bps),
            depositLimitUsd: (0, reified_1.decodeFromFields)("u64", fields.deposit_limit_usd),
            borrowLimitUsd: (0, reified_1.decodeFromFields)("u64", fields.borrow_limit_usd),
            interestRateUtils: (0, reified_1.decodeFromFields)(reified.vector("u8"), fields.interest_rate_utils),
            interestRateAprs: (0, reified_1.decodeFromFields)(reified.vector("u64"), fields.interest_rate_aprs),
            borrowFeeBps: (0, reified_1.decodeFromFields)("u64", fields.borrow_fee_bps),
            spreadFeeBps: (0, reified_1.decodeFromFields)("u64", fields.spread_fee_bps),
            protocolLiquidationFeeBps: (0, reified_1.decodeFromFields)("u64", fields.protocol_liquidation_fee_bps),
            isolated: (0, reified_1.decodeFromFields)("bool", fields.isolated),
            openAttributedBorrowLimitUsd: (0, reified_1.decodeFromFields)("u64", fields.open_attributed_borrow_limit_usd),
            closeAttributedBorrowLimitUsd: (0, reified_1.decodeFromFields)("u64", fields.close_attributed_borrow_limit_usd),
            additionalFields: (0, reified_1.decodeFromFields)(structs_1.Bag.reified(), fields.additional_fields),
        });
    }
    static fromFieldsWithTypes(item) {
        if (!isReserveConfig(item.type)) {
            throw new Error("not a ReserveConfig type");
        }
        return ReserveConfig.reified().new({
            openLtvPct: (0, reified_1.decodeFromFieldsWithTypes)("u8", item.fields.open_ltv_pct),
            closeLtvPct: (0, reified_1.decodeFromFieldsWithTypes)("u8", item.fields.close_ltv_pct),
            maxCloseLtvPct: (0, reified_1.decodeFromFieldsWithTypes)("u8", item.fields.max_close_ltv_pct),
            borrowWeightBps: (0, reified_1.decodeFromFieldsWithTypes)("u64", item.fields.borrow_weight_bps),
            depositLimit: (0, reified_1.decodeFromFieldsWithTypes)("u64", item.fields.deposit_limit),
            borrowLimit: (0, reified_1.decodeFromFieldsWithTypes)("u64", item.fields.borrow_limit),
            liquidationBonusBps: (0, reified_1.decodeFromFieldsWithTypes)("u64", item.fields.liquidation_bonus_bps),
            maxLiquidationBonusBps: (0, reified_1.decodeFromFieldsWithTypes)("u64", item.fields.max_liquidation_bonus_bps),
            depositLimitUsd: (0, reified_1.decodeFromFieldsWithTypes)("u64", item.fields.deposit_limit_usd),
            borrowLimitUsd: (0, reified_1.decodeFromFieldsWithTypes)("u64", item.fields.borrow_limit_usd),
            interestRateUtils: (0, reified_1.decodeFromFieldsWithTypes)(reified.vector("u8"), item.fields.interest_rate_utils),
            interestRateAprs: (0, reified_1.decodeFromFieldsWithTypes)(reified.vector("u64"), item.fields.interest_rate_aprs),
            borrowFeeBps: (0, reified_1.decodeFromFieldsWithTypes)("u64", item.fields.borrow_fee_bps),
            spreadFeeBps: (0, reified_1.decodeFromFieldsWithTypes)("u64", item.fields.spread_fee_bps),
            protocolLiquidationFeeBps: (0, reified_1.decodeFromFieldsWithTypes)("u64", item.fields.protocol_liquidation_fee_bps),
            isolated: (0, reified_1.decodeFromFieldsWithTypes)("bool", item.fields.isolated),
            openAttributedBorrowLimitUsd: (0, reified_1.decodeFromFieldsWithTypes)("u64", item.fields.open_attributed_borrow_limit_usd),
            closeAttributedBorrowLimitUsd: (0, reified_1.decodeFromFieldsWithTypes)("u64", item.fields.close_attributed_borrow_limit_usd),
            additionalFields: (0, reified_1.decodeFromFieldsWithTypes)(structs_1.Bag.reified(), item.fields.additional_fields),
        });
    }
    static fromBcs(data) {
        return ReserveConfig.fromFields(ReserveConfig.bcs.parse(data));
    }
    toJSONField() {
        return {
            openLtvPct: this.openLtvPct,
            closeLtvPct: this.closeLtvPct,
            maxCloseLtvPct: this.maxCloseLtvPct,
            borrowWeightBps: this.borrowWeightBps.toString(),
            depositLimit: this.depositLimit.toString(),
            borrowLimit: this.borrowLimit.toString(),
            liquidationBonusBps: this.liquidationBonusBps.toString(),
            maxLiquidationBonusBps: this.maxLiquidationBonusBps.toString(),
            depositLimitUsd: this.depositLimitUsd.toString(),
            borrowLimitUsd: this.borrowLimitUsd.toString(),
            interestRateUtils: (0, reified_1.fieldToJSON)(`vector<u8>`, this.interestRateUtils),
            interestRateAprs: (0, reified_1.fieldToJSON)(`vector<u64>`, this.interestRateAprs),
            borrowFeeBps: this.borrowFeeBps.toString(),
            spreadFeeBps: this.spreadFeeBps.toString(),
            protocolLiquidationFeeBps: this.protocolLiquidationFeeBps.toString(),
            isolated: this.isolated,
            openAttributedBorrowLimitUsd: this.openAttributedBorrowLimitUsd.toString(),
            closeAttributedBorrowLimitUsd: this.closeAttributedBorrowLimitUsd.toString(),
            additionalFields: this.additionalFields.toJSONField(),
        };
    }
    toJSON() {
        return Object.assign({ $typeName: this.$typeName, $typeArgs: this.$typeArgs }, this.toJSONField());
    }
    static fromJSONField(field) {
        return ReserveConfig.reified().new({
            openLtvPct: (0, reified_1.decodeFromJSONField)("u8", field.openLtvPct),
            closeLtvPct: (0, reified_1.decodeFromJSONField)("u8", field.closeLtvPct),
            maxCloseLtvPct: (0, reified_1.decodeFromJSONField)("u8", field.maxCloseLtvPct),
            borrowWeightBps: (0, reified_1.decodeFromJSONField)("u64", field.borrowWeightBps),
            depositLimit: (0, reified_1.decodeFromJSONField)("u64", field.depositLimit),
            borrowLimit: (0, reified_1.decodeFromJSONField)("u64", field.borrowLimit),
            liquidationBonusBps: (0, reified_1.decodeFromJSONField)("u64", field.liquidationBonusBps),
            maxLiquidationBonusBps: (0, reified_1.decodeFromJSONField)("u64", field.maxLiquidationBonusBps),
            depositLimitUsd: (0, reified_1.decodeFromJSONField)("u64", field.depositLimitUsd),
            borrowLimitUsd: (0, reified_1.decodeFromJSONField)("u64", field.borrowLimitUsd),
            interestRateUtils: (0, reified_1.decodeFromJSONField)(reified.vector("u8"), field.interestRateUtils),
            interestRateAprs: (0, reified_1.decodeFromJSONField)(reified.vector("u64"), field.interestRateAprs),
            borrowFeeBps: (0, reified_1.decodeFromJSONField)("u64", field.borrowFeeBps),
            spreadFeeBps: (0, reified_1.decodeFromJSONField)("u64", field.spreadFeeBps),
            protocolLiquidationFeeBps: (0, reified_1.decodeFromJSONField)("u64", field.protocolLiquidationFeeBps),
            isolated: (0, reified_1.decodeFromJSONField)("bool", field.isolated),
            openAttributedBorrowLimitUsd: (0, reified_1.decodeFromJSONField)("u64", field.openAttributedBorrowLimitUsd),
            closeAttributedBorrowLimitUsd: (0, reified_1.decodeFromJSONField)("u64", field.closeAttributedBorrowLimitUsd),
            additionalFields: (0, reified_1.decodeFromJSONField)(structs_1.Bag.reified(), field.additionalFields),
        });
    }
    static fromJSON(json) {
        if (json.$typeName !== ReserveConfig.$typeName) {
            throw new Error("not a WithTwoGenerics json object");
        }
        return ReserveConfig.fromJSONField(json);
    }
    static fromSuiParsedData(content) {
        if (content.dataType !== "moveObject") {
            throw new Error("not an object");
        }
        if (!isReserveConfig(content.type)) {
            throw new Error(`object at ${content.fields.id} is not a ReserveConfig object`);
        }
        return ReserveConfig.fromFieldsWithTypes(content);
    }
    static fromSuiObjectData(data) {
        if (data.bcs) {
            if (data.bcs.dataType !== "moveObject" ||
                !isReserveConfig(data.bcs.type)) {
                throw new Error(`object at is not a ReserveConfig object`);
            }
            return ReserveConfig.fromBcs((0, utils_1.fromB64)(data.bcs.bcsBytes));
        }
        if (data.content) {
            return ReserveConfig.fromSuiParsedData(data.content);
        }
        throw new Error("Both `bcs` and `content` fields are missing from the data. Include `showBcs` or `showContent` in the request.");
    }
    static fetch(client, id) {
        return __awaiter(this, void 0, void 0, function* () {
            var _a, _b;
            const res = yield client.getObject({ id, options: { showBcs: true } });
            if (res.error) {
                throw new Error(`error fetching ReserveConfig object at id ${id}: ${res.error.code}`);
            }
            if (((_b = (_a = res.data) === null || _a === void 0 ? void 0 : _a.bcs) === null || _b === void 0 ? void 0 : _b.dataType) !== "moveObject" ||
                !isReserveConfig(res.data.bcs.type)) {
                throw new Error(`object at id ${id} is not a ReserveConfig object`);
            }
            return ReserveConfig.fromSuiObjectData(res.data);
        });
    }
}
exports.ReserveConfig = ReserveConfig;
ReserveConfig.$typeName = `${index_1.PKG_V1}::reserve_config::ReserveConfig`;
ReserveConfig.$numTypeParams = 0;
ReserveConfig.$isPhantom = [];
/* ============================== ReserveConfigBuilder =============================== */
function isReserveConfigBuilder(type) {
    type = (0, util_1.compressSuiType)(type);
    return type === `${index_1.PKG_V1}::reserve_config::ReserveConfigBuilder`;
}
class ReserveConfigBuilder {
    constructor(typeArgs, fields) {
        this.__StructClass = true;
        this.$typeName = ReserveConfigBuilder.$typeName;
        this.$isPhantom = ReserveConfigBuilder.$isPhantom;
        this.$fullTypeName = (0, util_1.composeSuiType)(ReserveConfigBuilder.$typeName, ...typeArgs);
        this.$typeArgs = typeArgs;
        this.fields = fields.fields;
    }
    static reified() {
        return {
            typeName: ReserveConfigBuilder.$typeName,
            fullTypeName: (0, util_1.composeSuiType)(ReserveConfigBuilder.$typeName, ...[]),
            typeArgs: [],
            isPhantom: ReserveConfigBuilder.$isPhantom,
            reifiedTypeArgs: [],
            fromFields: (fields) => ReserveConfigBuilder.fromFields(fields),
            fromFieldsWithTypes: (item) => ReserveConfigBuilder.fromFieldsWithTypes(item),
            fromBcs: (data) => ReserveConfigBuilder.fromBcs(data),
            bcs: ReserveConfigBuilder.bcs,
            fromJSONField: (field) => ReserveConfigBuilder.fromJSONField(field),
            fromJSON: (json) => ReserveConfigBuilder.fromJSON(json),
            fromSuiParsedData: (content) => ReserveConfigBuilder.fromSuiParsedData(content),
            fromSuiObjectData: (content) => ReserveConfigBuilder.fromSuiObjectData(content),
            fetch: (client, id) => __awaiter(this, void 0, void 0, function* () { return ReserveConfigBuilder.fetch(client, id); }),
            new: (fields) => {
                return new ReserveConfigBuilder([], fields);
            },
            kind: "StructClassReified",
        };
    }
    static get r() {
        return ReserveConfigBuilder.reified();
    }
    static phantom() {
        return (0, reified_1.phantom)(ReserveConfigBuilder.reified());
    }
    static get p() {
        return ReserveConfigBuilder.phantom();
    }
    static get bcs() {
        return bcs_1.bcs.struct("ReserveConfigBuilder", {
            fields: structs_1.Bag.bcs,
        });
    }
    static fromFields(fields) {
        return ReserveConfigBuilder.reified().new({
            fields: (0, reified_1.decodeFromFields)(structs_1.Bag.reified(), fields.fields),
        });
    }
    static fromFieldsWithTypes(item) {
        if (!isReserveConfigBuilder(item.type)) {
            throw new Error("not a ReserveConfigBuilder type");
        }
        return ReserveConfigBuilder.reified().new({
            fields: (0, reified_1.decodeFromFieldsWithTypes)(structs_1.Bag.reified(), item.fields.fields),
        });
    }
    static fromBcs(data) {
        return ReserveConfigBuilder.fromFields(ReserveConfigBuilder.bcs.parse(data));
    }
    toJSONField() {
        return {
            fields: this.fields.toJSONField(),
        };
    }
    toJSON() {
        return Object.assign({ $typeName: this.$typeName, $typeArgs: this.$typeArgs }, this.toJSONField());
    }
    static fromJSONField(field) {
        return ReserveConfigBuilder.reified().new({
            fields: (0, reified_1.decodeFromJSONField)(structs_1.Bag.reified(), field.fields),
        });
    }
    static fromJSON(json) {
        if (json.$typeName !== ReserveConfigBuilder.$typeName) {
            throw new Error("not a WithTwoGenerics json object");
        }
        return ReserveConfigBuilder.fromJSONField(json);
    }
    static fromSuiParsedData(content) {
        if (content.dataType !== "moveObject") {
            throw new Error("not an object");
        }
        if (!isReserveConfigBuilder(content.type)) {
            throw new Error(`object at ${content.fields.id} is not a ReserveConfigBuilder object`);
        }
        return ReserveConfigBuilder.fromFieldsWithTypes(content);
    }
    static fromSuiObjectData(data) {
        if (data.bcs) {
            if (data.bcs.dataType !== "moveObject" ||
                !isReserveConfigBuilder(data.bcs.type)) {
                throw new Error(`object at is not a ReserveConfigBuilder object`);
            }
            return ReserveConfigBuilder.fromBcs((0, utils_1.fromB64)(data.bcs.bcsBytes));
        }
        if (data.content) {
            return ReserveConfigBuilder.fromSuiParsedData(data.content);
        }
        throw new Error("Both `bcs` and `content` fields are missing from the data. Include `showBcs` or `showContent` in the request.");
    }
    static fetch(client, id) {
        return __awaiter(this, void 0, void 0, function* () {
            var _a, _b;
            const res = yield client.getObject({ id, options: { showBcs: true } });
            if (res.error) {
                throw new Error(`error fetching ReserveConfigBuilder object at id ${id}: ${res.error.code}`);
            }
            if (((_b = (_a = res.data) === null || _a === void 0 ? void 0 : _a.bcs) === null || _b === void 0 ? void 0 : _b.dataType) !== "moveObject" ||
                !isReserveConfigBuilder(res.data.bcs.type)) {
                throw new Error(`object at id ${id} is not a ReserveConfigBuilder object`);
            }
            return ReserveConfigBuilder.fromSuiObjectData(res.data);
        });
    }
}
exports.ReserveConfigBuilder = ReserveConfigBuilder;
ReserveConfigBuilder.$typeName = `${index_1.PKG_V1}::reserve_config::ReserveConfigBuilder`;
ReserveConfigBuilder.$numTypeParams = 0;
ReserveConfigBuilder.$isPhantom = [];

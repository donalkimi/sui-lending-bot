"use strict";
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
exports.RateLimiterConfig = exports.RateLimiter = void 0;
exports.isRateLimiter = isRateLimiter;
exports.isRateLimiterConfig = isRateLimiterConfig;
const reified_1 = require("../../_framework/reified");
const util_1 = require("../../_framework/util");
const structs_1 = require("../decimal/structs");
const index_1 = require("../index");
const bcs_1 = require("@mysten/sui/bcs");
const utils_1 = require("@mysten/sui/utils");
/* ============================== RateLimiter =============================== */
function isRateLimiter(type) {
    type = (0, util_1.compressSuiType)(type);
    return type === `${index_1.PKG_V1}::rate_limiter::RateLimiter`;
}
class RateLimiter {
    constructor(typeArgs, fields) {
        this.__StructClass = true;
        this.$typeName = RateLimiter.$typeName;
        this.$isPhantom = RateLimiter.$isPhantom;
        this.$fullTypeName = (0, util_1.composeSuiType)(RateLimiter.$typeName, ...typeArgs);
        this.$typeArgs = typeArgs;
        this.config = fields.config;
        this.prevQty = fields.prevQty;
        this.windowStart = fields.windowStart;
        this.curQty = fields.curQty;
    }
    static reified() {
        return {
            typeName: RateLimiter.$typeName,
            fullTypeName: (0, util_1.composeSuiType)(RateLimiter.$typeName, ...[]),
            typeArgs: [],
            isPhantom: RateLimiter.$isPhantom,
            reifiedTypeArgs: [],
            fromFields: (fields) => RateLimiter.fromFields(fields),
            fromFieldsWithTypes: (item) => RateLimiter.fromFieldsWithTypes(item),
            fromBcs: (data) => RateLimiter.fromBcs(data),
            bcs: RateLimiter.bcs,
            fromJSONField: (field) => RateLimiter.fromJSONField(field),
            fromJSON: (json) => RateLimiter.fromJSON(json),
            fromSuiParsedData: (content) => RateLimiter.fromSuiParsedData(content),
            fromSuiObjectData: (content) => RateLimiter.fromSuiObjectData(content),
            fetch: (client, id) => __awaiter(this, void 0, void 0, function* () { return RateLimiter.fetch(client, id); }),
            new: (fields) => {
                return new RateLimiter([], fields);
            },
            kind: "StructClassReified",
        };
    }
    static get r() {
        return RateLimiter.reified();
    }
    static phantom() {
        return (0, reified_1.phantom)(RateLimiter.reified());
    }
    static get p() {
        return RateLimiter.phantom();
    }
    static get bcs() {
        return bcs_1.bcs.struct("RateLimiter", {
            config: RateLimiterConfig.bcs,
            prev_qty: structs_1.Decimal.bcs,
            window_start: bcs_1.bcs.u64(),
            cur_qty: structs_1.Decimal.bcs,
        });
    }
    static fromFields(fields) {
        return RateLimiter.reified().new({
            config: (0, reified_1.decodeFromFields)(RateLimiterConfig.reified(), fields.config),
            prevQty: (0, reified_1.decodeFromFields)(structs_1.Decimal.reified(), fields.prev_qty),
            windowStart: (0, reified_1.decodeFromFields)("u64", fields.window_start),
            curQty: (0, reified_1.decodeFromFields)(structs_1.Decimal.reified(), fields.cur_qty),
        });
    }
    static fromFieldsWithTypes(item) {
        if (!isRateLimiter(item.type)) {
            throw new Error("not a RateLimiter type");
        }
        return RateLimiter.reified().new({
            config: (0, reified_1.decodeFromFieldsWithTypes)(RateLimiterConfig.reified(), item.fields.config),
            prevQty: (0, reified_1.decodeFromFieldsWithTypes)(structs_1.Decimal.reified(), item.fields.prev_qty),
            windowStart: (0, reified_1.decodeFromFieldsWithTypes)("u64", item.fields.window_start),
            curQty: (0, reified_1.decodeFromFieldsWithTypes)(structs_1.Decimal.reified(), item.fields.cur_qty),
        });
    }
    static fromBcs(data) {
        return RateLimiter.fromFields(RateLimiter.bcs.parse(data));
    }
    toJSONField() {
        return {
            config: this.config.toJSONField(),
            prevQty: this.prevQty.toJSONField(),
            windowStart: this.windowStart.toString(),
            curQty: this.curQty.toJSONField(),
        };
    }
    toJSON() {
        return Object.assign({ $typeName: this.$typeName, $typeArgs: this.$typeArgs }, this.toJSONField());
    }
    static fromJSONField(field) {
        return RateLimiter.reified().new({
            config: (0, reified_1.decodeFromJSONField)(RateLimiterConfig.reified(), field.config),
            prevQty: (0, reified_1.decodeFromJSONField)(structs_1.Decimal.reified(), field.prevQty),
            windowStart: (0, reified_1.decodeFromJSONField)("u64", field.windowStart),
            curQty: (0, reified_1.decodeFromJSONField)(structs_1.Decimal.reified(), field.curQty),
        });
    }
    static fromJSON(json) {
        if (json.$typeName !== RateLimiter.$typeName) {
            throw new Error("not a WithTwoGenerics json object");
        }
        return RateLimiter.fromJSONField(json);
    }
    static fromSuiParsedData(content) {
        if (content.dataType !== "moveObject") {
            throw new Error("not an object");
        }
        if (!isRateLimiter(content.type)) {
            throw new Error(`object at ${content.fields.id} is not a RateLimiter object`);
        }
        return RateLimiter.fromFieldsWithTypes(content);
    }
    static fromSuiObjectData(data) {
        if (data.bcs) {
            if (data.bcs.dataType !== "moveObject" || !isRateLimiter(data.bcs.type)) {
                throw new Error(`object at is not a RateLimiter object`);
            }
            return RateLimiter.fromBcs((0, utils_1.fromB64)(data.bcs.bcsBytes));
        }
        if (data.content) {
            return RateLimiter.fromSuiParsedData(data.content);
        }
        throw new Error("Both `bcs` and `content` fields are missing from the data. Include `showBcs` or `showContent` in the request.");
    }
    static fetch(client, id) {
        return __awaiter(this, void 0, void 0, function* () {
            var _a, _b;
            const res = yield client.getObject({ id, options: { showBcs: true } });
            if (res.error) {
                throw new Error(`error fetching RateLimiter object at id ${id}: ${res.error.code}`);
            }
            if (((_b = (_a = res.data) === null || _a === void 0 ? void 0 : _a.bcs) === null || _b === void 0 ? void 0 : _b.dataType) !== "moveObject" ||
                !isRateLimiter(res.data.bcs.type)) {
                throw new Error(`object at id ${id} is not a RateLimiter object`);
            }
            return RateLimiter.fromSuiObjectData(res.data);
        });
    }
}
exports.RateLimiter = RateLimiter;
RateLimiter.$typeName = `${index_1.PKG_V1}::rate_limiter::RateLimiter`;
RateLimiter.$numTypeParams = 0;
RateLimiter.$isPhantom = [];
/* ============================== RateLimiterConfig =============================== */
function isRateLimiterConfig(type) {
    type = (0, util_1.compressSuiType)(type);
    return type === `${index_1.PKG_V1}::rate_limiter::RateLimiterConfig`;
}
class RateLimiterConfig {
    constructor(typeArgs, fields) {
        this.__StructClass = true;
        this.$typeName = RateLimiterConfig.$typeName;
        this.$isPhantom = RateLimiterConfig.$isPhantom;
        this.$fullTypeName = (0, util_1.composeSuiType)(RateLimiterConfig.$typeName, ...typeArgs);
        this.$typeArgs = typeArgs;
        this.windowDuration = fields.windowDuration;
        this.maxOutflow = fields.maxOutflow;
    }
    static reified() {
        return {
            typeName: RateLimiterConfig.$typeName,
            fullTypeName: (0, util_1.composeSuiType)(RateLimiterConfig.$typeName, ...[]),
            typeArgs: [],
            isPhantom: RateLimiterConfig.$isPhantom,
            reifiedTypeArgs: [],
            fromFields: (fields) => RateLimiterConfig.fromFields(fields),
            fromFieldsWithTypes: (item) => RateLimiterConfig.fromFieldsWithTypes(item),
            fromBcs: (data) => RateLimiterConfig.fromBcs(data),
            bcs: RateLimiterConfig.bcs,
            fromJSONField: (field) => RateLimiterConfig.fromJSONField(field),
            fromJSON: (json) => RateLimiterConfig.fromJSON(json),
            fromSuiParsedData: (content) => RateLimiterConfig.fromSuiParsedData(content),
            fromSuiObjectData: (content) => RateLimiterConfig.fromSuiObjectData(content),
            fetch: (client, id) => __awaiter(this, void 0, void 0, function* () { return RateLimiterConfig.fetch(client, id); }),
            new: (fields) => {
                return new RateLimiterConfig([], fields);
            },
            kind: "StructClassReified",
        };
    }
    static get r() {
        return RateLimiterConfig.reified();
    }
    static phantom() {
        return (0, reified_1.phantom)(RateLimiterConfig.reified());
    }
    static get p() {
        return RateLimiterConfig.phantom();
    }
    static get bcs() {
        return bcs_1.bcs.struct("RateLimiterConfig", {
            window_duration: bcs_1.bcs.u64(),
            max_outflow: bcs_1.bcs.u64(),
        });
    }
    static fromFields(fields) {
        return RateLimiterConfig.reified().new({
            windowDuration: (0, reified_1.decodeFromFields)("u64", fields.window_duration),
            maxOutflow: (0, reified_1.decodeFromFields)("u64", fields.max_outflow),
        });
    }
    static fromFieldsWithTypes(item) {
        if (!isRateLimiterConfig(item.type)) {
            throw new Error("not a RateLimiterConfig type");
        }
        return RateLimiterConfig.reified().new({
            windowDuration: (0, reified_1.decodeFromFieldsWithTypes)("u64", item.fields.window_duration),
            maxOutflow: (0, reified_1.decodeFromFieldsWithTypes)("u64", item.fields.max_outflow),
        });
    }
    static fromBcs(data) {
        return RateLimiterConfig.fromFields(RateLimiterConfig.bcs.parse(data));
    }
    toJSONField() {
        return {
            windowDuration: this.windowDuration.toString(),
            maxOutflow: this.maxOutflow.toString(),
        };
    }
    toJSON() {
        return Object.assign({ $typeName: this.$typeName, $typeArgs: this.$typeArgs }, this.toJSONField());
    }
    static fromJSONField(field) {
        return RateLimiterConfig.reified().new({
            windowDuration: (0, reified_1.decodeFromJSONField)("u64", field.windowDuration),
            maxOutflow: (0, reified_1.decodeFromJSONField)("u64", field.maxOutflow),
        });
    }
    static fromJSON(json) {
        if (json.$typeName !== RateLimiterConfig.$typeName) {
            throw new Error("not a WithTwoGenerics json object");
        }
        return RateLimiterConfig.fromJSONField(json);
    }
    static fromSuiParsedData(content) {
        if (content.dataType !== "moveObject") {
            throw new Error("not an object");
        }
        if (!isRateLimiterConfig(content.type)) {
            throw new Error(`object at ${content.fields.id} is not a RateLimiterConfig object`);
        }
        return RateLimiterConfig.fromFieldsWithTypes(content);
    }
    static fromSuiObjectData(data) {
        if (data.bcs) {
            if (data.bcs.dataType !== "moveObject" ||
                !isRateLimiterConfig(data.bcs.type)) {
                throw new Error(`object at is not a RateLimiterConfig object`);
            }
            return RateLimiterConfig.fromBcs((0, utils_1.fromB64)(data.bcs.bcsBytes));
        }
        if (data.content) {
            return RateLimiterConfig.fromSuiParsedData(data.content);
        }
        throw new Error("Both `bcs` and `content` fields are missing from the data. Include `showBcs` or `showContent` in the request.");
    }
    static fetch(client, id) {
        return __awaiter(this, void 0, void 0, function* () {
            var _a, _b;
            const res = yield client.getObject({ id, options: { showBcs: true } });
            if (res.error) {
                throw new Error(`error fetching RateLimiterConfig object at id ${id}: ${res.error.code}`);
            }
            if (((_b = (_a = res.data) === null || _a === void 0 ? void 0 : _a.bcs) === null || _b === void 0 ? void 0 : _b.dataType) !== "moveObject" ||
                !isRateLimiterConfig(res.data.bcs.type)) {
                throw new Error(`object at id ${id} is not a RateLimiterConfig object`);
            }
            return RateLimiterConfig.fromSuiObjectData(res.data);
        });
    }
}
exports.RateLimiterConfig = RateLimiterConfig;
RateLimiterConfig.$typeName = `${index_1.PKG_V1}::rate_limiter::RateLimiterConfig`;
RateLimiterConfig.$numTypeParams = 0;
RateLimiterConfig.$isPhantom = [];

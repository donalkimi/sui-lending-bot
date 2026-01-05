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
exports.PriceInfoObject = exports.PriceInfo = void 0;
exports.isPriceInfo = isPriceInfo;
exports.isPriceInfoObject = isPriceInfoObject;
const reified_1 = require("../../../../_framework/reified");
const util_1 = require("../../../../_framework/util");
const structs_1 = require("../../0x2/object/structs");
const index_1 = require("../index");
const structs_2 = require("../price-feed/structs");
const bcs_1 = require("@mysten/sui/bcs");
const utils_1 = require("@mysten/sui/utils");
/* ============================== PriceInfo =============================== */
function isPriceInfo(type) {
    type = (0, util_1.compressSuiType)(type);
    return type === `${index_1.PKG_V1}::price_info::PriceInfo`;
}
class PriceInfo {
    constructor(typeArgs, fields) {
        this.__StructClass = true;
        this.$typeName = PriceInfo.$typeName;
        this.$isPhantom = PriceInfo.$isPhantom;
        this.$fullTypeName = (0, util_1.composeSuiType)(PriceInfo.$typeName, ...typeArgs);
        this.$typeArgs = typeArgs;
        this.attestationTime = fields.attestationTime;
        this.arrivalTime = fields.arrivalTime;
        this.priceFeed = fields.priceFeed;
    }
    static reified() {
        return {
            typeName: PriceInfo.$typeName,
            fullTypeName: (0, util_1.composeSuiType)(PriceInfo.$typeName, ...[]),
            typeArgs: [],
            isPhantom: PriceInfo.$isPhantom,
            reifiedTypeArgs: [],
            fromFields: (fields) => PriceInfo.fromFields(fields),
            fromFieldsWithTypes: (item) => PriceInfo.fromFieldsWithTypes(item),
            fromBcs: (data) => PriceInfo.fromBcs(data),
            bcs: PriceInfo.bcs,
            fromJSONField: (field) => PriceInfo.fromJSONField(field),
            fromJSON: (json) => PriceInfo.fromJSON(json),
            fromSuiParsedData: (content) => PriceInfo.fromSuiParsedData(content),
            fromSuiObjectData: (content) => PriceInfo.fromSuiObjectData(content),
            fetch: (client, id) => __awaiter(this, void 0, void 0, function* () { return PriceInfo.fetch(client, id); }),
            new: (fields) => {
                return new PriceInfo([], fields);
            },
            kind: "StructClassReified",
        };
    }
    static get r() {
        return PriceInfo.reified();
    }
    static phantom() {
        return (0, reified_1.phantom)(PriceInfo.reified());
    }
    static get p() {
        return PriceInfo.phantom();
    }
    static get bcs() {
        return bcs_1.bcs.struct("PriceInfo", {
            attestation_time: bcs_1.bcs.u64(),
            arrival_time: bcs_1.bcs.u64(),
            price_feed: structs_2.PriceFeed.bcs,
        });
    }
    static fromFields(fields) {
        return PriceInfo.reified().new({
            attestationTime: (0, reified_1.decodeFromFields)("u64", fields.attestation_time),
            arrivalTime: (0, reified_1.decodeFromFields)("u64", fields.arrival_time),
            priceFeed: (0, reified_1.decodeFromFields)(structs_2.PriceFeed.reified(), fields.price_feed),
        });
    }
    static fromFieldsWithTypes(item) {
        if (!isPriceInfo(item.type)) {
            throw new Error("not a PriceInfo type");
        }
        return PriceInfo.reified().new({
            attestationTime: (0, reified_1.decodeFromFieldsWithTypes)("u64", item.fields.attestation_time),
            arrivalTime: (0, reified_1.decodeFromFieldsWithTypes)("u64", item.fields.arrival_time),
            priceFeed: (0, reified_1.decodeFromFieldsWithTypes)(structs_2.PriceFeed.reified(), item.fields.price_feed),
        });
    }
    static fromBcs(data) {
        return PriceInfo.fromFields(PriceInfo.bcs.parse(data));
    }
    toJSONField() {
        return {
            attestationTime: this.attestationTime.toString(),
            arrivalTime: this.arrivalTime.toString(),
            priceFeed: this.priceFeed.toJSONField(),
        };
    }
    toJSON() {
        return Object.assign({ $typeName: this.$typeName, $typeArgs: this.$typeArgs }, this.toJSONField());
    }
    static fromJSONField(field) {
        return PriceInfo.reified().new({
            attestationTime: (0, reified_1.decodeFromJSONField)("u64", field.attestationTime),
            arrivalTime: (0, reified_1.decodeFromJSONField)("u64", field.arrivalTime),
            priceFeed: (0, reified_1.decodeFromJSONField)(structs_2.PriceFeed.reified(), field.priceFeed),
        });
    }
    static fromJSON(json) {
        if (json.$typeName !== PriceInfo.$typeName) {
            throw new Error("not a WithTwoGenerics json object");
        }
        return PriceInfo.fromJSONField(json);
    }
    static fromSuiParsedData(content) {
        if (content.dataType !== "moveObject") {
            throw new Error("not an object");
        }
        if (!isPriceInfo(content.type)) {
            throw new Error(`object at ${content.fields.id} is not a PriceInfo object`);
        }
        return PriceInfo.fromFieldsWithTypes(content);
    }
    static fromSuiObjectData(data) {
        if (data.bcs) {
            if (data.bcs.dataType !== "moveObject" || !isPriceInfo(data.bcs.type)) {
                throw new Error(`object at is not a PriceInfo object`);
            }
            return PriceInfo.fromBcs((0, utils_1.fromB64)(data.bcs.bcsBytes));
        }
        if (data.content) {
            return PriceInfo.fromSuiParsedData(data.content);
        }
        throw new Error("Both `bcs` and `content` fields are missing from the data. Include `showBcs` or `showContent` in the request.");
    }
    static fetch(client, id) {
        return __awaiter(this, void 0, void 0, function* () {
            var _a, _b;
            const res = yield client.getObject({ id, options: { showBcs: true } });
            if (res.error) {
                throw new Error(`error fetching PriceInfo object at id ${id}: ${res.error.code}`);
            }
            if (((_b = (_a = res.data) === null || _a === void 0 ? void 0 : _a.bcs) === null || _b === void 0 ? void 0 : _b.dataType) !== "moveObject" ||
                !isPriceInfo(res.data.bcs.type)) {
                throw new Error(`object at id ${id} is not a PriceInfo object`);
            }
            return PriceInfo.fromSuiObjectData(res.data);
        });
    }
}
exports.PriceInfo = PriceInfo;
PriceInfo.$typeName = `${index_1.PKG_V1}::price_info::PriceInfo`;
PriceInfo.$numTypeParams = 0;
PriceInfo.$isPhantom = [];
/* ============================== PriceInfoObject =============================== */
function isPriceInfoObject(type) {
    type = (0, util_1.compressSuiType)(type);
    return type === `${index_1.PKG_V1}::price_info::PriceInfoObject`;
}
class PriceInfoObject {
    constructor(typeArgs, fields) {
        this.__StructClass = true;
        this.$typeName = PriceInfoObject.$typeName;
        this.$isPhantom = PriceInfoObject.$isPhantom;
        this.$fullTypeName = (0, util_1.composeSuiType)(PriceInfoObject.$typeName, ...typeArgs);
        this.$typeArgs = typeArgs;
        this.id = fields.id;
        this.priceInfo = fields.priceInfo;
    }
    static reified() {
        return {
            typeName: PriceInfoObject.$typeName,
            fullTypeName: (0, util_1.composeSuiType)(PriceInfoObject.$typeName, ...[]),
            typeArgs: [],
            isPhantom: PriceInfoObject.$isPhantom,
            reifiedTypeArgs: [],
            fromFields: (fields) => PriceInfoObject.fromFields(fields),
            fromFieldsWithTypes: (item) => PriceInfoObject.fromFieldsWithTypes(item),
            fromBcs: (data) => PriceInfoObject.fromBcs(data),
            bcs: PriceInfoObject.bcs,
            fromJSONField: (field) => PriceInfoObject.fromJSONField(field),
            fromJSON: (json) => PriceInfoObject.fromJSON(json),
            fromSuiParsedData: (content) => PriceInfoObject.fromSuiParsedData(content),
            fromSuiObjectData: (content) => PriceInfoObject.fromSuiObjectData(content),
            fetch: (client, id) => __awaiter(this, void 0, void 0, function* () { return PriceInfoObject.fetch(client, id); }),
            new: (fields) => {
                return new PriceInfoObject([], fields);
            },
            kind: "StructClassReified",
        };
    }
    static get r() {
        return PriceInfoObject.reified();
    }
    static phantom() {
        return (0, reified_1.phantom)(PriceInfoObject.reified());
    }
    static get p() {
        return PriceInfoObject.phantom();
    }
    static get bcs() {
        return bcs_1.bcs.struct("PriceInfoObject", {
            id: structs_1.UID.bcs,
            price_info: PriceInfo.bcs,
        });
    }
    static fromFields(fields) {
        return PriceInfoObject.reified().new({
            id: (0, reified_1.decodeFromFields)(structs_1.UID.reified(), fields.id),
            priceInfo: (0, reified_1.decodeFromFields)(PriceInfo.reified(), fields.price_info),
        });
    }
    static fromFieldsWithTypes(item) {
        if (!isPriceInfoObject(item.type)) {
            throw new Error("not a PriceInfoObject type");
        }
        return PriceInfoObject.reified().new({
            id: (0, reified_1.decodeFromFieldsWithTypes)(structs_1.UID.reified(), item.fields.id),
            priceInfo: (0, reified_1.decodeFromFieldsWithTypes)(PriceInfo.reified(), item.fields.price_info),
        });
    }
    static fromBcs(data) {
        return PriceInfoObject.fromFields(PriceInfoObject.bcs.parse(data));
    }
    toJSONField() {
        return {
            id: this.id,
            priceInfo: this.priceInfo.toJSONField(),
        };
    }
    toJSON() {
        return Object.assign({ $typeName: this.$typeName, $typeArgs: this.$typeArgs }, this.toJSONField());
    }
    static fromJSONField(field) {
        return PriceInfoObject.reified().new({
            id: (0, reified_1.decodeFromJSONField)(structs_1.UID.reified(), field.id),
            priceInfo: (0, reified_1.decodeFromJSONField)(PriceInfo.reified(), field.priceInfo),
        });
    }
    static fromJSON(json) {
        if (json.$typeName !== PriceInfoObject.$typeName) {
            throw new Error("not a WithTwoGenerics json object");
        }
        return PriceInfoObject.fromJSONField(json);
    }
    static fromSuiParsedData(content) {
        if (content.dataType !== "moveObject") {
            throw new Error("not an object");
        }
        if (!isPriceInfoObject(content.type)) {
            throw new Error(`object at ${content.fields.id} is not a PriceInfoObject object`);
        }
        return PriceInfoObject.fromFieldsWithTypes(content);
    }
    static fromSuiObjectData(data) {
        if (data.bcs) {
            if (data.bcs.dataType !== "moveObject" ||
                !isPriceInfoObject(data.bcs.type)) {
                throw new Error(`object at is not a PriceInfoObject object`);
            }
            return PriceInfoObject.fromBcs((0, utils_1.fromB64)(data.bcs.bcsBytes));
        }
        if (data.content) {
            return PriceInfoObject.fromSuiParsedData(data.content);
        }
        throw new Error("Both `bcs` and `content` fields are missing from the data. Include `showBcs` or `showContent` in the request.");
    }
    static fetch(client, id) {
        return __awaiter(this, void 0, void 0, function* () {
            var _a, _b;
            const res = yield client.getObject({ id, options: { showBcs: true } });
            if (res.error) {
                throw new Error(`error fetching PriceInfoObject object at id ${id}: ${res.error.code}`);
            }
            if (((_b = (_a = res.data) === null || _a === void 0 ? void 0 : _a.bcs) === null || _b === void 0 ? void 0 : _b.dataType) !== "moveObject" ||
                !isPriceInfoObject(res.data.bcs.type)) {
                throw new Error(`object at id ${id} is not a PriceInfoObject object`);
            }
            return PriceInfoObject.fromSuiObjectData(res.data);
        });
    }
}
exports.PriceInfoObject = PriceInfoObject;
PriceInfoObject.$typeName = `${index_1.PKG_V1}::price_info::PriceInfoObject`;
PriceInfoObject.$numTypeParams = 0;
PriceInfoObject.$isPhantom = [];

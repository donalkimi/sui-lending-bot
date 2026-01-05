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
exports.Price = void 0;
exports.isPrice = isPrice;
const reified_1 = require("../../../../_framework/reified");
const util_1 = require("../../../../_framework/util");
const structs_1 = require("../i64/structs");
const index_1 = require("../index");
const bcs_1 = require("@mysten/sui/bcs");
const utils_1 = require("@mysten/sui/utils");
/* ============================== Price =============================== */
function isPrice(type) {
    type = (0, util_1.compressSuiType)(type);
    return type === `${index_1.PKG_V1}::price::Price`;
}
class Price {
    constructor(typeArgs, fields) {
        this.__StructClass = true;
        this.$typeName = Price.$typeName;
        this.$isPhantom = Price.$isPhantom;
        this.$fullTypeName = (0, util_1.composeSuiType)(Price.$typeName, ...typeArgs);
        this.$typeArgs = typeArgs;
        this.price = fields.price;
        this.conf = fields.conf;
        this.expo = fields.expo;
        this.timestamp = fields.timestamp;
    }
    static reified() {
        return {
            typeName: Price.$typeName,
            fullTypeName: (0, util_1.composeSuiType)(Price.$typeName, ...[]),
            typeArgs: [],
            isPhantom: Price.$isPhantom,
            reifiedTypeArgs: [],
            fromFields: (fields) => Price.fromFields(fields),
            fromFieldsWithTypes: (item) => Price.fromFieldsWithTypes(item),
            fromBcs: (data) => Price.fromBcs(data),
            bcs: Price.bcs,
            fromJSONField: (field) => Price.fromJSONField(field),
            fromJSON: (json) => Price.fromJSON(json),
            fromSuiParsedData: (content) => Price.fromSuiParsedData(content),
            fromSuiObjectData: (content) => Price.fromSuiObjectData(content),
            fetch: (client, id) => __awaiter(this, void 0, void 0, function* () { return Price.fetch(client, id); }),
            new: (fields) => {
                return new Price([], fields);
            },
            kind: "StructClassReified",
        };
    }
    static get r() {
        return Price.reified();
    }
    static phantom() {
        return (0, reified_1.phantom)(Price.reified());
    }
    static get p() {
        return Price.phantom();
    }
    static get bcs() {
        return bcs_1.bcs.struct("Price", {
            price: structs_1.I64.bcs,
            conf: bcs_1.bcs.u64(),
            expo: structs_1.I64.bcs,
            timestamp: bcs_1.bcs.u64(),
        });
    }
    static fromFields(fields) {
        return Price.reified().new({
            price: (0, reified_1.decodeFromFields)(structs_1.I64.reified(), fields.price),
            conf: (0, reified_1.decodeFromFields)("u64", fields.conf),
            expo: (0, reified_1.decodeFromFields)(structs_1.I64.reified(), fields.expo),
            timestamp: (0, reified_1.decodeFromFields)("u64", fields.timestamp),
        });
    }
    static fromFieldsWithTypes(item) {
        if (!isPrice(item.type)) {
            throw new Error("not a Price type");
        }
        return Price.reified().new({
            price: (0, reified_1.decodeFromFieldsWithTypes)(structs_1.I64.reified(), item.fields.price),
            conf: (0, reified_1.decodeFromFieldsWithTypes)("u64", item.fields.conf),
            expo: (0, reified_1.decodeFromFieldsWithTypes)(structs_1.I64.reified(), item.fields.expo),
            timestamp: (0, reified_1.decodeFromFieldsWithTypes)("u64", item.fields.timestamp),
        });
    }
    static fromBcs(data) {
        return Price.fromFields(Price.bcs.parse(data));
    }
    toJSONField() {
        return {
            price: this.price.toJSONField(),
            conf: this.conf.toString(),
            expo: this.expo.toJSONField(),
            timestamp: this.timestamp.toString(),
        };
    }
    toJSON() {
        return Object.assign({ $typeName: this.$typeName, $typeArgs: this.$typeArgs }, this.toJSONField());
    }
    static fromJSONField(field) {
        return Price.reified().new({
            price: (0, reified_1.decodeFromJSONField)(structs_1.I64.reified(), field.price),
            conf: (0, reified_1.decodeFromJSONField)("u64", field.conf),
            expo: (0, reified_1.decodeFromJSONField)(structs_1.I64.reified(), field.expo),
            timestamp: (0, reified_1.decodeFromJSONField)("u64", field.timestamp),
        });
    }
    static fromJSON(json) {
        if (json.$typeName !== Price.$typeName) {
            throw new Error("not a WithTwoGenerics json object");
        }
        return Price.fromJSONField(json);
    }
    static fromSuiParsedData(content) {
        if (content.dataType !== "moveObject") {
            throw new Error("not an object");
        }
        if (!isPrice(content.type)) {
            throw new Error(`object at ${content.fields.id} is not a Price object`);
        }
        return Price.fromFieldsWithTypes(content);
    }
    static fromSuiObjectData(data) {
        if (data.bcs) {
            if (data.bcs.dataType !== "moveObject" || !isPrice(data.bcs.type)) {
                throw new Error(`object at is not a Price object`);
            }
            return Price.fromBcs((0, utils_1.fromB64)(data.bcs.bcsBytes));
        }
        if (data.content) {
            return Price.fromSuiParsedData(data.content);
        }
        throw new Error("Both `bcs` and `content` fields are missing from the data. Include `showBcs` or `showContent` in the request.");
    }
    static fetch(client, id) {
        return __awaiter(this, void 0, void 0, function* () {
            var _a, _b;
            const res = yield client.getObject({ id, options: { showBcs: true } });
            if (res.error) {
                throw new Error(`error fetching Price object at id ${id}: ${res.error.code}`);
            }
            if (((_b = (_a = res.data) === null || _a === void 0 ? void 0 : _a.bcs) === null || _b === void 0 ? void 0 : _b.dataType) !== "moveObject" ||
                !isPrice(res.data.bcs.type)) {
                throw new Error(`object at id ${id} is not a Price object`);
            }
            return Price.fromSuiObjectData(res.data);
        });
    }
}
exports.Price = Price;
Price.$typeName = `${index_1.PKG_V1}::price::Price`;
Price.$numTypeParams = 0;
Price.$isPhantom = [];

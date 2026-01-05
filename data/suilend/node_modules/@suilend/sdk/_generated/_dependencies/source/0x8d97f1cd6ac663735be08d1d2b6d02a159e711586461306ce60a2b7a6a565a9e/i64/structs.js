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
exports.I64 = void 0;
exports.isI64 = isI64;
const reified_1 = require("../../../../_framework/reified");
const util_1 = require("../../../../_framework/util");
const index_1 = require("../index");
const bcs_1 = require("@mysten/sui/bcs");
const utils_1 = require("@mysten/sui/utils");
/* ============================== I64 =============================== */
function isI64(type) {
    type = (0, util_1.compressSuiType)(type);
    return type === `${index_1.PKG_V1}::i64::I64`;
}
class I64 {
    constructor(typeArgs, fields) {
        this.__StructClass = true;
        this.$typeName = I64.$typeName;
        this.$isPhantom = I64.$isPhantom;
        this.$fullTypeName = (0, util_1.composeSuiType)(I64.$typeName, ...typeArgs);
        this.$typeArgs = typeArgs;
        this.negative = fields.negative;
        this.magnitude = fields.magnitude;
    }
    static reified() {
        return {
            typeName: I64.$typeName,
            fullTypeName: (0, util_1.composeSuiType)(I64.$typeName, ...[]),
            typeArgs: [],
            isPhantom: I64.$isPhantom,
            reifiedTypeArgs: [],
            fromFields: (fields) => I64.fromFields(fields),
            fromFieldsWithTypes: (item) => I64.fromFieldsWithTypes(item),
            fromBcs: (data) => I64.fromBcs(data),
            bcs: I64.bcs,
            fromJSONField: (field) => I64.fromJSONField(field),
            fromJSON: (json) => I64.fromJSON(json),
            fromSuiParsedData: (content) => I64.fromSuiParsedData(content),
            fromSuiObjectData: (content) => I64.fromSuiObjectData(content),
            fetch: (client, id) => __awaiter(this, void 0, void 0, function* () { return I64.fetch(client, id); }),
            new: (fields) => {
                return new I64([], fields);
            },
            kind: "StructClassReified",
        };
    }
    static get r() {
        return I64.reified();
    }
    static phantom() {
        return (0, reified_1.phantom)(I64.reified());
    }
    static get p() {
        return I64.phantom();
    }
    static get bcs() {
        return bcs_1.bcs.struct("I64", {
            negative: bcs_1.bcs.bool(),
            magnitude: bcs_1.bcs.u64(),
        });
    }
    static fromFields(fields) {
        return I64.reified().new({
            negative: (0, reified_1.decodeFromFields)("bool", fields.negative),
            magnitude: (0, reified_1.decodeFromFields)("u64", fields.magnitude),
        });
    }
    static fromFieldsWithTypes(item) {
        if (!isI64(item.type)) {
            throw new Error("not a I64 type");
        }
        return I64.reified().new({
            negative: (0, reified_1.decodeFromFieldsWithTypes)("bool", item.fields.negative),
            magnitude: (0, reified_1.decodeFromFieldsWithTypes)("u64", item.fields.magnitude),
        });
    }
    static fromBcs(data) {
        return I64.fromFields(I64.bcs.parse(data));
    }
    toJSONField() {
        return {
            negative: this.negative,
            magnitude: this.magnitude.toString(),
        };
    }
    toJSON() {
        return Object.assign({ $typeName: this.$typeName, $typeArgs: this.$typeArgs }, this.toJSONField());
    }
    static fromJSONField(field) {
        return I64.reified().new({
            negative: (0, reified_1.decodeFromJSONField)("bool", field.negative),
            magnitude: (0, reified_1.decodeFromJSONField)("u64", field.magnitude),
        });
    }
    static fromJSON(json) {
        if (json.$typeName !== I64.$typeName) {
            throw new Error("not a WithTwoGenerics json object");
        }
        return I64.fromJSONField(json);
    }
    static fromSuiParsedData(content) {
        if (content.dataType !== "moveObject") {
            throw new Error("not an object");
        }
        if (!isI64(content.type)) {
            throw new Error(`object at ${content.fields.id} is not a I64 object`);
        }
        return I64.fromFieldsWithTypes(content);
    }
    static fromSuiObjectData(data) {
        if (data.bcs) {
            if (data.bcs.dataType !== "moveObject" || !isI64(data.bcs.type)) {
                throw new Error(`object at is not a I64 object`);
            }
            return I64.fromBcs((0, utils_1.fromB64)(data.bcs.bcsBytes));
        }
        if (data.content) {
            return I64.fromSuiParsedData(data.content);
        }
        throw new Error("Both `bcs` and `content` fields are missing from the data. Include `showBcs` or `showContent` in the request.");
    }
    static fetch(client, id) {
        return __awaiter(this, void 0, void 0, function* () {
            var _a, _b;
            const res = yield client.getObject({ id, options: { showBcs: true } });
            if (res.error) {
                throw new Error(`error fetching I64 object at id ${id}: ${res.error.code}`);
            }
            if (((_b = (_a = res.data) === null || _a === void 0 ? void 0 : _a.bcs) === null || _b === void 0 ? void 0 : _b.dataType) !== "moveObject" || !isI64(res.data.bcs.type)) {
                throw new Error(`object at id ${id} is not a I64 object`);
            }
            return I64.fromSuiObjectData(res.data);
        });
    }
}
exports.I64 = I64;
I64.$typeName = `${index_1.PKG_V1}::i64::I64`;
I64.$numTypeParams = 0;
I64.$isPhantom = [];

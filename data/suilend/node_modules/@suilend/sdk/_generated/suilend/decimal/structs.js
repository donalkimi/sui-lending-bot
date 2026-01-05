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
exports.Decimal = void 0;
exports.isDecimal = isDecimal;
const reified_1 = require("../../_framework/reified");
const util_1 = require("../../_framework/util");
const index_1 = require("../index");
const bcs_1 = require("@mysten/sui/bcs");
const utils_1 = require("@mysten/sui/utils");
/* ============================== Decimal =============================== */
function isDecimal(type) {
    type = (0, util_1.compressSuiType)(type);
    return type === `${index_1.PKG_V1}::decimal::Decimal`;
}
class Decimal {
    constructor(typeArgs, fields) {
        this.__StructClass = true;
        this.$typeName = Decimal.$typeName;
        this.$isPhantom = Decimal.$isPhantom;
        this.$fullTypeName = (0, util_1.composeSuiType)(Decimal.$typeName, ...typeArgs);
        this.$typeArgs = typeArgs;
        this.value = fields.value;
    }
    static reified() {
        return {
            typeName: Decimal.$typeName,
            fullTypeName: (0, util_1.composeSuiType)(Decimal.$typeName, ...[]),
            typeArgs: [],
            isPhantom: Decimal.$isPhantom,
            reifiedTypeArgs: [],
            fromFields: (fields) => Decimal.fromFields(fields),
            fromFieldsWithTypes: (item) => Decimal.fromFieldsWithTypes(item),
            fromBcs: (data) => Decimal.fromBcs(data),
            bcs: Decimal.bcs,
            fromJSONField: (field) => Decimal.fromJSONField(field),
            fromJSON: (json) => Decimal.fromJSON(json),
            fromSuiParsedData: (content) => Decimal.fromSuiParsedData(content),
            fromSuiObjectData: (content) => Decimal.fromSuiObjectData(content),
            fetch: (client, id) => __awaiter(this, void 0, void 0, function* () { return Decimal.fetch(client, id); }),
            new: (fields) => {
                return new Decimal([], fields);
            },
            kind: "StructClassReified",
        };
    }
    static get r() {
        return Decimal.reified();
    }
    static phantom() {
        return (0, reified_1.phantom)(Decimal.reified());
    }
    static get p() {
        return Decimal.phantom();
    }
    static get bcs() {
        return bcs_1.bcs.struct("Decimal", {
            value: bcs_1.bcs.u256(),
        });
    }
    static fromFields(fields) {
        return Decimal.reified().new({
            value: (0, reified_1.decodeFromFields)("u256", fields.value),
        });
    }
    static fromFieldsWithTypes(item) {
        if (!isDecimal(item.type)) {
            throw new Error("not a Decimal type");
        }
        return Decimal.reified().new({
            value: (0, reified_1.decodeFromFieldsWithTypes)("u256", item.fields.value),
        });
    }
    static fromBcs(data) {
        return Decimal.fromFields(Decimal.bcs.parse(data));
    }
    toJSONField() {
        return {
            value: this.value.toString(),
        };
    }
    toJSON() {
        return Object.assign({ $typeName: this.$typeName, $typeArgs: this.$typeArgs }, this.toJSONField());
    }
    static fromJSONField(field) {
        return Decimal.reified().new({
            value: (0, reified_1.decodeFromJSONField)("u256", field.value),
        });
    }
    static fromJSON(json) {
        if (json.$typeName !== Decimal.$typeName) {
            throw new Error("not a WithTwoGenerics json object");
        }
        return Decimal.fromJSONField(json);
    }
    static fromSuiParsedData(content) {
        if (content.dataType !== "moveObject") {
            throw new Error("not an object");
        }
        if (!isDecimal(content.type)) {
            throw new Error(`object at ${content.fields.id} is not a Decimal object`);
        }
        return Decimal.fromFieldsWithTypes(content);
    }
    static fromSuiObjectData(data) {
        if (data.bcs) {
            if (data.bcs.dataType !== "moveObject" || !isDecimal(data.bcs.type)) {
                throw new Error(`object at is not a Decimal object`);
            }
            return Decimal.fromBcs((0, utils_1.fromB64)(data.bcs.bcsBytes));
        }
        if (data.content) {
            return Decimal.fromSuiParsedData(data.content);
        }
        throw new Error("Both `bcs` and `content` fields are missing from the data. Include `showBcs` or `showContent` in the request.");
    }
    static fetch(client, id) {
        return __awaiter(this, void 0, void 0, function* () {
            var _a, _b;
            const res = yield client.getObject({ id, options: { showBcs: true } });
            if (res.error) {
                throw new Error(`error fetching Decimal object at id ${id}: ${res.error.code}`);
            }
            if (((_b = (_a = res.data) === null || _a === void 0 ? void 0 : _a.bcs) === null || _b === void 0 ? void 0 : _b.dataType) !== "moveObject" ||
                !isDecimal(res.data.bcs.type)) {
                throw new Error(`object at id ${id} is not a Decimal object`);
            }
            return Decimal.fromSuiObjectData(res.data);
        });
    }
}
exports.Decimal = Decimal;
Decimal.$typeName = `${index_1.PKG_V1}::decimal::Decimal`;
Decimal.$numTypeParams = 0;
Decimal.$isPhantom = [];

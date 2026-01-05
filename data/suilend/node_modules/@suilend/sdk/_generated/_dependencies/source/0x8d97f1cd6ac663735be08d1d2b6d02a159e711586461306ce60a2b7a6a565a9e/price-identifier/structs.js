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
exports.PriceIdentifier = void 0;
exports.isPriceIdentifier = isPriceIdentifier;
const reified = __importStar(require("../../../../_framework/reified"));
const reified_1 = require("../../../../_framework/reified");
const util_1 = require("../../../../_framework/util");
const index_1 = require("../index");
const bcs_1 = require("@mysten/sui/bcs");
const utils_1 = require("@mysten/sui/utils");
/* ============================== PriceIdentifier =============================== */
function isPriceIdentifier(type) {
    type = (0, util_1.compressSuiType)(type);
    return type === `${index_1.PKG_V1}::price_identifier::PriceIdentifier`;
}
class PriceIdentifier {
    constructor(typeArgs, fields) {
        this.__StructClass = true;
        this.$typeName = PriceIdentifier.$typeName;
        this.$isPhantom = PriceIdentifier.$isPhantom;
        this.$fullTypeName = (0, util_1.composeSuiType)(PriceIdentifier.$typeName, ...typeArgs);
        this.$typeArgs = typeArgs;
        this.bytes = fields.bytes;
    }
    static reified() {
        return {
            typeName: PriceIdentifier.$typeName,
            fullTypeName: (0, util_1.composeSuiType)(PriceIdentifier.$typeName, ...[]),
            typeArgs: [],
            isPhantom: PriceIdentifier.$isPhantom,
            reifiedTypeArgs: [],
            fromFields: (fields) => PriceIdentifier.fromFields(fields),
            fromFieldsWithTypes: (item) => PriceIdentifier.fromFieldsWithTypes(item),
            fromBcs: (data) => PriceIdentifier.fromBcs(data),
            bcs: PriceIdentifier.bcs,
            fromJSONField: (field) => PriceIdentifier.fromJSONField(field),
            fromJSON: (json) => PriceIdentifier.fromJSON(json),
            fromSuiParsedData: (content) => PriceIdentifier.fromSuiParsedData(content),
            fromSuiObjectData: (content) => PriceIdentifier.fromSuiObjectData(content),
            fetch: (client, id) => __awaiter(this, void 0, void 0, function* () { return PriceIdentifier.fetch(client, id); }),
            new: (fields) => {
                return new PriceIdentifier([], fields);
            },
            kind: "StructClassReified",
        };
    }
    static get r() {
        return PriceIdentifier.reified();
    }
    static phantom() {
        return (0, reified_1.phantom)(PriceIdentifier.reified());
    }
    static get p() {
        return PriceIdentifier.phantom();
    }
    static get bcs() {
        return bcs_1.bcs.struct("PriceIdentifier", {
            bytes: bcs_1.bcs.vector(bcs_1.bcs.u8()),
        });
    }
    static fromFields(fields) {
        return PriceIdentifier.reified().new({
            bytes: (0, reified_1.decodeFromFields)(reified.vector("u8"), fields.bytes),
        });
    }
    static fromFieldsWithTypes(item) {
        if (!isPriceIdentifier(item.type)) {
            throw new Error("not a PriceIdentifier type");
        }
        return PriceIdentifier.reified().new({
            bytes: (0, reified_1.decodeFromFieldsWithTypes)(reified.vector("u8"), item.fields.bytes),
        });
    }
    static fromBcs(data) {
        return PriceIdentifier.fromFields(PriceIdentifier.bcs.parse(data));
    }
    toJSONField() {
        return {
            bytes: (0, reified_1.fieldToJSON)(`vector<u8>`, this.bytes),
        };
    }
    toJSON() {
        return Object.assign({ $typeName: this.$typeName, $typeArgs: this.$typeArgs }, this.toJSONField());
    }
    static fromJSONField(field) {
        return PriceIdentifier.reified().new({
            bytes: (0, reified_1.decodeFromJSONField)(reified.vector("u8"), field.bytes),
        });
    }
    static fromJSON(json) {
        if (json.$typeName !== PriceIdentifier.$typeName) {
            throw new Error("not a WithTwoGenerics json object");
        }
        return PriceIdentifier.fromJSONField(json);
    }
    static fromSuiParsedData(content) {
        if (content.dataType !== "moveObject") {
            throw new Error("not an object");
        }
        if (!isPriceIdentifier(content.type)) {
            throw new Error(`object at ${content.fields.id} is not a PriceIdentifier object`);
        }
        return PriceIdentifier.fromFieldsWithTypes(content);
    }
    static fromSuiObjectData(data) {
        if (data.bcs) {
            if (data.bcs.dataType !== "moveObject" ||
                !isPriceIdentifier(data.bcs.type)) {
                throw new Error(`object at is not a PriceIdentifier object`);
            }
            return PriceIdentifier.fromBcs((0, utils_1.fromB64)(data.bcs.bcsBytes));
        }
        if (data.content) {
            return PriceIdentifier.fromSuiParsedData(data.content);
        }
        throw new Error("Both `bcs` and `content` fields are missing from the data. Include `showBcs` or `showContent` in the request.");
    }
    static fetch(client, id) {
        return __awaiter(this, void 0, void 0, function* () {
            var _a, _b;
            const res = yield client.getObject({ id, options: { showBcs: true } });
            if (res.error) {
                throw new Error(`error fetching PriceIdentifier object at id ${id}: ${res.error.code}`);
            }
            if (((_b = (_a = res.data) === null || _a === void 0 ? void 0 : _a.bcs) === null || _b === void 0 ? void 0 : _b.dataType) !== "moveObject" ||
                !isPriceIdentifier(res.data.bcs.type)) {
                throw new Error(`object at id ${id} is not a PriceIdentifier object`);
            }
            return PriceIdentifier.fromSuiObjectData(res.data);
        });
    }
}
exports.PriceIdentifier = PriceIdentifier;
PriceIdentifier.$typeName = `${index_1.PKG_V1}::price_identifier::PriceIdentifier`;
PriceIdentifier.$numTypeParams = 0;
PriceIdentifier.$isPhantom = [];

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
exports.Option = void 0;
exports.isOption = isOption;
const reified = __importStar(require("../../../../_framework/reified"));
const reified_1 = require("../../../../_framework/reified");
const util_1 = require("../../../../_framework/util");
const index_1 = require("../index");
const bcs_1 = require("@mysten/sui/bcs");
const utils_1 = require("@mysten/sui/utils");
/* ============================== Option =============================== */
function isOption(type) {
    type = (0, util_1.compressSuiType)(type);
    return type.startsWith(`${index_1.PKG_V13}::option::Option` + "<");
}
class Option {
    constructor(typeArgs, fields) {
        this.__StructClass = true;
        this.__inner = null; // for type checking in reified.ts
        this.$typeName = Option.$typeName;
        this.$isPhantom = Option.$isPhantom;
        this.$fullTypeName = (0, util_1.composeSuiType)(Option.$typeName, ...typeArgs);
        this.$typeArgs = typeArgs;
        this.vec = fields.vec;
    }
    static reified(Element) {
        return {
            typeName: Option.$typeName,
            fullTypeName: (0, util_1.composeSuiType)(Option.$typeName, ...[(0, reified_1.extractType)(Element)]),
            typeArgs: [(0, reified_1.extractType)(Element)],
            isPhantom: Option.$isPhantom,
            reifiedTypeArgs: [Element],
            fromFields: (fields) => Option.fromFields(Element, fields),
            fromFieldsWithTypes: (item) => Option.fromFieldsWithTypes(Element, item),
            fromBcs: (data) => Option.fromBcs(Element, data),
            bcs: Option.bcs((0, reified_1.toBcs)(Element)),
            fromJSONField: (field) => Option.fromJSONField(Element, field),
            fromJSON: (json) => Option.fromJSON(Element, json),
            fromSuiParsedData: (content) => Option.fromSuiParsedData(Element, content),
            fromSuiObjectData: (content) => Option.fromSuiObjectData(Element, content),
            fetch: (client, id) => __awaiter(this, void 0, void 0, function* () { return Option.fetch(client, Element, id); }),
            new: (fields) => {
                return new Option([(0, reified_1.extractType)(Element)], fields);
            },
            kind: "StructClassReified",
        };
    }
    static get r() {
        return Option.reified;
    }
    static phantom(Element) {
        return (0, reified_1.phantom)(Option.reified(Element));
    }
    static get p() {
        return Option.phantom;
    }
    static get bcs() {
        return (Element) => bcs_1.bcs.struct(`Option<${Element.name}>`, {
            vec: bcs_1.bcs.vector(Element),
        });
    }
    static fromFields(typeArg, fields) {
        return Option.reified(typeArg).new({
            vec: (0, reified_1.decodeFromFields)(reified.vector(typeArg), fields.vec),
        });
    }
    static fromFieldsWithTypes(typeArg, item) {
        if (!isOption(item.type)) {
            throw new Error("not a Option type");
        }
        (0, reified_1.assertFieldsWithTypesArgsMatch)(item, [typeArg]);
        return Option.reified(typeArg).new({
            vec: (0, reified_1.decodeFromFieldsWithTypes)(reified.vector(typeArg), item.fields.vec),
        });
    }
    static fromBcs(typeArg, data) {
        const typeArgs = [typeArg];
        return Option.fromFields(typeArg, Option.bcs((0, reified_1.toBcs)(typeArgs[0])).parse(data));
    }
    toJSONField() {
        return {
            vec: (0, reified_1.fieldToJSON)(`vector<${this.$typeArgs[0]}>`, this.vec),
        };
    }
    toJSON() {
        return Object.assign({ $typeName: this.$typeName, $typeArgs: this.$typeArgs }, this.toJSONField());
    }
    static fromJSONField(typeArg, field) {
        return Option.reified(typeArg).new({
            vec: (0, reified_1.decodeFromJSONField)(reified.vector(typeArg), field.vec),
        });
    }
    static fromJSON(typeArg, json) {
        if (json.$typeName !== Option.$typeName) {
            throw new Error("not a WithTwoGenerics json object");
        }
        (0, reified_1.assertReifiedTypeArgsMatch)((0, util_1.composeSuiType)(Option.$typeName, (0, reified_1.extractType)(typeArg)), json.$typeArgs, [typeArg]);
        return Option.fromJSONField(typeArg, json);
    }
    static fromSuiParsedData(typeArg, content) {
        if (content.dataType !== "moveObject") {
            throw new Error("not an object");
        }
        if (!isOption(content.type)) {
            throw new Error(`object at ${content.fields.id} is not a Option object`);
        }
        return Option.fromFieldsWithTypes(typeArg, content);
    }
    static fromSuiObjectData(typeArg, data) {
        if (data.bcs) {
            if (data.bcs.dataType !== "moveObject" || !isOption(data.bcs.type)) {
                throw new Error(`object at is not a Option object`);
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
            return Option.fromBcs(typeArg, (0, utils_1.fromB64)(data.bcs.bcsBytes));
        }
        if (data.content) {
            return Option.fromSuiParsedData(typeArg, data.content);
        }
        throw new Error("Both `bcs` and `content` fields are missing from the data. Include `showBcs` or `showContent` in the request.");
    }
    static fetch(client, typeArg, id) {
        return __awaiter(this, void 0, void 0, function* () {
            var _a, _b;
            const res = yield client.getObject({ id, options: { showBcs: true } });
            if (res.error) {
                throw new Error(`error fetching Option object at id ${id}: ${res.error.code}`);
            }
            if (((_b = (_a = res.data) === null || _a === void 0 ? void 0 : _a.bcs) === null || _b === void 0 ? void 0 : _b.dataType) !== "moveObject" ||
                !isOption(res.data.bcs.type)) {
                throw new Error(`object at id ${id} is not a Option object`);
            }
            return Option.fromSuiObjectData(typeArg, res.data);
        });
    }
}
exports.Option = Option;
Option.$typeName = `${index_1.PKG_V13}::option::Option`;
Option.$numTypeParams = 1;
Option.$isPhantom = [false];

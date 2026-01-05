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
exports.Cell = void 0;
exports.isCell = isCell;
const structs_1 = require("../../_dependencies/source/0x1/option/structs");
const reified_1 = require("../../_framework/reified");
const util_1 = require("../../_framework/util");
const index_1 = require("../index");
const bcs_1 = require("@mysten/sui/bcs");
const utils_1 = require("@mysten/sui/utils");
/* ============================== Cell =============================== */
function isCell(type) {
    type = (0, util_1.compressSuiType)(type);
    return type.startsWith(`${index_1.PKG_V1}::cell::Cell` + "<");
}
class Cell {
    constructor(typeArgs, fields) {
        this.__StructClass = true;
        this.$typeName = Cell.$typeName;
        this.$isPhantom = Cell.$isPhantom;
        this.$fullTypeName = (0, util_1.composeSuiType)(Cell.$typeName, ...typeArgs);
        this.$typeArgs = typeArgs;
        this.element = fields.element;
    }
    static reified(Element) {
        return {
            typeName: Cell.$typeName,
            fullTypeName: (0, util_1.composeSuiType)(Cell.$typeName, ...[(0, reified_1.extractType)(Element)]),
            typeArgs: [(0, reified_1.extractType)(Element)],
            isPhantom: Cell.$isPhantom,
            reifiedTypeArgs: [Element],
            fromFields: (fields) => Cell.fromFields(Element, fields),
            fromFieldsWithTypes: (item) => Cell.fromFieldsWithTypes(Element, item),
            fromBcs: (data) => Cell.fromBcs(Element, data),
            bcs: Cell.bcs((0, reified_1.toBcs)(Element)),
            fromJSONField: (field) => Cell.fromJSONField(Element, field),
            fromJSON: (json) => Cell.fromJSON(Element, json),
            fromSuiParsedData: (content) => Cell.fromSuiParsedData(Element, content),
            fromSuiObjectData: (content) => Cell.fromSuiObjectData(Element, content),
            fetch: (client, id) => __awaiter(this, void 0, void 0, function* () { return Cell.fetch(client, Element, id); }),
            new: (fields) => {
                return new Cell([(0, reified_1.extractType)(Element)], fields);
            },
            kind: "StructClassReified",
        };
    }
    static get r() {
        return Cell.reified;
    }
    static phantom(Element) {
        return (0, reified_1.phantom)(Cell.reified(Element));
    }
    static get p() {
        return Cell.phantom;
    }
    static get bcs() {
        return (Element) => bcs_1.bcs.struct(`Cell<${Element.name}>`, {
            element: structs_1.Option.bcs(Element),
        });
    }
    static fromFields(typeArg, fields) {
        return Cell.reified(typeArg).new({
            element: (0, reified_1.decodeFromFields)(structs_1.Option.reified(typeArg), fields.element),
        });
    }
    static fromFieldsWithTypes(typeArg, item) {
        if (!isCell(item.type)) {
            throw new Error("not a Cell type");
        }
        (0, reified_1.assertFieldsWithTypesArgsMatch)(item, [typeArg]);
        return Cell.reified(typeArg).new({
            element: (0, reified_1.decodeFromFieldsWithTypes)(structs_1.Option.reified(typeArg), item.fields.element),
        });
    }
    static fromBcs(typeArg, data) {
        const typeArgs = [typeArg];
        return Cell.fromFields(typeArg, Cell.bcs((0, reified_1.toBcs)(typeArgs[0])).parse(data));
    }
    toJSONField() {
        return {
            element: (0, reified_1.fieldToJSON)(`${structs_1.Option.$typeName}<${this.$typeArgs[0]}>`, this.element),
        };
    }
    toJSON() {
        return Object.assign({ $typeName: this.$typeName, $typeArgs: this.$typeArgs }, this.toJSONField());
    }
    static fromJSONField(typeArg, field) {
        return Cell.reified(typeArg).new({
            element: (0, reified_1.decodeFromJSONField)(structs_1.Option.reified(typeArg), field.element),
        });
    }
    static fromJSON(typeArg, json) {
        if (json.$typeName !== Cell.$typeName) {
            throw new Error("not a WithTwoGenerics json object");
        }
        (0, reified_1.assertReifiedTypeArgsMatch)((0, util_1.composeSuiType)(Cell.$typeName, (0, reified_1.extractType)(typeArg)), json.$typeArgs, [typeArg]);
        return Cell.fromJSONField(typeArg, json);
    }
    static fromSuiParsedData(typeArg, content) {
        if (content.dataType !== "moveObject") {
            throw new Error("not an object");
        }
        if (!isCell(content.type)) {
            throw new Error(`object at ${content.fields.id} is not a Cell object`);
        }
        return Cell.fromFieldsWithTypes(typeArg, content);
    }
    static fromSuiObjectData(typeArg, data) {
        if (data.bcs) {
            if (data.bcs.dataType !== "moveObject" || !isCell(data.bcs.type)) {
                throw new Error(`object at is not a Cell object`);
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
            return Cell.fromBcs(typeArg, (0, utils_1.fromB64)(data.bcs.bcsBytes));
        }
        if (data.content) {
            return Cell.fromSuiParsedData(typeArg, data.content);
        }
        throw new Error("Both `bcs` and `content` fields are missing from the data. Include `showBcs` or `showContent` in the request.");
    }
    static fetch(client, typeArg, id) {
        return __awaiter(this, void 0, void 0, function* () {
            var _a, _b;
            const res = yield client.getObject({ id, options: { showBcs: true } });
            if (res.error) {
                throw new Error(`error fetching Cell object at id ${id}: ${res.error.code}`);
            }
            if (((_b = (_a = res.data) === null || _a === void 0 ? void 0 : _a.bcs) === null || _b === void 0 ? void 0 : _b.dataType) !== "moveObject" ||
                !isCell(res.data.bcs.type)) {
                throw new Error(`object at id ${id} is not a Cell object`);
            }
            return Cell.fromSuiObjectData(typeArg, res.data);
        });
    }
}
exports.Cell = Cell;
Cell.$typeName = `${index_1.PKG_V1}::cell::Cell`;
Cell.$numTypeParams = 1;
Cell.$isPhantom = [false];

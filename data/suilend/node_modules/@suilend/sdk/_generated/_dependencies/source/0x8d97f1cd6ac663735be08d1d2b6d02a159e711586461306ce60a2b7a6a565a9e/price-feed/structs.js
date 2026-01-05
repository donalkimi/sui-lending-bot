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
exports.PriceFeed = void 0;
exports.isPriceFeed = isPriceFeed;
const reified_1 = require("../../../../_framework/reified");
const util_1 = require("../../../../_framework/util");
const index_1 = require("../index");
const structs_1 = require("../price-identifier/structs");
const structs_2 = require("../price/structs");
const bcs_1 = require("@mysten/sui/bcs");
const utils_1 = require("@mysten/sui/utils");
/* ============================== PriceFeed =============================== */
function isPriceFeed(type) {
    type = (0, util_1.compressSuiType)(type);
    return type === `${index_1.PKG_V1}::price_feed::PriceFeed`;
}
class PriceFeed {
    constructor(typeArgs, fields) {
        this.__StructClass = true;
        this.$typeName = PriceFeed.$typeName;
        this.$isPhantom = PriceFeed.$isPhantom;
        this.$fullTypeName = (0, util_1.composeSuiType)(PriceFeed.$typeName, ...typeArgs);
        this.$typeArgs = typeArgs;
        this.priceIdentifier = fields.priceIdentifier;
        this.price = fields.price;
        this.emaPrice = fields.emaPrice;
    }
    static reified() {
        return {
            typeName: PriceFeed.$typeName,
            fullTypeName: (0, util_1.composeSuiType)(PriceFeed.$typeName, ...[]),
            typeArgs: [],
            isPhantom: PriceFeed.$isPhantom,
            reifiedTypeArgs: [],
            fromFields: (fields) => PriceFeed.fromFields(fields),
            fromFieldsWithTypes: (item) => PriceFeed.fromFieldsWithTypes(item),
            fromBcs: (data) => PriceFeed.fromBcs(data),
            bcs: PriceFeed.bcs,
            fromJSONField: (field) => PriceFeed.fromJSONField(field),
            fromJSON: (json) => PriceFeed.fromJSON(json),
            fromSuiParsedData: (content) => PriceFeed.fromSuiParsedData(content),
            fromSuiObjectData: (content) => PriceFeed.fromSuiObjectData(content),
            fetch: (client, id) => __awaiter(this, void 0, void 0, function* () { return PriceFeed.fetch(client, id); }),
            new: (fields) => {
                return new PriceFeed([], fields);
            },
            kind: "StructClassReified",
        };
    }
    static get r() {
        return PriceFeed.reified();
    }
    static phantom() {
        return (0, reified_1.phantom)(PriceFeed.reified());
    }
    static get p() {
        return PriceFeed.phantom();
    }
    static get bcs() {
        return bcs_1.bcs.struct("PriceFeed", {
            price_identifier: structs_1.PriceIdentifier.bcs,
            price: structs_2.Price.bcs,
            ema_price: structs_2.Price.bcs,
        });
    }
    static fromFields(fields) {
        return PriceFeed.reified().new({
            priceIdentifier: (0, reified_1.decodeFromFields)(structs_1.PriceIdentifier.reified(), fields.price_identifier),
            price: (0, reified_1.decodeFromFields)(structs_2.Price.reified(), fields.price),
            emaPrice: (0, reified_1.decodeFromFields)(structs_2.Price.reified(), fields.ema_price),
        });
    }
    static fromFieldsWithTypes(item) {
        if (!isPriceFeed(item.type)) {
            throw new Error("not a PriceFeed type");
        }
        return PriceFeed.reified().new({
            priceIdentifier: (0, reified_1.decodeFromFieldsWithTypes)(structs_1.PriceIdentifier.reified(), item.fields.price_identifier),
            price: (0, reified_1.decodeFromFieldsWithTypes)(structs_2.Price.reified(), item.fields.price),
            emaPrice: (0, reified_1.decodeFromFieldsWithTypes)(structs_2.Price.reified(), item.fields.ema_price),
        });
    }
    static fromBcs(data) {
        return PriceFeed.fromFields(PriceFeed.bcs.parse(data));
    }
    toJSONField() {
        return {
            priceIdentifier: this.priceIdentifier.toJSONField(),
            price: this.price.toJSONField(),
            emaPrice: this.emaPrice.toJSONField(),
        };
    }
    toJSON() {
        return Object.assign({ $typeName: this.$typeName, $typeArgs: this.$typeArgs }, this.toJSONField());
    }
    static fromJSONField(field) {
        return PriceFeed.reified().new({
            priceIdentifier: (0, reified_1.decodeFromJSONField)(structs_1.PriceIdentifier.reified(), field.priceIdentifier),
            price: (0, reified_1.decodeFromJSONField)(structs_2.Price.reified(), field.price),
            emaPrice: (0, reified_1.decodeFromJSONField)(structs_2.Price.reified(), field.emaPrice),
        });
    }
    static fromJSON(json) {
        if (json.$typeName !== PriceFeed.$typeName) {
            throw new Error("not a WithTwoGenerics json object");
        }
        return PriceFeed.fromJSONField(json);
    }
    static fromSuiParsedData(content) {
        if (content.dataType !== "moveObject") {
            throw new Error("not an object");
        }
        if (!isPriceFeed(content.type)) {
            throw new Error(`object at ${content.fields.id} is not a PriceFeed object`);
        }
        return PriceFeed.fromFieldsWithTypes(content);
    }
    static fromSuiObjectData(data) {
        if (data.bcs) {
            if (data.bcs.dataType !== "moveObject" || !isPriceFeed(data.bcs.type)) {
                throw new Error(`object at is not a PriceFeed object`);
            }
            return PriceFeed.fromBcs((0, utils_1.fromB64)(data.bcs.bcsBytes));
        }
        if (data.content) {
            return PriceFeed.fromSuiParsedData(data.content);
        }
        throw new Error("Both `bcs` and `content` fields are missing from the data. Include `showBcs` or `showContent` in the request.");
    }
    static fetch(client, id) {
        return __awaiter(this, void 0, void 0, function* () {
            var _a, _b;
            const res = yield client.getObject({ id, options: { showBcs: true } });
            if (res.error) {
                throw new Error(`error fetching PriceFeed object at id ${id}: ${res.error.code}`);
            }
            if (((_b = (_a = res.data) === null || _a === void 0 ? void 0 : _a.bcs) === null || _b === void 0 ? void 0 : _b.dataType) !== "moveObject" ||
                !isPriceFeed(res.data.bcs.type)) {
                throw new Error(`object at id ${id} is not a PriceFeed object`);
            }
            return PriceFeed.fromSuiObjectData(res.data);
        });
    }
}
exports.PriceFeed = PriceFeed;
PriceFeed.$typeName = `${index_1.PKG_V1}::price_feed::PriceFeed`;
PriceFeed.$numTypeParams = 0;
PriceFeed.$isPhantom = [];

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
exports.StakerKey = exports.ReserveAssetDataEvent = exports.Reserve = exports.LiquidityRequest = exports.InterestUpdateEvent = exports.ClaimStakingRewardsEvent = exports.CToken = exports.Balances = exports.BalanceKey = void 0;
exports.isBalanceKey = isBalanceKey;
exports.isBalances = isBalances;
exports.isCToken = isCToken;
exports.isClaimStakingRewardsEvent = isClaimStakingRewardsEvent;
exports.isInterestUpdateEvent = isInterestUpdateEvent;
exports.isLiquidityRequest = isLiquidityRequest;
exports.isReserve = isReserve;
exports.isReserveAssetDataEvent = isReserveAssetDataEvent;
exports.isStakerKey = isStakerKey;
const reified = __importStar(require("../../_framework/reified"));
const structs_1 = require("../../_dependencies/source/0x1/type-name/structs");
const structs_2 = require("../../_dependencies/source/0x2/balance/structs");
const structs_3 = require("../../_dependencies/source/0x2/object/structs");
const structs_4 = require("../../_dependencies/source/0x8d97f1cd6ac663735be08d1d2b6d02a159e711586461306ce60a2b7a6a565a9e/price-identifier/structs");
const reified_1 = require("../../_framework/reified");
const util_1 = require("../../_framework/util");
const structs_5 = require("../cell/structs");
const structs_6 = require("../decimal/structs");
const index_1 = require("../index");
const structs_7 = require("../liquidity-mining/structs");
const structs_8 = require("../reserve-config/structs");
const bcs_1 = require("@mysten/sui/bcs");
const utils_1 = require("@mysten/sui/utils");
/* ============================== BalanceKey =============================== */
function isBalanceKey(type) {
    type = (0, util_1.compressSuiType)(type);
    return type === `${index_1.PKG_V1}::reserve::BalanceKey`;
}
class BalanceKey {
    constructor(typeArgs, fields) {
        this.__StructClass = true;
        this.$typeName = BalanceKey.$typeName;
        this.$isPhantom = BalanceKey.$isPhantom;
        this.$fullTypeName = (0, util_1.composeSuiType)(BalanceKey.$typeName, ...typeArgs);
        this.$typeArgs = typeArgs;
        this.dummyField = fields.dummyField;
    }
    static reified() {
        return {
            typeName: BalanceKey.$typeName,
            fullTypeName: (0, util_1.composeSuiType)(BalanceKey.$typeName, ...[]),
            typeArgs: [],
            isPhantom: BalanceKey.$isPhantom,
            reifiedTypeArgs: [],
            fromFields: (fields) => BalanceKey.fromFields(fields),
            fromFieldsWithTypes: (item) => BalanceKey.fromFieldsWithTypes(item),
            fromBcs: (data) => BalanceKey.fromBcs(data),
            bcs: BalanceKey.bcs,
            fromJSONField: (field) => BalanceKey.fromJSONField(field),
            fromJSON: (json) => BalanceKey.fromJSON(json),
            fromSuiParsedData: (content) => BalanceKey.fromSuiParsedData(content),
            fromSuiObjectData: (content) => BalanceKey.fromSuiObjectData(content),
            fetch: (client, id) => __awaiter(this, void 0, void 0, function* () { return BalanceKey.fetch(client, id); }),
            new: (fields) => {
                return new BalanceKey([], fields);
            },
            kind: "StructClassReified",
        };
    }
    static get r() {
        return BalanceKey.reified();
    }
    static phantom() {
        return (0, reified_1.phantom)(BalanceKey.reified());
    }
    static get p() {
        return BalanceKey.phantom();
    }
    static get bcs() {
        return bcs_1.bcs.struct("BalanceKey", {
            dummy_field: bcs_1.bcs.bool(),
        });
    }
    static fromFields(fields) {
        return BalanceKey.reified().new({
            dummyField: (0, reified_1.decodeFromFields)("bool", fields.dummy_field),
        });
    }
    static fromFieldsWithTypes(item) {
        if (!isBalanceKey(item.type)) {
            throw new Error("not a BalanceKey type");
        }
        return BalanceKey.reified().new({
            dummyField: (0, reified_1.decodeFromFieldsWithTypes)("bool", item.fields.dummy_field),
        });
    }
    static fromBcs(data) {
        return BalanceKey.fromFields(BalanceKey.bcs.parse(data));
    }
    toJSONField() {
        return {
            dummyField: this.dummyField,
        };
    }
    toJSON() {
        return Object.assign({ $typeName: this.$typeName, $typeArgs: this.$typeArgs }, this.toJSONField());
    }
    static fromJSONField(field) {
        return BalanceKey.reified().new({
            dummyField: (0, reified_1.decodeFromJSONField)("bool", field.dummyField),
        });
    }
    static fromJSON(json) {
        if (json.$typeName !== BalanceKey.$typeName) {
            throw new Error("not a WithTwoGenerics json object");
        }
        return BalanceKey.fromJSONField(json);
    }
    static fromSuiParsedData(content) {
        if (content.dataType !== "moveObject") {
            throw new Error("not an object");
        }
        if (!isBalanceKey(content.type)) {
            throw new Error(`object at ${content.fields.id} is not a BalanceKey object`);
        }
        return BalanceKey.fromFieldsWithTypes(content);
    }
    static fromSuiObjectData(data) {
        if (data.bcs) {
            if (data.bcs.dataType !== "moveObject" || !isBalanceKey(data.bcs.type)) {
                throw new Error(`object at is not a BalanceKey object`);
            }
            return BalanceKey.fromBcs((0, utils_1.fromB64)(data.bcs.bcsBytes));
        }
        if (data.content) {
            return BalanceKey.fromSuiParsedData(data.content);
        }
        throw new Error("Both `bcs` and `content` fields are missing from the data. Include `showBcs` or `showContent` in the request.");
    }
    static fetch(client, id) {
        return __awaiter(this, void 0, void 0, function* () {
            var _a, _b;
            const res = yield client.getObject({ id, options: { showBcs: true } });
            if (res.error) {
                throw new Error(`error fetching BalanceKey object at id ${id}: ${res.error.code}`);
            }
            if (((_b = (_a = res.data) === null || _a === void 0 ? void 0 : _a.bcs) === null || _b === void 0 ? void 0 : _b.dataType) !== "moveObject" ||
                !isBalanceKey(res.data.bcs.type)) {
                throw new Error(`object at id ${id} is not a BalanceKey object`);
            }
            return BalanceKey.fromSuiObjectData(res.data);
        });
    }
}
exports.BalanceKey = BalanceKey;
BalanceKey.$typeName = `${index_1.PKG_V1}::reserve::BalanceKey`;
BalanceKey.$numTypeParams = 0;
BalanceKey.$isPhantom = [];
/* ============================== Balances =============================== */
function isBalances(type) {
    type = (0, util_1.compressSuiType)(type);
    return type.startsWith(`${index_1.PKG_V1}::reserve::Balances` + "<");
}
class Balances {
    constructor(typeArgs, fields) {
        this.__StructClass = true;
        this.$typeName = Balances.$typeName;
        this.$isPhantom = Balances.$isPhantom;
        this.$fullTypeName = (0, util_1.composeSuiType)(Balances.$typeName, ...typeArgs);
        this.$typeArgs = typeArgs;
        this.availableAmount = fields.availableAmount;
        this.ctokenSupply = fields.ctokenSupply;
        this.fees = fields.fees;
        this.ctokenFees = fields.ctokenFees;
        this.depositedCtokens = fields.depositedCtokens;
    }
    static reified(P, T) {
        return {
            typeName: Balances.$typeName,
            fullTypeName: (0, util_1.composeSuiType)(Balances.$typeName, ...[(0, reified_1.extractType)(P), (0, reified_1.extractType)(T)]),
            typeArgs: [(0, reified_1.extractType)(P), (0, reified_1.extractType)(T)],
            isPhantom: Balances.$isPhantom,
            reifiedTypeArgs: [P, T],
            fromFields: (fields) => Balances.fromFields([P, T], fields),
            fromFieldsWithTypes: (item) => Balances.fromFieldsWithTypes([P, T], item),
            fromBcs: (data) => Balances.fromBcs([P, T], data),
            bcs: Balances.bcs,
            fromJSONField: (field) => Balances.fromJSONField([P, T], field),
            fromJSON: (json) => Balances.fromJSON([P, T], json),
            fromSuiParsedData: (content) => Balances.fromSuiParsedData([P, T], content),
            fromSuiObjectData: (content) => Balances.fromSuiObjectData([P, T], content),
            fetch: (client, id) => __awaiter(this, void 0, void 0, function* () { return Balances.fetch(client, [P, T], id); }),
            new: (fields) => {
                return new Balances([(0, reified_1.extractType)(P), (0, reified_1.extractType)(T)], fields);
            },
            kind: "StructClassReified",
        };
    }
    static get r() {
        return Balances.reified;
    }
    static phantom(P, T) {
        return (0, reified_1.phantom)(Balances.reified(P, T));
    }
    static get p() {
        return Balances.phantom;
    }
    static get bcs() {
        return bcs_1.bcs.struct("Balances", {
            available_amount: structs_2.Balance.bcs,
            ctoken_supply: structs_2.Supply.bcs,
            fees: structs_2.Balance.bcs,
            ctoken_fees: structs_2.Balance.bcs,
            deposited_ctokens: structs_2.Balance.bcs,
        });
    }
    static fromFields(typeArgs, fields) {
        return Balances.reified(typeArgs[0], typeArgs[1]).new({
            availableAmount: (0, reified_1.decodeFromFields)(structs_2.Balance.reified(typeArgs[1]), fields.available_amount),
            ctokenSupply: (0, reified_1.decodeFromFields)(structs_2.Supply.reified(reified.phantom(CToken.reified(typeArgs[0], typeArgs[1]))), fields.ctoken_supply),
            fees: (0, reified_1.decodeFromFields)(structs_2.Balance.reified(typeArgs[1]), fields.fees),
            ctokenFees: (0, reified_1.decodeFromFields)(structs_2.Balance.reified(reified.phantom(CToken.reified(typeArgs[0], typeArgs[1]))), fields.ctoken_fees),
            depositedCtokens: (0, reified_1.decodeFromFields)(structs_2.Balance.reified(reified.phantom(CToken.reified(typeArgs[0], typeArgs[1]))), fields.deposited_ctokens),
        });
    }
    static fromFieldsWithTypes(typeArgs, item) {
        if (!isBalances(item.type)) {
            throw new Error("not a Balances type");
        }
        (0, reified_1.assertFieldsWithTypesArgsMatch)(item, typeArgs);
        return Balances.reified(typeArgs[0], typeArgs[1]).new({
            availableAmount: (0, reified_1.decodeFromFieldsWithTypes)(structs_2.Balance.reified(typeArgs[1]), item.fields.available_amount),
            ctokenSupply: (0, reified_1.decodeFromFieldsWithTypes)(structs_2.Supply.reified(reified.phantom(CToken.reified(typeArgs[0], typeArgs[1]))), item.fields.ctoken_supply),
            fees: (0, reified_1.decodeFromFieldsWithTypes)(structs_2.Balance.reified(typeArgs[1]), item.fields.fees),
            ctokenFees: (0, reified_1.decodeFromFieldsWithTypes)(structs_2.Balance.reified(reified.phantom(CToken.reified(typeArgs[0], typeArgs[1]))), item.fields.ctoken_fees),
            depositedCtokens: (0, reified_1.decodeFromFieldsWithTypes)(structs_2.Balance.reified(reified.phantom(CToken.reified(typeArgs[0], typeArgs[1]))), item.fields.deposited_ctokens),
        });
    }
    static fromBcs(typeArgs, data) {
        return Balances.fromFields(typeArgs, Balances.bcs.parse(data));
    }
    toJSONField() {
        return {
            availableAmount: this.availableAmount.toJSONField(),
            ctokenSupply: this.ctokenSupply.toJSONField(),
            fees: this.fees.toJSONField(),
            ctokenFees: this.ctokenFees.toJSONField(),
            depositedCtokens: this.depositedCtokens.toJSONField(),
        };
    }
    toJSON() {
        return Object.assign({ $typeName: this.$typeName, $typeArgs: this.$typeArgs }, this.toJSONField());
    }
    static fromJSONField(typeArgs, field) {
        return Balances.reified(typeArgs[0], typeArgs[1]).new({
            availableAmount: (0, reified_1.decodeFromJSONField)(structs_2.Balance.reified(typeArgs[1]), field.availableAmount),
            ctokenSupply: (0, reified_1.decodeFromJSONField)(structs_2.Supply.reified(reified.phantom(CToken.reified(typeArgs[0], typeArgs[1]))), field.ctokenSupply),
            fees: (0, reified_1.decodeFromJSONField)(structs_2.Balance.reified(typeArgs[1]), field.fees),
            ctokenFees: (0, reified_1.decodeFromJSONField)(structs_2.Balance.reified(reified.phantom(CToken.reified(typeArgs[0], typeArgs[1]))), field.ctokenFees),
            depositedCtokens: (0, reified_1.decodeFromJSONField)(structs_2.Balance.reified(reified.phantom(CToken.reified(typeArgs[0], typeArgs[1]))), field.depositedCtokens),
        });
    }
    static fromJSON(typeArgs, json) {
        if (json.$typeName !== Balances.$typeName) {
            throw new Error("not a WithTwoGenerics json object");
        }
        (0, reified_1.assertReifiedTypeArgsMatch)((0, util_1.composeSuiType)(Balances.$typeName, ...typeArgs.map(reified_1.extractType)), json.$typeArgs, typeArgs);
        return Balances.fromJSONField(typeArgs, json);
    }
    static fromSuiParsedData(typeArgs, content) {
        if (content.dataType !== "moveObject") {
            throw new Error("not an object");
        }
        if (!isBalances(content.type)) {
            throw new Error(`object at ${content.fields.id} is not a Balances object`);
        }
        return Balances.fromFieldsWithTypes(typeArgs, content);
    }
    static fromSuiObjectData(typeArgs, data) {
        if (data.bcs) {
            if (data.bcs.dataType !== "moveObject" || !isBalances(data.bcs.type)) {
                throw new Error(`object at is not a Balances object`);
            }
            const gotTypeArgs = (0, util_1.parseTypeName)(data.bcs.type).typeArgs;
            if (gotTypeArgs.length !== 2) {
                throw new Error(`type argument mismatch: expected 2 type arguments but got ${gotTypeArgs.length}`);
            }
            for (let i = 0; i < 2; i++) {
                const gotTypeArg = (0, util_1.compressSuiType)(gotTypeArgs[i]);
                const expectedTypeArg = (0, util_1.compressSuiType)((0, reified_1.extractType)(typeArgs[i]));
                if (gotTypeArg !== expectedTypeArg) {
                    throw new Error(`type argument mismatch at position ${i}: expected '${expectedTypeArg}' but got '${gotTypeArg}'`);
                }
            }
            return Balances.fromBcs(typeArgs, (0, utils_1.fromB64)(data.bcs.bcsBytes));
        }
        if (data.content) {
            return Balances.fromSuiParsedData(typeArgs, data.content);
        }
        throw new Error("Both `bcs` and `content` fields are missing from the data. Include `showBcs` or `showContent` in the request.");
    }
    static fetch(client, typeArgs, id) {
        return __awaiter(this, void 0, void 0, function* () {
            var _a, _b;
            const res = yield client.getObject({ id, options: { showBcs: true } });
            if (res.error) {
                throw new Error(`error fetching Balances object at id ${id}: ${res.error.code}`);
            }
            if (((_b = (_a = res.data) === null || _a === void 0 ? void 0 : _a.bcs) === null || _b === void 0 ? void 0 : _b.dataType) !== "moveObject" ||
                !isBalances(res.data.bcs.type)) {
                throw new Error(`object at id ${id} is not a Balances object`);
            }
            return Balances.fromSuiObjectData(typeArgs, res.data);
        });
    }
}
exports.Balances = Balances;
Balances.$typeName = `${index_1.PKG_V1}::reserve::Balances`;
Balances.$numTypeParams = 2;
Balances.$isPhantom = [true, true];
/* ============================== CToken =============================== */
function isCToken(type) {
    type = (0, util_1.compressSuiType)(type);
    return type.startsWith(`${index_1.PKG_V1}::reserve::CToken` + "<");
}
class CToken {
    constructor(typeArgs, fields) {
        this.__StructClass = true;
        this.$typeName = CToken.$typeName;
        this.$isPhantom = CToken.$isPhantom;
        this.$fullTypeName = (0, util_1.composeSuiType)(CToken.$typeName, ...typeArgs);
        this.$typeArgs = typeArgs;
        this.dummyField = fields.dummyField;
    }
    static reified(P, T) {
        return {
            typeName: CToken.$typeName,
            fullTypeName: (0, util_1.composeSuiType)(CToken.$typeName, ...[(0, reified_1.extractType)(P), (0, reified_1.extractType)(T)]),
            typeArgs: [(0, reified_1.extractType)(P), (0, reified_1.extractType)(T)],
            isPhantom: CToken.$isPhantom,
            reifiedTypeArgs: [P, T],
            fromFields: (fields) => CToken.fromFields([P, T], fields),
            fromFieldsWithTypes: (item) => CToken.fromFieldsWithTypes([P, T], item),
            fromBcs: (data) => CToken.fromBcs([P, T], data),
            bcs: CToken.bcs,
            fromJSONField: (field) => CToken.fromJSONField([P, T], field),
            fromJSON: (json) => CToken.fromJSON([P, T], json),
            fromSuiParsedData: (content) => CToken.fromSuiParsedData([P, T], content),
            fromSuiObjectData: (content) => CToken.fromSuiObjectData([P, T], content),
            fetch: (client, id) => __awaiter(this, void 0, void 0, function* () { return CToken.fetch(client, [P, T], id); }),
            new: (fields) => {
                return new CToken([(0, reified_1.extractType)(P), (0, reified_1.extractType)(T)], fields);
            },
            kind: "StructClassReified",
        };
    }
    static get r() {
        return CToken.reified;
    }
    static phantom(P, T) {
        return (0, reified_1.phantom)(CToken.reified(P, T));
    }
    static get p() {
        return CToken.phantom;
    }
    static get bcs() {
        return bcs_1.bcs.struct("CToken", {
            dummy_field: bcs_1.bcs.bool(),
        });
    }
    static fromFields(typeArgs, fields) {
        return CToken.reified(typeArgs[0], typeArgs[1]).new({
            dummyField: (0, reified_1.decodeFromFields)("bool", fields.dummy_field),
        });
    }
    static fromFieldsWithTypes(typeArgs, item) {
        if (!isCToken(item.type)) {
            throw new Error("not a CToken type");
        }
        (0, reified_1.assertFieldsWithTypesArgsMatch)(item, typeArgs);
        return CToken.reified(typeArgs[0], typeArgs[1]).new({
            dummyField: (0, reified_1.decodeFromFieldsWithTypes)("bool", item.fields.dummy_field),
        });
    }
    static fromBcs(typeArgs, data) {
        return CToken.fromFields(typeArgs, CToken.bcs.parse(data));
    }
    toJSONField() {
        return {
            dummyField: this.dummyField,
        };
    }
    toJSON() {
        return Object.assign({ $typeName: this.$typeName, $typeArgs: this.$typeArgs }, this.toJSONField());
    }
    static fromJSONField(typeArgs, field) {
        return CToken.reified(typeArgs[0], typeArgs[1]).new({
            dummyField: (0, reified_1.decodeFromJSONField)("bool", field.dummyField),
        });
    }
    static fromJSON(typeArgs, json) {
        if (json.$typeName !== CToken.$typeName) {
            throw new Error("not a WithTwoGenerics json object");
        }
        (0, reified_1.assertReifiedTypeArgsMatch)((0, util_1.composeSuiType)(CToken.$typeName, ...typeArgs.map(reified_1.extractType)), json.$typeArgs, typeArgs);
        return CToken.fromJSONField(typeArgs, json);
    }
    static fromSuiParsedData(typeArgs, content) {
        if (content.dataType !== "moveObject") {
            throw new Error("not an object");
        }
        if (!isCToken(content.type)) {
            throw new Error(`object at ${content.fields.id} is not a CToken object`);
        }
        return CToken.fromFieldsWithTypes(typeArgs, content);
    }
    static fromSuiObjectData(typeArgs, data) {
        if (data.bcs) {
            if (data.bcs.dataType !== "moveObject" || !isCToken(data.bcs.type)) {
                throw new Error(`object at is not a CToken object`);
            }
            const gotTypeArgs = (0, util_1.parseTypeName)(data.bcs.type).typeArgs;
            if (gotTypeArgs.length !== 2) {
                throw new Error(`type argument mismatch: expected 2 type arguments but got ${gotTypeArgs.length}`);
            }
            for (let i = 0; i < 2; i++) {
                const gotTypeArg = (0, util_1.compressSuiType)(gotTypeArgs[i]);
                const expectedTypeArg = (0, util_1.compressSuiType)((0, reified_1.extractType)(typeArgs[i]));
                if (gotTypeArg !== expectedTypeArg) {
                    throw new Error(`type argument mismatch at position ${i}: expected '${expectedTypeArg}' but got '${gotTypeArg}'`);
                }
            }
            return CToken.fromBcs(typeArgs, (0, utils_1.fromB64)(data.bcs.bcsBytes));
        }
        if (data.content) {
            return CToken.fromSuiParsedData(typeArgs, data.content);
        }
        throw new Error("Both `bcs` and `content` fields are missing from the data. Include `showBcs` or `showContent` in the request.");
    }
    static fetch(client, typeArgs, id) {
        return __awaiter(this, void 0, void 0, function* () {
            var _a, _b;
            const res = yield client.getObject({ id, options: { showBcs: true } });
            if (res.error) {
                throw new Error(`error fetching CToken object at id ${id}: ${res.error.code}`);
            }
            if (((_b = (_a = res.data) === null || _a === void 0 ? void 0 : _a.bcs) === null || _b === void 0 ? void 0 : _b.dataType) !== "moveObject" ||
                !isCToken(res.data.bcs.type)) {
                throw new Error(`object at id ${id} is not a CToken object`);
            }
            return CToken.fromSuiObjectData(typeArgs, res.data);
        });
    }
}
exports.CToken = CToken;
CToken.$typeName = `${index_1.PKG_V1}::reserve::CToken`;
CToken.$numTypeParams = 2;
CToken.$isPhantom = [true, true];
/* ============================== ClaimStakingRewardsEvent =============================== */
function isClaimStakingRewardsEvent(type) {
    type = (0, util_1.compressSuiType)(type);
    return type === `${index_1.PKG_V8}::reserve::ClaimStakingRewardsEvent`;
}
class ClaimStakingRewardsEvent {
    constructor(typeArgs, fields) {
        this.__StructClass = true;
        this.$typeName = ClaimStakingRewardsEvent.$typeName;
        this.$isPhantom = ClaimStakingRewardsEvent.$isPhantom;
        this.$fullTypeName = (0, util_1.composeSuiType)(ClaimStakingRewardsEvent.$typeName, ...typeArgs);
        this.$typeArgs = typeArgs;
        this.lendingMarketId = fields.lendingMarketId;
        this.coinType = fields.coinType;
        this.reserveId = fields.reserveId;
        this.amount = fields.amount;
    }
    static reified() {
        return {
            typeName: ClaimStakingRewardsEvent.$typeName,
            fullTypeName: (0, util_1.composeSuiType)(ClaimStakingRewardsEvent.$typeName, ...[]),
            typeArgs: [],
            isPhantom: ClaimStakingRewardsEvent.$isPhantom,
            reifiedTypeArgs: [],
            fromFields: (fields) => ClaimStakingRewardsEvent.fromFields(fields),
            fromFieldsWithTypes: (item) => ClaimStakingRewardsEvent.fromFieldsWithTypes(item),
            fromBcs: (data) => ClaimStakingRewardsEvent.fromBcs(data),
            bcs: ClaimStakingRewardsEvent.bcs,
            fromJSONField: (field) => ClaimStakingRewardsEvent.fromJSONField(field),
            fromJSON: (json) => ClaimStakingRewardsEvent.fromJSON(json),
            fromSuiParsedData: (content) => ClaimStakingRewardsEvent.fromSuiParsedData(content),
            fromSuiObjectData: (content) => ClaimStakingRewardsEvent.fromSuiObjectData(content),
            fetch: (client, id) => __awaiter(this, void 0, void 0, function* () { return ClaimStakingRewardsEvent.fetch(client, id); }),
            new: (fields) => {
                return new ClaimStakingRewardsEvent([], fields);
            },
            kind: "StructClassReified",
        };
    }
    static get r() {
        return ClaimStakingRewardsEvent.reified();
    }
    static phantom() {
        return (0, reified_1.phantom)(ClaimStakingRewardsEvent.reified());
    }
    static get p() {
        return ClaimStakingRewardsEvent.phantom();
    }
    static get bcs() {
        return bcs_1.bcs.struct("ClaimStakingRewardsEvent", {
            lending_market_id: bcs_1.bcs
                .bytes(32)
                .transform({
                input: (val) => (0, utils_1.fromHEX)(val),
                output: (val) => (0, utils_1.toHEX)(val),
            }),
            coin_type: structs_1.TypeName.bcs,
            reserve_id: bcs_1.bcs
                .bytes(32)
                .transform({
                input: (val) => (0, utils_1.fromHEX)(val),
                output: (val) => (0, utils_1.toHEX)(val),
            }),
            amount: bcs_1.bcs.u64(),
        });
    }
    static fromFields(fields) {
        return ClaimStakingRewardsEvent.reified().new({
            lendingMarketId: (0, reified_1.decodeFromFields)("address", fields.lending_market_id),
            coinType: (0, reified_1.decodeFromFields)(structs_1.TypeName.reified(), fields.coin_type),
            reserveId: (0, reified_1.decodeFromFields)("address", fields.reserve_id),
            amount: (0, reified_1.decodeFromFields)("u64", fields.amount),
        });
    }
    static fromFieldsWithTypes(item) {
        if (!isClaimStakingRewardsEvent(item.type)) {
            throw new Error("not a ClaimStakingRewardsEvent type");
        }
        return ClaimStakingRewardsEvent.reified().new({
            lendingMarketId: (0, reified_1.decodeFromFieldsWithTypes)("address", item.fields.lending_market_id),
            coinType: (0, reified_1.decodeFromFieldsWithTypes)(structs_1.TypeName.reified(), item.fields.coin_type),
            reserveId: (0, reified_1.decodeFromFieldsWithTypes)("address", item.fields.reserve_id),
            amount: (0, reified_1.decodeFromFieldsWithTypes)("u64", item.fields.amount),
        });
    }
    static fromBcs(data) {
        return ClaimStakingRewardsEvent.fromFields(ClaimStakingRewardsEvent.bcs.parse(data));
    }
    toJSONField() {
        return {
            lendingMarketId: this.lendingMarketId,
            coinType: this.coinType.toJSONField(),
            reserveId: this.reserveId,
            amount: this.amount.toString(),
        };
    }
    toJSON() {
        return Object.assign({ $typeName: this.$typeName, $typeArgs: this.$typeArgs }, this.toJSONField());
    }
    static fromJSONField(field) {
        return ClaimStakingRewardsEvent.reified().new({
            lendingMarketId: (0, reified_1.decodeFromJSONField)("address", field.lendingMarketId),
            coinType: (0, reified_1.decodeFromJSONField)(structs_1.TypeName.reified(), field.coinType),
            reserveId: (0, reified_1.decodeFromJSONField)("address", field.reserveId),
            amount: (0, reified_1.decodeFromJSONField)("u64", field.amount),
        });
    }
    static fromJSON(json) {
        if (json.$typeName !== ClaimStakingRewardsEvent.$typeName) {
            throw new Error("not a WithTwoGenerics json object");
        }
        return ClaimStakingRewardsEvent.fromJSONField(json);
    }
    static fromSuiParsedData(content) {
        if (content.dataType !== "moveObject") {
            throw new Error("not an object");
        }
        if (!isClaimStakingRewardsEvent(content.type)) {
            throw new Error(`object at ${content.fields.id} is not a ClaimStakingRewardsEvent object`);
        }
        return ClaimStakingRewardsEvent.fromFieldsWithTypes(content);
    }
    static fromSuiObjectData(data) {
        if (data.bcs) {
            if (data.bcs.dataType !== "moveObject" ||
                !isClaimStakingRewardsEvent(data.bcs.type)) {
                throw new Error(`object at is not a ClaimStakingRewardsEvent object`);
            }
            return ClaimStakingRewardsEvent.fromBcs((0, utils_1.fromB64)(data.bcs.bcsBytes));
        }
        if (data.content) {
            return ClaimStakingRewardsEvent.fromSuiParsedData(data.content);
        }
        throw new Error("Both `bcs` and `content` fields are missing from the data. Include `showBcs` or `showContent` in the request.");
    }
    static fetch(client, id) {
        return __awaiter(this, void 0, void 0, function* () {
            var _a, _b;
            const res = yield client.getObject({ id, options: { showBcs: true } });
            if (res.error) {
                throw new Error(`error fetching ClaimStakingRewardsEvent object at id ${id}: ${res.error.code}`);
            }
            if (((_b = (_a = res.data) === null || _a === void 0 ? void 0 : _a.bcs) === null || _b === void 0 ? void 0 : _b.dataType) !== "moveObject" ||
                !isClaimStakingRewardsEvent(res.data.bcs.type)) {
                throw new Error(`object at id ${id} is not a ClaimStakingRewardsEvent object`);
            }
            return ClaimStakingRewardsEvent.fromSuiObjectData(res.data);
        });
    }
}
exports.ClaimStakingRewardsEvent = ClaimStakingRewardsEvent;
ClaimStakingRewardsEvent.$typeName = `${index_1.PKG_V8}::reserve::ClaimStakingRewardsEvent`;
ClaimStakingRewardsEvent.$numTypeParams = 0;
ClaimStakingRewardsEvent.$isPhantom = [];
/* ============================== InterestUpdateEvent =============================== */
function isInterestUpdateEvent(type) {
    type = (0, util_1.compressSuiType)(type);
    return type === `${index_1.PKG_V1}::reserve::InterestUpdateEvent`;
}
class InterestUpdateEvent {
    constructor(typeArgs, fields) {
        this.__StructClass = true;
        this.$typeName = InterestUpdateEvent.$typeName;
        this.$isPhantom = InterestUpdateEvent.$isPhantom;
        this.$fullTypeName = (0, util_1.composeSuiType)(InterestUpdateEvent.$typeName, ...typeArgs);
        this.$typeArgs = typeArgs;
        this.lendingMarketId = fields.lendingMarketId;
        this.coinType = fields.coinType;
        this.reserveId = fields.reserveId;
        this.cumulativeBorrowRate = fields.cumulativeBorrowRate;
        this.availableAmount = fields.availableAmount;
        this.borrowedAmount = fields.borrowedAmount;
        this.unclaimedSpreadFees = fields.unclaimedSpreadFees;
        this.ctokenSupply = fields.ctokenSupply;
        this.borrowInterestPaid = fields.borrowInterestPaid;
        this.spreadFee = fields.spreadFee;
        this.supplyInterestEarned = fields.supplyInterestEarned;
        this.borrowInterestPaidUsdEstimate = fields.borrowInterestPaidUsdEstimate;
        this.protocolFeeUsdEstimate = fields.protocolFeeUsdEstimate;
        this.supplyInterestEarnedUsdEstimate =
            fields.supplyInterestEarnedUsdEstimate;
    }
    static reified() {
        return {
            typeName: InterestUpdateEvent.$typeName,
            fullTypeName: (0, util_1.composeSuiType)(InterestUpdateEvent.$typeName, ...[]),
            typeArgs: [],
            isPhantom: InterestUpdateEvent.$isPhantom,
            reifiedTypeArgs: [],
            fromFields: (fields) => InterestUpdateEvent.fromFields(fields),
            fromFieldsWithTypes: (item) => InterestUpdateEvent.fromFieldsWithTypes(item),
            fromBcs: (data) => InterestUpdateEvent.fromBcs(data),
            bcs: InterestUpdateEvent.bcs,
            fromJSONField: (field) => InterestUpdateEvent.fromJSONField(field),
            fromJSON: (json) => InterestUpdateEvent.fromJSON(json),
            fromSuiParsedData: (content) => InterestUpdateEvent.fromSuiParsedData(content),
            fromSuiObjectData: (content) => InterestUpdateEvent.fromSuiObjectData(content),
            fetch: (client, id) => __awaiter(this, void 0, void 0, function* () { return InterestUpdateEvent.fetch(client, id); }),
            new: (fields) => {
                return new InterestUpdateEvent([], fields);
            },
            kind: "StructClassReified",
        };
    }
    static get r() {
        return InterestUpdateEvent.reified();
    }
    static phantom() {
        return (0, reified_1.phantom)(InterestUpdateEvent.reified());
    }
    static get p() {
        return InterestUpdateEvent.phantom();
    }
    static get bcs() {
        return bcs_1.bcs.struct("InterestUpdateEvent", {
            lending_market_id: bcs_1.bcs
                .bytes(32)
                .transform({
                input: (val) => (0, utils_1.fromHEX)(val),
                output: (val) => (0, utils_1.toHEX)(val),
            }),
            coin_type: structs_1.TypeName.bcs,
            reserve_id: bcs_1.bcs
                .bytes(32)
                .transform({
                input: (val) => (0, utils_1.fromHEX)(val),
                output: (val) => (0, utils_1.toHEX)(val),
            }),
            cumulative_borrow_rate: structs_6.Decimal.bcs,
            available_amount: bcs_1.bcs.u64(),
            borrowed_amount: structs_6.Decimal.bcs,
            unclaimed_spread_fees: structs_6.Decimal.bcs,
            ctoken_supply: bcs_1.bcs.u64(),
            borrow_interest_paid: structs_6.Decimal.bcs,
            spread_fee: structs_6.Decimal.bcs,
            supply_interest_earned: structs_6.Decimal.bcs,
            borrow_interest_paid_usd_estimate: structs_6.Decimal.bcs,
            protocol_fee_usd_estimate: structs_6.Decimal.bcs,
            supply_interest_earned_usd_estimate: structs_6.Decimal.bcs,
        });
    }
    static fromFields(fields) {
        return InterestUpdateEvent.reified().new({
            lendingMarketId: (0, reified_1.decodeFromFields)("address", fields.lending_market_id),
            coinType: (0, reified_1.decodeFromFields)(structs_1.TypeName.reified(), fields.coin_type),
            reserveId: (0, reified_1.decodeFromFields)("address", fields.reserve_id),
            cumulativeBorrowRate: (0, reified_1.decodeFromFields)(structs_6.Decimal.reified(), fields.cumulative_borrow_rate),
            availableAmount: (0, reified_1.decodeFromFields)("u64", fields.available_amount),
            borrowedAmount: (0, reified_1.decodeFromFields)(structs_6.Decimal.reified(), fields.borrowed_amount),
            unclaimedSpreadFees: (0, reified_1.decodeFromFields)(structs_6.Decimal.reified(), fields.unclaimed_spread_fees),
            ctokenSupply: (0, reified_1.decodeFromFields)("u64", fields.ctoken_supply),
            borrowInterestPaid: (0, reified_1.decodeFromFields)(structs_6.Decimal.reified(), fields.borrow_interest_paid),
            spreadFee: (0, reified_1.decodeFromFields)(structs_6.Decimal.reified(), fields.spread_fee),
            supplyInterestEarned: (0, reified_1.decodeFromFields)(structs_6.Decimal.reified(), fields.supply_interest_earned),
            borrowInterestPaidUsdEstimate: (0, reified_1.decodeFromFields)(structs_6.Decimal.reified(), fields.borrow_interest_paid_usd_estimate),
            protocolFeeUsdEstimate: (0, reified_1.decodeFromFields)(structs_6.Decimal.reified(), fields.protocol_fee_usd_estimate),
            supplyInterestEarnedUsdEstimate: (0, reified_1.decodeFromFields)(structs_6.Decimal.reified(), fields.supply_interest_earned_usd_estimate),
        });
    }
    static fromFieldsWithTypes(item) {
        if (!isInterestUpdateEvent(item.type)) {
            throw new Error("not a InterestUpdateEvent type");
        }
        return InterestUpdateEvent.reified().new({
            lendingMarketId: (0, reified_1.decodeFromFieldsWithTypes)("address", item.fields.lending_market_id),
            coinType: (0, reified_1.decodeFromFieldsWithTypes)(structs_1.TypeName.reified(), item.fields.coin_type),
            reserveId: (0, reified_1.decodeFromFieldsWithTypes)("address", item.fields.reserve_id),
            cumulativeBorrowRate: (0, reified_1.decodeFromFieldsWithTypes)(structs_6.Decimal.reified(), item.fields.cumulative_borrow_rate),
            availableAmount: (0, reified_1.decodeFromFieldsWithTypes)("u64", item.fields.available_amount),
            borrowedAmount: (0, reified_1.decodeFromFieldsWithTypes)(structs_6.Decimal.reified(), item.fields.borrowed_amount),
            unclaimedSpreadFees: (0, reified_1.decodeFromFieldsWithTypes)(structs_6.Decimal.reified(), item.fields.unclaimed_spread_fees),
            ctokenSupply: (0, reified_1.decodeFromFieldsWithTypes)("u64", item.fields.ctoken_supply),
            borrowInterestPaid: (0, reified_1.decodeFromFieldsWithTypes)(structs_6.Decimal.reified(), item.fields.borrow_interest_paid),
            spreadFee: (0, reified_1.decodeFromFieldsWithTypes)(structs_6.Decimal.reified(), item.fields.spread_fee),
            supplyInterestEarned: (0, reified_1.decodeFromFieldsWithTypes)(structs_6.Decimal.reified(), item.fields.supply_interest_earned),
            borrowInterestPaidUsdEstimate: (0, reified_1.decodeFromFieldsWithTypes)(structs_6.Decimal.reified(), item.fields.borrow_interest_paid_usd_estimate),
            protocolFeeUsdEstimate: (0, reified_1.decodeFromFieldsWithTypes)(structs_6.Decimal.reified(), item.fields.protocol_fee_usd_estimate),
            supplyInterestEarnedUsdEstimate: (0, reified_1.decodeFromFieldsWithTypes)(structs_6.Decimal.reified(), item.fields.supply_interest_earned_usd_estimate),
        });
    }
    static fromBcs(data) {
        return InterestUpdateEvent.fromFields(InterestUpdateEvent.bcs.parse(data));
    }
    toJSONField() {
        return {
            lendingMarketId: this.lendingMarketId,
            coinType: this.coinType.toJSONField(),
            reserveId: this.reserveId,
            cumulativeBorrowRate: this.cumulativeBorrowRate.toJSONField(),
            availableAmount: this.availableAmount.toString(),
            borrowedAmount: this.borrowedAmount.toJSONField(),
            unclaimedSpreadFees: this.unclaimedSpreadFees.toJSONField(),
            ctokenSupply: this.ctokenSupply.toString(),
            borrowInterestPaid: this.borrowInterestPaid.toJSONField(),
            spreadFee: this.spreadFee.toJSONField(),
            supplyInterestEarned: this.supplyInterestEarned.toJSONField(),
            borrowInterestPaidUsdEstimate: this.borrowInterestPaidUsdEstimate.toJSONField(),
            protocolFeeUsdEstimate: this.protocolFeeUsdEstimate.toJSONField(),
            supplyInterestEarnedUsdEstimate: this.supplyInterestEarnedUsdEstimate.toJSONField(),
        };
    }
    toJSON() {
        return Object.assign({ $typeName: this.$typeName, $typeArgs: this.$typeArgs }, this.toJSONField());
    }
    static fromJSONField(field) {
        return InterestUpdateEvent.reified().new({
            lendingMarketId: (0, reified_1.decodeFromJSONField)("address", field.lendingMarketId),
            coinType: (0, reified_1.decodeFromJSONField)(structs_1.TypeName.reified(), field.coinType),
            reserveId: (0, reified_1.decodeFromJSONField)("address", field.reserveId),
            cumulativeBorrowRate: (0, reified_1.decodeFromJSONField)(structs_6.Decimal.reified(), field.cumulativeBorrowRate),
            availableAmount: (0, reified_1.decodeFromJSONField)("u64", field.availableAmount),
            borrowedAmount: (0, reified_1.decodeFromJSONField)(structs_6.Decimal.reified(), field.borrowedAmount),
            unclaimedSpreadFees: (0, reified_1.decodeFromJSONField)(structs_6.Decimal.reified(), field.unclaimedSpreadFees),
            ctokenSupply: (0, reified_1.decodeFromJSONField)("u64", field.ctokenSupply),
            borrowInterestPaid: (0, reified_1.decodeFromJSONField)(structs_6.Decimal.reified(), field.borrowInterestPaid),
            spreadFee: (0, reified_1.decodeFromJSONField)(structs_6.Decimal.reified(), field.spreadFee),
            supplyInterestEarned: (0, reified_1.decodeFromJSONField)(structs_6.Decimal.reified(), field.supplyInterestEarned),
            borrowInterestPaidUsdEstimate: (0, reified_1.decodeFromJSONField)(structs_6.Decimal.reified(), field.borrowInterestPaidUsdEstimate),
            protocolFeeUsdEstimate: (0, reified_1.decodeFromJSONField)(structs_6.Decimal.reified(), field.protocolFeeUsdEstimate),
            supplyInterestEarnedUsdEstimate: (0, reified_1.decodeFromJSONField)(structs_6.Decimal.reified(), field.supplyInterestEarnedUsdEstimate),
        });
    }
    static fromJSON(json) {
        if (json.$typeName !== InterestUpdateEvent.$typeName) {
            throw new Error("not a WithTwoGenerics json object");
        }
        return InterestUpdateEvent.fromJSONField(json);
    }
    static fromSuiParsedData(content) {
        if (content.dataType !== "moveObject") {
            throw new Error("not an object");
        }
        if (!isInterestUpdateEvent(content.type)) {
            throw new Error(`object at ${content.fields.id} is not a InterestUpdateEvent object`);
        }
        return InterestUpdateEvent.fromFieldsWithTypes(content);
    }
    static fromSuiObjectData(data) {
        if (data.bcs) {
            if (data.bcs.dataType !== "moveObject" ||
                !isInterestUpdateEvent(data.bcs.type)) {
                throw new Error(`object at is not a InterestUpdateEvent object`);
            }
            return InterestUpdateEvent.fromBcs((0, utils_1.fromB64)(data.bcs.bcsBytes));
        }
        if (data.content) {
            return InterestUpdateEvent.fromSuiParsedData(data.content);
        }
        throw new Error("Both `bcs` and `content` fields are missing from the data. Include `showBcs` or `showContent` in the request.");
    }
    static fetch(client, id) {
        return __awaiter(this, void 0, void 0, function* () {
            var _a, _b;
            const res = yield client.getObject({ id, options: { showBcs: true } });
            if (res.error) {
                throw new Error(`error fetching InterestUpdateEvent object at id ${id}: ${res.error.code}`);
            }
            if (((_b = (_a = res.data) === null || _a === void 0 ? void 0 : _a.bcs) === null || _b === void 0 ? void 0 : _b.dataType) !== "moveObject" ||
                !isInterestUpdateEvent(res.data.bcs.type)) {
                throw new Error(`object at id ${id} is not a InterestUpdateEvent object`);
            }
            return InterestUpdateEvent.fromSuiObjectData(res.data);
        });
    }
}
exports.InterestUpdateEvent = InterestUpdateEvent;
InterestUpdateEvent.$typeName = `${index_1.PKG_V1}::reserve::InterestUpdateEvent`;
InterestUpdateEvent.$numTypeParams = 0;
InterestUpdateEvent.$isPhantom = [];
/* ============================== LiquidityRequest =============================== */
function isLiquidityRequest(type) {
    type = (0, util_1.compressSuiType)(type);
    return type.startsWith(`${index_1.PKG_V8}::reserve::LiquidityRequest` + "<");
}
class LiquidityRequest {
    constructor(typeArgs, fields) {
        this.__StructClass = true;
        this.$typeName = LiquidityRequest.$typeName;
        this.$isPhantom = LiquidityRequest.$isPhantom;
        this.$fullTypeName = (0, util_1.composeSuiType)(LiquidityRequest.$typeName, ...typeArgs);
        this.$typeArgs = typeArgs;
        this.amount = fields.amount;
        this.fee = fields.fee;
    }
    static reified(P, T) {
        return {
            typeName: LiquidityRequest.$typeName,
            fullTypeName: (0, util_1.composeSuiType)(LiquidityRequest.$typeName, ...[(0, reified_1.extractType)(P), (0, reified_1.extractType)(T)]),
            typeArgs: [(0, reified_1.extractType)(P), (0, reified_1.extractType)(T)],
            isPhantom: LiquidityRequest.$isPhantom,
            reifiedTypeArgs: [P, T],
            fromFields: (fields) => LiquidityRequest.fromFields([P, T], fields),
            fromFieldsWithTypes: (item) => LiquidityRequest.fromFieldsWithTypes([P, T], item),
            fromBcs: (data) => LiquidityRequest.fromBcs([P, T], data),
            bcs: LiquidityRequest.bcs,
            fromJSONField: (field) => LiquidityRequest.fromJSONField([P, T], field),
            fromJSON: (json) => LiquidityRequest.fromJSON([P, T], json),
            fromSuiParsedData: (content) => LiquidityRequest.fromSuiParsedData([P, T], content),
            fromSuiObjectData: (content) => LiquidityRequest.fromSuiObjectData([P, T], content),
            fetch: (client, id) => __awaiter(this, void 0, void 0, function* () { return LiquidityRequest.fetch(client, [P, T], id); }),
            new: (fields) => {
                return new LiquidityRequest([(0, reified_1.extractType)(P), (0, reified_1.extractType)(T)], fields);
            },
            kind: "StructClassReified",
        };
    }
    static get r() {
        return LiquidityRequest.reified;
    }
    static phantom(P, T) {
        return (0, reified_1.phantom)(LiquidityRequest.reified(P, T));
    }
    static get p() {
        return LiquidityRequest.phantom;
    }
    static get bcs() {
        return bcs_1.bcs.struct("LiquidityRequest", {
            amount: bcs_1.bcs.u64(),
            fee: bcs_1.bcs.u64(),
        });
    }
    static fromFields(typeArgs, fields) {
        return LiquidityRequest.reified(typeArgs[0], typeArgs[1]).new({
            amount: (0, reified_1.decodeFromFields)("u64", fields.amount),
            fee: (0, reified_1.decodeFromFields)("u64", fields.fee),
        });
    }
    static fromFieldsWithTypes(typeArgs, item) {
        if (!isLiquidityRequest(item.type)) {
            throw new Error("not a LiquidityRequest type");
        }
        (0, reified_1.assertFieldsWithTypesArgsMatch)(item, typeArgs);
        return LiquidityRequest.reified(typeArgs[0], typeArgs[1]).new({
            amount: (0, reified_1.decodeFromFieldsWithTypes)("u64", item.fields.amount),
            fee: (0, reified_1.decodeFromFieldsWithTypes)("u64", item.fields.fee),
        });
    }
    static fromBcs(typeArgs, data) {
        return LiquidityRequest.fromFields(typeArgs, LiquidityRequest.bcs.parse(data));
    }
    toJSONField() {
        return {
            amount: this.amount.toString(),
            fee: this.fee.toString(),
        };
    }
    toJSON() {
        return Object.assign({ $typeName: this.$typeName, $typeArgs: this.$typeArgs }, this.toJSONField());
    }
    static fromJSONField(typeArgs, field) {
        return LiquidityRequest.reified(typeArgs[0], typeArgs[1]).new({
            amount: (0, reified_1.decodeFromJSONField)("u64", field.amount),
            fee: (0, reified_1.decodeFromJSONField)("u64", field.fee),
        });
    }
    static fromJSON(typeArgs, json) {
        if (json.$typeName !== LiquidityRequest.$typeName) {
            throw new Error("not a WithTwoGenerics json object");
        }
        (0, reified_1.assertReifiedTypeArgsMatch)((0, util_1.composeSuiType)(LiquidityRequest.$typeName, ...typeArgs.map(reified_1.extractType)), json.$typeArgs, typeArgs);
        return LiquidityRequest.fromJSONField(typeArgs, json);
    }
    static fromSuiParsedData(typeArgs, content) {
        if (content.dataType !== "moveObject") {
            throw new Error("not an object");
        }
        if (!isLiquidityRequest(content.type)) {
            throw new Error(`object at ${content.fields.id} is not a LiquidityRequest object`);
        }
        return LiquidityRequest.fromFieldsWithTypes(typeArgs, content);
    }
    static fromSuiObjectData(typeArgs, data) {
        if (data.bcs) {
            if (data.bcs.dataType !== "moveObject" ||
                !isLiquidityRequest(data.bcs.type)) {
                throw new Error(`object at is not a LiquidityRequest object`);
            }
            const gotTypeArgs = (0, util_1.parseTypeName)(data.bcs.type).typeArgs;
            if (gotTypeArgs.length !== 2) {
                throw new Error(`type argument mismatch: expected 2 type arguments but got ${gotTypeArgs.length}`);
            }
            for (let i = 0; i < 2; i++) {
                const gotTypeArg = (0, util_1.compressSuiType)(gotTypeArgs[i]);
                const expectedTypeArg = (0, util_1.compressSuiType)((0, reified_1.extractType)(typeArgs[i]));
                if (gotTypeArg !== expectedTypeArg) {
                    throw new Error(`type argument mismatch at position ${i}: expected '${expectedTypeArg}' but got '${gotTypeArg}'`);
                }
            }
            return LiquidityRequest.fromBcs(typeArgs, (0, utils_1.fromB64)(data.bcs.bcsBytes));
        }
        if (data.content) {
            return LiquidityRequest.fromSuiParsedData(typeArgs, data.content);
        }
        throw new Error("Both `bcs` and `content` fields are missing from the data. Include `showBcs` or `showContent` in the request.");
    }
    static fetch(client, typeArgs, id) {
        return __awaiter(this, void 0, void 0, function* () {
            var _a, _b;
            const res = yield client.getObject({ id, options: { showBcs: true } });
            if (res.error) {
                throw new Error(`error fetching LiquidityRequest object at id ${id}: ${res.error.code}`);
            }
            if (((_b = (_a = res.data) === null || _a === void 0 ? void 0 : _a.bcs) === null || _b === void 0 ? void 0 : _b.dataType) !== "moveObject" ||
                !isLiquidityRequest(res.data.bcs.type)) {
                throw new Error(`object at id ${id} is not a LiquidityRequest object`);
            }
            return LiquidityRequest.fromSuiObjectData(typeArgs, res.data);
        });
    }
}
exports.LiquidityRequest = LiquidityRequest;
LiquidityRequest.$typeName = `${index_1.PKG_V8}::reserve::LiquidityRequest`;
LiquidityRequest.$numTypeParams = 2;
LiquidityRequest.$isPhantom = [true, true];
/* ============================== Reserve =============================== */
function isReserve(type) {
    type = (0, util_1.compressSuiType)(type);
    return type.startsWith(`${index_1.PKG_V1}::reserve::Reserve` + "<");
}
class Reserve {
    constructor(typeArgs, fields) {
        this.__StructClass = true;
        this.$typeName = Reserve.$typeName;
        this.$isPhantom = Reserve.$isPhantom;
        this.$fullTypeName = (0, util_1.composeSuiType)(Reserve.$typeName, ...typeArgs);
        this.$typeArgs = typeArgs;
        this.id = fields.id;
        this.lendingMarketId = fields.lendingMarketId;
        this.arrayIndex = fields.arrayIndex;
        this.coinType = fields.coinType;
        this.config = fields.config;
        this.mintDecimals = fields.mintDecimals;
        this.priceIdentifier = fields.priceIdentifier;
        this.price = fields.price;
        this.smoothedPrice = fields.smoothedPrice;
        this.priceLastUpdateTimestampS = fields.priceLastUpdateTimestampS;
        this.availableAmount = fields.availableAmount;
        this.ctokenSupply = fields.ctokenSupply;
        this.borrowedAmount = fields.borrowedAmount;
        this.cumulativeBorrowRate = fields.cumulativeBorrowRate;
        this.interestLastUpdateTimestampS = fields.interestLastUpdateTimestampS;
        this.unclaimedSpreadFees = fields.unclaimedSpreadFees;
        this.attributedBorrowValue = fields.attributedBorrowValue;
        this.depositsPoolRewardManager = fields.depositsPoolRewardManager;
        this.borrowsPoolRewardManager = fields.borrowsPoolRewardManager;
    }
    static reified(P) {
        return {
            typeName: Reserve.$typeName,
            fullTypeName: (0, util_1.composeSuiType)(Reserve.$typeName, ...[(0, reified_1.extractType)(P)]),
            typeArgs: [(0, reified_1.extractType)(P)],
            isPhantom: Reserve.$isPhantom,
            reifiedTypeArgs: [P],
            fromFields: (fields) => Reserve.fromFields(P, fields),
            fromFieldsWithTypes: (item) => Reserve.fromFieldsWithTypes(P, item),
            fromBcs: (data) => Reserve.fromBcs(P, data),
            bcs: Reserve.bcs,
            fromJSONField: (field) => Reserve.fromJSONField(P, field),
            fromJSON: (json) => Reserve.fromJSON(P, json),
            fromSuiParsedData: (content) => Reserve.fromSuiParsedData(P, content),
            fromSuiObjectData: (content) => Reserve.fromSuiObjectData(P, content),
            fetch: (client, id) => __awaiter(this, void 0, void 0, function* () { return Reserve.fetch(client, P, id); }),
            new: (fields) => {
                return new Reserve([(0, reified_1.extractType)(P)], fields);
            },
            kind: "StructClassReified",
        };
    }
    static get r() {
        return Reserve.reified;
    }
    static phantom(P) {
        return (0, reified_1.phantom)(Reserve.reified(P));
    }
    static get p() {
        return Reserve.phantom;
    }
    static get bcs() {
        return bcs_1.bcs.struct("Reserve", {
            id: structs_3.UID.bcs,
            lending_market_id: structs_3.ID.bcs,
            array_index: bcs_1.bcs.u64(),
            coin_type: structs_1.TypeName.bcs,
            config: structs_5.Cell.bcs(structs_8.ReserveConfig.bcs),
            mint_decimals: bcs_1.bcs.u8(),
            price_identifier: structs_4.PriceIdentifier.bcs,
            price: structs_6.Decimal.bcs,
            smoothed_price: structs_6.Decimal.bcs,
            price_last_update_timestamp_s: bcs_1.bcs.u64(),
            available_amount: bcs_1.bcs.u64(),
            ctoken_supply: bcs_1.bcs.u64(),
            borrowed_amount: structs_6.Decimal.bcs,
            cumulative_borrow_rate: structs_6.Decimal.bcs,
            interest_last_update_timestamp_s: bcs_1.bcs.u64(),
            unclaimed_spread_fees: structs_6.Decimal.bcs,
            attributed_borrow_value: structs_6.Decimal.bcs,
            deposits_pool_reward_manager: structs_7.PoolRewardManager.bcs,
            borrows_pool_reward_manager: structs_7.PoolRewardManager.bcs,
        });
    }
    static fromFields(typeArg, fields) {
        return Reserve.reified(typeArg).new({
            id: (0, reified_1.decodeFromFields)(structs_3.UID.reified(), fields.id),
            lendingMarketId: (0, reified_1.decodeFromFields)(structs_3.ID.reified(), fields.lending_market_id),
            arrayIndex: (0, reified_1.decodeFromFields)("u64", fields.array_index),
            coinType: (0, reified_1.decodeFromFields)(structs_1.TypeName.reified(), fields.coin_type),
            config: (0, reified_1.decodeFromFields)(structs_5.Cell.reified(structs_8.ReserveConfig.reified()), fields.config),
            mintDecimals: (0, reified_1.decodeFromFields)("u8", fields.mint_decimals),
            priceIdentifier: (0, reified_1.decodeFromFields)(structs_4.PriceIdentifier.reified(), fields.price_identifier),
            price: (0, reified_1.decodeFromFields)(structs_6.Decimal.reified(), fields.price),
            smoothedPrice: (0, reified_1.decodeFromFields)(structs_6.Decimal.reified(), fields.smoothed_price),
            priceLastUpdateTimestampS: (0, reified_1.decodeFromFields)("u64", fields.price_last_update_timestamp_s),
            availableAmount: (0, reified_1.decodeFromFields)("u64", fields.available_amount),
            ctokenSupply: (0, reified_1.decodeFromFields)("u64", fields.ctoken_supply),
            borrowedAmount: (0, reified_1.decodeFromFields)(structs_6.Decimal.reified(), fields.borrowed_amount),
            cumulativeBorrowRate: (0, reified_1.decodeFromFields)(structs_6.Decimal.reified(), fields.cumulative_borrow_rate),
            interestLastUpdateTimestampS: (0, reified_1.decodeFromFields)("u64", fields.interest_last_update_timestamp_s),
            unclaimedSpreadFees: (0, reified_1.decodeFromFields)(structs_6.Decimal.reified(), fields.unclaimed_spread_fees),
            attributedBorrowValue: (0, reified_1.decodeFromFields)(structs_6.Decimal.reified(), fields.attributed_borrow_value),
            depositsPoolRewardManager: (0, reified_1.decodeFromFields)(structs_7.PoolRewardManager.reified(), fields.deposits_pool_reward_manager),
            borrowsPoolRewardManager: (0, reified_1.decodeFromFields)(structs_7.PoolRewardManager.reified(), fields.borrows_pool_reward_manager),
        });
    }
    static fromFieldsWithTypes(typeArg, item) {
        if (!isReserve(item.type)) {
            throw new Error("not a Reserve type");
        }
        (0, reified_1.assertFieldsWithTypesArgsMatch)(item, [typeArg]);
        return Reserve.reified(typeArg).new({
            id: (0, reified_1.decodeFromFieldsWithTypes)(structs_3.UID.reified(), item.fields.id),
            lendingMarketId: (0, reified_1.decodeFromFieldsWithTypes)(structs_3.ID.reified(), item.fields.lending_market_id),
            arrayIndex: (0, reified_1.decodeFromFieldsWithTypes)("u64", item.fields.array_index),
            coinType: (0, reified_1.decodeFromFieldsWithTypes)(structs_1.TypeName.reified(), item.fields.coin_type),
            config: (0, reified_1.decodeFromFieldsWithTypes)(structs_5.Cell.reified(structs_8.ReserveConfig.reified()), item.fields.config),
            mintDecimals: (0, reified_1.decodeFromFieldsWithTypes)("u8", item.fields.mint_decimals),
            priceIdentifier: (0, reified_1.decodeFromFieldsWithTypes)(structs_4.PriceIdentifier.reified(), item.fields.price_identifier),
            price: (0, reified_1.decodeFromFieldsWithTypes)(structs_6.Decimal.reified(), item.fields.price),
            smoothedPrice: (0, reified_1.decodeFromFieldsWithTypes)(structs_6.Decimal.reified(), item.fields.smoothed_price),
            priceLastUpdateTimestampS: (0, reified_1.decodeFromFieldsWithTypes)("u64", item.fields.price_last_update_timestamp_s),
            availableAmount: (0, reified_1.decodeFromFieldsWithTypes)("u64", item.fields.available_amount),
            ctokenSupply: (0, reified_1.decodeFromFieldsWithTypes)("u64", item.fields.ctoken_supply),
            borrowedAmount: (0, reified_1.decodeFromFieldsWithTypes)(structs_6.Decimal.reified(), item.fields.borrowed_amount),
            cumulativeBorrowRate: (0, reified_1.decodeFromFieldsWithTypes)(structs_6.Decimal.reified(), item.fields.cumulative_borrow_rate),
            interestLastUpdateTimestampS: (0, reified_1.decodeFromFieldsWithTypes)("u64", item.fields.interest_last_update_timestamp_s),
            unclaimedSpreadFees: (0, reified_1.decodeFromFieldsWithTypes)(structs_6.Decimal.reified(), item.fields.unclaimed_spread_fees),
            attributedBorrowValue: (0, reified_1.decodeFromFieldsWithTypes)(structs_6.Decimal.reified(), item.fields.attributed_borrow_value),
            depositsPoolRewardManager: (0, reified_1.decodeFromFieldsWithTypes)(structs_7.PoolRewardManager.reified(), item.fields.deposits_pool_reward_manager),
            borrowsPoolRewardManager: (0, reified_1.decodeFromFieldsWithTypes)(structs_7.PoolRewardManager.reified(), item.fields.borrows_pool_reward_manager),
        });
    }
    static fromBcs(typeArg, data) {
        return Reserve.fromFields(typeArg, Reserve.bcs.parse(data));
    }
    toJSONField() {
        return {
            id: this.id,
            lendingMarketId: this.lendingMarketId,
            arrayIndex: this.arrayIndex.toString(),
            coinType: this.coinType.toJSONField(),
            config: this.config.toJSONField(),
            mintDecimals: this.mintDecimals,
            priceIdentifier: this.priceIdentifier.toJSONField(),
            price: this.price.toJSONField(),
            smoothedPrice: this.smoothedPrice.toJSONField(),
            priceLastUpdateTimestampS: this.priceLastUpdateTimestampS.toString(),
            availableAmount: this.availableAmount.toString(),
            ctokenSupply: this.ctokenSupply.toString(),
            borrowedAmount: this.borrowedAmount.toJSONField(),
            cumulativeBorrowRate: this.cumulativeBorrowRate.toJSONField(),
            interestLastUpdateTimestampS: this.interestLastUpdateTimestampS.toString(),
            unclaimedSpreadFees: this.unclaimedSpreadFees.toJSONField(),
            attributedBorrowValue: this.attributedBorrowValue.toJSONField(),
            depositsPoolRewardManager: this.depositsPoolRewardManager.toJSONField(),
            borrowsPoolRewardManager: this.borrowsPoolRewardManager.toJSONField(),
        };
    }
    toJSON() {
        return Object.assign({ $typeName: this.$typeName, $typeArgs: this.$typeArgs }, this.toJSONField());
    }
    static fromJSONField(typeArg, field) {
        return Reserve.reified(typeArg).new({
            id: (0, reified_1.decodeFromJSONField)(structs_3.UID.reified(), field.id),
            lendingMarketId: (0, reified_1.decodeFromJSONField)(structs_3.ID.reified(), field.lendingMarketId),
            arrayIndex: (0, reified_1.decodeFromJSONField)("u64", field.arrayIndex),
            coinType: (0, reified_1.decodeFromJSONField)(structs_1.TypeName.reified(), field.coinType),
            config: (0, reified_1.decodeFromJSONField)(structs_5.Cell.reified(structs_8.ReserveConfig.reified()), field.config),
            mintDecimals: (0, reified_1.decodeFromJSONField)("u8", field.mintDecimals),
            priceIdentifier: (0, reified_1.decodeFromJSONField)(structs_4.PriceIdentifier.reified(), field.priceIdentifier),
            price: (0, reified_1.decodeFromJSONField)(structs_6.Decimal.reified(), field.price),
            smoothedPrice: (0, reified_1.decodeFromJSONField)(structs_6.Decimal.reified(), field.smoothedPrice),
            priceLastUpdateTimestampS: (0, reified_1.decodeFromJSONField)("u64", field.priceLastUpdateTimestampS),
            availableAmount: (0, reified_1.decodeFromJSONField)("u64", field.availableAmount),
            ctokenSupply: (0, reified_1.decodeFromJSONField)("u64", field.ctokenSupply),
            borrowedAmount: (0, reified_1.decodeFromJSONField)(structs_6.Decimal.reified(), field.borrowedAmount),
            cumulativeBorrowRate: (0, reified_1.decodeFromJSONField)(structs_6.Decimal.reified(), field.cumulativeBorrowRate),
            interestLastUpdateTimestampS: (0, reified_1.decodeFromJSONField)("u64", field.interestLastUpdateTimestampS),
            unclaimedSpreadFees: (0, reified_1.decodeFromJSONField)(structs_6.Decimal.reified(), field.unclaimedSpreadFees),
            attributedBorrowValue: (0, reified_1.decodeFromJSONField)(structs_6.Decimal.reified(), field.attributedBorrowValue),
            depositsPoolRewardManager: (0, reified_1.decodeFromJSONField)(structs_7.PoolRewardManager.reified(), field.depositsPoolRewardManager),
            borrowsPoolRewardManager: (0, reified_1.decodeFromJSONField)(structs_7.PoolRewardManager.reified(), field.borrowsPoolRewardManager),
        });
    }
    static fromJSON(typeArg, json) {
        if (json.$typeName !== Reserve.$typeName) {
            throw new Error("not a WithTwoGenerics json object");
        }
        (0, reified_1.assertReifiedTypeArgsMatch)((0, util_1.composeSuiType)(Reserve.$typeName, (0, reified_1.extractType)(typeArg)), json.$typeArgs, [typeArg]);
        return Reserve.fromJSONField(typeArg, json);
    }
    static fromSuiParsedData(typeArg, content) {
        if (content.dataType !== "moveObject") {
            throw new Error("not an object");
        }
        if (!isReserve(content.type)) {
            throw new Error(`object at ${content.fields.id} is not a Reserve object`);
        }
        return Reserve.fromFieldsWithTypes(typeArg, content);
    }
    static fromSuiObjectData(typeArg, data) {
        if (data.bcs) {
            if (data.bcs.dataType !== "moveObject" || !isReserve(data.bcs.type)) {
                throw new Error(`object at is not a Reserve object`);
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
            return Reserve.fromBcs(typeArg, (0, utils_1.fromB64)(data.bcs.bcsBytes));
        }
        if (data.content) {
            return Reserve.fromSuiParsedData(typeArg, data.content);
        }
        throw new Error("Both `bcs` and `content` fields are missing from the data. Include `showBcs` or `showContent` in the request.");
    }
    static fetch(client, typeArg, id) {
        return __awaiter(this, void 0, void 0, function* () {
            var _a, _b;
            const res = yield client.getObject({ id, options: { showBcs: true } });
            if (res.error) {
                throw new Error(`error fetching Reserve object at id ${id}: ${res.error.code}`);
            }
            if (((_b = (_a = res.data) === null || _a === void 0 ? void 0 : _a.bcs) === null || _b === void 0 ? void 0 : _b.dataType) !== "moveObject" ||
                !isReserve(res.data.bcs.type)) {
                throw new Error(`object at id ${id} is not a Reserve object`);
            }
            return Reserve.fromSuiObjectData(typeArg, res.data);
        });
    }
}
exports.Reserve = Reserve;
Reserve.$typeName = `${index_1.PKG_V1}::reserve::Reserve`;
Reserve.$numTypeParams = 1;
Reserve.$isPhantom = [true];
/* ============================== ReserveAssetDataEvent =============================== */
function isReserveAssetDataEvent(type) {
    type = (0, util_1.compressSuiType)(type);
    return type === `${index_1.PKG_V1}::reserve::ReserveAssetDataEvent`;
}
class ReserveAssetDataEvent {
    constructor(typeArgs, fields) {
        this.__StructClass = true;
        this.$typeName = ReserveAssetDataEvent.$typeName;
        this.$isPhantom = ReserveAssetDataEvent.$isPhantom;
        this.$fullTypeName = (0, util_1.composeSuiType)(ReserveAssetDataEvent.$typeName, ...typeArgs);
        this.$typeArgs = typeArgs;
        this.lendingMarketId = fields.lendingMarketId;
        this.coinType = fields.coinType;
        this.reserveId = fields.reserveId;
        this.availableAmount = fields.availableAmount;
        this.supplyAmount = fields.supplyAmount;
        this.borrowedAmount = fields.borrowedAmount;
        this.availableAmountUsdEstimate = fields.availableAmountUsdEstimate;
        this.supplyAmountUsdEstimate = fields.supplyAmountUsdEstimate;
        this.borrowedAmountUsdEstimate = fields.borrowedAmountUsdEstimate;
        this.borrowApr = fields.borrowApr;
        this.supplyApr = fields.supplyApr;
        this.ctokenSupply = fields.ctokenSupply;
        this.cumulativeBorrowRate = fields.cumulativeBorrowRate;
        this.price = fields.price;
        this.smoothedPrice = fields.smoothedPrice;
        this.priceLastUpdateTimestampS = fields.priceLastUpdateTimestampS;
    }
    static reified() {
        return {
            typeName: ReserveAssetDataEvent.$typeName,
            fullTypeName: (0, util_1.composeSuiType)(ReserveAssetDataEvent.$typeName, ...[]),
            typeArgs: [],
            isPhantom: ReserveAssetDataEvent.$isPhantom,
            reifiedTypeArgs: [],
            fromFields: (fields) => ReserveAssetDataEvent.fromFields(fields),
            fromFieldsWithTypes: (item) => ReserveAssetDataEvent.fromFieldsWithTypes(item),
            fromBcs: (data) => ReserveAssetDataEvent.fromBcs(data),
            bcs: ReserveAssetDataEvent.bcs,
            fromJSONField: (field) => ReserveAssetDataEvent.fromJSONField(field),
            fromJSON: (json) => ReserveAssetDataEvent.fromJSON(json),
            fromSuiParsedData: (content) => ReserveAssetDataEvent.fromSuiParsedData(content),
            fromSuiObjectData: (content) => ReserveAssetDataEvent.fromSuiObjectData(content),
            fetch: (client, id) => __awaiter(this, void 0, void 0, function* () { return ReserveAssetDataEvent.fetch(client, id); }),
            new: (fields) => {
                return new ReserveAssetDataEvent([], fields);
            },
            kind: "StructClassReified",
        };
    }
    static get r() {
        return ReserveAssetDataEvent.reified();
    }
    static phantom() {
        return (0, reified_1.phantom)(ReserveAssetDataEvent.reified());
    }
    static get p() {
        return ReserveAssetDataEvent.phantom();
    }
    static get bcs() {
        return bcs_1.bcs.struct("ReserveAssetDataEvent", {
            lending_market_id: bcs_1.bcs
                .bytes(32)
                .transform({
                input: (val) => (0, utils_1.fromHEX)(val),
                output: (val) => (0, utils_1.toHEX)(val),
            }),
            coin_type: structs_1.TypeName.bcs,
            reserve_id: bcs_1.bcs
                .bytes(32)
                .transform({
                input: (val) => (0, utils_1.fromHEX)(val),
                output: (val) => (0, utils_1.toHEX)(val),
            }),
            available_amount: structs_6.Decimal.bcs,
            supply_amount: structs_6.Decimal.bcs,
            borrowed_amount: structs_6.Decimal.bcs,
            available_amount_usd_estimate: structs_6.Decimal.bcs,
            supply_amount_usd_estimate: structs_6.Decimal.bcs,
            borrowed_amount_usd_estimate: structs_6.Decimal.bcs,
            borrow_apr: structs_6.Decimal.bcs,
            supply_apr: structs_6.Decimal.bcs,
            ctoken_supply: bcs_1.bcs.u64(),
            cumulative_borrow_rate: structs_6.Decimal.bcs,
            price: structs_6.Decimal.bcs,
            smoothed_price: structs_6.Decimal.bcs,
            price_last_update_timestamp_s: bcs_1.bcs.u64(),
        });
    }
    static fromFields(fields) {
        return ReserveAssetDataEvent.reified().new({
            lendingMarketId: (0, reified_1.decodeFromFields)("address", fields.lending_market_id),
            coinType: (0, reified_1.decodeFromFields)(structs_1.TypeName.reified(), fields.coin_type),
            reserveId: (0, reified_1.decodeFromFields)("address", fields.reserve_id),
            availableAmount: (0, reified_1.decodeFromFields)(structs_6.Decimal.reified(), fields.available_amount),
            supplyAmount: (0, reified_1.decodeFromFields)(structs_6.Decimal.reified(), fields.supply_amount),
            borrowedAmount: (0, reified_1.decodeFromFields)(structs_6.Decimal.reified(), fields.borrowed_amount),
            availableAmountUsdEstimate: (0, reified_1.decodeFromFields)(structs_6.Decimal.reified(), fields.available_amount_usd_estimate),
            supplyAmountUsdEstimate: (0, reified_1.decodeFromFields)(structs_6.Decimal.reified(), fields.supply_amount_usd_estimate),
            borrowedAmountUsdEstimate: (0, reified_1.decodeFromFields)(structs_6.Decimal.reified(), fields.borrowed_amount_usd_estimate),
            borrowApr: (0, reified_1.decodeFromFields)(structs_6.Decimal.reified(), fields.borrow_apr),
            supplyApr: (0, reified_1.decodeFromFields)(structs_6.Decimal.reified(), fields.supply_apr),
            ctokenSupply: (0, reified_1.decodeFromFields)("u64", fields.ctoken_supply),
            cumulativeBorrowRate: (0, reified_1.decodeFromFields)(structs_6.Decimal.reified(), fields.cumulative_borrow_rate),
            price: (0, reified_1.decodeFromFields)(structs_6.Decimal.reified(), fields.price),
            smoothedPrice: (0, reified_1.decodeFromFields)(structs_6.Decimal.reified(), fields.smoothed_price),
            priceLastUpdateTimestampS: (0, reified_1.decodeFromFields)("u64", fields.price_last_update_timestamp_s),
        });
    }
    static fromFieldsWithTypes(item) {
        if (!isReserveAssetDataEvent(item.type)) {
            throw new Error("not a ReserveAssetDataEvent type");
        }
        return ReserveAssetDataEvent.reified().new({
            lendingMarketId: (0, reified_1.decodeFromFieldsWithTypes)("address", item.fields.lending_market_id),
            coinType: (0, reified_1.decodeFromFieldsWithTypes)(structs_1.TypeName.reified(), item.fields.coin_type),
            reserveId: (0, reified_1.decodeFromFieldsWithTypes)("address", item.fields.reserve_id),
            availableAmount: (0, reified_1.decodeFromFieldsWithTypes)(structs_6.Decimal.reified(), item.fields.available_amount),
            supplyAmount: (0, reified_1.decodeFromFieldsWithTypes)(structs_6.Decimal.reified(), item.fields.supply_amount),
            borrowedAmount: (0, reified_1.decodeFromFieldsWithTypes)(structs_6.Decimal.reified(), item.fields.borrowed_amount),
            availableAmountUsdEstimate: (0, reified_1.decodeFromFieldsWithTypes)(structs_6.Decimal.reified(), item.fields.available_amount_usd_estimate),
            supplyAmountUsdEstimate: (0, reified_1.decodeFromFieldsWithTypes)(structs_6.Decimal.reified(), item.fields.supply_amount_usd_estimate),
            borrowedAmountUsdEstimate: (0, reified_1.decodeFromFieldsWithTypes)(structs_6.Decimal.reified(), item.fields.borrowed_amount_usd_estimate),
            borrowApr: (0, reified_1.decodeFromFieldsWithTypes)(structs_6.Decimal.reified(), item.fields.borrow_apr),
            supplyApr: (0, reified_1.decodeFromFieldsWithTypes)(structs_6.Decimal.reified(), item.fields.supply_apr),
            ctokenSupply: (0, reified_1.decodeFromFieldsWithTypes)("u64", item.fields.ctoken_supply),
            cumulativeBorrowRate: (0, reified_1.decodeFromFieldsWithTypes)(structs_6.Decimal.reified(), item.fields.cumulative_borrow_rate),
            price: (0, reified_1.decodeFromFieldsWithTypes)(structs_6.Decimal.reified(), item.fields.price),
            smoothedPrice: (0, reified_1.decodeFromFieldsWithTypes)(structs_6.Decimal.reified(), item.fields.smoothed_price),
            priceLastUpdateTimestampS: (0, reified_1.decodeFromFieldsWithTypes)("u64", item.fields.price_last_update_timestamp_s),
        });
    }
    static fromBcs(data) {
        return ReserveAssetDataEvent.fromFields(ReserveAssetDataEvent.bcs.parse(data));
    }
    toJSONField() {
        return {
            lendingMarketId: this.lendingMarketId,
            coinType: this.coinType.toJSONField(),
            reserveId: this.reserveId,
            availableAmount: this.availableAmount.toJSONField(),
            supplyAmount: this.supplyAmount.toJSONField(),
            borrowedAmount: this.borrowedAmount.toJSONField(),
            availableAmountUsdEstimate: this.availableAmountUsdEstimate.toJSONField(),
            supplyAmountUsdEstimate: this.supplyAmountUsdEstimate.toJSONField(),
            borrowedAmountUsdEstimate: this.borrowedAmountUsdEstimate.toJSONField(),
            borrowApr: this.borrowApr.toJSONField(),
            supplyApr: this.supplyApr.toJSONField(),
            ctokenSupply: this.ctokenSupply.toString(),
            cumulativeBorrowRate: this.cumulativeBorrowRate.toJSONField(),
            price: this.price.toJSONField(),
            smoothedPrice: this.smoothedPrice.toJSONField(),
            priceLastUpdateTimestampS: this.priceLastUpdateTimestampS.toString(),
        };
    }
    toJSON() {
        return Object.assign({ $typeName: this.$typeName, $typeArgs: this.$typeArgs }, this.toJSONField());
    }
    static fromJSONField(field) {
        return ReserveAssetDataEvent.reified().new({
            lendingMarketId: (0, reified_1.decodeFromJSONField)("address", field.lendingMarketId),
            coinType: (0, reified_1.decodeFromJSONField)(structs_1.TypeName.reified(), field.coinType),
            reserveId: (0, reified_1.decodeFromJSONField)("address", field.reserveId),
            availableAmount: (0, reified_1.decodeFromJSONField)(structs_6.Decimal.reified(), field.availableAmount),
            supplyAmount: (0, reified_1.decodeFromJSONField)(structs_6.Decimal.reified(), field.supplyAmount),
            borrowedAmount: (0, reified_1.decodeFromJSONField)(structs_6.Decimal.reified(), field.borrowedAmount),
            availableAmountUsdEstimate: (0, reified_1.decodeFromJSONField)(structs_6.Decimal.reified(), field.availableAmountUsdEstimate),
            supplyAmountUsdEstimate: (0, reified_1.decodeFromJSONField)(structs_6.Decimal.reified(), field.supplyAmountUsdEstimate),
            borrowedAmountUsdEstimate: (0, reified_1.decodeFromJSONField)(structs_6.Decimal.reified(), field.borrowedAmountUsdEstimate),
            borrowApr: (0, reified_1.decodeFromJSONField)(structs_6.Decimal.reified(), field.borrowApr),
            supplyApr: (0, reified_1.decodeFromJSONField)(structs_6.Decimal.reified(), field.supplyApr),
            ctokenSupply: (0, reified_1.decodeFromJSONField)("u64", field.ctokenSupply),
            cumulativeBorrowRate: (0, reified_1.decodeFromJSONField)(structs_6.Decimal.reified(), field.cumulativeBorrowRate),
            price: (0, reified_1.decodeFromJSONField)(structs_6.Decimal.reified(), field.price),
            smoothedPrice: (0, reified_1.decodeFromJSONField)(structs_6.Decimal.reified(), field.smoothedPrice),
            priceLastUpdateTimestampS: (0, reified_1.decodeFromJSONField)("u64", field.priceLastUpdateTimestampS),
        });
    }
    static fromJSON(json) {
        if (json.$typeName !== ReserveAssetDataEvent.$typeName) {
            throw new Error("not a WithTwoGenerics json object");
        }
        return ReserveAssetDataEvent.fromJSONField(json);
    }
    static fromSuiParsedData(content) {
        if (content.dataType !== "moveObject") {
            throw new Error("not an object");
        }
        if (!isReserveAssetDataEvent(content.type)) {
            throw new Error(`object at ${content.fields.id} is not a ReserveAssetDataEvent object`);
        }
        return ReserveAssetDataEvent.fromFieldsWithTypes(content);
    }
    static fromSuiObjectData(data) {
        if (data.bcs) {
            if (data.bcs.dataType !== "moveObject" ||
                !isReserveAssetDataEvent(data.bcs.type)) {
                throw new Error(`object at is not a ReserveAssetDataEvent object`);
            }
            return ReserveAssetDataEvent.fromBcs((0, utils_1.fromB64)(data.bcs.bcsBytes));
        }
        if (data.content) {
            return ReserveAssetDataEvent.fromSuiParsedData(data.content);
        }
        throw new Error("Both `bcs` and `content` fields are missing from the data. Include `showBcs` or `showContent` in the request.");
    }
    static fetch(client, id) {
        return __awaiter(this, void 0, void 0, function* () {
            var _a, _b;
            const res = yield client.getObject({ id, options: { showBcs: true } });
            if (res.error) {
                throw new Error(`error fetching ReserveAssetDataEvent object at id ${id}: ${res.error.code}`);
            }
            if (((_b = (_a = res.data) === null || _a === void 0 ? void 0 : _a.bcs) === null || _b === void 0 ? void 0 : _b.dataType) !== "moveObject" ||
                !isReserveAssetDataEvent(res.data.bcs.type)) {
                throw new Error(`object at id ${id} is not a ReserveAssetDataEvent object`);
            }
            return ReserveAssetDataEvent.fromSuiObjectData(res.data);
        });
    }
}
exports.ReserveAssetDataEvent = ReserveAssetDataEvent;
ReserveAssetDataEvent.$typeName = `${index_1.PKG_V1}::reserve::ReserveAssetDataEvent`;
ReserveAssetDataEvent.$numTypeParams = 0;
ReserveAssetDataEvent.$isPhantom = [];
/* ============================== StakerKey =============================== */
function isStakerKey(type) {
    type = (0, util_1.compressSuiType)(type);
    return type === `${index_1.PKG_V8}::reserve::StakerKey`;
}
class StakerKey {
    constructor(typeArgs, fields) {
        this.__StructClass = true;
        this.$typeName = StakerKey.$typeName;
        this.$isPhantom = StakerKey.$isPhantom;
        this.$fullTypeName = (0, util_1.composeSuiType)(StakerKey.$typeName, ...typeArgs);
        this.$typeArgs = typeArgs;
        this.dummyField = fields.dummyField;
    }
    static reified() {
        return {
            typeName: StakerKey.$typeName,
            fullTypeName: (0, util_1.composeSuiType)(StakerKey.$typeName, ...[]),
            typeArgs: [],
            isPhantom: StakerKey.$isPhantom,
            reifiedTypeArgs: [],
            fromFields: (fields) => StakerKey.fromFields(fields),
            fromFieldsWithTypes: (item) => StakerKey.fromFieldsWithTypes(item),
            fromBcs: (data) => StakerKey.fromBcs(data),
            bcs: StakerKey.bcs,
            fromJSONField: (field) => StakerKey.fromJSONField(field),
            fromJSON: (json) => StakerKey.fromJSON(json),
            fromSuiParsedData: (content) => StakerKey.fromSuiParsedData(content),
            fromSuiObjectData: (content) => StakerKey.fromSuiObjectData(content),
            fetch: (client, id) => __awaiter(this, void 0, void 0, function* () { return StakerKey.fetch(client, id); }),
            new: (fields) => {
                return new StakerKey([], fields);
            },
            kind: "StructClassReified",
        };
    }
    static get r() {
        return StakerKey.reified();
    }
    static phantom() {
        return (0, reified_1.phantom)(StakerKey.reified());
    }
    static get p() {
        return StakerKey.phantom();
    }
    static get bcs() {
        return bcs_1.bcs.struct("StakerKey", {
            dummy_field: bcs_1.bcs.bool(),
        });
    }
    static fromFields(fields) {
        return StakerKey.reified().new({
            dummyField: (0, reified_1.decodeFromFields)("bool", fields.dummy_field),
        });
    }
    static fromFieldsWithTypes(item) {
        if (!isStakerKey(item.type)) {
            throw new Error("not a StakerKey type");
        }
        return StakerKey.reified().new({
            dummyField: (0, reified_1.decodeFromFieldsWithTypes)("bool", item.fields.dummy_field),
        });
    }
    static fromBcs(data) {
        return StakerKey.fromFields(StakerKey.bcs.parse(data));
    }
    toJSONField() {
        return {
            dummyField: this.dummyField,
        };
    }
    toJSON() {
        return Object.assign({ $typeName: this.$typeName, $typeArgs: this.$typeArgs }, this.toJSONField());
    }
    static fromJSONField(field) {
        return StakerKey.reified().new({
            dummyField: (0, reified_1.decodeFromJSONField)("bool", field.dummyField),
        });
    }
    static fromJSON(json) {
        if (json.$typeName !== StakerKey.$typeName) {
            throw new Error("not a WithTwoGenerics json object");
        }
        return StakerKey.fromJSONField(json);
    }
    static fromSuiParsedData(content) {
        if (content.dataType !== "moveObject") {
            throw new Error("not an object");
        }
        if (!isStakerKey(content.type)) {
            throw new Error(`object at ${content.fields.id} is not a StakerKey object`);
        }
        return StakerKey.fromFieldsWithTypes(content);
    }
    static fromSuiObjectData(data) {
        if (data.bcs) {
            if (data.bcs.dataType !== "moveObject" || !isStakerKey(data.bcs.type)) {
                throw new Error(`object at is not a StakerKey object`);
            }
            return StakerKey.fromBcs((0, utils_1.fromB64)(data.bcs.bcsBytes));
        }
        if (data.content) {
            return StakerKey.fromSuiParsedData(data.content);
        }
        throw new Error("Both `bcs` and `content` fields are missing from the data. Include `showBcs` or `showContent` in the request.");
    }
    static fetch(client, id) {
        return __awaiter(this, void 0, void 0, function* () {
            var _a, _b;
            const res = yield client.getObject({ id, options: { showBcs: true } });
            if (res.error) {
                throw new Error(`error fetching StakerKey object at id ${id}: ${res.error.code}`);
            }
            if (((_b = (_a = res.data) === null || _a === void 0 ? void 0 : _a.bcs) === null || _b === void 0 ? void 0 : _b.dataType) !== "moveObject" ||
                !isStakerKey(res.data.bcs.type)) {
                throw new Error(`object at id ${id} is not a StakerKey object`);
            }
            return StakerKey.fromSuiObjectData(res.data);
        });
    }
}
exports.StakerKey = StakerKey;
StakerKey.$typeName = `${index_1.PKG_V8}::reserve::StakerKey`;
StakerKey.$numTypeParams = 0;
StakerKey.$isPhantom = [];

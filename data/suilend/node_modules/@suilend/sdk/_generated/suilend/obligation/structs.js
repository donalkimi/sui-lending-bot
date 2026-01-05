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
exports.ObligationDataEvent = exports.Obligation = exports.ExistStaleOracles = exports.DepositRecord = exports.Deposit = exports.BorrowRecord = exports.Borrow = void 0;
exports.isBorrow = isBorrow;
exports.isBorrowRecord = isBorrowRecord;
exports.isDeposit = isDeposit;
exports.isDepositRecord = isDepositRecord;
exports.isExistStaleOracles = isExistStaleOracles;
exports.isObligation = isObligation;
exports.isObligationDataEvent = isObligationDataEvent;
const reified = __importStar(require("../../_framework/reified"));
const structs_1 = require("../../_dependencies/source/0x1/type-name/structs");
const structs_2 = require("../../_dependencies/source/0x2/object/structs");
const reified_1 = require("../../_framework/reified");
const util_1 = require("../../_framework/util");
const structs_3 = require("../decimal/structs");
const index_1 = require("../index");
const structs_4 = require("../liquidity-mining/structs");
const bcs_1 = require("@mysten/sui/bcs");
const utils_1 = require("@mysten/sui/utils");
/* ============================== Borrow =============================== */
function isBorrow(type) {
    type = (0, util_1.compressSuiType)(type);
    return type === `${index_1.PKG_V1}::obligation::Borrow`;
}
class Borrow {
    constructor(typeArgs, fields) {
        this.__StructClass = true;
        this.$typeName = Borrow.$typeName;
        this.$isPhantom = Borrow.$isPhantom;
        this.$fullTypeName = (0, util_1.composeSuiType)(Borrow.$typeName, ...typeArgs);
        this.$typeArgs = typeArgs;
        this.coinType = fields.coinType;
        this.reserveArrayIndex = fields.reserveArrayIndex;
        this.borrowedAmount = fields.borrowedAmount;
        this.cumulativeBorrowRate = fields.cumulativeBorrowRate;
        this.marketValue = fields.marketValue;
        this.userRewardManagerIndex = fields.userRewardManagerIndex;
    }
    static reified() {
        return {
            typeName: Borrow.$typeName,
            fullTypeName: (0, util_1.composeSuiType)(Borrow.$typeName, ...[]),
            typeArgs: [],
            isPhantom: Borrow.$isPhantom,
            reifiedTypeArgs: [],
            fromFields: (fields) => Borrow.fromFields(fields),
            fromFieldsWithTypes: (item) => Borrow.fromFieldsWithTypes(item),
            fromBcs: (data) => Borrow.fromBcs(data),
            bcs: Borrow.bcs,
            fromJSONField: (field) => Borrow.fromJSONField(field),
            fromJSON: (json) => Borrow.fromJSON(json),
            fromSuiParsedData: (content) => Borrow.fromSuiParsedData(content),
            fromSuiObjectData: (content) => Borrow.fromSuiObjectData(content),
            fetch: (client, id) => __awaiter(this, void 0, void 0, function* () { return Borrow.fetch(client, id); }),
            new: (fields) => {
                return new Borrow([], fields);
            },
            kind: "StructClassReified",
        };
    }
    static get r() {
        return Borrow.reified();
    }
    static phantom() {
        return (0, reified_1.phantom)(Borrow.reified());
    }
    static get p() {
        return Borrow.phantom();
    }
    static get bcs() {
        return bcs_1.bcs.struct("Borrow", {
            coin_type: structs_1.TypeName.bcs,
            reserve_array_index: bcs_1.bcs.u64(),
            borrowed_amount: structs_3.Decimal.bcs,
            cumulative_borrow_rate: structs_3.Decimal.bcs,
            market_value: structs_3.Decimal.bcs,
            user_reward_manager_index: bcs_1.bcs.u64(),
        });
    }
    static fromFields(fields) {
        return Borrow.reified().new({
            coinType: (0, reified_1.decodeFromFields)(structs_1.TypeName.reified(), fields.coin_type),
            reserveArrayIndex: (0, reified_1.decodeFromFields)("u64", fields.reserve_array_index),
            borrowedAmount: (0, reified_1.decodeFromFields)(structs_3.Decimal.reified(), fields.borrowed_amount),
            cumulativeBorrowRate: (0, reified_1.decodeFromFields)(structs_3.Decimal.reified(), fields.cumulative_borrow_rate),
            marketValue: (0, reified_1.decodeFromFields)(structs_3.Decimal.reified(), fields.market_value),
            userRewardManagerIndex: (0, reified_1.decodeFromFields)("u64", fields.user_reward_manager_index),
        });
    }
    static fromFieldsWithTypes(item) {
        if (!isBorrow(item.type)) {
            throw new Error("not a Borrow type");
        }
        return Borrow.reified().new({
            coinType: (0, reified_1.decodeFromFieldsWithTypes)(structs_1.TypeName.reified(), item.fields.coin_type),
            reserveArrayIndex: (0, reified_1.decodeFromFieldsWithTypes)("u64", item.fields.reserve_array_index),
            borrowedAmount: (0, reified_1.decodeFromFieldsWithTypes)(structs_3.Decimal.reified(), item.fields.borrowed_amount),
            cumulativeBorrowRate: (0, reified_1.decodeFromFieldsWithTypes)(structs_3.Decimal.reified(), item.fields.cumulative_borrow_rate),
            marketValue: (0, reified_1.decodeFromFieldsWithTypes)(structs_3.Decimal.reified(), item.fields.market_value),
            userRewardManagerIndex: (0, reified_1.decodeFromFieldsWithTypes)("u64", item.fields.user_reward_manager_index),
        });
    }
    static fromBcs(data) {
        return Borrow.fromFields(Borrow.bcs.parse(data));
    }
    toJSONField() {
        return {
            coinType: this.coinType.toJSONField(),
            reserveArrayIndex: this.reserveArrayIndex.toString(),
            borrowedAmount: this.borrowedAmount.toJSONField(),
            cumulativeBorrowRate: this.cumulativeBorrowRate.toJSONField(),
            marketValue: this.marketValue.toJSONField(),
            userRewardManagerIndex: this.userRewardManagerIndex.toString(),
        };
    }
    toJSON() {
        return Object.assign({ $typeName: this.$typeName, $typeArgs: this.$typeArgs }, this.toJSONField());
    }
    static fromJSONField(field) {
        return Borrow.reified().new({
            coinType: (0, reified_1.decodeFromJSONField)(structs_1.TypeName.reified(), field.coinType),
            reserveArrayIndex: (0, reified_1.decodeFromJSONField)("u64", field.reserveArrayIndex),
            borrowedAmount: (0, reified_1.decodeFromJSONField)(structs_3.Decimal.reified(), field.borrowedAmount),
            cumulativeBorrowRate: (0, reified_1.decodeFromJSONField)(structs_3.Decimal.reified(), field.cumulativeBorrowRate),
            marketValue: (0, reified_1.decodeFromJSONField)(structs_3.Decimal.reified(), field.marketValue),
            userRewardManagerIndex: (0, reified_1.decodeFromJSONField)("u64", field.userRewardManagerIndex),
        });
    }
    static fromJSON(json) {
        if (json.$typeName !== Borrow.$typeName) {
            throw new Error("not a WithTwoGenerics json object");
        }
        return Borrow.fromJSONField(json);
    }
    static fromSuiParsedData(content) {
        if (content.dataType !== "moveObject") {
            throw new Error("not an object");
        }
        if (!isBorrow(content.type)) {
            throw new Error(`object at ${content.fields.id} is not a Borrow object`);
        }
        return Borrow.fromFieldsWithTypes(content);
    }
    static fromSuiObjectData(data) {
        if (data.bcs) {
            if (data.bcs.dataType !== "moveObject" || !isBorrow(data.bcs.type)) {
                throw new Error(`object at is not a Borrow object`);
            }
            return Borrow.fromBcs((0, utils_1.fromB64)(data.bcs.bcsBytes));
        }
        if (data.content) {
            return Borrow.fromSuiParsedData(data.content);
        }
        throw new Error("Both `bcs` and `content` fields are missing from the data. Include `showBcs` or `showContent` in the request.");
    }
    static fetch(client, id) {
        return __awaiter(this, void 0, void 0, function* () {
            var _a, _b;
            const res = yield client.getObject({ id, options: { showBcs: true } });
            if (res.error) {
                throw new Error(`error fetching Borrow object at id ${id}: ${res.error.code}`);
            }
            if (((_b = (_a = res.data) === null || _a === void 0 ? void 0 : _a.bcs) === null || _b === void 0 ? void 0 : _b.dataType) !== "moveObject" ||
                !isBorrow(res.data.bcs.type)) {
                throw new Error(`object at id ${id} is not a Borrow object`);
            }
            return Borrow.fromSuiObjectData(res.data);
        });
    }
}
exports.Borrow = Borrow;
Borrow.$typeName = `${index_1.PKG_V1}::obligation::Borrow`;
Borrow.$numTypeParams = 0;
Borrow.$isPhantom = [];
/* ============================== BorrowRecord =============================== */
function isBorrowRecord(type) {
    type = (0, util_1.compressSuiType)(type);
    return type === `${index_1.PKG_V1}::obligation::BorrowRecord`;
}
class BorrowRecord {
    constructor(typeArgs, fields) {
        this.__StructClass = true;
        this.$typeName = BorrowRecord.$typeName;
        this.$isPhantom = BorrowRecord.$isPhantom;
        this.$fullTypeName = (0, util_1.composeSuiType)(BorrowRecord.$typeName, ...typeArgs);
        this.$typeArgs = typeArgs;
        this.coinType = fields.coinType;
        this.reserveArrayIndex = fields.reserveArrayIndex;
        this.borrowedAmount = fields.borrowedAmount;
        this.cumulativeBorrowRate = fields.cumulativeBorrowRate;
        this.marketValue = fields.marketValue;
        this.userRewardManagerIndex = fields.userRewardManagerIndex;
    }
    static reified() {
        return {
            typeName: BorrowRecord.$typeName,
            fullTypeName: (0, util_1.composeSuiType)(BorrowRecord.$typeName, ...[]),
            typeArgs: [],
            isPhantom: BorrowRecord.$isPhantom,
            reifiedTypeArgs: [],
            fromFields: (fields) => BorrowRecord.fromFields(fields),
            fromFieldsWithTypes: (item) => BorrowRecord.fromFieldsWithTypes(item),
            fromBcs: (data) => BorrowRecord.fromBcs(data),
            bcs: BorrowRecord.bcs,
            fromJSONField: (field) => BorrowRecord.fromJSONField(field),
            fromJSON: (json) => BorrowRecord.fromJSON(json),
            fromSuiParsedData: (content) => BorrowRecord.fromSuiParsedData(content),
            fromSuiObjectData: (content) => BorrowRecord.fromSuiObjectData(content),
            fetch: (client, id) => __awaiter(this, void 0, void 0, function* () { return BorrowRecord.fetch(client, id); }),
            new: (fields) => {
                return new BorrowRecord([], fields);
            },
            kind: "StructClassReified",
        };
    }
    static get r() {
        return BorrowRecord.reified();
    }
    static phantom() {
        return (0, reified_1.phantom)(BorrowRecord.reified());
    }
    static get p() {
        return BorrowRecord.phantom();
    }
    static get bcs() {
        return bcs_1.bcs.struct("BorrowRecord", {
            coin_type: structs_1.TypeName.bcs,
            reserve_array_index: bcs_1.bcs.u64(),
            borrowed_amount: structs_3.Decimal.bcs,
            cumulative_borrow_rate: structs_3.Decimal.bcs,
            market_value: structs_3.Decimal.bcs,
            user_reward_manager_index: bcs_1.bcs.u64(),
        });
    }
    static fromFields(fields) {
        return BorrowRecord.reified().new({
            coinType: (0, reified_1.decodeFromFields)(structs_1.TypeName.reified(), fields.coin_type),
            reserveArrayIndex: (0, reified_1.decodeFromFields)("u64", fields.reserve_array_index),
            borrowedAmount: (0, reified_1.decodeFromFields)(structs_3.Decimal.reified(), fields.borrowed_amount),
            cumulativeBorrowRate: (0, reified_1.decodeFromFields)(structs_3.Decimal.reified(), fields.cumulative_borrow_rate),
            marketValue: (0, reified_1.decodeFromFields)(structs_3.Decimal.reified(), fields.market_value),
            userRewardManagerIndex: (0, reified_1.decodeFromFields)("u64", fields.user_reward_manager_index),
        });
    }
    static fromFieldsWithTypes(item) {
        if (!isBorrowRecord(item.type)) {
            throw new Error("not a BorrowRecord type");
        }
        return BorrowRecord.reified().new({
            coinType: (0, reified_1.decodeFromFieldsWithTypes)(structs_1.TypeName.reified(), item.fields.coin_type),
            reserveArrayIndex: (0, reified_1.decodeFromFieldsWithTypes)("u64", item.fields.reserve_array_index),
            borrowedAmount: (0, reified_1.decodeFromFieldsWithTypes)(structs_3.Decimal.reified(), item.fields.borrowed_amount),
            cumulativeBorrowRate: (0, reified_1.decodeFromFieldsWithTypes)(structs_3.Decimal.reified(), item.fields.cumulative_borrow_rate),
            marketValue: (0, reified_1.decodeFromFieldsWithTypes)(structs_3.Decimal.reified(), item.fields.market_value),
            userRewardManagerIndex: (0, reified_1.decodeFromFieldsWithTypes)("u64", item.fields.user_reward_manager_index),
        });
    }
    static fromBcs(data) {
        return BorrowRecord.fromFields(BorrowRecord.bcs.parse(data));
    }
    toJSONField() {
        return {
            coinType: this.coinType.toJSONField(),
            reserveArrayIndex: this.reserveArrayIndex.toString(),
            borrowedAmount: this.borrowedAmount.toJSONField(),
            cumulativeBorrowRate: this.cumulativeBorrowRate.toJSONField(),
            marketValue: this.marketValue.toJSONField(),
            userRewardManagerIndex: this.userRewardManagerIndex.toString(),
        };
    }
    toJSON() {
        return Object.assign({ $typeName: this.$typeName, $typeArgs: this.$typeArgs }, this.toJSONField());
    }
    static fromJSONField(field) {
        return BorrowRecord.reified().new({
            coinType: (0, reified_1.decodeFromJSONField)(structs_1.TypeName.reified(), field.coinType),
            reserveArrayIndex: (0, reified_1.decodeFromJSONField)("u64", field.reserveArrayIndex),
            borrowedAmount: (0, reified_1.decodeFromJSONField)(structs_3.Decimal.reified(), field.borrowedAmount),
            cumulativeBorrowRate: (0, reified_1.decodeFromJSONField)(structs_3.Decimal.reified(), field.cumulativeBorrowRate),
            marketValue: (0, reified_1.decodeFromJSONField)(structs_3.Decimal.reified(), field.marketValue),
            userRewardManagerIndex: (0, reified_1.decodeFromJSONField)("u64", field.userRewardManagerIndex),
        });
    }
    static fromJSON(json) {
        if (json.$typeName !== BorrowRecord.$typeName) {
            throw new Error("not a WithTwoGenerics json object");
        }
        return BorrowRecord.fromJSONField(json);
    }
    static fromSuiParsedData(content) {
        if (content.dataType !== "moveObject") {
            throw new Error("not an object");
        }
        if (!isBorrowRecord(content.type)) {
            throw new Error(`object at ${content.fields.id} is not a BorrowRecord object`);
        }
        return BorrowRecord.fromFieldsWithTypes(content);
    }
    static fromSuiObjectData(data) {
        if (data.bcs) {
            if (data.bcs.dataType !== "moveObject" ||
                !isBorrowRecord(data.bcs.type)) {
                throw new Error(`object at is not a BorrowRecord object`);
            }
            return BorrowRecord.fromBcs((0, utils_1.fromB64)(data.bcs.bcsBytes));
        }
        if (data.content) {
            return BorrowRecord.fromSuiParsedData(data.content);
        }
        throw new Error("Both `bcs` and `content` fields are missing from the data. Include `showBcs` or `showContent` in the request.");
    }
    static fetch(client, id) {
        return __awaiter(this, void 0, void 0, function* () {
            var _a, _b;
            const res = yield client.getObject({ id, options: { showBcs: true } });
            if (res.error) {
                throw new Error(`error fetching BorrowRecord object at id ${id}: ${res.error.code}`);
            }
            if (((_b = (_a = res.data) === null || _a === void 0 ? void 0 : _a.bcs) === null || _b === void 0 ? void 0 : _b.dataType) !== "moveObject" ||
                !isBorrowRecord(res.data.bcs.type)) {
                throw new Error(`object at id ${id} is not a BorrowRecord object`);
            }
            return BorrowRecord.fromSuiObjectData(res.data);
        });
    }
}
exports.BorrowRecord = BorrowRecord;
BorrowRecord.$typeName = `${index_1.PKG_V1}::obligation::BorrowRecord`;
BorrowRecord.$numTypeParams = 0;
BorrowRecord.$isPhantom = [];
/* ============================== Deposit =============================== */
function isDeposit(type) {
    type = (0, util_1.compressSuiType)(type);
    return type === `${index_1.PKG_V1}::obligation::Deposit`;
}
class Deposit {
    constructor(typeArgs, fields) {
        this.__StructClass = true;
        this.$typeName = Deposit.$typeName;
        this.$isPhantom = Deposit.$isPhantom;
        this.$fullTypeName = (0, util_1.composeSuiType)(Deposit.$typeName, ...typeArgs);
        this.$typeArgs = typeArgs;
        this.coinType = fields.coinType;
        this.reserveArrayIndex = fields.reserveArrayIndex;
        this.depositedCtokenAmount = fields.depositedCtokenAmount;
        this.marketValue = fields.marketValue;
        this.userRewardManagerIndex = fields.userRewardManagerIndex;
        this.attributedBorrowValue = fields.attributedBorrowValue;
    }
    static reified() {
        return {
            typeName: Deposit.$typeName,
            fullTypeName: (0, util_1.composeSuiType)(Deposit.$typeName, ...[]),
            typeArgs: [],
            isPhantom: Deposit.$isPhantom,
            reifiedTypeArgs: [],
            fromFields: (fields) => Deposit.fromFields(fields),
            fromFieldsWithTypes: (item) => Deposit.fromFieldsWithTypes(item),
            fromBcs: (data) => Deposit.fromBcs(data),
            bcs: Deposit.bcs,
            fromJSONField: (field) => Deposit.fromJSONField(field),
            fromJSON: (json) => Deposit.fromJSON(json),
            fromSuiParsedData: (content) => Deposit.fromSuiParsedData(content),
            fromSuiObjectData: (content) => Deposit.fromSuiObjectData(content),
            fetch: (client, id) => __awaiter(this, void 0, void 0, function* () { return Deposit.fetch(client, id); }),
            new: (fields) => {
                return new Deposit([], fields);
            },
            kind: "StructClassReified",
        };
    }
    static get r() {
        return Deposit.reified();
    }
    static phantom() {
        return (0, reified_1.phantom)(Deposit.reified());
    }
    static get p() {
        return Deposit.phantom();
    }
    static get bcs() {
        return bcs_1.bcs.struct("Deposit", {
            coin_type: structs_1.TypeName.bcs,
            reserve_array_index: bcs_1.bcs.u64(),
            deposited_ctoken_amount: bcs_1.bcs.u64(),
            market_value: structs_3.Decimal.bcs,
            user_reward_manager_index: bcs_1.bcs.u64(),
            attributed_borrow_value: structs_3.Decimal.bcs,
        });
    }
    static fromFields(fields) {
        return Deposit.reified().new({
            coinType: (0, reified_1.decodeFromFields)(structs_1.TypeName.reified(), fields.coin_type),
            reserveArrayIndex: (0, reified_1.decodeFromFields)("u64", fields.reserve_array_index),
            depositedCtokenAmount: (0, reified_1.decodeFromFields)("u64", fields.deposited_ctoken_amount),
            marketValue: (0, reified_1.decodeFromFields)(structs_3.Decimal.reified(), fields.market_value),
            userRewardManagerIndex: (0, reified_1.decodeFromFields)("u64", fields.user_reward_manager_index),
            attributedBorrowValue: (0, reified_1.decodeFromFields)(structs_3.Decimal.reified(), fields.attributed_borrow_value),
        });
    }
    static fromFieldsWithTypes(item) {
        if (!isDeposit(item.type)) {
            throw new Error("not a Deposit type");
        }
        return Deposit.reified().new({
            coinType: (0, reified_1.decodeFromFieldsWithTypes)(structs_1.TypeName.reified(), item.fields.coin_type),
            reserveArrayIndex: (0, reified_1.decodeFromFieldsWithTypes)("u64", item.fields.reserve_array_index),
            depositedCtokenAmount: (0, reified_1.decodeFromFieldsWithTypes)("u64", item.fields.deposited_ctoken_amount),
            marketValue: (0, reified_1.decodeFromFieldsWithTypes)(structs_3.Decimal.reified(), item.fields.market_value),
            userRewardManagerIndex: (0, reified_1.decodeFromFieldsWithTypes)("u64", item.fields.user_reward_manager_index),
            attributedBorrowValue: (0, reified_1.decodeFromFieldsWithTypes)(structs_3.Decimal.reified(), item.fields.attributed_borrow_value),
        });
    }
    static fromBcs(data) {
        return Deposit.fromFields(Deposit.bcs.parse(data));
    }
    toJSONField() {
        return {
            coinType: this.coinType.toJSONField(),
            reserveArrayIndex: this.reserveArrayIndex.toString(),
            depositedCtokenAmount: this.depositedCtokenAmount.toString(),
            marketValue: this.marketValue.toJSONField(),
            userRewardManagerIndex: this.userRewardManagerIndex.toString(),
            attributedBorrowValue: this.attributedBorrowValue.toJSONField(),
        };
    }
    toJSON() {
        return Object.assign({ $typeName: this.$typeName, $typeArgs: this.$typeArgs }, this.toJSONField());
    }
    static fromJSONField(field) {
        return Deposit.reified().new({
            coinType: (0, reified_1.decodeFromJSONField)(structs_1.TypeName.reified(), field.coinType),
            reserveArrayIndex: (0, reified_1.decodeFromJSONField)("u64", field.reserveArrayIndex),
            depositedCtokenAmount: (0, reified_1.decodeFromJSONField)("u64", field.depositedCtokenAmount),
            marketValue: (0, reified_1.decodeFromJSONField)(structs_3.Decimal.reified(), field.marketValue),
            userRewardManagerIndex: (0, reified_1.decodeFromJSONField)("u64", field.userRewardManagerIndex),
            attributedBorrowValue: (0, reified_1.decodeFromJSONField)(structs_3.Decimal.reified(), field.attributedBorrowValue),
        });
    }
    static fromJSON(json) {
        if (json.$typeName !== Deposit.$typeName) {
            throw new Error("not a WithTwoGenerics json object");
        }
        return Deposit.fromJSONField(json);
    }
    static fromSuiParsedData(content) {
        if (content.dataType !== "moveObject") {
            throw new Error("not an object");
        }
        if (!isDeposit(content.type)) {
            throw new Error(`object at ${content.fields.id} is not a Deposit object`);
        }
        return Deposit.fromFieldsWithTypes(content);
    }
    static fromSuiObjectData(data) {
        if (data.bcs) {
            if (data.bcs.dataType !== "moveObject" || !isDeposit(data.bcs.type)) {
                throw new Error(`object at is not a Deposit object`);
            }
            return Deposit.fromBcs((0, utils_1.fromB64)(data.bcs.bcsBytes));
        }
        if (data.content) {
            return Deposit.fromSuiParsedData(data.content);
        }
        throw new Error("Both `bcs` and `content` fields are missing from the data. Include `showBcs` or `showContent` in the request.");
    }
    static fetch(client, id) {
        return __awaiter(this, void 0, void 0, function* () {
            var _a, _b;
            const res = yield client.getObject({ id, options: { showBcs: true } });
            if (res.error) {
                throw new Error(`error fetching Deposit object at id ${id}: ${res.error.code}`);
            }
            if (((_b = (_a = res.data) === null || _a === void 0 ? void 0 : _a.bcs) === null || _b === void 0 ? void 0 : _b.dataType) !== "moveObject" ||
                !isDeposit(res.data.bcs.type)) {
                throw new Error(`object at id ${id} is not a Deposit object`);
            }
            return Deposit.fromSuiObjectData(res.data);
        });
    }
}
exports.Deposit = Deposit;
Deposit.$typeName = `${index_1.PKG_V1}::obligation::Deposit`;
Deposit.$numTypeParams = 0;
Deposit.$isPhantom = [];
/* ============================== DepositRecord =============================== */
function isDepositRecord(type) {
    type = (0, util_1.compressSuiType)(type);
    return type === `${index_1.PKG_V1}::obligation::DepositRecord`;
}
class DepositRecord {
    constructor(typeArgs, fields) {
        this.__StructClass = true;
        this.$typeName = DepositRecord.$typeName;
        this.$isPhantom = DepositRecord.$isPhantom;
        this.$fullTypeName = (0, util_1.composeSuiType)(DepositRecord.$typeName, ...typeArgs);
        this.$typeArgs = typeArgs;
        this.coinType = fields.coinType;
        this.reserveArrayIndex = fields.reserveArrayIndex;
        this.depositedCtokenAmount = fields.depositedCtokenAmount;
        this.marketValue = fields.marketValue;
        this.userRewardManagerIndex = fields.userRewardManagerIndex;
        this.attributedBorrowValue = fields.attributedBorrowValue;
    }
    static reified() {
        return {
            typeName: DepositRecord.$typeName,
            fullTypeName: (0, util_1.composeSuiType)(DepositRecord.$typeName, ...[]),
            typeArgs: [],
            isPhantom: DepositRecord.$isPhantom,
            reifiedTypeArgs: [],
            fromFields: (fields) => DepositRecord.fromFields(fields),
            fromFieldsWithTypes: (item) => DepositRecord.fromFieldsWithTypes(item),
            fromBcs: (data) => DepositRecord.fromBcs(data),
            bcs: DepositRecord.bcs,
            fromJSONField: (field) => DepositRecord.fromJSONField(field),
            fromJSON: (json) => DepositRecord.fromJSON(json),
            fromSuiParsedData: (content) => DepositRecord.fromSuiParsedData(content),
            fromSuiObjectData: (content) => DepositRecord.fromSuiObjectData(content),
            fetch: (client, id) => __awaiter(this, void 0, void 0, function* () { return DepositRecord.fetch(client, id); }),
            new: (fields) => {
                return new DepositRecord([], fields);
            },
            kind: "StructClassReified",
        };
    }
    static get r() {
        return DepositRecord.reified();
    }
    static phantom() {
        return (0, reified_1.phantom)(DepositRecord.reified());
    }
    static get p() {
        return DepositRecord.phantom();
    }
    static get bcs() {
        return bcs_1.bcs.struct("DepositRecord", {
            coin_type: structs_1.TypeName.bcs,
            reserve_array_index: bcs_1.bcs.u64(),
            deposited_ctoken_amount: bcs_1.bcs.u64(),
            market_value: structs_3.Decimal.bcs,
            user_reward_manager_index: bcs_1.bcs.u64(),
            attributed_borrow_value: structs_3.Decimal.bcs,
        });
    }
    static fromFields(fields) {
        return DepositRecord.reified().new({
            coinType: (0, reified_1.decodeFromFields)(structs_1.TypeName.reified(), fields.coin_type),
            reserveArrayIndex: (0, reified_1.decodeFromFields)("u64", fields.reserve_array_index),
            depositedCtokenAmount: (0, reified_1.decodeFromFields)("u64", fields.deposited_ctoken_amount),
            marketValue: (0, reified_1.decodeFromFields)(structs_3.Decimal.reified(), fields.market_value),
            userRewardManagerIndex: (0, reified_1.decodeFromFields)("u64", fields.user_reward_manager_index),
            attributedBorrowValue: (0, reified_1.decodeFromFields)(structs_3.Decimal.reified(), fields.attributed_borrow_value),
        });
    }
    static fromFieldsWithTypes(item) {
        if (!isDepositRecord(item.type)) {
            throw new Error("not a DepositRecord type");
        }
        return DepositRecord.reified().new({
            coinType: (0, reified_1.decodeFromFieldsWithTypes)(structs_1.TypeName.reified(), item.fields.coin_type),
            reserveArrayIndex: (0, reified_1.decodeFromFieldsWithTypes)("u64", item.fields.reserve_array_index),
            depositedCtokenAmount: (0, reified_1.decodeFromFieldsWithTypes)("u64", item.fields.deposited_ctoken_amount),
            marketValue: (0, reified_1.decodeFromFieldsWithTypes)(structs_3.Decimal.reified(), item.fields.market_value),
            userRewardManagerIndex: (0, reified_1.decodeFromFieldsWithTypes)("u64", item.fields.user_reward_manager_index),
            attributedBorrowValue: (0, reified_1.decodeFromFieldsWithTypes)(structs_3.Decimal.reified(), item.fields.attributed_borrow_value),
        });
    }
    static fromBcs(data) {
        return DepositRecord.fromFields(DepositRecord.bcs.parse(data));
    }
    toJSONField() {
        return {
            coinType: this.coinType.toJSONField(),
            reserveArrayIndex: this.reserveArrayIndex.toString(),
            depositedCtokenAmount: this.depositedCtokenAmount.toString(),
            marketValue: this.marketValue.toJSONField(),
            userRewardManagerIndex: this.userRewardManagerIndex.toString(),
            attributedBorrowValue: this.attributedBorrowValue.toJSONField(),
        };
    }
    toJSON() {
        return Object.assign({ $typeName: this.$typeName, $typeArgs: this.$typeArgs }, this.toJSONField());
    }
    static fromJSONField(field) {
        return DepositRecord.reified().new({
            coinType: (0, reified_1.decodeFromJSONField)(structs_1.TypeName.reified(), field.coinType),
            reserveArrayIndex: (0, reified_1.decodeFromJSONField)("u64", field.reserveArrayIndex),
            depositedCtokenAmount: (0, reified_1.decodeFromJSONField)("u64", field.depositedCtokenAmount),
            marketValue: (0, reified_1.decodeFromJSONField)(structs_3.Decimal.reified(), field.marketValue),
            userRewardManagerIndex: (0, reified_1.decodeFromJSONField)("u64", field.userRewardManagerIndex),
            attributedBorrowValue: (0, reified_1.decodeFromJSONField)(structs_3.Decimal.reified(), field.attributedBorrowValue),
        });
    }
    static fromJSON(json) {
        if (json.$typeName !== DepositRecord.$typeName) {
            throw new Error("not a WithTwoGenerics json object");
        }
        return DepositRecord.fromJSONField(json);
    }
    static fromSuiParsedData(content) {
        if (content.dataType !== "moveObject") {
            throw new Error("not an object");
        }
        if (!isDepositRecord(content.type)) {
            throw new Error(`object at ${content.fields.id} is not a DepositRecord object`);
        }
        return DepositRecord.fromFieldsWithTypes(content);
    }
    static fromSuiObjectData(data) {
        if (data.bcs) {
            if (data.bcs.dataType !== "moveObject" ||
                !isDepositRecord(data.bcs.type)) {
                throw new Error(`object at is not a DepositRecord object`);
            }
            return DepositRecord.fromBcs((0, utils_1.fromB64)(data.bcs.bcsBytes));
        }
        if (data.content) {
            return DepositRecord.fromSuiParsedData(data.content);
        }
        throw new Error("Both `bcs` and `content` fields are missing from the data. Include `showBcs` or `showContent` in the request.");
    }
    static fetch(client, id) {
        return __awaiter(this, void 0, void 0, function* () {
            var _a, _b;
            const res = yield client.getObject({ id, options: { showBcs: true } });
            if (res.error) {
                throw new Error(`error fetching DepositRecord object at id ${id}: ${res.error.code}`);
            }
            if (((_b = (_a = res.data) === null || _a === void 0 ? void 0 : _a.bcs) === null || _b === void 0 ? void 0 : _b.dataType) !== "moveObject" ||
                !isDepositRecord(res.data.bcs.type)) {
                throw new Error(`object at id ${id} is not a DepositRecord object`);
            }
            return DepositRecord.fromSuiObjectData(res.data);
        });
    }
}
exports.DepositRecord = DepositRecord;
DepositRecord.$typeName = `${index_1.PKG_V1}::obligation::DepositRecord`;
DepositRecord.$numTypeParams = 0;
DepositRecord.$isPhantom = [];
/* ============================== ExistStaleOracles =============================== */
function isExistStaleOracles(type) {
    type = (0, util_1.compressSuiType)(type);
    return type === `${index_1.PKG_V11}::obligation::ExistStaleOracles`;
}
class ExistStaleOracles {
    constructor(typeArgs, fields) {
        this.__StructClass = true;
        this.$typeName = ExistStaleOracles.$typeName;
        this.$isPhantom = ExistStaleOracles.$isPhantom;
        this.$fullTypeName = (0, util_1.composeSuiType)(ExistStaleOracles.$typeName, ...typeArgs);
        this.$typeArgs = typeArgs;
        this.dummyField = fields.dummyField;
    }
    static reified() {
        return {
            typeName: ExistStaleOracles.$typeName,
            fullTypeName: (0, util_1.composeSuiType)(ExistStaleOracles.$typeName, ...[]),
            typeArgs: [],
            isPhantom: ExistStaleOracles.$isPhantom,
            reifiedTypeArgs: [],
            fromFields: (fields) => ExistStaleOracles.fromFields(fields),
            fromFieldsWithTypes: (item) => ExistStaleOracles.fromFieldsWithTypes(item),
            fromBcs: (data) => ExistStaleOracles.fromBcs(data),
            bcs: ExistStaleOracles.bcs,
            fromJSONField: (field) => ExistStaleOracles.fromJSONField(field),
            fromJSON: (json) => ExistStaleOracles.fromJSON(json),
            fromSuiParsedData: (content) => ExistStaleOracles.fromSuiParsedData(content),
            fromSuiObjectData: (content) => ExistStaleOracles.fromSuiObjectData(content),
            fetch: (client, id) => __awaiter(this, void 0, void 0, function* () { return ExistStaleOracles.fetch(client, id); }),
            new: (fields) => {
                return new ExistStaleOracles([], fields);
            },
            kind: "StructClassReified",
        };
    }
    static get r() {
        return ExistStaleOracles.reified();
    }
    static phantom() {
        return (0, reified_1.phantom)(ExistStaleOracles.reified());
    }
    static get p() {
        return ExistStaleOracles.phantom();
    }
    static get bcs() {
        return bcs_1.bcs.struct("ExistStaleOracles", {
            dummy_field: bcs_1.bcs.bool(),
        });
    }
    static fromFields(fields) {
        return ExistStaleOracles.reified().new({
            dummyField: (0, reified_1.decodeFromFields)("bool", fields.dummy_field),
        });
    }
    static fromFieldsWithTypes(item) {
        if (!isExistStaleOracles(item.type)) {
            throw new Error("not a ExistStaleOracles type");
        }
        return ExistStaleOracles.reified().new({
            dummyField: (0, reified_1.decodeFromFieldsWithTypes)("bool", item.fields.dummy_field),
        });
    }
    static fromBcs(data) {
        return ExistStaleOracles.fromFields(ExistStaleOracles.bcs.parse(data));
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
        return ExistStaleOracles.reified().new({
            dummyField: (0, reified_1.decodeFromJSONField)("bool", field.dummyField),
        });
    }
    static fromJSON(json) {
        if (json.$typeName !== ExistStaleOracles.$typeName) {
            throw new Error("not a WithTwoGenerics json object");
        }
        return ExistStaleOracles.fromJSONField(json);
    }
    static fromSuiParsedData(content) {
        if (content.dataType !== "moveObject") {
            throw new Error("not an object");
        }
        if (!isExistStaleOracles(content.type)) {
            throw new Error(`object at ${content.fields.id} is not a ExistStaleOracles object`);
        }
        return ExistStaleOracles.fromFieldsWithTypes(content);
    }
    static fromSuiObjectData(data) {
        if (data.bcs) {
            if (data.bcs.dataType !== "moveObject" ||
                !isExistStaleOracles(data.bcs.type)) {
                throw new Error(`object at is not a ExistStaleOracles object`);
            }
            return ExistStaleOracles.fromBcs((0, utils_1.fromB64)(data.bcs.bcsBytes));
        }
        if (data.content) {
            return ExistStaleOracles.fromSuiParsedData(data.content);
        }
        throw new Error("Both `bcs` and `content` fields are missing from the data. Include `showBcs` or `showContent` in the request.");
    }
    static fetch(client, id) {
        return __awaiter(this, void 0, void 0, function* () {
            var _a, _b;
            const res = yield client.getObject({ id, options: { showBcs: true } });
            if (res.error) {
                throw new Error(`error fetching ExistStaleOracles object at id ${id}: ${res.error.code}`);
            }
            if (((_b = (_a = res.data) === null || _a === void 0 ? void 0 : _a.bcs) === null || _b === void 0 ? void 0 : _b.dataType) !== "moveObject" ||
                !isExistStaleOracles(res.data.bcs.type)) {
                throw new Error(`object at id ${id} is not a ExistStaleOracles object`);
            }
            return ExistStaleOracles.fromSuiObjectData(res.data);
        });
    }
}
exports.ExistStaleOracles = ExistStaleOracles;
ExistStaleOracles.$typeName = `${index_1.PKG_V11}::obligation::ExistStaleOracles`;
ExistStaleOracles.$numTypeParams = 0;
ExistStaleOracles.$isPhantom = [];
/* ============================== Obligation =============================== */
function isObligation(type) {
    type = (0, util_1.compressSuiType)(type);
    return type.startsWith(`${index_1.PKG_V1}::obligation::Obligation` + "<");
}
class Obligation {
    constructor(typeArgs, fields) {
        this.__StructClass = true;
        this.$typeName = Obligation.$typeName;
        this.$isPhantom = Obligation.$isPhantom;
        this.$fullTypeName = (0, util_1.composeSuiType)(Obligation.$typeName, ...typeArgs);
        this.$typeArgs = typeArgs;
        this.id = fields.id;
        this.lendingMarketId = fields.lendingMarketId;
        this.deposits = fields.deposits;
        this.borrows = fields.borrows;
        this.depositedValueUsd = fields.depositedValueUsd;
        this.allowedBorrowValueUsd = fields.allowedBorrowValueUsd;
        this.unhealthyBorrowValueUsd = fields.unhealthyBorrowValueUsd;
        this.superUnhealthyBorrowValueUsd = fields.superUnhealthyBorrowValueUsd;
        this.unweightedBorrowedValueUsd = fields.unweightedBorrowedValueUsd;
        this.weightedBorrowedValueUsd = fields.weightedBorrowedValueUsd;
        this.weightedBorrowedValueUpperBoundUsd =
            fields.weightedBorrowedValueUpperBoundUsd;
        this.borrowingIsolatedAsset = fields.borrowingIsolatedAsset;
        this.userRewardManagers = fields.userRewardManagers;
        this.badDebtUsd = fields.badDebtUsd;
        this.closable = fields.closable;
    }
    static reified(P) {
        return {
            typeName: Obligation.$typeName,
            fullTypeName: (0, util_1.composeSuiType)(Obligation.$typeName, ...[(0, reified_1.extractType)(P)]),
            typeArgs: [(0, reified_1.extractType)(P)],
            isPhantom: Obligation.$isPhantom,
            reifiedTypeArgs: [P],
            fromFields: (fields) => Obligation.fromFields(P, fields),
            fromFieldsWithTypes: (item) => Obligation.fromFieldsWithTypes(P, item),
            fromBcs: (data) => Obligation.fromBcs(P, data),
            bcs: Obligation.bcs,
            fromJSONField: (field) => Obligation.fromJSONField(P, field),
            fromJSON: (json) => Obligation.fromJSON(P, json),
            fromSuiParsedData: (content) => Obligation.fromSuiParsedData(P, content),
            fromSuiObjectData: (content) => Obligation.fromSuiObjectData(P, content),
            fetch: (client, id) => __awaiter(this, void 0, void 0, function* () { return Obligation.fetch(client, P, id); }),
            new: (fields) => {
                return new Obligation([(0, reified_1.extractType)(P)], fields);
            },
            kind: "StructClassReified",
        };
    }
    static get r() {
        return Obligation.reified;
    }
    static phantom(P) {
        return (0, reified_1.phantom)(Obligation.reified(P));
    }
    static get p() {
        return Obligation.phantom;
    }
    static get bcs() {
        return bcs_1.bcs.struct("Obligation", {
            id: structs_2.UID.bcs,
            lending_market_id: structs_2.ID.bcs,
            deposits: bcs_1.bcs.vector(Deposit.bcs),
            borrows: bcs_1.bcs.vector(Borrow.bcs),
            deposited_value_usd: structs_3.Decimal.bcs,
            allowed_borrow_value_usd: structs_3.Decimal.bcs,
            unhealthy_borrow_value_usd: structs_3.Decimal.bcs,
            super_unhealthy_borrow_value_usd: structs_3.Decimal.bcs,
            unweighted_borrowed_value_usd: structs_3.Decimal.bcs,
            weighted_borrowed_value_usd: structs_3.Decimal.bcs,
            weighted_borrowed_value_upper_bound_usd: structs_3.Decimal.bcs,
            borrowing_isolated_asset: bcs_1.bcs.bool(),
            user_reward_managers: bcs_1.bcs.vector(structs_4.UserRewardManager.bcs),
            bad_debt_usd: structs_3.Decimal.bcs,
            closable: bcs_1.bcs.bool(),
        });
    }
    static fromFields(typeArg, fields) {
        return Obligation.reified(typeArg).new({
            id: (0, reified_1.decodeFromFields)(structs_2.UID.reified(), fields.id),
            lendingMarketId: (0, reified_1.decodeFromFields)(structs_2.ID.reified(), fields.lending_market_id),
            deposits: (0, reified_1.decodeFromFields)(reified.vector(Deposit.reified()), fields.deposits),
            borrows: (0, reified_1.decodeFromFields)(reified.vector(Borrow.reified()), fields.borrows),
            depositedValueUsd: (0, reified_1.decodeFromFields)(structs_3.Decimal.reified(), fields.deposited_value_usd),
            allowedBorrowValueUsd: (0, reified_1.decodeFromFields)(structs_3.Decimal.reified(), fields.allowed_borrow_value_usd),
            unhealthyBorrowValueUsd: (0, reified_1.decodeFromFields)(structs_3.Decimal.reified(), fields.unhealthy_borrow_value_usd),
            superUnhealthyBorrowValueUsd: (0, reified_1.decodeFromFields)(structs_3.Decimal.reified(), fields.super_unhealthy_borrow_value_usd),
            unweightedBorrowedValueUsd: (0, reified_1.decodeFromFields)(structs_3.Decimal.reified(), fields.unweighted_borrowed_value_usd),
            weightedBorrowedValueUsd: (0, reified_1.decodeFromFields)(structs_3.Decimal.reified(), fields.weighted_borrowed_value_usd),
            weightedBorrowedValueUpperBoundUsd: (0, reified_1.decodeFromFields)(structs_3.Decimal.reified(), fields.weighted_borrowed_value_upper_bound_usd),
            borrowingIsolatedAsset: (0, reified_1.decodeFromFields)("bool", fields.borrowing_isolated_asset),
            userRewardManagers: (0, reified_1.decodeFromFields)(reified.vector(structs_4.UserRewardManager.reified()), fields.user_reward_managers),
            badDebtUsd: (0, reified_1.decodeFromFields)(structs_3.Decimal.reified(), fields.bad_debt_usd),
            closable: (0, reified_1.decodeFromFields)("bool", fields.closable),
        });
    }
    static fromFieldsWithTypes(typeArg, item) {
        if (!isObligation(item.type)) {
            throw new Error("not a Obligation type");
        }
        (0, reified_1.assertFieldsWithTypesArgsMatch)(item, [typeArg]);
        return Obligation.reified(typeArg).new({
            id: (0, reified_1.decodeFromFieldsWithTypes)(structs_2.UID.reified(), item.fields.id),
            lendingMarketId: (0, reified_1.decodeFromFieldsWithTypes)(structs_2.ID.reified(), item.fields.lending_market_id),
            deposits: (0, reified_1.decodeFromFieldsWithTypes)(reified.vector(Deposit.reified()), item.fields.deposits),
            borrows: (0, reified_1.decodeFromFieldsWithTypes)(reified.vector(Borrow.reified()), item.fields.borrows),
            depositedValueUsd: (0, reified_1.decodeFromFieldsWithTypes)(structs_3.Decimal.reified(), item.fields.deposited_value_usd),
            allowedBorrowValueUsd: (0, reified_1.decodeFromFieldsWithTypes)(structs_3.Decimal.reified(), item.fields.allowed_borrow_value_usd),
            unhealthyBorrowValueUsd: (0, reified_1.decodeFromFieldsWithTypes)(structs_3.Decimal.reified(), item.fields.unhealthy_borrow_value_usd),
            superUnhealthyBorrowValueUsd: (0, reified_1.decodeFromFieldsWithTypes)(structs_3.Decimal.reified(), item.fields.super_unhealthy_borrow_value_usd),
            unweightedBorrowedValueUsd: (0, reified_1.decodeFromFieldsWithTypes)(structs_3.Decimal.reified(), item.fields.unweighted_borrowed_value_usd),
            weightedBorrowedValueUsd: (0, reified_1.decodeFromFieldsWithTypes)(structs_3.Decimal.reified(), item.fields.weighted_borrowed_value_usd),
            weightedBorrowedValueUpperBoundUsd: (0, reified_1.decodeFromFieldsWithTypes)(structs_3.Decimal.reified(), item.fields.weighted_borrowed_value_upper_bound_usd),
            borrowingIsolatedAsset: (0, reified_1.decodeFromFieldsWithTypes)("bool", item.fields.borrowing_isolated_asset),
            userRewardManagers: (0, reified_1.decodeFromFieldsWithTypes)(reified.vector(structs_4.UserRewardManager.reified()), item.fields.user_reward_managers),
            badDebtUsd: (0, reified_1.decodeFromFieldsWithTypes)(structs_3.Decimal.reified(), item.fields.bad_debt_usd),
            closable: (0, reified_1.decodeFromFieldsWithTypes)("bool", item.fields.closable),
        });
    }
    static fromBcs(typeArg, data) {
        return Obligation.fromFields(typeArg, Obligation.bcs.parse(data));
    }
    toJSONField() {
        return {
            id: this.id,
            lendingMarketId: this.lendingMarketId,
            deposits: (0, reified_1.fieldToJSON)(`vector<${Deposit.$typeName}>`, this.deposits),
            borrows: (0, reified_1.fieldToJSON)(`vector<${Borrow.$typeName}>`, this.borrows),
            depositedValueUsd: this.depositedValueUsd.toJSONField(),
            allowedBorrowValueUsd: this.allowedBorrowValueUsd.toJSONField(),
            unhealthyBorrowValueUsd: this.unhealthyBorrowValueUsd.toJSONField(),
            superUnhealthyBorrowValueUsd: this.superUnhealthyBorrowValueUsd.toJSONField(),
            unweightedBorrowedValueUsd: this.unweightedBorrowedValueUsd.toJSONField(),
            weightedBorrowedValueUsd: this.weightedBorrowedValueUsd.toJSONField(),
            weightedBorrowedValueUpperBoundUsd: this.weightedBorrowedValueUpperBoundUsd.toJSONField(),
            borrowingIsolatedAsset: this.borrowingIsolatedAsset,
            userRewardManagers: (0, reified_1.fieldToJSON)(`vector<${structs_4.UserRewardManager.$typeName}>`, this.userRewardManagers),
            badDebtUsd: this.badDebtUsd.toJSONField(),
            closable: this.closable,
        };
    }
    toJSON() {
        return Object.assign({ $typeName: this.$typeName, $typeArgs: this.$typeArgs }, this.toJSONField());
    }
    static fromJSONField(typeArg, field) {
        return Obligation.reified(typeArg).new({
            id: (0, reified_1.decodeFromJSONField)(structs_2.UID.reified(), field.id),
            lendingMarketId: (0, reified_1.decodeFromJSONField)(structs_2.ID.reified(), field.lendingMarketId),
            deposits: (0, reified_1.decodeFromJSONField)(reified.vector(Deposit.reified()), field.deposits),
            borrows: (0, reified_1.decodeFromJSONField)(reified.vector(Borrow.reified()), field.borrows),
            depositedValueUsd: (0, reified_1.decodeFromJSONField)(structs_3.Decimal.reified(), field.depositedValueUsd),
            allowedBorrowValueUsd: (0, reified_1.decodeFromJSONField)(structs_3.Decimal.reified(), field.allowedBorrowValueUsd),
            unhealthyBorrowValueUsd: (0, reified_1.decodeFromJSONField)(structs_3.Decimal.reified(), field.unhealthyBorrowValueUsd),
            superUnhealthyBorrowValueUsd: (0, reified_1.decodeFromJSONField)(structs_3.Decimal.reified(), field.superUnhealthyBorrowValueUsd),
            unweightedBorrowedValueUsd: (0, reified_1.decodeFromJSONField)(structs_3.Decimal.reified(), field.unweightedBorrowedValueUsd),
            weightedBorrowedValueUsd: (0, reified_1.decodeFromJSONField)(structs_3.Decimal.reified(), field.weightedBorrowedValueUsd),
            weightedBorrowedValueUpperBoundUsd: (0, reified_1.decodeFromJSONField)(structs_3.Decimal.reified(), field.weightedBorrowedValueUpperBoundUsd),
            borrowingIsolatedAsset: (0, reified_1.decodeFromJSONField)("bool", field.borrowingIsolatedAsset),
            userRewardManagers: (0, reified_1.decodeFromJSONField)(reified.vector(structs_4.UserRewardManager.reified()), field.userRewardManagers),
            badDebtUsd: (0, reified_1.decodeFromJSONField)(structs_3.Decimal.reified(), field.badDebtUsd),
            closable: (0, reified_1.decodeFromJSONField)("bool", field.closable),
        });
    }
    static fromJSON(typeArg, json) {
        if (json.$typeName !== Obligation.$typeName) {
            throw new Error("not a WithTwoGenerics json object");
        }
        (0, reified_1.assertReifiedTypeArgsMatch)((0, util_1.composeSuiType)(Obligation.$typeName, (0, reified_1.extractType)(typeArg)), json.$typeArgs, [typeArg]);
        return Obligation.fromJSONField(typeArg, json);
    }
    static fromSuiParsedData(typeArg, content) {
        if (content.dataType !== "moveObject") {
            throw new Error("not an object");
        }
        if (!isObligation(content.type)) {
            throw new Error(`object at ${content.fields.id} is not a Obligation object`);
        }
        return Obligation.fromFieldsWithTypes(typeArg, content);
    }
    static fromSuiObjectData(typeArg, data) {
        if (data.bcs) {
            if (data.bcs.dataType !== "moveObject" || !isObligation(data.bcs.type)) {
                throw new Error(`object at is not a Obligation object`);
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
            return Obligation.fromBcs(typeArg, (0, utils_1.fromB64)(data.bcs.bcsBytes));
        }
        if (data.content) {
            return Obligation.fromSuiParsedData(typeArg, data.content);
        }
        throw new Error("Both `bcs` and `content` fields are missing from the data. Include `showBcs` or `showContent` in the request.");
    }
    static fetch(client, typeArg, id) {
        return __awaiter(this, void 0, void 0, function* () {
            var _a, _b;
            const res = yield client.getObject({ id, options: { showBcs: true } });
            if (res.error) {
                throw new Error(`error fetching Obligation object at id ${id}: ${res.error.code}`);
            }
            if (((_b = (_a = res.data) === null || _a === void 0 ? void 0 : _a.bcs) === null || _b === void 0 ? void 0 : _b.dataType) !== "moveObject" ||
                !isObligation(res.data.bcs.type)) {
                throw new Error(`object at id ${id} is not a Obligation object`);
            }
            return Obligation.fromSuiObjectData(typeArg, res.data);
        });
    }
}
exports.Obligation = Obligation;
Obligation.$typeName = `${index_1.PKG_V1}::obligation::Obligation`;
Obligation.$numTypeParams = 1;
Obligation.$isPhantom = [true];
/* ============================== ObligationDataEvent =============================== */
function isObligationDataEvent(type) {
    type = (0, util_1.compressSuiType)(type);
    return type === `${index_1.PKG_V1}::obligation::ObligationDataEvent`;
}
class ObligationDataEvent {
    constructor(typeArgs, fields) {
        this.__StructClass = true;
        this.$typeName = ObligationDataEvent.$typeName;
        this.$isPhantom = ObligationDataEvent.$isPhantom;
        this.$fullTypeName = (0, util_1.composeSuiType)(ObligationDataEvent.$typeName, ...typeArgs);
        this.$typeArgs = typeArgs;
        this.lendingMarketId = fields.lendingMarketId;
        this.obligationId = fields.obligationId;
        this.deposits = fields.deposits;
        this.borrows = fields.borrows;
        this.depositedValueUsd = fields.depositedValueUsd;
        this.allowedBorrowValueUsd = fields.allowedBorrowValueUsd;
        this.unhealthyBorrowValueUsd = fields.unhealthyBorrowValueUsd;
        this.superUnhealthyBorrowValueUsd = fields.superUnhealthyBorrowValueUsd;
        this.unweightedBorrowedValueUsd = fields.unweightedBorrowedValueUsd;
        this.weightedBorrowedValueUsd = fields.weightedBorrowedValueUsd;
        this.weightedBorrowedValueUpperBoundUsd =
            fields.weightedBorrowedValueUpperBoundUsd;
        this.borrowingIsolatedAsset = fields.borrowingIsolatedAsset;
        this.badDebtUsd = fields.badDebtUsd;
        this.closable = fields.closable;
    }
    static reified() {
        return {
            typeName: ObligationDataEvent.$typeName,
            fullTypeName: (0, util_1.composeSuiType)(ObligationDataEvent.$typeName, ...[]),
            typeArgs: [],
            isPhantom: ObligationDataEvent.$isPhantom,
            reifiedTypeArgs: [],
            fromFields: (fields) => ObligationDataEvent.fromFields(fields),
            fromFieldsWithTypes: (item) => ObligationDataEvent.fromFieldsWithTypes(item),
            fromBcs: (data) => ObligationDataEvent.fromBcs(data),
            bcs: ObligationDataEvent.bcs,
            fromJSONField: (field) => ObligationDataEvent.fromJSONField(field),
            fromJSON: (json) => ObligationDataEvent.fromJSON(json),
            fromSuiParsedData: (content) => ObligationDataEvent.fromSuiParsedData(content),
            fromSuiObjectData: (content) => ObligationDataEvent.fromSuiObjectData(content),
            fetch: (client, id) => __awaiter(this, void 0, void 0, function* () { return ObligationDataEvent.fetch(client, id); }),
            new: (fields) => {
                return new ObligationDataEvent([], fields);
            },
            kind: "StructClassReified",
        };
    }
    static get r() {
        return ObligationDataEvent.reified();
    }
    static phantom() {
        return (0, reified_1.phantom)(ObligationDataEvent.reified());
    }
    static get p() {
        return ObligationDataEvent.phantom();
    }
    static get bcs() {
        return bcs_1.bcs.struct("ObligationDataEvent", {
            lending_market_id: bcs_1.bcs
                .bytes(32)
                .transform({
                input: (val) => (0, utils_1.fromHEX)(val),
                output: (val) => (0, utils_1.toHEX)(val),
            }),
            obligation_id: bcs_1.bcs
                .bytes(32)
                .transform({
                input: (val) => (0, utils_1.fromHEX)(val),
                output: (val) => (0, utils_1.toHEX)(val),
            }),
            deposits: bcs_1.bcs.vector(DepositRecord.bcs),
            borrows: bcs_1.bcs.vector(BorrowRecord.bcs),
            deposited_value_usd: structs_3.Decimal.bcs,
            allowed_borrow_value_usd: structs_3.Decimal.bcs,
            unhealthy_borrow_value_usd: structs_3.Decimal.bcs,
            super_unhealthy_borrow_value_usd: structs_3.Decimal.bcs,
            unweighted_borrowed_value_usd: structs_3.Decimal.bcs,
            weighted_borrowed_value_usd: structs_3.Decimal.bcs,
            weighted_borrowed_value_upper_bound_usd: structs_3.Decimal.bcs,
            borrowing_isolated_asset: bcs_1.bcs.bool(),
            bad_debt_usd: structs_3.Decimal.bcs,
            closable: bcs_1.bcs.bool(),
        });
    }
    static fromFields(fields) {
        return ObligationDataEvent.reified().new({
            lendingMarketId: (0, reified_1.decodeFromFields)("address", fields.lending_market_id),
            obligationId: (0, reified_1.decodeFromFields)("address", fields.obligation_id),
            deposits: (0, reified_1.decodeFromFields)(reified.vector(DepositRecord.reified()), fields.deposits),
            borrows: (0, reified_1.decodeFromFields)(reified.vector(BorrowRecord.reified()), fields.borrows),
            depositedValueUsd: (0, reified_1.decodeFromFields)(structs_3.Decimal.reified(), fields.deposited_value_usd),
            allowedBorrowValueUsd: (0, reified_1.decodeFromFields)(structs_3.Decimal.reified(), fields.allowed_borrow_value_usd),
            unhealthyBorrowValueUsd: (0, reified_1.decodeFromFields)(structs_3.Decimal.reified(), fields.unhealthy_borrow_value_usd),
            superUnhealthyBorrowValueUsd: (0, reified_1.decodeFromFields)(structs_3.Decimal.reified(), fields.super_unhealthy_borrow_value_usd),
            unweightedBorrowedValueUsd: (0, reified_1.decodeFromFields)(structs_3.Decimal.reified(), fields.unweighted_borrowed_value_usd),
            weightedBorrowedValueUsd: (0, reified_1.decodeFromFields)(structs_3.Decimal.reified(), fields.weighted_borrowed_value_usd),
            weightedBorrowedValueUpperBoundUsd: (0, reified_1.decodeFromFields)(structs_3.Decimal.reified(), fields.weighted_borrowed_value_upper_bound_usd),
            borrowingIsolatedAsset: (0, reified_1.decodeFromFields)("bool", fields.borrowing_isolated_asset),
            badDebtUsd: (0, reified_1.decodeFromFields)(structs_3.Decimal.reified(), fields.bad_debt_usd),
            closable: (0, reified_1.decodeFromFields)("bool", fields.closable),
        });
    }
    static fromFieldsWithTypes(item) {
        if (!isObligationDataEvent(item.type)) {
            throw new Error("not a ObligationDataEvent type");
        }
        return ObligationDataEvent.reified().new({
            lendingMarketId: (0, reified_1.decodeFromFieldsWithTypes)("address", item.fields.lending_market_id),
            obligationId: (0, reified_1.decodeFromFieldsWithTypes)("address", item.fields.obligation_id),
            deposits: (0, reified_1.decodeFromFieldsWithTypes)(reified.vector(DepositRecord.reified()), item.fields.deposits),
            borrows: (0, reified_1.decodeFromFieldsWithTypes)(reified.vector(BorrowRecord.reified()), item.fields.borrows),
            depositedValueUsd: (0, reified_1.decodeFromFieldsWithTypes)(structs_3.Decimal.reified(), item.fields.deposited_value_usd),
            allowedBorrowValueUsd: (0, reified_1.decodeFromFieldsWithTypes)(structs_3.Decimal.reified(), item.fields.allowed_borrow_value_usd),
            unhealthyBorrowValueUsd: (0, reified_1.decodeFromFieldsWithTypes)(structs_3.Decimal.reified(), item.fields.unhealthy_borrow_value_usd),
            superUnhealthyBorrowValueUsd: (0, reified_1.decodeFromFieldsWithTypes)(structs_3.Decimal.reified(), item.fields.super_unhealthy_borrow_value_usd),
            unweightedBorrowedValueUsd: (0, reified_1.decodeFromFieldsWithTypes)(structs_3.Decimal.reified(), item.fields.unweighted_borrowed_value_usd),
            weightedBorrowedValueUsd: (0, reified_1.decodeFromFieldsWithTypes)(structs_3.Decimal.reified(), item.fields.weighted_borrowed_value_usd),
            weightedBorrowedValueUpperBoundUsd: (0, reified_1.decodeFromFieldsWithTypes)(structs_3.Decimal.reified(), item.fields.weighted_borrowed_value_upper_bound_usd),
            borrowingIsolatedAsset: (0, reified_1.decodeFromFieldsWithTypes)("bool", item.fields.borrowing_isolated_asset),
            badDebtUsd: (0, reified_1.decodeFromFieldsWithTypes)(structs_3.Decimal.reified(), item.fields.bad_debt_usd),
            closable: (0, reified_1.decodeFromFieldsWithTypes)("bool", item.fields.closable),
        });
    }
    static fromBcs(data) {
        return ObligationDataEvent.fromFields(ObligationDataEvent.bcs.parse(data));
    }
    toJSONField() {
        return {
            lendingMarketId: this.lendingMarketId,
            obligationId: this.obligationId,
            deposits: (0, reified_1.fieldToJSON)(`vector<${DepositRecord.$typeName}>`, this.deposits),
            borrows: (0, reified_1.fieldToJSON)(`vector<${BorrowRecord.$typeName}>`, this.borrows),
            depositedValueUsd: this.depositedValueUsd.toJSONField(),
            allowedBorrowValueUsd: this.allowedBorrowValueUsd.toJSONField(),
            unhealthyBorrowValueUsd: this.unhealthyBorrowValueUsd.toJSONField(),
            superUnhealthyBorrowValueUsd: this.superUnhealthyBorrowValueUsd.toJSONField(),
            unweightedBorrowedValueUsd: this.unweightedBorrowedValueUsd.toJSONField(),
            weightedBorrowedValueUsd: this.weightedBorrowedValueUsd.toJSONField(),
            weightedBorrowedValueUpperBoundUsd: this.weightedBorrowedValueUpperBoundUsd.toJSONField(),
            borrowingIsolatedAsset: this.borrowingIsolatedAsset,
            badDebtUsd: this.badDebtUsd.toJSONField(),
            closable: this.closable,
        };
    }
    toJSON() {
        return Object.assign({ $typeName: this.$typeName, $typeArgs: this.$typeArgs }, this.toJSONField());
    }
    static fromJSONField(field) {
        return ObligationDataEvent.reified().new({
            lendingMarketId: (0, reified_1.decodeFromJSONField)("address", field.lendingMarketId),
            obligationId: (0, reified_1.decodeFromJSONField)("address", field.obligationId),
            deposits: (0, reified_1.decodeFromJSONField)(reified.vector(DepositRecord.reified()), field.deposits),
            borrows: (0, reified_1.decodeFromJSONField)(reified.vector(BorrowRecord.reified()), field.borrows),
            depositedValueUsd: (0, reified_1.decodeFromJSONField)(structs_3.Decimal.reified(), field.depositedValueUsd),
            allowedBorrowValueUsd: (0, reified_1.decodeFromJSONField)(structs_3.Decimal.reified(), field.allowedBorrowValueUsd),
            unhealthyBorrowValueUsd: (0, reified_1.decodeFromJSONField)(structs_3.Decimal.reified(), field.unhealthyBorrowValueUsd),
            superUnhealthyBorrowValueUsd: (0, reified_1.decodeFromJSONField)(structs_3.Decimal.reified(), field.superUnhealthyBorrowValueUsd),
            unweightedBorrowedValueUsd: (0, reified_1.decodeFromJSONField)(structs_3.Decimal.reified(), field.unweightedBorrowedValueUsd),
            weightedBorrowedValueUsd: (0, reified_1.decodeFromJSONField)(structs_3.Decimal.reified(), field.weightedBorrowedValueUsd),
            weightedBorrowedValueUpperBoundUsd: (0, reified_1.decodeFromJSONField)(structs_3.Decimal.reified(), field.weightedBorrowedValueUpperBoundUsd),
            borrowingIsolatedAsset: (0, reified_1.decodeFromJSONField)("bool", field.borrowingIsolatedAsset),
            badDebtUsd: (0, reified_1.decodeFromJSONField)(structs_3.Decimal.reified(), field.badDebtUsd),
            closable: (0, reified_1.decodeFromJSONField)("bool", field.closable),
        });
    }
    static fromJSON(json) {
        if (json.$typeName !== ObligationDataEvent.$typeName) {
            throw new Error("not a WithTwoGenerics json object");
        }
        return ObligationDataEvent.fromJSONField(json);
    }
    static fromSuiParsedData(content) {
        if (content.dataType !== "moveObject") {
            throw new Error("not an object");
        }
        if (!isObligationDataEvent(content.type)) {
            throw new Error(`object at ${content.fields.id} is not a ObligationDataEvent object`);
        }
        return ObligationDataEvent.fromFieldsWithTypes(content);
    }
    static fromSuiObjectData(data) {
        if (data.bcs) {
            if (data.bcs.dataType !== "moveObject" ||
                !isObligationDataEvent(data.bcs.type)) {
                throw new Error(`object at is not a ObligationDataEvent object`);
            }
            return ObligationDataEvent.fromBcs((0, utils_1.fromB64)(data.bcs.bcsBytes));
        }
        if (data.content) {
            return ObligationDataEvent.fromSuiParsedData(data.content);
        }
        throw new Error("Both `bcs` and `content` fields are missing from the data. Include `showBcs` or `showContent` in the request.");
    }
    static fetch(client, id) {
        return __awaiter(this, void 0, void 0, function* () {
            var _a, _b;
            const res = yield client.getObject({ id, options: { showBcs: true } });
            if (res.error) {
                throw new Error(`error fetching ObligationDataEvent object at id ${id}: ${res.error.code}`);
            }
            if (((_b = (_a = res.data) === null || _a === void 0 ? void 0 : _a.bcs) === null || _b === void 0 ? void 0 : _b.dataType) !== "moveObject" ||
                !isObligationDataEvent(res.data.bcs.type)) {
                throw new Error(`object at id ${id} is not a ObligationDataEvent object`);
            }
            return ObligationDataEvent.fromSuiObjectData(res.data);
        });
    }
}
exports.ObligationDataEvent = ObligationDataEvent;
ObligationDataEvent.$typeName = `${index_1.PKG_V1}::obligation::ObligationDataEvent`;
ObligationDataEvent.$numTypeParams = 0;
ObligationDataEvent.$isPhantom = [];

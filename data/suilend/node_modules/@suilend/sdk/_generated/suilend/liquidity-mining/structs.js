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
exports.UserRewardManager = exports.UserReward = exports.RewardBalance = exports.PoolRewardManager = exports.PoolReward = void 0;
exports.isPoolReward = isPoolReward;
exports.isPoolRewardManager = isPoolRewardManager;
exports.isRewardBalance = isRewardBalance;
exports.isUserReward = isUserReward;
exports.isUserRewardManager = isUserRewardManager;
const reified = __importStar(require("../../_framework/reified"));
const structs_1 = require("../../_dependencies/source/0x1/option/structs");
const structs_2 = require("../../_dependencies/source/0x1/type-name/structs");
const structs_3 = require("../../_dependencies/source/0x2/bag/structs");
const structs_4 = require("../../_dependencies/source/0x2/object/structs");
const reified_1 = require("../../_framework/reified");
const util_1 = require("../../_framework/util");
const structs_5 = require("../decimal/structs");
const index_1 = require("../index");
const bcs_1 = require("@mysten/sui/bcs");
const utils_1 = require("@mysten/sui/utils");
/* ============================== PoolReward =============================== */
function isPoolReward(type) {
    type = (0, util_1.compressSuiType)(type);
    return type === `${index_1.PKG_V1}::liquidity_mining::PoolReward`;
}
class PoolReward {
    constructor(typeArgs, fields) {
        this.__StructClass = true;
        this.$typeName = PoolReward.$typeName;
        this.$isPhantom = PoolReward.$isPhantom;
        this.$fullTypeName = (0, util_1.composeSuiType)(PoolReward.$typeName, ...typeArgs);
        this.$typeArgs = typeArgs;
        this.id = fields.id;
        this.poolRewardManagerId = fields.poolRewardManagerId;
        this.coinType = fields.coinType;
        this.startTimeMs = fields.startTimeMs;
        this.endTimeMs = fields.endTimeMs;
        this.totalRewards = fields.totalRewards;
        this.allocatedRewards = fields.allocatedRewards;
        this.cumulativeRewardsPerShare = fields.cumulativeRewardsPerShare;
        this.numUserRewardManagers = fields.numUserRewardManagers;
        this.additionalFields = fields.additionalFields;
    }
    static reified() {
        return {
            typeName: PoolReward.$typeName,
            fullTypeName: (0, util_1.composeSuiType)(PoolReward.$typeName, ...[]),
            typeArgs: [],
            isPhantom: PoolReward.$isPhantom,
            reifiedTypeArgs: [],
            fromFields: (fields) => PoolReward.fromFields(fields),
            fromFieldsWithTypes: (item) => PoolReward.fromFieldsWithTypes(item),
            fromBcs: (data) => PoolReward.fromBcs(data),
            bcs: PoolReward.bcs,
            fromJSONField: (field) => PoolReward.fromJSONField(field),
            fromJSON: (json) => PoolReward.fromJSON(json),
            fromSuiParsedData: (content) => PoolReward.fromSuiParsedData(content),
            fromSuiObjectData: (content) => PoolReward.fromSuiObjectData(content),
            fetch: (client, id) => __awaiter(this, void 0, void 0, function* () { return PoolReward.fetch(client, id); }),
            new: (fields) => {
                return new PoolReward([], fields);
            },
            kind: "StructClassReified",
        };
    }
    static get r() {
        return PoolReward.reified();
    }
    static phantom() {
        return (0, reified_1.phantom)(PoolReward.reified());
    }
    static get p() {
        return PoolReward.phantom();
    }
    static get bcs() {
        return bcs_1.bcs.struct("PoolReward", {
            id: structs_4.UID.bcs,
            pool_reward_manager_id: structs_4.ID.bcs,
            coin_type: structs_2.TypeName.bcs,
            start_time_ms: bcs_1.bcs.u64(),
            end_time_ms: bcs_1.bcs.u64(),
            total_rewards: bcs_1.bcs.u64(),
            allocated_rewards: structs_5.Decimal.bcs,
            cumulative_rewards_per_share: structs_5.Decimal.bcs,
            num_user_reward_managers: bcs_1.bcs.u64(),
            additional_fields: structs_3.Bag.bcs,
        });
    }
    static fromFields(fields) {
        return PoolReward.reified().new({
            id: (0, reified_1.decodeFromFields)(structs_4.UID.reified(), fields.id),
            poolRewardManagerId: (0, reified_1.decodeFromFields)(structs_4.ID.reified(), fields.pool_reward_manager_id),
            coinType: (0, reified_1.decodeFromFields)(structs_2.TypeName.reified(), fields.coin_type),
            startTimeMs: (0, reified_1.decodeFromFields)("u64", fields.start_time_ms),
            endTimeMs: (0, reified_1.decodeFromFields)("u64", fields.end_time_ms),
            totalRewards: (0, reified_1.decodeFromFields)("u64", fields.total_rewards),
            allocatedRewards: (0, reified_1.decodeFromFields)(structs_5.Decimal.reified(), fields.allocated_rewards),
            cumulativeRewardsPerShare: (0, reified_1.decodeFromFields)(structs_5.Decimal.reified(), fields.cumulative_rewards_per_share),
            numUserRewardManagers: (0, reified_1.decodeFromFields)("u64", fields.num_user_reward_managers),
            additionalFields: (0, reified_1.decodeFromFields)(structs_3.Bag.reified(), fields.additional_fields),
        });
    }
    static fromFieldsWithTypes(item) {
        if (!isPoolReward(item.type)) {
            throw new Error("not a PoolReward type");
        }
        return PoolReward.reified().new({
            id: (0, reified_1.decodeFromFieldsWithTypes)(structs_4.UID.reified(), item.fields.id),
            poolRewardManagerId: (0, reified_1.decodeFromFieldsWithTypes)(structs_4.ID.reified(), item.fields.pool_reward_manager_id),
            coinType: (0, reified_1.decodeFromFieldsWithTypes)(structs_2.TypeName.reified(), item.fields.coin_type),
            startTimeMs: (0, reified_1.decodeFromFieldsWithTypes)("u64", item.fields.start_time_ms),
            endTimeMs: (0, reified_1.decodeFromFieldsWithTypes)("u64", item.fields.end_time_ms),
            totalRewards: (0, reified_1.decodeFromFieldsWithTypes)("u64", item.fields.total_rewards),
            allocatedRewards: (0, reified_1.decodeFromFieldsWithTypes)(structs_5.Decimal.reified(), item.fields.allocated_rewards),
            cumulativeRewardsPerShare: (0, reified_1.decodeFromFieldsWithTypes)(structs_5.Decimal.reified(), item.fields.cumulative_rewards_per_share),
            numUserRewardManagers: (0, reified_1.decodeFromFieldsWithTypes)("u64", item.fields.num_user_reward_managers),
            additionalFields: (0, reified_1.decodeFromFieldsWithTypes)(structs_3.Bag.reified(), item.fields.additional_fields),
        });
    }
    static fromBcs(data) {
        return PoolReward.fromFields(PoolReward.bcs.parse(data));
    }
    toJSONField() {
        return {
            id: this.id,
            poolRewardManagerId: this.poolRewardManagerId,
            coinType: this.coinType.toJSONField(),
            startTimeMs: this.startTimeMs.toString(),
            endTimeMs: this.endTimeMs.toString(),
            totalRewards: this.totalRewards.toString(),
            allocatedRewards: this.allocatedRewards.toJSONField(),
            cumulativeRewardsPerShare: this.cumulativeRewardsPerShare.toJSONField(),
            numUserRewardManagers: this.numUserRewardManagers.toString(),
            additionalFields: this.additionalFields.toJSONField(),
        };
    }
    toJSON() {
        return Object.assign({ $typeName: this.$typeName, $typeArgs: this.$typeArgs }, this.toJSONField());
    }
    static fromJSONField(field) {
        return PoolReward.reified().new({
            id: (0, reified_1.decodeFromJSONField)(structs_4.UID.reified(), field.id),
            poolRewardManagerId: (0, reified_1.decodeFromJSONField)(structs_4.ID.reified(), field.poolRewardManagerId),
            coinType: (0, reified_1.decodeFromJSONField)(structs_2.TypeName.reified(), field.coinType),
            startTimeMs: (0, reified_1.decodeFromJSONField)("u64", field.startTimeMs),
            endTimeMs: (0, reified_1.decodeFromJSONField)("u64", field.endTimeMs),
            totalRewards: (0, reified_1.decodeFromJSONField)("u64", field.totalRewards),
            allocatedRewards: (0, reified_1.decodeFromJSONField)(structs_5.Decimal.reified(), field.allocatedRewards),
            cumulativeRewardsPerShare: (0, reified_1.decodeFromJSONField)(structs_5.Decimal.reified(), field.cumulativeRewardsPerShare),
            numUserRewardManagers: (0, reified_1.decodeFromJSONField)("u64", field.numUserRewardManagers),
            additionalFields: (0, reified_1.decodeFromJSONField)(structs_3.Bag.reified(), field.additionalFields),
        });
    }
    static fromJSON(json) {
        if (json.$typeName !== PoolReward.$typeName) {
            throw new Error("not a WithTwoGenerics json object");
        }
        return PoolReward.fromJSONField(json);
    }
    static fromSuiParsedData(content) {
        if (content.dataType !== "moveObject") {
            throw new Error("not an object");
        }
        if (!isPoolReward(content.type)) {
            throw new Error(`object at ${content.fields.id} is not a PoolReward object`);
        }
        return PoolReward.fromFieldsWithTypes(content);
    }
    static fromSuiObjectData(data) {
        if (data.bcs) {
            if (data.bcs.dataType !== "moveObject" || !isPoolReward(data.bcs.type)) {
                throw new Error(`object at is not a PoolReward object`);
            }
            return PoolReward.fromBcs((0, utils_1.fromB64)(data.bcs.bcsBytes));
        }
        if (data.content) {
            return PoolReward.fromSuiParsedData(data.content);
        }
        throw new Error("Both `bcs` and `content` fields are missing from the data. Include `showBcs` or `showContent` in the request.");
    }
    static fetch(client, id) {
        return __awaiter(this, void 0, void 0, function* () {
            var _a, _b;
            const res = yield client.getObject({ id, options: { showBcs: true } });
            if (res.error) {
                throw new Error(`error fetching PoolReward object at id ${id}: ${res.error.code}`);
            }
            if (((_b = (_a = res.data) === null || _a === void 0 ? void 0 : _a.bcs) === null || _b === void 0 ? void 0 : _b.dataType) !== "moveObject" ||
                !isPoolReward(res.data.bcs.type)) {
                throw new Error(`object at id ${id} is not a PoolReward object`);
            }
            return PoolReward.fromSuiObjectData(res.data);
        });
    }
}
exports.PoolReward = PoolReward;
PoolReward.$typeName = `${index_1.PKG_V1}::liquidity_mining::PoolReward`;
PoolReward.$numTypeParams = 0;
PoolReward.$isPhantom = [];
/* ============================== PoolRewardManager =============================== */
function isPoolRewardManager(type) {
    type = (0, util_1.compressSuiType)(type);
    return type === `${index_1.PKG_V1}::liquidity_mining::PoolRewardManager`;
}
class PoolRewardManager {
    constructor(typeArgs, fields) {
        this.__StructClass = true;
        this.$typeName = PoolRewardManager.$typeName;
        this.$isPhantom = PoolRewardManager.$isPhantom;
        this.$fullTypeName = (0, util_1.composeSuiType)(PoolRewardManager.$typeName, ...typeArgs);
        this.$typeArgs = typeArgs;
        this.id = fields.id;
        this.totalShares = fields.totalShares;
        this.poolRewards = fields.poolRewards;
        this.lastUpdateTimeMs = fields.lastUpdateTimeMs;
    }
    static reified() {
        return {
            typeName: PoolRewardManager.$typeName,
            fullTypeName: (0, util_1.composeSuiType)(PoolRewardManager.$typeName, ...[]),
            typeArgs: [],
            isPhantom: PoolRewardManager.$isPhantom,
            reifiedTypeArgs: [],
            fromFields: (fields) => PoolRewardManager.fromFields(fields),
            fromFieldsWithTypes: (item) => PoolRewardManager.fromFieldsWithTypes(item),
            fromBcs: (data) => PoolRewardManager.fromBcs(data),
            bcs: PoolRewardManager.bcs,
            fromJSONField: (field) => PoolRewardManager.fromJSONField(field),
            fromJSON: (json) => PoolRewardManager.fromJSON(json),
            fromSuiParsedData: (content) => PoolRewardManager.fromSuiParsedData(content),
            fromSuiObjectData: (content) => PoolRewardManager.fromSuiObjectData(content),
            fetch: (client, id) => __awaiter(this, void 0, void 0, function* () { return PoolRewardManager.fetch(client, id); }),
            new: (fields) => {
                return new PoolRewardManager([], fields);
            },
            kind: "StructClassReified",
        };
    }
    static get r() {
        return PoolRewardManager.reified();
    }
    static phantom() {
        return (0, reified_1.phantom)(PoolRewardManager.reified());
    }
    static get p() {
        return PoolRewardManager.phantom();
    }
    static get bcs() {
        return bcs_1.bcs.struct("PoolRewardManager", {
            id: structs_4.UID.bcs,
            total_shares: bcs_1.bcs.u64(),
            pool_rewards: bcs_1.bcs.vector(structs_1.Option.bcs(PoolReward.bcs)),
            last_update_time_ms: bcs_1.bcs.u64(),
        });
    }
    static fromFields(fields) {
        return PoolRewardManager.reified().new({
            id: (0, reified_1.decodeFromFields)(structs_4.UID.reified(), fields.id),
            totalShares: (0, reified_1.decodeFromFields)("u64", fields.total_shares),
            poolRewards: (0, reified_1.decodeFromFields)(reified.vector(structs_1.Option.reified(PoolReward.reified())), fields.pool_rewards),
            lastUpdateTimeMs: (0, reified_1.decodeFromFields)("u64", fields.last_update_time_ms),
        });
    }
    static fromFieldsWithTypes(item) {
        if (!isPoolRewardManager(item.type)) {
            throw new Error("not a PoolRewardManager type");
        }
        return PoolRewardManager.reified().new({
            id: (0, reified_1.decodeFromFieldsWithTypes)(structs_4.UID.reified(), item.fields.id),
            totalShares: (0, reified_1.decodeFromFieldsWithTypes)("u64", item.fields.total_shares),
            poolRewards: (0, reified_1.decodeFromFieldsWithTypes)(reified.vector(structs_1.Option.reified(PoolReward.reified())), item.fields.pool_rewards),
            lastUpdateTimeMs: (0, reified_1.decodeFromFieldsWithTypes)("u64", item.fields.last_update_time_ms),
        });
    }
    static fromBcs(data) {
        return PoolRewardManager.fromFields(PoolRewardManager.bcs.parse(data));
    }
    toJSONField() {
        return {
            id: this.id,
            totalShares: this.totalShares.toString(),
            poolRewards: (0, reified_1.fieldToJSON)(`vector<${structs_1.Option.$typeName}<${PoolReward.$typeName}>>`, this.poolRewards),
            lastUpdateTimeMs: this.lastUpdateTimeMs.toString(),
        };
    }
    toJSON() {
        return Object.assign({ $typeName: this.$typeName, $typeArgs: this.$typeArgs }, this.toJSONField());
    }
    static fromJSONField(field) {
        return PoolRewardManager.reified().new({
            id: (0, reified_1.decodeFromJSONField)(structs_4.UID.reified(), field.id),
            totalShares: (0, reified_1.decodeFromJSONField)("u64", field.totalShares),
            poolRewards: (0, reified_1.decodeFromJSONField)(reified.vector(structs_1.Option.reified(PoolReward.reified())), field.poolRewards),
            lastUpdateTimeMs: (0, reified_1.decodeFromJSONField)("u64", field.lastUpdateTimeMs),
        });
    }
    static fromJSON(json) {
        if (json.$typeName !== PoolRewardManager.$typeName) {
            throw new Error("not a WithTwoGenerics json object");
        }
        return PoolRewardManager.fromJSONField(json);
    }
    static fromSuiParsedData(content) {
        if (content.dataType !== "moveObject") {
            throw new Error("not an object");
        }
        if (!isPoolRewardManager(content.type)) {
            throw new Error(`object at ${content.fields.id} is not a PoolRewardManager object`);
        }
        return PoolRewardManager.fromFieldsWithTypes(content);
    }
    static fromSuiObjectData(data) {
        if (data.bcs) {
            if (data.bcs.dataType !== "moveObject" ||
                !isPoolRewardManager(data.bcs.type)) {
                throw new Error(`object at is not a PoolRewardManager object`);
            }
            return PoolRewardManager.fromBcs((0, utils_1.fromB64)(data.bcs.bcsBytes));
        }
        if (data.content) {
            return PoolRewardManager.fromSuiParsedData(data.content);
        }
        throw new Error("Both `bcs` and `content` fields are missing from the data. Include `showBcs` or `showContent` in the request.");
    }
    static fetch(client, id) {
        return __awaiter(this, void 0, void 0, function* () {
            var _a, _b;
            const res = yield client.getObject({ id, options: { showBcs: true } });
            if (res.error) {
                throw new Error(`error fetching PoolRewardManager object at id ${id}: ${res.error.code}`);
            }
            if (((_b = (_a = res.data) === null || _a === void 0 ? void 0 : _a.bcs) === null || _b === void 0 ? void 0 : _b.dataType) !== "moveObject" ||
                !isPoolRewardManager(res.data.bcs.type)) {
                throw new Error(`object at id ${id} is not a PoolRewardManager object`);
            }
            return PoolRewardManager.fromSuiObjectData(res.data);
        });
    }
}
exports.PoolRewardManager = PoolRewardManager;
PoolRewardManager.$typeName = `${index_1.PKG_V1}::liquidity_mining::PoolRewardManager`;
PoolRewardManager.$numTypeParams = 0;
PoolRewardManager.$isPhantom = [];
/* ============================== RewardBalance =============================== */
function isRewardBalance(type) {
    type = (0, util_1.compressSuiType)(type);
    return type.startsWith(`${index_1.PKG_V1}::liquidity_mining::RewardBalance` + "<");
}
class RewardBalance {
    constructor(typeArgs, fields) {
        this.__StructClass = true;
        this.$typeName = RewardBalance.$typeName;
        this.$isPhantom = RewardBalance.$isPhantom;
        this.$fullTypeName = (0, util_1.composeSuiType)(RewardBalance.$typeName, ...typeArgs);
        this.$typeArgs = typeArgs;
        this.dummyField = fields.dummyField;
    }
    static reified(T) {
        return {
            typeName: RewardBalance.$typeName,
            fullTypeName: (0, util_1.composeSuiType)(RewardBalance.$typeName, ...[(0, reified_1.extractType)(T)]),
            typeArgs: [(0, reified_1.extractType)(T)],
            isPhantom: RewardBalance.$isPhantom,
            reifiedTypeArgs: [T],
            fromFields: (fields) => RewardBalance.fromFields(T, fields),
            fromFieldsWithTypes: (item) => RewardBalance.fromFieldsWithTypes(T, item),
            fromBcs: (data) => RewardBalance.fromBcs(T, data),
            bcs: RewardBalance.bcs,
            fromJSONField: (field) => RewardBalance.fromJSONField(T, field),
            fromJSON: (json) => RewardBalance.fromJSON(T, json),
            fromSuiParsedData: (content) => RewardBalance.fromSuiParsedData(T, content),
            fromSuiObjectData: (content) => RewardBalance.fromSuiObjectData(T, content),
            fetch: (client, id) => __awaiter(this, void 0, void 0, function* () { return RewardBalance.fetch(client, T, id); }),
            new: (fields) => {
                return new RewardBalance([(0, reified_1.extractType)(T)], fields);
            },
            kind: "StructClassReified",
        };
    }
    static get r() {
        return RewardBalance.reified;
    }
    static phantom(T) {
        return (0, reified_1.phantom)(RewardBalance.reified(T));
    }
    static get p() {
        return RewardBalance.phantom;
    }
    static get bcs() {
        return bcs_1.bcs.struct("RewardBalance", {
            dummy_field: bcs_1.bcs.bool(),
        });
    }
    static fromFields(typeArg, fields) {
        return RewardBalance.reified(typeArg).new({
            dummyField: (0, reified_1.decodeFromFields)("bool", fields.dummy_field),
        });
    }
    static fromFieldsWithTypes(typeArg, item) {
        if (!isRewardBalance(item.type)) {
            throw new Error("not a RewardBalance type");
        }
        (0, reified_1.assertFieldsWithTypesArgsMatch)(item, [typeArg]);
        return RewardBalance.reified(typeArg).new({
            dummyField: (0, reified_1.decodeFromFieldsWithTypes)("bool", item.fields.dummy_field),
        });
    }
    static fromBcs(typeArg, data) {
        return RewardBalance.fromFields(typeArg, RewardBalance.bcs.parse(data));
    }
    toJSONField() {
        return {
            dummyField: this.dummyField,
        };
    }
    toJSON() {
        return Object.assign({ $typeName: this.$typeName, $typeArgs: this.$typeArgs }, this.toJSONField());
    }
    static fromJSONField(typeArg, field) {
        return RewardBalance.reified(typeArg).new({
            dummyField: (0, reified_1.decodeFromJSONField)("bool", field.dummyField),
        });
    }
    static fromJSON(typeArg, json) {
        if (json.$typeName !== RewardBalance.$typeName) {
            throw new Error("not a WithTwoGenerics json object");
        }
        (0, reified_1.assertReifiedTypeArgsMatch)((0, util_1.composeSuiType)(RewardBalance.$typeName, (0, reified_1.extractType)(typeArg)), json.$typeArgs, [typeArg]);
        return RewardBalance.fromJSONField(typeArg, json);
    }
    static fromSuiParsedData(typeArg, content) {
        if (content.dataType !== "moveObject") {
            throw new Error("not an object");
        }
        if (!isRewardBalance(content.type)) {
            throw new Error(`object at ${content.fields.id} is not a RewardBalance object`);
        }
        return RewardBalance.fromFieldsWithTypes(typeArg, content);
    }
    static fromSuiObjectData(typeArg, data) {
        if (data.bcs) {
            if (data.bcs.dataType !== "moveObject" ||
                !isRewardBalance(data.bcs.type)) {
                throw new Error(`object at is not a RewardBalance object`);
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
            return RewardBalance.fromBcs(typeArg, (0, utils_1.fromB64)(data.bcs.bcsBytes));
        }
        if (data.content) {
            return RewardBalance.fromSuiParsedData(typeArg, data.content);
        }
        throw new Error("Both `bcs` and `content` fields are missing from the data. Include `showBcs` or `showContent` in the request.");
    }
    static fetch(client, typeArg, id) {
        return __awaiter(this, void 0, void 0, function* () {
            var _a, _b;
            const res = yield client.getObject({ id, options: { showBcs: true } });
            if (res.error) {
                throw new Error(`error fetching RewardBalance object at id ${id}: ${res.error.code}`);
            }
            if (((_b = (_a = res.data) === null || _a === void 0 ? void 0 : _a.bcs) === null || _b === void 0 ? void 0 : _b.dataType) !== "moveObject" ||
                !isRewardBalance(res.data.bcs.type)) {
                throw new Error(`object at id ${id} is not a RewardBalance object`);
            }
            return RewardBalance.fromSuiObjectData(typeArg, res.data);
        });
    }
}
exports.RewardBalance = RewardBalance;
RewardBalance.$typeName = `${index_1.PKG_V1}::liquidity_mining::RewardBalance`;
RewardBalance.$numTypeParams = 1;
RewardBalance.$isPhantom = [true];
/* ============================== UserReward =============================== */
function isUserReward(type) {
    type = (0, util_1.compressSuiType)(type);
    return type === `${index_1.PKG_V1}::liquidity_mining::UserReward`;
}
class UserReward {
    constructor(typeArgs, fields) {
        this.__StructClass = true;
        this.$typeName = UserReward.$typeName;
        this.$isPhantom = UserReward.$isPhantom;
        this.$fullTypeName = (0, util_1.composeSuiType)(UserReward.$typeName, ...typeArgs);
        this.$typeArgs = typeArgs;
        this.poolRewardId = fields.poolRewardId;
        this.earnedRewards = fields.earnedRewards;
        this.cumulativeRewardsPerShare = fields.cumulativeRewardsPerShare;
    }
    static reified() {
        return {
            typeName: UserReward.$typeName,
            fullTypeName: (0, util_1.composeSuiType)(UserReward.$typeName, ...[]),
            typeArgs: [],
            isPhantom: UserReward.$isPhantom,
            reifiedTypeArgs: [],
            fromFields: (fields) => UserReward.fromFields(fields),
            fromFieldsWithTypes: (item) => UserReward.fromFieldsWithTypes(item),
            fromBcs: (data) => UserReward.fromBcs(data),
            bcs: UserReward.bcs,
            fromJSONField: (field) => UserReward.fromJSONField(field),
            fromJSON: (json) => UserReward.fromJSON(json),
            fromSuiParsedData: (content) => UserReward.fromSuiParsedData(content),
            fromSuiObjectData: (content) => UserReward.fromSuiObjectData(content),
            fetch: (client, id) => __awaiter(this, void 0, void 0, function* () { return UserReward.fetch(client, id); }),
            new: (fields) => {
                return new UserReward([], fields);
            },
            kind: "StructClassReified",
        };
    }
    static get r() {
        return UserReward.reified();
    }
    static phantom() {
        return (0, reified_1.phantom)(UserReward.reified());
    }
    static get p() {
        return UserReward.phantom();
    }
    static get bcs() {
        return bcs_1.bcs.struct("UserReward", {
            pool_reward_id: structs_4.ID.bcs,
            earned_rewards: structs_5.Decimal.bcs,
            cumulative_rewards_per_share: structs_5.Decimal.bcs,
        });
    }
    static fromFields(fields) {
        return UserReward.reified().new({
            poolRewardId: (0, reified_1.decodeFromFields)(structs_4.ID.reified(), fields.pool_reward_id),
            earnedRewards: (0, reified_1.decodeFromFields)(structs_5.Decimal.reified(), fields.earned_rewards),
            cumulativeRewardsPerShare: (0, reified_1.decodeFromFields)(structs_5.Decimal.reified(), fields.cumulative_rewards_per_share),
        });
    }
    static fromFieldsWithTypes(item) {
        if (!isUserReward(item.type)) {
            throw new Error("not a UserReward type");
        }
        return UserReward.reified().new({
            poolRewardId: (0, reified_1.decodeFromFieldsWithTypes)(structs_4.ID.reified(), item.fields.pool_reward_id),
            earnedRewards: (0, reified_1.decodeFromFieldsWithTypes)(structs_5.Decimal.reified(), item.fields.earned_rewards),
            cumulativeRewardsPerShare: (0, reified_1.decodeFromFieldsWithTypes)(structs_5.Decimal.reified(), item.fields.cumulative_rewards_per_share),
        });
    }
    static fromBcs(data) {
        return UserReward.fromFields(UserReward.bcs.parse(data));
    }
    toJSONField() {
        return {
            poolRewardId: this.poolRewardId,
            earnedRewards: this.earnedRewards.toJSONField(),
            cumulativeRewardsPerShare: this.cumulativeRewardsPerShare.toJSONField(),
        };
    }
    toJSON() {
        return Object.assign({ $typeName: this.$typeName, $typeArgs: this.$typeArgs }, this.toJSONField());
    }
    static fromJSONField(field) {
        return UserReward.reified().new({
            poolRewardId: (0, reified_1.decodeFromJSONField)(structs_4.ID.reified(), field.poolRewardId),
            earnedRewards: (0, reified_1.decodeFromJSONField)(structs_5.Decimal.reified(), field.earnedRewards),
            cumulativeRewardsPerShare: (0, reified_1.decodeFromJSONField)(structs_5.Decimal.reified(), field.cumulativeRewardsPerShare),
        });
    }
    static fromJSON(json) {
        if (json.$typeName !== UserReward.$typeName) {
            throw new Error("not a WithTwoGenerics json object");
        }
        return UserReward.fromJSONField(json);
    }
    static fromSuiParsedData(content) {
        if (content.dataType !== "moveObject") {
            throw new Error("not an object");
        }
        if (!isUserReward(content.type)) {
            throw new Error(`object at ${content.fields.id} is not a UserReward object`);
        }
        return UserReward.fromFieldsWithTypes(content);
    }
    static fromSuiObjectData(data) {
        if (data.bcs) {
            if (data.bcs.dataType !== "moveObject" || !isUserReward(data.bcs.type)) {
                throw new Error(`object at is not a UserReward object`);
            }
            return UserReward.fromBcs((0, utils_1.fromB64)(data.bcs.bcsBytes));
        }
        if (data.content) {
            return UserReward.fromSuiParsedData(data.content);
        }
        throw new Error("Both `bcs` and `content` fields are missing from the data. Include `showBcs` or `showContent` in the request.");
    }
    static fetch(client, id) {
        return __awaiter(this, void 0, void 0, function* () {
            var _a, _b;
            const res = yield client.getObject({ id, options: { showBcs: true } });
            if (res.error) {
                throw new Error(`error fetching UserReward object at id ${id}: ${res.error.code}`);
            }
            if (((_b = (_a = res.data) === null || _a === void 0 ? void 0 : _a.bcs) === null || _b === void 0 ? void 0 : _b.dataType) !== "moveObject" ||
                !isUserReward(res.data.bcs.type)) {
                throw new Error(`object at id ${id} is not a UserReward object`);
            }
            return UserReward.fromSuiObjectData(res.data);
        });
    }
}
exports.UserReward = UserReward;
UserReward.$typeName = `${index_1.PKG_V1}::liquidity_mining::UserReward`;
UserReward.$numTypeParams = 0;
UserReward.$isPhantom = [];
/* ============================== UserRewardManager =============================== */
function isUserRewardManager(type) {
    type = (0, util_1.compressSuiType)(type);
    return type === `${index_1.PKG_V1}::liquidity_mining::UserRewardManager`;
}
class UserRewardManager {
    constructor(typeArgs, fields) {
        this.__StructClass = true;
        this.$typeName = UserRewardManager.$typeName;
        this.$isPhantom = UserRewardManager.$isPhantom;
        this.$fullTypeName = (0, util_1.composeSuiType)(UserRewardManager.$typeName, ...typeArgs);
        this.$typeArgs = typeArgs;
        this.poolRewardManagerId = fields.poolRewardManagerId;
        this.share = fields.share;
        this.rewards = fields.rewards;
        this.lastUpdateTimeMs = fields.lastUpdateTimeMs;
    }
    static reified() {
        return {
            typeName: UserRewardManager.$typeName,
            fullTypeName: (0, util_1.composeSuiType)(UserRewardManager.$typeName, ...[]),
            typeArgs: [],
            isPhantom: UserRewardManager.$isPhantom,
            reifiedTypeArgs: [],
            fromFields: (fields) => UserRewardManager.fromFields(fields),
            fromFieldsWithTypes: (item) => UserRewardManager.fromFieldsWithTypes(item),
            fromBcs: (data) => UserRewardManager.fromBcs(data),
            bcs: UserRewardManager.bcs,
            fromJSONField: (field) => UserRewardManager.fromJSONField(field),
            fromJSON: (json) => UserRewardManager.fromJSON(json),
            fromSuiParsedData: (content) => UserRewardManager.fromSuiParsedData(content),
            fromSuiObjectData: (content) => UserRewardManager.fromSuiObjectData(content),
            fetch: (client, id) => __awaiter(this, void 0, void 0, function* () { return UserRewardManager.fetch(client, id); }),
            new: (fields) => {
                return new UserRewardManager([], fields);
            },
            kind: "StructClassReified",
        };
    }
    static get r() {
        return UserRewardManager.reified();
    }
    static phantom() {
        return (0, reified_1.phantom)(UserRewardManager.reified());
    }
    static get p() {
        return UserRewardManager.phantom();
    }
    static get bcs() {
        return bcs_1.bcs.struct("UserRewardManager", {
            pool_reward_manager_id: structs_4.ID.bcs,
            share: bcs_1.bcs.u64(),
            rewards: bcs_1.bcs.vector(structs_1.Option.bcs(UserReward.bcs)),
            last_update_time_ms: bcs_1.bcs.u64(),
        });
    }
    static fromFields(fields) {
        return UserRewardManager.reified().new({
            poolRewardManagerId: (0, reified_1.decodeFromFields)(structs_4.ID.reified(), fields.pool_reward_manager_id),
            share: (0, reified_1.decodeFromFields)("u64", fields.share),
            rewards: (0, reified_1.decodeFromFields)(reified.vector(structs_1.Option.reified(UserReward.reified())), fields.rewards),
            lastUpdateTimeMs: (0, reified_1.decodeFromFields)("u64", fields.last_update_time_ms),
        });
    }
    static fromFieldsWithTypes(item) {
        if (!isUserRewardManager(item.type)) {
            throw new Error("not a UserRewardManager type");
        }
        return UserRewardManager.reified().new({
            poolRewardManagerId: (0, reified_1.decodeFromFieldsWithTypes)(structs_4.ID.reified(), item.fields.pool_reward_manager_id),
            share: (0, reified_1.decodeFromFieldsWithTypes)("u64", item.fields.share),
            rewards: (0, reified_1.decodeFromFieldsWithTypes)(reified.vector(structs_1.Option.reified(UserReward.reified())), item.fields.rewards),
            lastUpdateTimeMs: (0, reified_1.decodeFromFieldsWithTypes)("u64", item.fields.last_update_time_ms),
        });
    }
    static fromBcs(data) {
        return UserRewardManager.fromFields(UserRewardManager.bcs.parse(data));
    }
    toJSONField() {
        return {
            poolRewardManagerId: this.poolRewardManagerId,
            share: this.share.toString(),
            rewards: (0, reified_1.fieldToJSON)(`vector<${structs_1.Option.$typeName}<${UserReward.$typeName}>>`, this.rewards),
            lastUpdateTimeMs: this.lastUpdateTimeMs.toString(),
        };
    }
    toJSON() {
        return Object.assign({ $typeName: this.$typeName, $typeArgs: this.$typeArgs }, this.toJSONField());
    }
    static fromJSONField(field) {
        return UserRewardManager.reified().new({
            poolRewardManagerId: (0, reified_1.decodeFromJSONField)(structs_4.ID.reified(), field.poolRewardManagerId),
            share: (0, reified_1.decodeFromJSONField)("u64", field.share),
            rewards: (0, reified_1.decodeFromJSONField)(reified.vector(structs_1.Option.reified(UserReward.reified())), field.rewards),
            lastUpdateTimeMs: (0, reified_1.decodeFromJSONField)("u64", field.lastUpdateTimeMs),
        });
    }
    static fromJSON(json) {
        if (json.$typeName !== UserRewardManager.$typeName) {
            throw new Error("not a WithTwoGenerics json object");
        }
        return UserRewardManager.fromJSONField(json);
    }
    static fromSuiParsedData(content) {
        if (content.dataType !== "moveObject") {
            throw new Error("not an object");
        }
        if (!isUserRewardManager(content.type)) {
            throw new Error(`object at ${content.fields.id} is not a UserRewardManager object`);
        }
        return UserRewardManager.fromFieldsWithTypes(content);
    }
    static fromSuiObjectData(data) {
        if (data.bcs) {
            if (data.bcs.dataType !== "moveObject" ||
                !isUserRewardManager(data.bcs.type)) {
                throw new Error(`object at is not a UserRewardManager object`);
            }
            return UserRewardManager.fromBcs((0, utils_1.fromB64)(data.bcs.bcsBytes));
        }
        if (data.content) {
            return UserRewardManager.fromSuiParsedData(data.content);
        }
        throw new Error("Both `bcs` and `content` fields are missing from the data. Include `showBcs` or `showContent` in the request.");
    }
    static fetch(client, id) {
        return __awaiter(this, void 0, void 0, function* () {
            var _a, _b;
            const res = yield client.getObject({ id, options: { showBcs: true } });
            if (res.error) {
                throw new Error(`error fetching UserRewardManager object at id ${id}: ${res.error.code}`);
            }
            if (((_b = (_a = res.data) === null || _a === void 0 ? void 0 : _a.bcs) === null || _b === void 0 ? void 0 : _b.dataType) !== "moveObject" ||
                !isUserRewardManager(res.data.bcs.type)) {
                throw new Error(`object at id ${id} is not a UserRewardManager object`);
            }
            return UserRewardManager.fromSuiObjectData(res.data);
        });
    }
}
exports.UserRewardManager = UserRewardManager;
UserRewardManager.$typeName = `${index_1.PKG_V1}::liquidity_mining::UserRewardManager`;
UserRewardManager.$numTypeParams = 0;
UserRewardManager.$isPhantom = [];

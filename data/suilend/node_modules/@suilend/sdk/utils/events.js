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
exports.ObligationDataEvent = exports.ClaimRewardEvent = exports.LiquidateEvent = exports.RepayEvent = exports.BorrowEvent = exports.WithdrawEvent = exports.DepositEvent = exports.RedeemEvent = exports.MintEvent = exports.ReserveAssetDataEvent = exports.InterestUpdateEvent = exports.GenericSuilendEvent = exports.SuilendTransactionModule = exports.SuilendEventType = void 0;
exports.getEvents = getEvents;
exports.getRedeemEvent = getRedeemEvent;
var SuilendEventType;
(function (SuilendEventType) {
    SuilendEventType["InterestUpdateEvent"] = "InterestUpdateEvent";
    SuilendEventType["ReserveAssetDataEvent"] = "ReserveAssetDataEvent";
    SuilendEventType["MintEvent"] = "MintEvent";
    SuilendEventType["RedeemEvent"] = "RedeemEvent";
    SuilendEventType["DepositEvent"] = "DepositEvent";
    SuilendEventType["WithdrawEvent"] = "WithdrawEvent";
    SuilendEventType["BorrowEvent"] = "BorrowEvent";
    SuilendEventType["RepayEvent"] = "RepayEvent";
    SuilendEventType["LiquidateEvent"] = "LiquidateEvent";
    SuilendEventType["ClaimRewardEvent"] = "ClaimRewardEvent";
    SuilendEventType["ObligationDataEvent"] = "ObligationDataEvent";
})(SuilendEventType || (exports.SuilendEventType = SuilendEventType = {}));
var SuilendTransactionModule;
(function (SuilendTransactionModule) {
    SuilendTransactionModule["LendingMarket"] = "lending_market";
    SuilendTransactionModule["Reserve"] = "reserve";
})(SuilendTransactionModule || (exports.SuilendTransactionModule = SuilendTransactionModule = {}));
class TypedParamsSuiEvent {
    constructor(event) {
        this.event = event;
    }
    params() {
        return this.event.parsedJson;
    }
    isType(module, eventType) {
        return this.event.type.includes(`${module}::${eventType}`);
    }
}
class GenericSuilendEvent extends TypedParamsSuiEvent {
}
exports.GenericSuilendEvent = GenericSuilendEvent;
class InterestUpdateEvent extends TypedParamsSuiEvent {
}
exports.InterestUpdateEvent = InterestUpdateEvent;
class ReserveAssetDataEvent extends TypedParamsSuiEvent {
}
exports.ReserveAssetDataEvent = ReserveAssetDataEvent;
class MintEvent extends TypedParamsSuiEvent {
}
exports.MintEvent = MintEvent;
class RedeemEvent extends TypedParamsSuiEvent {
}
exports.RedeemEvent = RedeemEvent;
class DepositEvent extends TypedParamsSuiEvent {
}
exports.DepositEvent = DepositEvent;
class WithdrawEvent extends TypedParamsSuiEvent {
}
exports.WithdrawEvent = WithdrawEvent;
class BorrowEvent extends TypedParamsSuiEvent {
}
exports.BorrowEvent = BorrowEvent;
class RepayEvent extends TypedParamsSuiEvent {
}
exports.RepayEvent = RepayEvent;
class LiquidateEvent extends TypedParamsSuiEvent {
}
exports.LiquidateEvent = LiquidateEvent;
class ClaimRewardEvent extends TypedParamsSuiEvent {
}
exports.ClaimRewardEvent = ClaimRewardEvent;
class ObligationDataEvent extends TypedParamsSuiEvent {
}
exports.ObligationDataEvent = ObligationDataEvent;
function getEvents(client, digest) {
    return __awaiter(this, void 0, void 0, function* () {
        const tx = yield client.getTransactionBlock({
            digest,
            options: { showEvents: true },
        });
        const events = [];
        for (const event of tx.events || []) {
            events.push(new GenericSuilendEvent(event));
        }
        return events;
    });
}
function getRedeemEvent(client, digest) {
    return __awaiter(this, void 0, void 0, function* () {
        const events = yield getEvents(client, digest);
        for (const event of events) {
            if (event.isType(SuilendTransactionModule.LendingMarket, SuilendEventType.RedeemEvent)) {
                return event;
            }
        }
        return null;
    });
}

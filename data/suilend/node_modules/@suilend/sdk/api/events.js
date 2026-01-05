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
exports.fetchDownsampledApiReserveAssetDataEvents = void 0;
/**
 * Note: This SDK function is experimental and may change or require authentication in the future.
 */
const fetchDownsampledApiReserveAssetDataEvents = (reserveId, days, sampleIntervalS) => __awaiter(void 0, void 0, void 0, function* () {
    const url = `https://api.suilend.fi/events/downsampled-reserve-asset-data?reserveId=${reserveId}&days=${days}&sampleIntervalS=${sampleIntervalS}`;
    const res = yield fetch(url);
    const json = yield res.json();
    return json;
});
exports.fetchDownsampledApiReserveAssetDataEvents = fetchDownsampledApiReserveAssetDataEvents;

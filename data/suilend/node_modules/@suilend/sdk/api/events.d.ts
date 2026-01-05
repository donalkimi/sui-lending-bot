import { DownsampledApiReserveAssetDataEvent } from "../lib/types";
/**
 * Note: This SDK function is experimental and may change or require authentication in the future.
 */
export declare const fetchDownsampledApiReserveAssetDataEvents: (reserveId: string, days: number, sampleIntervalS: number) => Promise<DownsampledApiReserveAssetDataEvent[]>;

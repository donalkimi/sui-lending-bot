import { Transaction, TransactionArgument, TransactionObjectInput } from "@mysten/sui/transactions";
export interface NewArgs {
    config: TransactionObjectInput;
    curTime: bigint | TransactionArgument;
}
export declare function new_(tx: Transaction, args: NewArgs): import("@mysten/sui/transactions").TransactionResult;
export interface CurrentOutflowArgs {
    rateLimiter: TransactionObjectInput;
    curTime: bigint | TransactionArgument;
}
export declare function currentOutflow(tx: Transaction, args: CurrentOutflowArgs): import("@mysten/sui/transactions").TransactionResult;
export interface NewConfigArgs {
    windowDuration: bigint | TransactionArgument;
    maxOutflow: bigint | TransactionArgument;
}
export declare function newConfig(tx: Transaction, args: NewConfigArgs): import("@mysten/sui/transactions").TransactionResult;
export interface ProcessQtyArgs {
    rateLimiter: TransactionObjectInput;
    curTime: bigint | TransactionArgument;
    qty: TransactionObjectInput;
}
export declare function processQty(tx: Transaction, args: ProcessQtyArgs): import("@mysten/sui/transactions").TransactionResult;
export interface RemainingOutflowArgs {
    rateLimiter: TransactionObjectInput;
    curTime: bigint | TransactionArgument;
}
export declare function remainingOutflow(tx: Transaction, args: RemainingOutflowArgs): import("@mysten/sui/transactions").TransactionResult;
export interface UpdateInternalArgs {
    rateLimiter: TransactionObjectInput;
    curTime: bigint | TransactionArgument;
}
export declare function updateInternal(tx: Transaction, args: UpdateInternalArgs): import("@mysten/sui/transactions").TransactionResult;

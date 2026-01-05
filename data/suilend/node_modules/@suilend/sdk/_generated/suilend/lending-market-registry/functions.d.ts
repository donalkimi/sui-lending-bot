import { Transaction, TransactionObjectInput } from "@mysten/sui/transactions";
export declare function init(tx: Transaction): import("@mysten/sui/transactions").TransactionResult;
export declare function createLendingMarket(tx: Transaction, typeArg: string, registry: TransactionObjectInput): import("@mysten/sui/transactions").TransactionResult;

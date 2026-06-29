/**
 * Custom exceptions hierarchy for the GrowthScout AI TS/JS SDK.
 */
export declare class GrowthScoutError extends Error {
    constructor(message: string);
}
export declare class GrowthScoutNetworkError extends GrowthScoutError {
}
export declare class GrowthScoutAuthenticationError extends GrowthScoutError {
}
export declare class GrowthScoutValidationError extends GrowthScoutError {
}
export declare class GrowthScoutRateLimitError extends GrowthScoutError {
    retryAfterSeconds: number;
    constructor(message: string, retryAfterSeconds?: number);
}
export declare class GrowthScoutLockConflictError extends GrowthScoutError {
}
export declare class GrowthScoutPayloadTooLargeError extends GrowthScoutError {
}

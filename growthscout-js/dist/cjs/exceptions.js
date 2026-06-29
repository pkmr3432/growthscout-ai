"use strict";
// growthscout-js/src/exceptions.ts
/**
 * Custom exceptions hierarchy for the GrowthScout AI TS/JS SDK.
 */
Object.defineProperty(exports, "__esModule", { value: true });
exports.GrowthScoutPayloadTooLargeError = exports.GrowthScoutLockConflictError = exports.GrowthScoutRateLimitError = exports.GrowthScoutValidationError = exports.GrowthScoutAuthenticationError = exports.GrowthScoutNetworkError = exports.GrowthScoutError = void 0;
class GrowthScoutError extends Error {
    constructor(message) {
        super(message);
        this.name = this.constructor.name;
        Object.setPrototypeOf(this, new.target.prototype);
    }
}
exports.GrowthScoutError = GrowthScoutError;
class GrowthScoutNetworkError extends GrowthScoutError {
}
exports.GrowthScoutNetworkError = GrowthScoutNetworkError;
class GrowthScoutAuthenticationError extends GrowthScoutError {
}
exports.GrowthScoutAuthenticationError = GrowthScoutAuthenticationError;
class GrowthScoutValidationError extends GrowthScoutError {
}
exports.GrowthScoutValidationError = GrowthScoutValidationError;
class GrowthScoutRateLimitError extends GrowthScoutError {
    retryAfterSeconds;
    constructor(message, retryAfterSeconds = 1.0) {
        super(message);
        this.retryAfterSeconds = retryAfterSeconds;
    }
}
exports.GrowthScoutRateLimitError = GrowthScoutRateLimitError;
class GrowthScoutLockConflictError extends GrowthScoutError {
}
exports.GrowthScoutLockConflictError = GrowthScoutLockConflictError;
class GrowthScoutPayloadTooLargeError extends GrowthScoutError {
}
exports.GrowthScoutPayloadTooLargeError = GrowthScoutPayloadTooLargeError;
//# sourceMappingURL=exceptions.js.map
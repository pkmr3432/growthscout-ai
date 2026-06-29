// growthscout-js/src/exceptions.ts
/**
 * Custom exceptions hierarchy for the GrowthScout AI TS/JS SDK.
 */

export class GrowthScoutError extends Error {
  constructor(message: string) {
    super(message);
    this.name = this.constructor.name;
    Object.setPrototypeOf(this, new.target.prototype);
  }
}

export class GrowthScoutNetworkError extends GrowthScoutError {}

export class GrowthScoutAuthenticationError extends GrowthScoutError {}

export class GrowthScoutValidationError extends GrowthScoutError {}

export class GrowthScoutRateLimitError extends GrowthScoutError {
  public retryAfterSeconds: number;

  constructor(message: string, retryAfterSeconds: number = 1.0) {
    super(message);
    this.retryAfterSeconds = retryAfterSeconds;
  }
}

export class GrowthScoutLockConflictError extends GrowthScoutError {}

export class GrowthScoutPayloadTooLargeError extends GrowthScoutError {}

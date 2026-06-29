/**
 * SSE Event Stream consumer for JavaScript/TypeScript SDK.
 */
export declare class EventStream {
    private client;
    private sessionId;
    private lastEventId;
    private active;
    private listeners;
    constructor(client: any, sessionId: string);
    /**
     * Registers a callback listener for specific event types.
     */
    on(event: string, callback: (data: any) => void): void;
    /**
     * Closes the active stream connection.
     */
    close(): void;
    /**
     * Starts listening to the stream, handling chunks and reconnection automatically.
     */
    listen(): Promise<void>;
    private emit;
    private parseBlock;
}

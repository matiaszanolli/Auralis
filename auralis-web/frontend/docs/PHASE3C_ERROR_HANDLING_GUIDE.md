# Phase 3c: Error Handling Extraction Guide

## Overview

Phase 3c centralizes error handling patterns across four complex services into a single, reusable utility module (`errorHandling.ts`), reducing code duplication and improving consistency.

**Created**: `src/utils/errorHandling.ts` (420+ lines)
**Refactored**: `src/services/mseStreamingService.ts` (removed 21 lines of duplicate retry logic)

## Error Handling Utilities Provided

### 1. RetryPolicy Configuration
```typescript
interface RetryPolicy {
  maxRetries: number;
  initialDelayMs: number;
  maxDelayMs: number;
  backoffMultiplier: number;
  jitterFraction: number;
  shouldRetry?: (error: Error) => boolean;
}
```

**Usage**: Configure retry behavior per operation:
```typescript
await retryWithBackoff(fetchFn, {
  maxRetries: 3,
  initialDelayMs: 100,
  backoffMultiplier: 2,
  shouldRetry: isRetryableError,
});
```

### 2. WebSocketManager Class
Unified WebSocket connection management with automatic reconnection:

```typescript
const manager = new WebSocketManager(url, {
  maxReconnectAttempts: 10,
  initialReconnectDelayMs: 1000,
  backoffMultiplier: 1.5,
});

manager.on('message', (event) => { /* ... */ });
await manager.connect();
manager.send(data);
```

**Features**:
- Automatic exponential backoff reconnection
- Heartbeat detection
- Event handlers (open, close, message, error)
- Configurable reconnection limits

### 3. Error Classification
```typescript
classifyErrorSeverity(error) // Returns: 'low' | 'medium' | 'high' | 'critical'
isRetryableError(error)       // Returns: boolean
```

### 4. Error Recovery Chain
```typescript
const recovery = new ErrorRecoveryChain()
  .add(strategy1)
  .add(strategy2);

if (await recovery.tryRecover(error)) {
  // Recovery succeeded
}
```

### 5. Global Error Logger
```typescript
globalErrorLogger.log(error, 'context');
globalErrorLogger.getHistory(100);
globalErrorLogger.getErrorsBySeverity('high');
```

## Refactoring Pattern: mseStreamingService.ts

### Before
```typescript
// Had its own retry logic:
export async function retryWithBackoff<T>(
  fn: () => Promise<T>,
  maxRetries: number = 3,
  baseDelay: number = 100
): Promise<T> {
  // 20+ lines of retry logic
}

// Applied to loadChunk:
const response = await fetch(url);
if (!response.ok) throw new Error(...);
```

### After
```typescript
import { retryWithBackoff, isRetryableError } from '../utils/errorHandling';

const response = await retryWithBackoff(
  async () => {
    const res = await fetch(url);
    if (!res.ok) throw new Error(...);
    return res;
  },
  {
    maxRetries: 3,
    initialDelayMs: 100,
    shouldRetry: isRetryableError,
  }
);
```

**Improvements**:
- ✅ Removed 21 lines of duplicate code
- ✅ Automatic network error detection with `isRetryableError`
- ✅ Exponential backoff with jitter
- ✅ Consistent retry behavior across all services
- ✅ Better error logging and monitoring

## Refactoring Guide for Remaining Services

### processingService.ts (385 lines)

**Current Error Handling**:
- WebSocket connection with hardcoded 3-second reconnect (lines 102-136)
- Manual error handling in connectWebSocket
- Job progress callbacks without error recovery

**Refactoring Steps**:
1. Replace WebSocket connection code with `WebSocketManager`
2. Use `withErrorLogging` wrapper for API calls
3. Add `ErrorRecoveryChain` for job processing failures

**Example**:
```typescript
// OLD
this.ws = new WebSocket(this.wsUrl);
this.ws.onopen = () => { /* ... */ };
this.ws.onerror = (error) => { reject(error); };
this.ws.onclose = () => {
  setTimeout(() => this.connectWebSocket(), 3000); // Hardcoded retry
};

// NEW
const wsManager = new WebSocketManager(this.wsUrl, {
  maxReconnectAttempts: 10,
  initialReconnectDelayMs: 1000,
  backoffMultiplier: 1.5,
  onReconnectAttempt: (attempt, delay) => {
    console.log(`Reconnecting... Attempt ${attempt}`);
  },
});

wsManager.on('message', (event) => {
  this.handleWebSocketMessage(event);
});

await wsManager.connect();
```

**Lines Saved**: ~30 lines (automatic reconnection logic)

---

### RealTimeAnalysisStream.ts (605 lines)

**Current Error Handling**:
- Manual reconnection logic with exponential backoff (lines 112-114)
- Error callbacks with severity classification (lines 105, 129)
- Timeout handling scattered throughout

**Refactoring Steps**:
1. Replace WebSocket handling with `WebSocketManager`
2. Use `ErrorLogger` for error tracking
3. Implement `createTimeoutPromise` for buffer processing

**Example**:
```typescript
// OLD
private reconnectAttempts = 0;
private maxReconnectAttempts = 10;
private reconnectInterval = 1000; // Start with 1 second
// ... ~50 lines of manual reconnection logic

// NEW
const wsManager = new WebSocketManager(url, {
  maxReconnectAttempts: 10,
  initialReconnectDelayMs: 1000,
  backoffMultiplier: 1.5,
});

// All reconnection logic handled automatically
```

**Lines Saved**: ~50+ lines

---

### AnalysisExportService.ts (886 lines)

**Current Error Handling**:
- Manual file download with basic error handling
- No retry logic for large exports
- Service-specific timeout handling

**Refactoring Steps**:
1. Use `resilientFetch` for all API calls
2. Add `ErrorRecoveryChain` for export operation failures
3. Implement timeout protection with `createTimeoutPromise`
4. Use `ErrorLogger` for export progress tracking

**Example**:
```typescript
// OLD
async downloadResult(jobId: string): Promise<Blob> {
  const response = await fetch(`${this.baseUrl}/...`);
  if (!response.ok) throw new Error(...);
  return response.blob();
}

// NEW
async downloadResult(jobId: string): Promise<Blob> {
  const response = await resilientFetch(`${this.baseUrl}/...`, {}, {
    maxRetries: 5,
    initialDelayMs: 500,
  });

  // Add timeout protection for large exports
  const blob = await createTimeoutPromise(
    response.blob(),
    60000, // 60 second timeout
    'Export download timed out'
  );

  globalErrorLogger.log(null, 'Export successful');
  return blob;
}
```

**Lines Saved**: ~40+ lines

---

## Implementation Checklist

### Phase 3c - Part 1 (COMPLETE)
- [x] Create `errorHandling.ts` utility module
- [x] Refactor `mseStreamingService.ts`
- [ ] Commit error handling utilities and mseStreamingService refactoring

### Phase 3c - Part 2 (READY FOR NEXT SESSION)
- [ ] Refactor `processingService.ts` (~30 lines saved)
- [ ] Refactor `RealTimeAnalysisStream.ts` (~50 lines saved)
- [ ] Refactor `AnalysisExportService.ts` (~40 lines saved)
- [ ] Run full test suite
- [ ] Commit remaining service refactorings
- [ ] Update roadmap

## Expected Impact

- **Code Reduction**: ~150-200 lines saved across 4 services
- **Code Duplication**: Eliminated 3+ instances of retry/reconnection logic
- **Consistency**: All services now use standardized error handling
- **Maintainability**: Centralized error handling makes policy changes easier
- **Debugging**: Unified error logging for better visibility

## Testing Strategy

1. **Unit Tests** (per service):
   - Verify retry behavior on network errors
   - Test timeout handling
   - Validate error recovery

2. **Integration Tests**:
   - Test cross-service error propagation
   - Verify WebSocket reconnection under failure conditions
   - Test error logger accuracy

3. **Manual Testing**:
   - Kill network and verify auto-reconnection
   - Test export with large files
   - Verify streaming recovery from interruptions

## Notes

- All refactoring maintains backward compatibility
- Error handling is automatic (no API changes for consumers)
- Services can override retry policies for specific operations
- Error logger provides audit trail for debugging

## References

- `src/utils/errorHandling.ts` - Main utility module
- `src/services/mseStreamingService.ts` - Example refactored service
- [TESTING_GUIDELINES.md](../../docs/development/TESTING_GUIDELINES.md)

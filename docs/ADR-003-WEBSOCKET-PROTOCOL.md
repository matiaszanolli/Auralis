# ADR-003: WebSocket Message Protocol Design

**Status**: Accepted
**Date**: 2024-11-28
**Author**: Architecture Team
**Decision**: Implement standardized WebSocket protocol for real-time player synchronization
**Applies To**: All WebSocket communication between frontend and backend

---

## Context

Real-time synchronization is critical for the player experience:
- Multiple clients (desktop, web) playing same library
- Synchronized queue updates
- Live position tracking
- Instant playback state changes

Current WebSocket implementation is ad-hoc. The modernization requires a formal, extensible protocol.

### Requirements

1. **Message Ordering**: Deliver messages in order (no race conditions)
2. **Bidirectional**: Both client and server can initiate messages
3. **Type Safety**: Message validation and structure verification
4. **Extensibility**: Easy to add new message types without protocol changes
5. **Debugging**: Clear format for debugging and monitoring
6. **Performance**: Minimal overhead, efficient serialization
7. **Reliability**: Handle disconnections gracefully, reconnect automatically

---

## Decision

### Protocol Structure

All WebSocket messages follow this envelope:

```typescript
interface WebSocketMessage<T = any> {
  // Unique message identifier for correlation
  id: string;

  // Message type (player.start, queue.add, etc.)
  type: string;

  // Message payload (type-specific data)
  data: T;

  // Sequence number for ordering
  sequence: number;

  // Timestamp for debugging
  timestamp: number;

  // Request ID this is responding to (if response)
  responseToId?: string;

  // Error information (if error)
  error?: {
    code: string;
    message: string;
    details?: Record<string, any>;
  };
}
```

### Message Type Hierarchy

```
player.*
  ├─ player.start          Client → Server: Start playback
  ├─ player.pause          Client → Server: Pause playback
  ├─ player.stop           Client → Server: Stop playback
  ├─ player.seek           Client → Server: Seek to position
  ├─ player.state          Server → Client: Player state update
  └─ player.position       Server → Client: Position update (periodic)

queue.*
  ├─ queue.add             Client → Server: Add track to queue
  ├─ queue.remove          Client → Server: Remove from queue
  ├─ queue.reorder         Client → Server: Reorder queue
  ├─ queue.clear           Client → Server: Clear queue
  ├─ queue.state           Server → Client: Queue state update
  └─ queue.position        Server → Client: Current queue position

library.*
  ├─ library.search        Client → Server: Search library
  ├─ library.browse        Client → Server: Browse collection
  └─ library.results       Server → Client: Search/browse results

connection.*
  ├─ connection.ping       Client → Server: Heartbeat
  ├─ connection.pong       Server → Client: Heartbeat response
  ├─ connection.ready      Server → Client: Ready for messages
  └─ connection.close      Either → Either: Close connection

notification.*
  ├─ notification.info     Server → Client: Info notification
  ├─ notification.warning  Server → Client: Warning notification
  └─ notification.error    Server → Client: Error notification
```

### Message Examples

#### Player Control Messages

```typescript
// Client: Start playback
{
  id: "msg_123456",
  type: "player.start",
  sequence: 1,
  timestamp: 1701154200000,
  data: {
    trackId: "track_789",
    position: 0
  }
}

// Server: Player state update
{
  id: "msg_123457",
  type: "player.state",
  sequence: 2,
  timestamp: 1701154201000,
  data: {
    isPlaying: true,
    currentTrack: {
      id: "track_789",
      title: "Song Title",
      artist: "Artist Name",
      duration: 240000
    },
    position: 0,
    volume: 0.8,
    playbackRate: 1.0
  }
}

// Server: Position update (sent every 1 second during playback)
{
  id: "msg_123458",
  type: "player.position",
  sequence: 3,
  timestamp: 1701154202000,
  data: {
    position: 1000,  // in milliseconds
    isPlaying: true
  }
}

// Client: Seek to position
{
  id: "msg_123459",
  type: "player.seek",
  sequence: 4,
  timestamp: 1701154203000,
  data: {
    position: 120000,  // Seek to 2 minutes
    trackId: "track_789"
  }
}
```

#### Queue Control Messages

```typescript
// Client: Add track to queue
{
  id: "msg_123460",
  type: "queue.add",
  sequence: 5,
  timestamp: 1701154204000,
  data: {
    trackId: "track_101",
    position: "end",  // or specific index
    metadata: {
      source: "search",
      searchQuery: "Beatles"
    }
  }
}

// Server: Queue state update
{
  id: "msg_123461",
  type: "queue.state",
  sequence: 6,
  timestamp: 1701154205000,
  data: {
    position: 0,
    length: 50,
    tracks: [
      {
        id: "track_101",
        title: "Track 1",
        artist: "Artist",
        duration: 240000,
        addedAt: 1701154204000
      },
      // ... more tracks
    ],
    totalDuration: 12000000
  }
}

// Client: Remove from queue
{
  id: "msg_123462",
  type: "queue.remove",
  sequence: 7,
  timestamp: 1701154206000,
  data: {
    position: 0  // Remove track at position 0
  }
}
```

#### Connection Management

```typescript
// Client: Heartbeat (every 30 seconds)
{
  id: "msg_123463",
  type: "connection.ping",
  sequence: 8,
  timestamp: 1701154207000,
  data: {}
}

// Server: Heartbeat response
{
  id: "msg_123464",
  type: "connection.pong",
  sequence: 9,
  timestamp: 1701154208000,
  responseToId: "msg_123463",
  data: {
    serverTime: 1701154208000
  }
}

// Server: Ready for messages (sent on connect)
{
  id: "msg_123465",
  type: "connection.ready",
  sequence: 0,
  timestamp: 1701154209000,
  data: {
    clientId: "client_xyz",
    sessionId: "session_abc",
    serverVersion: "1.1.0",
    features: ["streaming", "cache", "realtime"]
  }
}
```

#### Error Handling

```typescript
// Server: Error response to invalid message
{
  id: "msg_123466",
  type: "player.start",
  sequence: 10,
  timestamp: 1701154210000,
  responseToId: "msg_123459",  // Responding to request
  error: {
    code: "INVALID_TRACK",
    message: "Track not found",
    details: {
      trackId: "track_999",
      availableAlternatives: ["track_101", "track_102"]
    }
  }
}
```

---

## Implementation Details

### Backend (Python)

```python
# models.py - Message types
from enum import Enum
from typing import Dict, Any, Optional
from pydantic import BaseModel

class MessageType(str, Enum):
    """All valid message types."""
    PLAYER_START = "player.start"
    PLAYER_PAUSE = "player.pause"
    PLAYER_STOP = "player.stop"
    PLAYER_SEEK = "player.seek"
    PLAYER_STATE = "player.state"
    PLAYER_POSITION = "player.position"

    QUEUE_ADD = "queue.add"
    QUEUE_REMOVE = "queue.remove"
    QUEUE_REORDER = "queue.reorder"
    QUEUE_CLEAR = "queue.clear"
    QUEUE_STATE = "queue.state"
    QUEUE_POSITION = "queue.position"

    CONNECTION_PING = "connection.ping"
    CONNECTION_PONG = "connection.pong"
    CONNECTION_READY = "connection.ready"
    CONNECTION_CLOSE = "connection.close"

    NOTIFICATION_INFO = "notification.info"
    NOTIFICATION_WARNING = "notification.warning"
    NOTIFICATION_ERROR = "notification.error"

class ErrorInfo(BaseModel):
    """Error information."""
    code: str
    message: str
    details: Optional[Dict[str, Any]] = None

class WebSocketMessage(BaseModel):
    """WebSocket message envelope."""
    id: str
    type: MessageType
    data: Dict[str, Any]
    sequence: int
    timestamp: int
    responseToId: Optional[str] = None
    error: Optional[ErrorInfo] = None

    class Config:
        use_enum_values = True
```

```python
# handler.py - Message handling
class WebSocketHandler:
    """Handle WebSocket messages."""

    def __init__(self, player_state: PlayerState):
        self.player = player_state
        self.sequence_counter = 0

    async def handle_message(
        self,
        message: WebSocketMessage,
        websocket: WebSocket,
    ) -> Optional[WebSocketMessage]:
        """Handle incoming message and return response if needed."""
        try:
            # Route by message type
            if message.type == MessageType.PLAYER_START:
                return await self.handle_player_start(message)
            elif message.type == MessageType.PLAYER_PAUSE:
                return await self.handle_player_pause(message)
            elif message.type == MessageType.CONNECTION_PING:
                return self.handle_ping(message)
            else:
                return self.create_error(
                    message,
                    "UNKNOWN_TYPE",
                    f"Unknown message type: {message.type}"
                )

        except Exception as e:
            logger.error(f"Error handling message: {e}")
            return self.create_error(
                message,
                "INTERNAL_ERROR",
                str(e)
            )

    async def handle_player_start(
        self,
        message: WebSocketMessage,
    ) -> WebSocketMessage:
        """Handle player start request."""
        track_id = message.data.get('trackId')

        # Validate track exists
        track = await self.player.load_track(track_id)
        if not track:
            return self.create_error(
                message,
                "INVALID_TRACK",
                f"Track {track_id} not found"
            )

        # Start playback
        await self.player.start(track_id)

        # Return state update
        return self.create_message(
            MessageType.PLAYER_STATE,
            data={
                'isPlaying': True,
                'currentTrack': track.to_dict(),
                'position': 0,
            },
            responseToId=message.id
        )

    def create_message(
        self,
        message_type: MessageType,
        data: Dict[str, Any],
        responseToId: Optional[str] = None,
    ) -> WebSocketMessage:
        """Create WebSocket message."""
        self.sequence_counter += 1
        return WebSocketMessage(
            id=generate_message_id(),
            type=message_type,
            data=data,
            sequence=self.sequence_counter,
            timestamp=int(time.time() * 1000),
            responseToId=responseToId,
        )

    def create_error(
        self,
        request: WebSocketMessage,
        code: str,
        message: str,
        details: Optional[Dict] = None,
    ) -> WebSocketMessage:
        """Create error response."""
        self.sequence_counter += 1
        return WebSocketMessage(
            id=generate_message_id(),
            type=request.type,
            data={},
            sequence=self.sequence_counter,
            timestamp=int(time.time() * 1000),
            responseToId=request.id,
            error=ErrorInfo(
                code=code,
                message=message,
                details=details
            )
        )

    def handle_ping(
        self,
        message: WebSocketMessage,
    ) -> WebSocketMessage:
        """Handle heartbeat ping."""
        return self.create_message(
            MessageType.CONNECTION_PONG,
            data={'serverTime': int(time.time() * 1000)},
            responseToId=message.id
        )
```

### Frontend (TypeScript)

```typescript
// types.ts - Message types
export interface ErrorInfo {
  code: string;
  message: string;
  details?: Record<string, any>;
}

export interface WebSocketMessage<T = any> {
  id: string;
  type: string;
  data: T;
  sequence: number;
  timestamp: number;
  responseToId?: string;
  error?: ErrorInfo;
}

export type PlayerStartData = {
  trackId: string;
  position?: number;
};

export type PlayerStateData = {
  isPlaying: boolean;
  currentTrack: Track | null;
  position: number;
  volume: number;
};

export type QueueAddData = {
  trackId: string;
  position: 'end' | number;
};
```

```typescript
// websocket.ts - Client implementation
import { useCallback, useEffect, useRef, useState } from 'react';

export class WebSocketClient {
  private ws: WebSocket | null = null;
  private url: string;
  private sequence = 0;
  private pendingRequests = new Map<string, Promise<WebSocketMessage>>();

  constructor(url: string) {
    this.url = url;
  }

  connect(): Promise<void> {
    return new Promise((resolve, reject) => {
      this.ws = new WebSocket(this.url);

      this.ws.onopen = () => {
        console.log('WebSocket connected');
        this.startHeartbeat();
        resolve();
      };

      this.ws.onerror = (error) => {
        console.error('WebSocket error:', error);
        reject(error);
      };

      this.ws.onmessage = (event) => {
        const message: WebSocketMessage = JSON.parse(event.data);
        this.handleMessage(message);
      };
    });
  }

  async send<T, R>(
    type: string,
    data: T,
  ): Promise<R> {
    const id = this.generateId();
    this.sequence++;

    const message: WebSocketMessage = {
      id,
      type,
      data,
      sequence: this.sequence,
      timestamp: Date.now(),
    };

    // Create promise for response
    const responsePromise = new Promise<WebSocketMessage>((resolve) => {
      this.pendingRequests.set(id, Promise.resolve());
      // Will be resolved when response arrives
      const checkResponse = setInterval(() => {
        if (this.pendingRequests.has(`${id}_response`)) {
          const response = this.pendingRequests.get(`${id}_response`);
          clearInterval(checkResponse);
          resolve(response!);
        }
      }, 10);
    });

    this.ws!.send(JSON.stringify(message));
    return responsePromise as Promise<R>;
  }

  private handleMessage(message: WebSocketMessage): void {
    // Handle response to request
    if (message.responseToId) {
      this.pendingRequests.set(
        `${message.responseToId}_response`,
        message
      );
      return;
    }

    // Handle server-initiated message
    switch (message.type) {
      case 'connection.ready':
        this.handleReady(message);
        break;
      case 'player.state':
        this.handlePlayerState(message);
        break;
      case 'player.position':
        this.handlePlayerPosition(message);
        break;
      case 'queue.state':
        this.handleQueueState(message);
        break;
      default:
        console.warn(`Unknown message type: ${message.type}`);
    }
  }

  private startHeartbeat(): void {
    setInterval(() => {
      this.send('connection.ping', {});
    }, 30000);  // Every 30 seconds
  }

  private generateId(): string {
    return `msg_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`;
  }

  private handleReady(message: WebSocketMessage): void {
    console.log('WebSocket ready:', message.data);
  }

  private handlePlayerState(message: WebSocketMessage): void {
    console.log('Player state:', message.data);
    // Dispatch to Redux
  }

  private handlePlayerPosition(message: WebSocketMessage): void {
    // Update position without full state change
  }

  private handleQueueState(message: WebSocketMessage): void {
    console.log('Queue state:', message.data);
    // Dispatch to Redux
  }
}
```

---

## Error Handling Strategy

### Client-Side Error Recovery

```typescript
class WebSocketClient {
  private reconnectAttempts = 0;
  private maxReconnectAttempts = 5;
  private reconnectDelay = 1000; // 1 second

  async ensureConnected(): Promise<void> {
    if (!this.ws || this.ws.readyState === WebSocket.CLOSED) {
      await this.reconnect();
    }
  }

  private async reconnect(): Promise<void> {
    while (this.reconnectAttempts < this.maxReconnectAttempts) {
      try {
        await this.connect();
        this.reconnectAttempts = 0;
        return;
      } catch (error) {
        this.reconnectAttempts++;
        const delay = this.reconnectDelay * Math.pow(2, this.reconnectAttempts);
        console.log(`Reconnecting in ${delay}ms...`);
        await sleep(delay);
      }
    }
    throw new Error('Max reconnection attempts exceeded');
  }
}
```

### Server-Side Message Validation

```python
class WebSocketHandler:
    async def validate_message(
        self,
        message: Dict[str, Any],
    ) -> Optional[str]:
        """Validate message structure. Return error code if invalid."""

        # Check required fields
        required_fields = ['id', 'type', 'data', 'sequence', 'timestamp']
        for field in required_fields:
            if field not in message:
                return "INVALID_MESSAGE_STRUCTURE"

        # Check type is valid
        if message['type'] not in MessageType.__members__.values():
            return "UNKNOWN_MESSAGE_TYPE"

        # Check sequence is monotonically increasing
        if message['sequence'] <= self.last_sequence:
            return "OUT_OF_ORDER_MESSAGE"

        self.last_sequence = message['sequence']
        return None
```

---

## Backpressure & Rate Limiting

### Server-Side

```python
class WebSocketHandler:
    MAX_MESSAGES_PER_SECOND = 100

    def __init__(self):
        self.message_timestamps = deque(maxlen=100)

    async def check_rate_limit(self) -> bool:
        """Check if client exceeds rate limit."""
        now = time.time()

        # Remove timestamps older than 1 second
        while self.message_timestamps and self.message_timestamps[0] < now - 1:
            self.message_timestamps.popleft()

        if len(self.message_timestamps) >= self.MAX_MESSAGES_PER_SECOND:
            return False  # Rate limited

        self.message_timestamps.append(now)
        return True
```

### Client-Side

```typescript
class WebSocketClient {
  private messageQueue: WebSocketMessage[] = [];
  private isProcessing = false;
  private maxQueueSize = 50;

  async send(message: WebSocketMessage): Promise<void> {
    // Queue message if processing
    if (this.isProcessing || this.ws?.readyState !== WebSocket.OPEN) {
      if (this.messageQueue.length >= this.maxQueueSize) {
        throw new Error('Message queue full');
      }
      this.messageQueue.push(message);
      return;
    }

    // Send immediately if not processing
    this.ws!.send(JSON.stringify(message));
  }

  private async processQueue(): Promise<void> {
    this.isProcessing = true;
    while (this.messageQueue.length > 0) {
      const message = this.messageQueue.shift()!;
      this.ws!.send(JSON.stringify(message));
      // Small delay between messages to avoid overwhelming server
      await sleep(10);
    }
    this.isProcessing = false;
  }
}
```

---

## Consequences

### Positive
- ✅ Standardized message format (easy to debug)
- ✅ Type-safe communication
- ✅ Clear error handling
- ✅ Extensible for new features
- ✅ Built-in heartbeat mechanism
- ✅ Message ordering guarantees
- ✅ Clear request/response correlation

### Trade-offs
- ⚠️ Slightly more overhead than minimal protocol
- ⚠️ Requires schema validation on both sides
- ⚠️ JSON serialization cost (mitigated by gzip)

### Mitigations
- Message batching to reduce overhead
- Optional binary protocol layer (future)
- Connection pooling for multiple clients

---

## Monitoring & Debugging

### Server Logging

```python
# Log all messages in debug mode
DEBUG_LOG = {
    'timestamp': message.timestamp,
    'id': message.id,
    'type': message.type,
    'sequence': message.sequence,
    'clientIp': client_ip,
    'latency_ms': current_time - message.timestamp,
}

if message.error:
    DEBUG_LOG['error'] = message.error.code
    logger.warning(f"WebSocket error: {DEBUG_LOG}")
else:
    logger.debug(f"WebSocket message: {DEBUG_LOG}")
```

### Client DevTools Extension

Display WebSocket messages in Chrome DevTools for debugging:
- Message history with timeline
- Request/response correlation
- Latency measurements
- Error highlighting

---

## Related Decisions
- ADR-001: React 18 + TypeScript + Redux Toolkit Stack
- ADR-002: Phase 7.5 Cache Integration Architecture
- ADR-004: Component Size and Structure Limits

---

## Future Enhancements

### Binary Protocol (Phase 7.6+)
- Reduce message size with Protocol Buffers or MessagePack
- Faster serialization/deserialization
- Better for high-frequency updates

### Multiplexing
- Support multiple concurrent operations per connection
- Request prioritization
- Bandwidth optimization

---

## References
- [WebSocket Standard](https://tools.ietf.org/html/rfc6455)
- [JSON Schema](https://json-schema.org/)
- [FastAPI WebSocket Documentation](https://fastapi.tiangolo.com/advanced/websockets/)
- [Socket.io Documentation](https://socket.io/docs/)

---

**Next Review**: After Phase B.3 WebSocket enhancement (Week 5)
**Last Updated**: 2024-11-28

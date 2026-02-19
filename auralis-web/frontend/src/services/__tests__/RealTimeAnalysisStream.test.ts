/**
 * Tests for RealTimeAnalysisStream — issue #2462
 *
 * Verifies that the phantom `this.isStreaming` property is gone and that
 * startStreaming / stopStreaming / disconnect correctly drive state through
 * stateManager, so isStreamingData() always reflects true state.
 */

import { describe, it, expect, vi, beforeEach } from 'vitest';

// ---------------------------------------------------------------------------
// Mock streamingInfrastructure
// ---------------------------------------------------------------------------

const mockSetStreaming = vi.fn();
const mockSetConnected = vi.fn();
const mockGetStatus = vi.fn();
const mockGetMetrics = vi.fn();
const mockRecordPacketReceived = vi.fn();
const mockRecordPacketsDropped = vi.fn();
const mockUpdateLatency = vi.fn();
const mockUpdateBufferHealth = vi.fn();
const mockOnStatusChange = vi.fn();
const mockCleanup = vi.fn();

vi.mock('../../utils/streamingInfrastructure', () => ({
  createStreamingState: () => ({
    setStreaming: mockSetStreaming,
    setConnected: mockSetConnected,
    getStatus: mockGetStatus,
    getMetrics: mockGetMetrics,
    recordPacketReceived: mockRecordPacketReceived,
    recordPacketsDropped: mockRecordPacketsDropped,
    updateLatency: mockUpdateLatency,
    updateBufferHealth: mockUpdateBufferHealth,
    onStatusChange: mockOnStatusChange,
    cleanup: mockCleanup,
  }),
  createSubscriptionManager: () => ({ clear: vi.fn() }),
  createBackpressureManager: () => ({ checkBackpressure: vi.fn() }),
}));

// ---------------------------------------------------------------------------
// Mock errorHandling
// ---------------------------------------------------------------------------

vi.mock('../../utils/errorHandling', () => ({
  WebSocketManager: vi.fn().mockImplementation(() => ({
    on: vi.fn(),
    connect: vi.fn().mockResolvedValue(undefined),
    close: vi.fn(),
    send: vi.fn(),
    isConnected: vi.fn().mockReturnValue(false),
  })),
  classifyErrorSeverity: vi.fn().mockReturnValue('high'),
}));

// ---------------------------------------------------------------------------
// Import after mocks
// ---------------------------------------------------------------------------

import { RealTimeAnalysisStream } from '../RealTimeAnalysisStream';

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function makeStream(): RealTimeAnalysisStream {
  // suppress setInterval during construction
  vi.spyOn(window, 'setInterval').mockReturnValue(0 as unknown as ReturnType<typeof setInterval>);
  return new RealTimeAnalysisStream();
}

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

describe('RealTimeAnalysisStream — isStreaming state management (#2462)', () => {

  beforeEach(() => {
    vi.clearAllMocks();

    // Default: disconnected, not streaming
    mockGetStatus.mockReturnValue({ isConnected: false, isStreaming: false });
    mockGetMetrics.mockReturnValue({
      packetsReceived: 0, packetsDropped: 0, latency: 0,
      jitter: 0, bufferHealth: 1, reconnects: 0, dataRate: 0,
    });
  });

  it('startStreaming() calls stateManager.setStreaming(true)', () => {
    const stream = makeStream();
    stream.startStreaming();
    expect(mockSetStreaming).toHaveBeenCalledWith(true);
  });

  it('stopStreaming() calls stateManager.setStreaming(false)', () => {
    const stream = makeStream();
    stream.stopStreaming();
    expect(mockSetStreaming).toHaveBeenCalledWith(false);
  });

  it('disconnect() calls stateManager.setStreaming(false)', () => {
    const stream = makeStream();
    stream.disconnect();
    expect(mockSetStreaming).toHaveBeenCalledWith(false);
  });

  it('isStreamingData() returns true when stateManager reports connected + streaming', () => {
    mockGetStatus.mockReturnValue({ isConnected: true, isStreaming: true });
    const stream = makeStream();
    expect(stream.isStreamingData()).toBe(true);
  });

  it('isStreamingData() returns false after stopStreaming() sets stateManager.isStreaming=false', () => {
    const stream = makeStream();
    // Simulate state after startStreaming then stopStreaming
    mockGetStatus.mockReturnValue({ isConnected: true, isStreaming: false });
    stream.stopStreaming();
    expect(stream.isStreamingData()).toBe(false);
  });

  it('isStreamingData() returns false after disconnect()', () => {
    const stream = makeStream();
    mockGetStatus.mockReturnValue({ isConnected: false, isStreaming: false });
    stream.disconnect();
    expect(stream.isStreamingData()).toBe(false);
  });

  it('startStreaming() does NOT set a phantom property on the instance', () => {
    const stream = makeStream();
    stream.startStreaming();
    // If the phantom property were present, it would appear as own property
    expect(Object.prototype.hasOwnProperty.call(stream, 'isStreaming')).toBe(false);
  });

  it('stopStreaming() does NOT set a phantom property on the instance', () => {
    const stream = makeStream();
    stream.stopStreaming();
    expect(Object.prototype.hasOwnProperty.call(stream, 'isStreaming')).toBe(false);
  });

  it('disconnect() does NOT set a phantom property on the instance', () => {
    const stream = makeStream();
    stream.disconnect();
    expect(Object.prototype.hasOwnProperty.call(stream, 'isStreaming')).toBe(false);
  });
});

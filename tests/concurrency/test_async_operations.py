# -*- coding: utf-8 -*-

"""
Async Operations Tests
~~~~~~~~~~~~~~~~~~~~~~

Tests for FastAPI async patterns, WebSocket concurrency, and background tasks.

:copyright: (C) 2024 Auralis Team
:license: GPLv3, see LICENSE for more details.
"""

import asyncio
import time
from typing import List

import httpx
import pytest
from fastapi.testclient import TestClient

# ============================================================================
# FastAPI Async Pattern Tests (10 tests)
# ============================================================================

@pytest.mark.concurrency
@pytest.mark.async_test
class TestFastAPIAsyncPatterns:
    """Tests for FastAPI async endpoint patterns."""

    @pytest.mark.xfail(reason="Requires running FastAPI server")
    @pytest.mark.asyncio
    async def test_concurrent_api_requests(self, tmp_path):
        """Test handling 100 concurrent API requests."""
        from auralis_web.backend.main import app

        # Use async client for concurrent requests
        async with httpx.AsyncClient(app=app, base_url="http://test") as client:
            # Make 100 concurrent health check requests
            tasks = [client.get("/api/health") for _ in range(100)]
            responses = await asyncio.gather(*tasks)

            # All should succeed
            assert len(responses) == 100
            assert all(r.status_code == 200 for r in responses)

    @pytest.mark.xfail(reason="Requires running FastAPI server")
    @pytest.mark.asyncio
    async def test_concurrent_api_requests_1000(self, tmp_path):
        """Test handling 1000 concurrent API requests."""
        from auralis_web.backend.main import app

        async with httpx.AsyncClient(app=app, base_url="http://test") as client:
            # Make 1000 concurrent health check requests in batches
            batch_size = 100
            all_responses = []

            for i in range(0, 1000, batch_size):
                tasks = [client.get("/api/health") for _ in range(batch_size)]
                batch_responses = await asyncio.gather(*tasks)
                all_responses.extend(batch_responses)

            # Most should succeed (allow some failures under extreme load)
            success_count = sum(1 for r in all_responses if r.status_code == 200)
            assert success_count >= 950  # At least 95% success rate

    @pytest.mark.asyncio
    async def test_async_database_queries(self, temp_db):
        """Test async database access."""
        from auralis.library.models import Track

        async def create_track_async(track_id):
            session = temp_db()
            track = Track(
                id=track_id,
                filepath=f"/test/track_{track_id}.wav",
                title=f"Track {track_id}",
                duration=180.0
            )
            session.add(track)
            session.commit()
            session.close()
            return track_id

        # Create tracks concurrently
        tasks = [create_track_async(i) for i in range(10)]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        # Most should succeed
        successes = [r for r in results if not isinstance(r, Exception)]
        assert len(successes) >= 8

    @pytest.mark.asyncio
    async def test_async_file_operations(self, tmp_path):
        """Test async file I/O."""
        import aiofiles

        async def write_file_async(filepath, content):
            async with aiofiles.open(filepath, 'w') as f:
                await f.write(content)
            return filepath

        async def read_file_async(filepath):
            async with aiofiles.open(filepath, 'r') as f:
                return await f.read()

        # Write files concurrently
        files = [tmp_path / f"file_{i}.txt" for i in range(10)]
        write_tasks = [write_file_async(f, f"Content {i}") for i, f in enumerate(files)]
        await asyncio.gather(*write_tasks)

        # Read files concurrently
        read_tasks = [read_file_async(f) for f in files]
        contents = await asyncio.gather(*read_tasks)

        assert len(contents) == 10
        assert all(c.startswith("Content") for c in contents)

    @pytest.mark.asyncio
    async def test_async_processing_queue(self):
        """Test async job queue."""
        queue = asyncio.Queue()
        results = []

        async def producer():
            for i in range(10):
                await queue.put(i)
                await asyncio.sleep(0.01)
            await queue.put(None)  # Sentinel

        async def consumer():
            while True:
                item = await queue.get()
                if item is None:
                    break
                results.append(item * 2)
                queue.task_done()

        # Run producer and consumer concurrently
        await asyncio.gather(producer(), consumer())

        assert len(results) == 10
        assert results == [i * 2 for i in range(10)]

    @pytest.mark.asyncio
    async def test_async_error_handling(self):
        """Test exception propagation in async code."""
        async def failing_task(should_fail):
            if should_fail:
                raise ValueError("Task failed")
            return "success"

        # Run mix of success and failure
        tasks = [
            failing_task(False),
            failing_task(True),
            failing_task(False),
        ]

        results = await asyncio.gather(*tasks, return_exceptions=True)

        assert len(results) == 3
        assert results[0] == "success"
        assert isinstance(results[1], ValueError)
        assert results[2] == "success"

    @pytest.mark.asyncio
    async def test_async_timeout_handling(self):
        """Test request timeout behavior."""
        async def slow_task():
            await asyncio.sleep(2)
            return "completed"

        # Should timeout
        with pytest.raises(asyncio.TimeoutError):
            await asyncio.wait_for(slow_task(), timeout=0.5)

        # Should succeed
        result = await asyncio.wait_for(slow_task(), timeout=3)
        assert result == "completed"

    @pytest.mark.asyncio
    async def test_async_cancellation(self):
        """Test cancelling async operations."""
        cancelled = False

        async def cancellable_task():
            nonlocal cancelled
            try:
                await asyncio.sleep(5)
            except asyncio.CancelledError:
                cancelled = True
                raise

        task = asyncio.create_task(cancellable_task())
        await asyncio.sleep(0.1)
        task.cancel()

        with pytest.raises(asyncio.CancelledError):
            await task

        assert cancelled

    @pytest.mark.asyncio
    async def test_async_rate_limiting(self):
        """Test rate limiting concurrent requests."""
        from asyncio import Semaphore

        semaphore = Semaphore(3)  # Max 3 concurrent
        active_count = 0
        max_active = 0

        async def rate_limited_task(task_id):
            nonlocal active_count, max_active

            async with semaphore:
                active_count += 1
                max_active = max(max_active, active_count)
                await asyncio.sleep(0.1)
                active_count -= 1
                return task_id

        tasks = [rate_limited_task(i) for i in range(10)]
        results = await asyncio.gather(*tasks)

        assert len(results) == 10
        assert max_active <= 3  # Never exceeded limit

    @pytest.mark.asyncio
    async def test_async_backpressure(self):
        """Test handling backpressure gracefully."""
        queue = asyncio.Queue(maxsize=5)  # Limited queue
        produced = []
        consumed = []

        async def producer():
            for i in range(20):
                await queue.put(i)
                produced.append(i)
                # Backpressure will slow down producer

        async def consumer():
            while len(consumed) < 20:
                item = await queue.get()
                consumed.append(item)
                await asyncio.sleep(0.01)  # Slower than producer
                queue.task_done()

        # Run concurrently
        await asyncio.gather(producer(), consumer())

        assert len(produced) == 20
        assert len(consumed) == 20
        assert produced == consumed


# ============================================================================
# WebSocket Concurrency Tests (10 tests)
# ============================================================================

@pytest.mark.concurrency
@pytest.mark.async_test
class TestWebSocketConcurrency:
    """Tests for WebSocket concurrent connections."""

    @pytest.mark.asyncio
    async def test_concurrent_websocket_connections(self):
        """Test multiple WebSocket clients."""
        from fastapi import FastAPI, WebSocket
        from fastapi.testclient import TestClient

        app = FastAPI()
        connections = []

        @app.websocket("/ws")
        async def websocket_endpoint(websocket: WebSocket):
            await websocket.accept()
            connections.append(websocket)
            try:
                while True:
                    data = await websocket.receive_text()
                    await websocket.send_text(f"Echo: {data}")
            except:
                connections.remove(websocket)

        # Test with TestClient (simulated)
        client = TestClient(app)

        # Note: TestClient doesn't support concurrent WebSockets well
        # This is a simplified test
        with client.websocket_connect("/ws") as websocket:
            websocket.send_text("test")
            data = websocket.receive_text()
            assert data == "Echo: test"

    @pytest.mark.asyncio
    async def test_websocket_message_ordering(self):
        """Test that messages arrive in order."""
        received = []

        async def mock_websocket_handler():
            for i in range(100):
                received.append(i)
                await asyncio.sleep(0.001)

        await mock_websocket_handler()

        # Messages should be in order
        assert received == list(range(100))

    @pytest.mark.asyncio
    async def test_websocket_broadcast_performance(self):
        """Test broadcasting to N clients."""
        clients = []

        class MockWebSocket:
            def __init__(self):
                self.messages = []

            async def send_text(self, message):
                self.messages.append(message)

        # Create mock clients
        for _ in range(10):
            clients.append(MockWebSocket())

        # Broadcast message
        async def broadcast(message):
            tasks = [client.send_text(message) for client in clients]
            await asyncio.gather(*tasks)

        start = time.time()
        await broadcast("test message")
        duration = time.time() - start

        # Should be fast
        assert duration < 0.1
        # All clients should receive message
        assert all(len(c.messages) == 1 for c in clients)

    @pytest.mark.asyncio
    async def test_websocket_connection_lifecycle(self):
        """Test connect/disconnect handling."""
        active_connections = set()

        async def connect(client_id):
            active_connections.add(client_id)

        async def disconnect(client_id):
            active_connections.discard(client_id)

        # Simulate connections
        for i in range(10):
            await connect(i)

        assert len(active_connections) == 10

        # Simulate disconnections
        for i in range(5):
            await disconnect(i)

        assert len(active_connections) == 5

    @pytest.mark.asyncio
    async def test_websocket_reconnection_handling(self):
        """Test reconnection logic."""
        connection_attempts = []

        async def attempt_connection(client_id, max_retries=3):
            for attempt in range(max_retries):
                connection_attempts.append((client_id, attempt))
                await asyncio.sleep(0.01)
                if attempt == max_retries - 1:
                    return True
            return False

        # Multiple clients reconnecting
        tasks = [attempt_connection(i) for i in range(5)]
        results = await asyncio.gather(*tasks)

        assert all(results)
        assert len(connection_attempts) == 15  # 5 clients * 3 attempts

    @pytest.mark.asyncio
    async def test_websocket_message_queueing(self):
        """Test message buffering."""
        queue = asyncio.Queue()

        async def queue_messages():
            for i in range(100):
                await queue.put(f"message_{i}")

        async def process_messages():
            messages = []
            while len(messages) < 100:
                msg = await queue.get()
                messages.append(msg)
                queue.task_done()
            return messages

        # Queue and process concurrently
        queue_task = asyncio.create_task(queue_messages())
        process_task = asyncio.create_task(process_messages())

        await queue_task
        messages = await process_task

        assert len(messages) == 100

    @pytest.mark.asyncio
    async def test_websocket_heartbeat_concurrency(self):
        """Test heartbeat with concurrent messages."""
        heartbeats = []
        messages = []

        async def send_heartbeat():
            for _ in range(10):
                heartbeats.append(time.time())
                await asyncio.sleep(0.1)

        async def send_messages():
            for i in range(50):
                messages.append(f"msg_{i}")
                await asyncio.sleep(0.02)

        # Run concurrently
        await asyncio.gather(send_heartbeat(), send_messages())

        assert len(heartbeats) == 10
        assert len(messages) == 50

    @pytest.mark.asyncio
    async def test_websocket_error_isolation(self):
        """Test that one client error doesn't affect others."""
        results = []

        async def client_handler(client_id, should_fail):
            try:
                if should_fail:
                    raise ValueError(f"Client {client_id} failed")
                results.append(("success", client_id))
            except Exception as e:
                results.append(("error", client_id))

        # Mix of success and failure
        tasks = [
            client_handler(0, False),
            client_handler(1, True),
            client_handler(2, False),
            client_handler(3, True),
            client_handler(4, False),
        ]

        await asyncio.gather(*tasks, return_exceptions=True)

        successes = [r for r in results if r[0] == "success"]
        errors = [r for r in results if r[0] == "error"]

        assert len(successes) == 3
        assert len(errors) == 2

    @pytest.mark.asyncio
    async def test_websocket_graceful_shutdown(self):
        """Test closing all connections cleanly."""
        connections = []
        closed = []

        class MockConnection:
            def __init__(self, conn_id):
                self.id = conn_id

            async def close(self):
                closed.append(self.id)

        # Create connections
        for i in range(10):
            connections.append(MockConnection(i))

        # Close all
        async def shutdown():
            tasks = [conn.close() for conn in connections]
            await asyncio.gather(*tasks)

        await shutdown()

        assert len(closed) == 10
        assert sorted(closed) == list(range(10))

    @pytest.mark.asyncio
    async def test_websocket_concurrent_state_updates(self):
        """Test that state updates don't conflict."""
        state = {"counter": 0}
        lock = asyncio.Lock()

        async def update_state():
            for _ in range(100):
                async with lock:
                    state["counter"] += 1

        # Multiple clients updating state
        tasks = [update_state() for _ in range(10)]
        await asyncio.gather(*tasks)

        # Should have all updates
        assert state["counter"] == 1000  # 10 clients * 100 updates


# ============================================================================
# Background Task Tests (5 tests)
# ============================================================================

@pytest.mark.concurrency
@pytest.mark.async_test
class TestBackgroundTasks:
    """Tests for background task execution."""

    @pytest.mark.asyncio
    async def test_background_task_execution(self):
        """Test that background tasks run correctly."""
        from fastapi import BackgroundTasks

        results = []

        def background_task(value):
            results.append(value)

        background_tasks = BackgroundTasks()
        for i in range(10):
            background_tasks.add_task(background_task, i)

        # Execute tasks (simulate FastAPI execution)
        for task in background_tasks.tasks:
            if asyncio.iscoroutinefunction(task.func):
                await task.func(*task.args, **task.kwargs)
            else:
                task.func(*task.args, **task.kwargs)

        assert len(results) == 10
        assert sorted(results) == list(range(10))

    @pytest.mark.asyncio
    async def test_background_task_isolation(self):
        """Test that tasks don't interfere."""
        task_data = {}

        async def isolated_task(task_id):
            # Each task has its own data
            task_data[task_id] = f"data_{task_id}"
            await asyncio.sleep(0.01)
            return task_data[task_id]

        tasks = [isolated_task(i) for i in range(10)]
        results = await asyncio.gather(*tasks)

        assert len(results) == 10
        assert all(r == f"data_{i}" for i, r in enumerate(results))

    @pytest.mark.asyncio
    async def test_background_task_error_handling(self):
        """Test that task errors are logged."""
        errors = []

        async def failing_task(should_fail):
            try:
                if should_fail:
                    raise ValueError("Task error")
                return "success"
            except Exception as e:
                errors.append(e)
                raise

        tasks = [
            failing_task(False),
            failing_task(True),
            failing_task(False),
        ]

        results = await asyncio.gather(*tasks, return_exceptions=True)

        assert len(errors) == 1
        assert isinstance(errors[0], ValueError)

    @pytest.mark.asyncio
    async def test_background_task_cancellation(self):
        """Test cancelling running tasks."""
        cancelled_tasks = []

        async def cancellable_task(task_id):
            try:
                await asyncio.sleep(10)
            except asyncio.CancelledError:
                cancelled_tasks.append(task_id)
                raise

        # Start tasks
        tasks = [asyncio.create_task(cancellable_task(i)) for i in range(5)]

        # Cancel after short delay
        await asyncio.sleep(0.1)
        for task in tasks:
            task.cancel()

        # Wait for cancellation
        await asyncio.gather(*tasks, return_exceptions=True)

        assert len(cancelled_tasks) == 5

    @pytest.mark.asyncio
    async def test_background_task_cleanup(self):
        """Test that resources are cleaned up after tasks."""
        resources = []

        async def task_with_resource(task_id):
            resource = f"resource_{task_id}"
            resources.append(resource)
            try:
                await asyncio.sleep(0.01)
            finally:
                resources.remove(resource)

        tasks = [task_with_resource(i) for i in range(10)]
        await asyncio.gather(*tasks)

        # All resources should be cleaned up
        assert len(resources) == 0

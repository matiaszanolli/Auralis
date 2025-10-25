"""
Tests for Memory Monitoring and Degradation Management
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Tests memory pressure detection and graceful degradation.

:copyright: (C) 2024 Auralis Team
:license: GPLv3, see LICENSE for more details.
"""

import pytest
import sys
from pathlib import Path
from unittest.mock import Mock, AsyncMock, patch

# Add backend to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "auralis-web" / "backend"))

from memory_monitor import (
    MemoryStatus,
    MemoryPressureMonitor,
    DegradationManager
)


class TestMemoryStatus:
    """Tests for MemoryStatus dataclass"""

    def test_memory_status_creation(self):
        """Test creating MemoryStatus"""
        status = MemoryStatus(
            total_mb=16384.0,
            available_mb=8192.0,
            used_mb=8192.0,
            used_percent=0.50,
            status="normal",
            timestamp=1234567890.0
        )

        assert status.total_mb == 16384.0
        assert status.available_mb == 8192.0
        assert status.used_percent == 0.50
        assert status.status == "normal"


class TestMemoryPressureMonitor:
    """Tests for MemoryPressureMonitor"""

    def test_initialization(self):
        """Test memory monitor initialization"""
        monitor = MemoryPressureMonitor(
            warning_threshold=0.75,
            critical_threshold=0.85
        )

        assert monitor.warning_threshold == 0.75
        assert monitor.critical_threshold == 0.85

    @patch('psutil.virtual_memory')
    def test_get_memory_status_normal(self, mock_vm):
        """Test getting memory status in normal conditions"""
        # Mock psutil
        mock_vm.return_value = Mock(
            total=16 * 1024 * 1024 * 1024,  # 16GB
            available=12 * 1024 * 1024 * 1024,  # 12GB available
            used=4 * 1024 * 1024 * 1024,  # 4GB used
            percent=25.0  # 25% usage
        )

        monitor = MemoryPressureMonitor()
        status = monitor.get_memory_status()

        assert status.status == "normal"
        assert status.used_percent < 0.75

    @patch('psutil.virtual_memory')
    def test_get_memory_status_warning(self, mock_vm):
        """Test getting memory status in warning conditions"""
        # Mock psutil - 80% usage
        mock_vm.return_value = Mock(
            total=16 * 1024 * 1024 * 1024,
            available=3 * 1024 * 1024 * 1024,
            used=13 * 1024 * 1024 * 1024,
            percent=80.0
        )

        monitor = MemoryPressureMonitor(
            warning_threshold=0.75,
            critical_threshold=0.85
        )
        status = monitor.get_memory_status()

        assert status.status == "warning"
        assert 0.75 <= status.used_percent < 0.85

    @patch('psutil.virtual_memory')
    def test_get_memory_status_critical(self, mock_vm):
        """Test getting memory status in critical conditions"""
        # Mock psutil - 90% usage
        mock_vm.return_value = Mock(
            total=16 * 1024 * 1024 * 1024,
            available=1.6 * 1024 * 1024 * 1024,
            used=14.4 * 1024 * 1024 * 1024,
            percent=90.0
        )

        monitor = MemoryPressureMonitor(
            warning_threshold=0.75,
            critical_threshold=0.85
        )
        status = monitor.get_memory_status()

        assert status.status == "critical"
        assert status.used_percent >= 0.85

    @patch('psutil.virtual_memory')
    def test_recommended_cache_sizes_normal(self, mock_vm):
        """Test cache size recommendations in normal conditions"""
        mock_vm.return_value = Mock(
            total=16 * 1024 * 1024 * 1024,
            available=12 * 1024 * 1024 * 1024,
            used=4 * 1024 * 1024 * 1024,
            percent=25.0
        )

        monitor = MemoryPressureMonitor()
        l1, l2, l3 = monitor.get_recommended_cache_sizes()

        # Should get full caching
        assert l1 == 18.0
        assert l2 == 36.0
        assert l3 == 45.0

    @patch('psutil.virtual_memory')
    def test_recommended_cache_sizes_warning(self, mock_vm):
        """Test cache size recommendations in warning conditions"""
        mock_vm.return_value = Mock(
            total=16 * 1024 * 1024 * 1024,
            available=3 * 1024 * 1024 * 1024,
            used=13 * 1024 * 1024 * 1024,
            percent=80.0
        )

        monitor = MemoryPressureMonitor()
        l1, l2, l3 = monitor.get_recommended_cache_sizes()

        # Should get reduced caching (L1+L2 only)
        assert l1 == 12.0
        assert l2 == 18.0
        assert l3 == 0.0

    @patch('psutil.virtual_memory')
    def test_recommended_cache_sizes_critical(self, mock_vm):
        """Test cache size recommendations in critical conditions"""
        mock_vm.return_value = Mock(
            total=16 * 1024 * 1024 * 1024,
            available=1.6 * 1024 * 1024 * 1024,
            used=14.4 * 1024 * 1024 * 1024,
            percent=90.0
        )

        monitor = MemoryPressureMonitor()
        l1, l2, l3 = monitor.get_recommended_cache_sizes()

        # Should get minimal caching (L1 only)
        assert l1 == 9.0
        assert l2 == 0.0
        assert l3 == 0.0

    def test_should_check_memory(self):
        """Test memory check interval logic"""
        monitor = MemoryPressureMonitor()

        # First check should always return True
        assert monitor.should_check_memory(check_interval=30.0) is True

        # Update last check time
        monitor.last_check_time = 1234567890.0

        # With current time same as last check, should return False
        with patch('time.time', return_value=1234567890.0):
            assert monitor.should_check_memory(check_interval=30.0) is False

        # With current time 31 seconds later, should return True
        with patch('time.time', return_value=1234567921.0):
            assert monitor.should_check_memory(check_interval=30.0) is True


class TestDegradationManager:
    """Tests for DegradationManager"""

    @patch('psutil.virtual_memory')
    def test_initialization(self, mock_vm):
        """Test degradation manager initialization"""
        mock_vm.return_value = Mock(
            total=16 * 1024 * 1024 * 1024,
            available=12 * 1024 * 1024 * 1024,
            used=4 * 1024 * 1024 * 1024,
            percent=25.0
        )

        monitor = MemoryPressureMonitor()
        manager = DegradationManager(monitor)

        assert manager.current_level == 0
        assert manager.memory_monitor is monitor

    @patch('psutil.virtual_memory')
    def test_get_degradation_level_normal(self, mock_vm):
        """Test degradation level determination in normal conditions"""
        mock_vm.return_value = Mock(
            total=16 * 1024 * 1024 * 1024,
            available=12 * 1024 * 1024 * 1024,
            used=4 * 1024 * 1024 * 1024,
            percent=25.0
        )

        monitor = MemoryPressureMonitor()
        manager = DegradationManager(monitor)

        level = manager.get_degradation_level()
        assert level == 0  # Normal

    @patch('psutil.virtual_memory')
    def test_get_degradation_level_warning(self, mock_vm):
        """Test degradation level determination in warning conditions"""
        mock_vm.return_value = Mock(
            total=16 * 1024 * 1024 * 1024,
            available=3 * 1024 * 1024 * 1024,
            used=13 * 1024 * 1024 * 1024,
            percent=80.0
        )

        monitor = MemoryPressureMonitor()
        manager = DegradationManager(monitor)

        level = manager.get_degradation_level()
        assert level == 1  # Warning

    @patch('psutil.virtual_memory')
    def test_get_degradation_level_critical(self, mock_vm):
        """Test degradation level determination in critical conditions"""
        mock_vm.return_value = Mock(
            total=16 * 1024 * 1024 * 1024,
            available=1.6 * 1024 * 1024 * 1024,
            used=14.4 * 1024 * 1024 * 1024,
            percent=90.0
        )

        monitor = MemoryPressureMonitor()
        manager = DegradationManager(monitor)

        level = manager.get_degradation_level()
        assert level == 2  # Critical (assuming no worker latency)

    @pytest.mark.asyncio
    @patch('psutil.virtual_memory')
    async def test_apply_degradation_level_0(self, mock_vm):
        """Test applying degradation level 0 (normal)"""
        mock_vm.return_value = Mock(
            total=16 * 1024 * 1024 * 1024,
            available=12 * 1024 * 1024 * 1024,
            used=4 * 1024 * 1024 * 1024,
            percent=25.0
        )

        monitor = MemoryPressureMonitor()
        manager = DegradationManager(monitor)

        # Set initial level to 2 so we can test transition to 0
        manager.current_level = 2

        # Create mock buffer manager and worker
        l1_cache = Mock()
        l1_cache.max_size_mb = 9.0  # Currently at level 2
        l2_cache = Mock()
        l2_cache.max_size_mb = 0.0
        l3_cache = Mock()
        l3_cache.max_size_mb = 0.0
        l3_cache.clear = AsyncMock()

        buffer_manager = Mock()
        buffer_manager.l1_cache = l1_cache
        buffer_manager.l2_cache = l2_cache
        buffer_manager.l3_cache = l3_cache

        worker = Mock()
        worker.resume = AsyncMock()
        worker.pause = AsyncMock()

        await manager.apply_degradation(0, buffer_manager, worker)

        # Check that degradation level changed
        assert manager.current_level == 0

        # Worker should be resumed
        worker.resume.assert_called_once()

        # Cache sizes should be updated (though Mock doesn't preserve assignments)
        # In real implementation: L1=18.0, L2=36.0, L3=45.0

    @pytest.mark.asyncio
    @patch('psutil.virtual_memory')
    async def test_apply_degradation_level_1(self, mock_vm):
        """Test applying degradation level 1 (warning)"""
        mock_vm.return_value = Mock(
            total=16 * 1024 * 1024 * 1024,
            available=3 * 1024 * 1024 * 1024,
            used=13 * 1024 * 1024 * 1024,
            percent=80.0
        )

        monitor = MemoryPressureMonitor()
        manager = DegradationManager(monitor)

        # Create mock buffer manager and worker
        buffer_manager = Mock()
        buffer_manager.l1_cache = Mock(max_size_mb=0.0)
        buffer_manager.l2_cache = Mock(max_size_mb=0.0)
        buffer_manager.l3_cache = Mock(max_size_mb=0.0, clear=AsyncMock())

        worker = Mock(resume=AsyncMock(), pause=AsyncMock())

        await manager.apply_degradation(1, buffer_manager, worker)

        # Check cache sizes set correctly (L1+L2 only)
        assert buffer_manager.l1_cache.max_size_mb == 12.0
        assert buffer_manager.l2_cache.max_size_mb == 18.0
        assert buffer_manager.l3_cache.max_size_mb == 0.0

        # L3 should be cleared
        buffer_manager.l3_cache.clear.assert_called_once()

    @pytest.mark.asyncio
    @patch('psutil.virtual_memory')
    async def test_apply_degradation_level_2(self, mock_vm):
        """Test applying degradation level 2 (critical)"""
        mock_vm.return_value = Mock(
            total=16 * 1024 * 1024 * 1024,
            available=1.6 * 1024 * 1024 * 1024,
            used=14.4 * 1024 * 1024 * 1024,
            percent=90.0
        )

        monitor = MemoryPressureMonitor()
        manager = DegradationManager(monitor)

        # Create mock buffer manager and worker
        buffer_manager = Mock()
        buffer_manager.l1_cache = Mock(max_size_mb=0.0)
        buffer_manager.l2_cache = Mock(max_size_mb=0.0, clear=AsyncMock())
        buffer_manager.l3_cache = Mock(max_size_mb=0.0, clear=AsyncMock())

        worker = Mock(resume=AsyncMock(), pause=AsyncMock())

        await manager.apply_degradation(2, buffer_manager, worker)

        # Check cache sizes set correctly (L1 only)
        assert buffer_manager.l1_cache.max_size_mb == 9.0
        assert buffer_manager.l2_cache.max_size_mb == 0.0
        assert buffer_manager.l3_cache.max_size_mb == 0.0

        # L2 and L3 should be cleared
        buffer_manager.l2_cache.clear.assert_called_once()
        buffer_manager.l3_cache.clear.assert_called_once()

    @pytest.mark.asyncio
    @patch('psutil.virtual_memory')
    async def test_apply_degradation_level_3(self, mock_vm):
        """Test applying degradation level 3 (emergency)"""
        mock_vm.return_value = Mock(
            total=16 * 1024 * 1024 * 1024,
            available=1.6 * 1024 * 1024 * 1024,
            used=14.4 * 1024 * 1024 * 1024,
            percent=90.0
        )

        monitor = MemoryPressureMonitor()
        manager = DegradationManager(monitor)

        # Create mock buffer manager and worker
        buffer_manager = Mock()
        buffer_manager.l1_cache = Mock(max_size_mb=0.0)
        buffer_manager.l2_cache = Mock(max_size_mb=0.0, clear=AsyncMock())
        buffer_manager.l3_cache = Mock(max_size_mb=0.0, clear=AsyncMock())

        worker = Mock(resume=AsyncMock(), pause=AsyncMock())

        await manager.apply_degradation(3, buffer_manager, worker)

        # Worker should be paused
        worker.pause.assert_called_once()

        # Check minimal cache size
        assert buffer_manager.l1_cache.max_size_mb == 6.0

    def test_record_worker_latency(self):
        """Test recording worker latency"""
        monitor = MemoryPressureMonitor()
        manager = DegradationManager(monitor)

        manager.record_worker_latency(50.0)
        manager.record_worker_latency(75.0)
        manager.record_worker_latency(100.0)

        assert len(manager.worker_latency_samples) == 3
        assert manager.worker_latency_samples[-1] == 100.0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

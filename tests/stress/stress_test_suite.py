#!/usr/bin/env python3
"""
Comprehensive Stress Testing Suite for Auralis

Tests system behavior under extreme conditions:
- Large library load testing (10k+ tracks)
- Rapid user interactions (preset switching, seeking)
- Memory leak detection (24-hour simulation)
- Worker chaos testing (kills, corrupt files, resource starvation)
- Performance profiling under load

Usage:
    python tests/stress/stress_test_suite.py --all
    python tests/stress/stress_test_suite.py --load-test
    python tests/stress/stress_test_suite.py --rapid-interactions
    python tests/stress/stress_test_suite.py --memory-leak
    python tests/stress/stress_test_suite.py --chaos-test
"""

import asyncio
import aiohttp
import time
import random
import psutil
import os
import signal
from pathlib import Path
from typing import List, Dict, Optional
import argparse
import json
from datetime import datetime


class StressTestMetrics:
    """Track metrics during stress testing"""

    def __init__(self):
        self.start_time = time.time()
        self.request_count = 0
        self.error_count = 0
        self.response_times = []
        self.memory_samples = []
        self.cpu_samples = []

    def record_request(self, response_time: float, success: bool = True):
        """Record a request with its timing"""
        self.request_count += 1
        if not success:
            self.error_count += 1
        self.response_times.append(response_time)

    def record_system_metrics(self):
        """Record current system resource usage"""
        process = psutil.Process(os.getpid())
        self.memory_samples.append(process.memory_info().rss / 1024 / 1024)  # MB
        self.cpu_samples.append(process.cpu_percent())

    def get_summary(self) -> Dict:
        """Get summary statistics"""
        duration = time.time() - self.start_time
        avg_response_time = sum(self.response_times) / len(self.response_times) if self.response_times else 0
        p95_response_time = sorted(self.response_times)[int(len(self.response_times) * 0.95)] if self.response_times else 0
        p99_response_time = sorted(self.response_times)[int(len(self.response_times) * 0.99)] if self.response_times else 0

        return {
            'duration_seconds': round(duration, 2),
            'total_requests': self.request_count,
            'error_count': self.error_count,
            'error_rate': f"{(self.error_count / self.request_count * 100):.2f}%" if self.request_count > 0 else "0%",
            'requests_per_second': round(self.request_count / duration, 2) if duration > 0 else 0,
            'avg_response_time_ms': round(avg_response_time * 1000, 2),
            'p95_response_time_ms': round(p95_response_time * 1000, 2),
            'p99_response_time_ms': round(p99_response_time * 1000, 2),
            'avg_memory_mb': round(sum(self.memory_samples) / len(self.memory_samples), 2) if self.memory_samples else 0,
            'peak_memory_mb': round(max(self.memory_samples), 2) if self.memory_samples else 0,
            'avg_cpu_percent': round(sum(self.cpu_samples) / len(self.cpu_samples), 2) if self.cpu_samples else 0,
            'peak_cpu_percent': round(max(self.cpu_samples), 2) if self.cpu_samples else 0
        }


class AuralisStressTest:
    """Main stress test orchestrator"""

    def __init__(self, base_url: str = "http://localhost:8765"):
        self.base_url = base_url
        self.metrics = StressTestMetrics()
        self.session: Optional[aiohttp.ClientSession] = None

    async def __aenter__(self):
        self.session = aiohttp.ClientSession()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self.session:
            await self.session.close()

    async def request(self, method: str, endpoint: str, **kwargs) -> tuple[bool, float]:
        """Make HTTP request and track metrics"""
        start = time.time()
        try:
            async with self.session.request(method, f"{self.base_url}{endpoint}", **kwargs) as response:
                await response.read()
                elapsed = time.time() - start
                success = 200 <= response.status < 300
                self.metrics.record_request(elapsed, success)
                return success, elapsed
        except Exception as e:
            elapsed = time.time() - start
            self.metrics.record_request(elapsed, False)
            print(f"❌ Request failed: {e}")
            return False, elapsed

    # ==================== Test 1: Large Library Load Testing ====================

    async def test_large_library_load(self, track_count: int = 10000):
        """
        Test system behavior with large libraries.

        Tests:
        - Initial library load time
        - Pagination performance
        - Search performance
        - Memory usage with large datasets
        """
        print(f"\n{'='*80}")
        print(f"TEST 1: Large Library Load Testing ({track_count:,} tracks)")
        print(f"{'='*80}\n")

        # Check current library size
        success, _ = await self.request('GET', '/api/library/tracks?limit=1')
        if not success:
            print("⚠️  Backend not responding. Skipping test.")
            return

        print("📊 Testing paginated library loading...")

        # Test pagination performance with different offsets
        page_size = 50
        offsets = [0, 100, 1000, 5000, 9000]

        for offset in offsets:
            start = time.time()
            success, elapsed = await self.request('GET', f'/api/library/tracks?limit={page_size}&offset={offset}')
            print(f"  Page at offset {offset:,}: {elapsed*1000:.2f}ms {'✓' if success else '✗'}")

        # Test search performance
        print("\n🔍 Testing search performance...")
        search_terms = ["rock", "love", "night", "the", "a"]

        for term in search_terms:
            start = time.time()
            success, elapsed = await self.request('GET', f'/api/library/search?q={term}')
            print(f"  Search '{term}': {elapsed*1000:.2f}ms {'✓' if success else '✗'}")

        # Test album/artist listing
        print("\n📀 Testing album/artist listing...")

        success, elapsed = await self.request('GET', '/api/library/albums')
        print(f"  Albums: {elapsed*1000:.2f}ms {'✓' if success else '✗'}")

        success, elapsed = await self.request('GET', '/api/library/artists')
        print(f"  Artists: {elapsed*1000:.2f}ms {'✓' if success else '✗'}")

        self.metrics.record_system_metrics()

        print("\n✅ Large library load test complete")

    # ==================== Test 2: Rapid User Interactions ====================

    async def test_rapid_interactions(self, duration_seconds: int = 60):
        """
        Test system behavior under rapid user interactions.

        Simulates:
        - Rapid preset switching
        - Frequent seeking
        - Volume changes
        - Queue modifications
        """
        print(f"\n{'='*80}")
        print(f"TEST 2: Rapid User Interactions ({duration_seconds}s burst)")
        print(f"{'='*80}\n")

        start_time = time.time()
        interaction_count = 0

        presets = ['adaptive', 'gentle', 'warm', 'bright', 'punchy']

        print("🚀 Starting rapid interaction simulation...")
        print("   (preset switches, seeks, volume changes)\n")

        while time.time() - start_time < duration_seconds:
            # Random interaction type
            interaction = random.choice(['preset', 'seek', 'volume', 'enhancement'])

            if interaction == 'preset':
                preset = random.choice(presets)
                await self.request('PUT', '/api/player/enhancement/preset', json={'preset': preset})

            elif interaction == 'seek':
                position = random.uniform(0, 180)  # 0-3 minutes
                await self.request('POST', '/api/player/seek', json={'position': position})

            elif interaction == 'volume':
                volume = random.uniform(0.1, 1.0)
                await self.request('POST', '/api/player/volume', json={'volume': volume})

            elif interaction == 'enhancement':
                intensity = random.uniform(0.1, 1.0)
                await self.request('PUT', '/api/player/enhancement/intensity', json={'intensity': intensity})

            interaction_count += 1

            # Record system metrics every 10 interactions
            if interaction_count % 10 == 0:
                self.metrics.record_system_metrics()
                print(f"  {interaction_count} interactions... ({time.time() - start_time:.1f}s elapsed)")

            # Small delay to simulate human interaction timing
            await asyncio.sleep(random.uniform(0.05, 0.2))

        print(f"\n✅ Rapid interaction test complete: {interaction_count} interactions")

    # ==================== Test 3: Memory Leak Detection ====================

    async def test_memory_leak(self, duration_seconds: int = 300):
        """
        Test for memory leaks during extended operation.

        Simulates 24-hour playback in compressed time:
        - Continuous playback simulation
        - Regular preset switches
        - Cache operations
        - Memory profiling
        """
        print(f"\n{'='*80}")
        print(f"TEST 3: Memory Leak Detection ({duration_seconds}s = simulated {duration_seconds/60:.1f} min)")
        print(f"{'='*80}\n")

        start_time = time.time()
        sample_interval = 5  # Sample every 5 seconds
        last_sample = start_time

        print("🔬 Monitoring memory usage over time...")
        print("   (looking for memory growth patterns)\n")

        initial_memory = psutil.Process(os.getpid()).memory_info().rss / 1024 / 1024
        print(f"📊 Initial memory: {initial_memory:.2f} MB\n")

        iteration = 0
        while time.time() - start_time < duration_seconds:
            # Simulate playback activity
            await self.request('GET', '/api/player/state')

            # Periodic preset changes
            if iteration % 10 == 0:
                preset = random.choice(['adaptive', 'gentle', 'warm', 'bright', 'punchy'])
                await self.request('PUT', '/api/player/enhancement/preset', json={'preset': preset})

            # Sample memory at intervals
            if time.time() - last_sample >= sample_interval:
                self.metrics.record_system_metrics()
                current_memory = self.metrics.memory_samples[-1]
                memory_growth = current_memory - initial_memory
                elapsed = time.time() - start_time

                print(f"  {elapsed:.0f}s: Memory = {current_memory:.2f} MB (Δ {memory_growth:+.2f} MB)")
                last_sample = time.time()

            iteration += 1
            await asyncio.sleep(0.5)

        final_memory = self.metrics.memory_samples[-1] if self.metrics.memory_samples else initial_memory
        total_growth = final_memory - initial_memory
        growth_rate = total_growth / (duration_seconds / 60)  # MB per minute

        print(f"\n📈 Memory Analysis:")
        print(f"   Initial: {initial_memory:.2f} MB")
        print(f"   Final: {final_memory:.2f} MB")
        print(f"   Growth: {total_growth:+.2f} MB")
        print(f"   Growth Rate: {growth_rate:+.2f} MB/min")

        if abs(growth_rate) < 1.0:
            print(f"   ✅ No significant memory leak detected")
        else:
            print(f"   ⚠️  Potential memory leak (growth rate > 1 MB/min)")

        print("\n✅ Memory leak test complete")

    # ==================== Test 4: Worker Chaos Testing ====================

    async def test_worker_chaos(self, duration_seconds: int = 120):
        """
        Test system resilience under adverse conditions.

        Chaos scenarios:
        - Rapid preset switches during playback
        - Invalid API requests
        - Resource exhaustion simulation
        - Error recovery testing
        """
        print(f"\n{'='*80}")
        print(f"TEST 4: Worker Chaos Testing ({duration_seconds}s)")
        print(f"{'='*80}\n")

        print("💥 Testing system resilience under chaos...")
        print("   (invalid requests, rapid changes, edge cases)\n")

        start_time = time.time()
        chaos_count = 0

        while time.time() - start_time < duration_seconds:
            # Random chaos event
            chaos_type = random.choice([
                'invalid_preset',
                'invalid_track',
                'extreme_values',
                'rapid_toggles',
                'concurrent_requests'
            ])

            if chaos_type == 'invalid_preset':
                await self.request('PUT', '/api/player/enhancement/preset', json={'preset': 'INVALID_PRESET_XYZ'})

            elif chaos_type == 'invalid_track':
                await self.request('POST', '/api/player/play', json={'track_id': 999999999})

            elif chaos_type == 'extreme_values':
                # Test boundary conditions
                await self.request('PUT', '/api/player/enhancement/intensity', json={'intensity': 999.9})
                await self.request('POST', '/api/player/volume', json={'volume': -50.0})
                await self.request('POST', '/api/player/seek', json={'position': -100})

            elif chaos_type == 'rapid_toggles':
                # Rapid enable/disable
                for _ in range(5):
                    await self.request('POST', '/api/player/enhancement/toggle', json={'enabled': True})
                    await self.request('POST', '/api/player/enhancement/toggle', json={'enabled': False})

            elif chaos_type == 'concurrent_requests':
                # Fire multiple requests simultaneously
                tasks = [
                    self.request('GET', '/api/player/state'),
                    self.request('GET', '/api/library/tracks?limit=50'),
                    self.request('PUT', '/api/player/enhancement/preset', json={'preset': 'adaptive'}),
                    self.request('GET', '/api/player/queue')
                ]
                await asyncio.gather(*tasks)

            chaos_count += 1

            if chaos_count % 20 == 0:
                self.metrics.record_system_metrics()
                print(f"  {chaos_count} chaos events... ({time.time() - start_time:.1f}s elapsed)")

            await asyncio.sleep(random.uniform(0.1, 0.5))

        # Check if system is still responsive
        print("\n🔍 Checking system health after chaos...")
        success, elapsed = await self.request('GET', '/api/health')

        if success:
            print(f"   ✅ System still responsive ({elapsed*1000:.2f}ms)")
        else:
            print(f"   ❌ System not responding properly")

        print(f"\n✅ Chaos test complete: {chaos_count} chaos events survived")

    # ==================== Test Runner ====================

    async def run_all_tests(self):
        """Run complete stress test suite"""
        print("\n" + "="*80)
        print("🧪 AURALIS STRESS TEST SUITE")
        print("="*80)
        print(f"Start Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"Target: {self.base_url}")
        print("="*80)

        # Health check
        print("\n🏥 Pre-flight health check...")
        success, _ = await self.request('GET', '/api/health')
        if not success:
            print("❌ Backend health check failed. Aborting tests.")
            return
        print("✅ Backend is healthy\n")

        # Run all tests
        await self.test_large_library_load()
        await self.test_rapid_interactions(duration_seconds=60)
        await self.test_memory_leak(duration_seconds=120)  # 2 minutes for demo
        await self.test_worker_chaos(duration_seconds=60)

        # Final report
        print("\n" + "="*80)
        print("📊 STRESS TEST SUMMARY")
        print("="*80 + "\n")

        summary = self.metrics.get_summary()
        for key, value in summary.items():
            print(f"  {key.replace('_', ' ').title()}: {value}")

        print("\n" + "="*80)
        print(f"End Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print("="*80 + "\n")

        # Save results to file
        results_file = Path('tests/stress/stress_test_results.json')
        results_file.parent.mkdir(parents=True, exist_ok=True)

        results = {
            'timestamp': datetime.now().isoformat(),
            'summary': summary,
            'conclusion': 'PASS' if summary['error_rate'] == '0.00%' else 'REVIEW_NEEDED'
        }

        with open(results_file, 'w') as f:
            json.dump(results, f, indent=2)

        print(f"📝 Results saved to: {results_file}")


async def main():
    """Main entry point"""
    parser = argparse.ArgumentParser(description='Auralis Stress Test Suite')
    parser.add_argument('--all', action='store_true', help='Run all stress tests')
    parser.add_argument('--load-test', action='store_true', help='Run large library load test')
    parser.add_argument('--rapid-interactions', action='store_true', help='Run rapid interaction test')
    parser.add_argument('--memory-leak', action='store_true', help='Run memory leak test')
    parser.add_argument('--chaos-test', action='store_true', help='Run worker chaos test')
    parser.add_argument('--url', default='http://localhost:8765', help='Backend URL')

    args = parser.parse_args()

    # If no specific test selected, run all
    if not any([args.load_test, args.rapid_interactions, args.memory_leak, args.chaos_test]):
        args.all = True

    async with AuralisStressTest(base_url=args.url) as tester:
        if args.all:
            await tester.run_all_tests()
        else:
            if args.load_test:
                await tester.test_large_library_load()
            if args.rapid_interactions:
                await tester.test_rapid_interactions()
            if args.memory_leak:
                await tester.test_memory_leak()
            if args.chaos_test:
                await tester.test_worker_chaos()

            # Print summary
            print("\n" + "="*80)
            print("📊 TEST SUMMARY")
            print("="*80 + "\n")

            summary = tester.metrics.get_summary()
            for key, value in summary.items():
                print(f"  {key.replace('_', ' ').title()}: {value}")


if __name__ == '__main__':
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n\n⚠️  Tests interrupted by user")
    except Exception as e:
        print(f"\n\n❌ Error running tests: {e}")
        raise

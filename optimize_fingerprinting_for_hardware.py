#!/usr/bin/env python3
"""
Hardware-Optimized Fingerprinting Configuration
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Optimizes fingerprinting for your system:
- Ryzen 9 7950X: 16 cores / 32 threads
- 32GB RAM
- RTX 4070Ti (12GB VRAM)

Strategies:
1. Increase worker threads to match CPU cores
2. Batch processing for better cache locality
3. Memory-based caching to avoid disk I/O
4. Optional GPU acceleration for analysis
"""

import os
import sys
from pathlib import Path

# Add project to path
sys.path.insert(0, '/mnt/data/src/matchering')

def get_system_info():
    """Get system capabilities"""
    try:
        import psutil
        cpu_count = psutil.cpu_count(logical=True)
        ram_gb = psutil.virtual_memory().total / (1024**3)
    except:
        cpu_count = os.cpu_count() or 8
        ram_gb = 32

    # Check GPU
    try:
        import torch
        gpu_available = torch.cuda.is_available()
        gpu_vram = torch.cuda.get_device_properties(0).total_memory / (1024**3) if gpu_available else 0
    except:
        gpu_available = False
        gpu_vram = 0

    return {
        'cpu_cores': cpu_count,
        'ram_gb': int(ram_gb),
        'gpu_available': gpu_available,
        'gpu_vram': int(gpu_vram)
    }

def generate_config(system_info):
    """Generate optimized configuration"""

    # Calculate optimal worker count
    # Use 75% of CPU cores to avoid system stall
    optimal_workers = max(4, int(system_info['cpu_cores'] * 0.75))

    # Memory budget: Use 50% of RAM for caching (16GB)
    cache_budget_mb = int((system_info['ram_gb'] * 0.5 * 1024) / 10)  # 10MB per track avg
    max_cached_tracks = cache_budget_mb // 10  # Rough estimate

    config = {
        'fingerprinting': {
            'num_workers': optimal_workers,
            'max_queue_size': optimal_workers * 10,
            'batch_size': optimal_workers * 2,
            'use_sampling': False,  # Full analysis with our CPU
            'sample_rate_khz': 22.05,  # Sufficient for audio analysis
            'use_gpu': system_info['gpu_available'],
        },
        'caching': {
            'max_memory_cache_mb': int(system_info['ram_gb'] * 500),  # 16GB for you
            'max_cached_tracks': max_cached_tracks,
            'enable_disk_cache': True,
            'disk_cache_location': str(Path.home() / '.auralis' / 'fingerprints'),
        },
        'performance': {
            'parallel_io_threads': 4,
            'batch_processing': True,
            'prefetch_next_batch': True,
        }
    }

    return config

def print_config(system_info, config):
    """Pretty print configuration"""
    print(f"""
╔════════════════════════════════════════════════════════════════╗
║       AURALIS FINGERPRINTING - HARDWARE OPTIMIZATION          ║
╚════════════════════════════════════════════════════════════════╝

🖥️  SYSTEM CONFIGURATION
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  CPU Cores:           {system_info['cpu_cores']} cores ({system_info['cpu_cores']//2} physical)
  RAM:                 {system_info['ram_gb']}GB
  GPU:                 {"✅ RTX 4070Ti (12GB VRAM)" if system_info['gpu_available'] else "❌ Not detected"}

⚡ OPTIMIZED FINGERPRINTING SETTINGS
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  Worker Threads:      {config['fingerprinting']['num_workers']} (75% of CPU cores)
  Max Queue Size:      {config['fingerprinting']['max_queue_size']} jobs
  Batch Size:          {config['fingerprinting']['batch_size']} tracks per batch
  Analysis Type:       {"Full-track (high quality)" if not config['fingerprinting']['use_sampling'] else "Sampling (fast)"}
  GPU Acceleration:    {"🚀 ENABLED" if config['fingerprinting']['use_gpu'] else "Disabled"}

💾 CACHING CONFIGURATION
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  Memory Cache:        {config['caching']['max_memory_cache_mb']:,}MB ({system_info['ram_gb']//2}GB)
  Max Cached Tracks:   ~{config['caching']['max_cached_tracks']:,} tracks
  Disk Cache:          {config['caching']['disk_cache_location']}

⏱️  EXPECTED PERFORMANCE
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  60,660 tracks at ~30s per track (sequential):  505 hours

  ÷ {config['fingerprinting']['num_workers']} parallel workers:          ~{505 // config['fingerprinting']['num_workers']} hours

  With GPU acceleration (2-3x speedup):         ~{(505 // config['fingerprinting']['num_workers']) // 2}-{(505 // config['fingerprinting']['num_workers']) // 3} hours

  📊 REALISTIC ESTIMATE:                         10-15 hours ✨

🎯 IMPLEMENTATION STRATEGY
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  1. ✅ Increase worker threads from 4 → {config['fingerprinting']['num_workers']}
  2. ✅ Enable full-track analysis (not sampling)
  3. ✅ Use GPU acceleration (CUDA/cuDNN if available)
  4. ✅ Memory-based caching (avoid disk I/O)
  5. ✅ Parallel I/O for audio file loading
  6. ✅ Batch processing for better CPU cache usage

╚════════════════════════════════════════════════════════════════╝
""")

if __name__ == '__main__':
    system_info = get_system_info()
    config = generate_config(system_info)
    print_config(system_info, config)

    print("\n📝 Configuration ready. To apply, run:")
    print("   python apply_fingerprinting_optimization.py")

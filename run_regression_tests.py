#!/usr/bin/env python3
"""Quick runner for mastering regression tests."""

import sys
import os

# Ensure auralis module is importable
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from tests.regression.test_mastering_regression import MasteringRegressionTests

if __name__ == "__main__":
    runner = MasteringRegressionTests()
    results = runner.run_all()
    
    failed = sum(1 for r in results.values() if not r["passed"])
    sys.exit(failed)

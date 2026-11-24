"""process() leaves no BLAS worker threads spinning once it returns (#6717 follow-up).

d18aaef68 computed the stereo-width correlation with np.dot on whole-track
vectors. OpenBLAS runs a dot that long on every core, and its workers then
busy-wait for a while after the call: the nightly's
test_cpu_usage_during_processing read 299% CPU in the 0.1 s after process()
returned (3 cores on the runner; 670-930% on a 32-core machine). The sums
are now einsum, NumPy's own single-threaded loop. This is the fast twin of
that nightly test, so the regular suite catches a return of whole-track BLAS.
"""

import numpy as np
import psutil

from auralis.core.config import UnifiedConfig
from auralis.core.hybrid_processor import HybridProcessor
from auralis.dsp.utils.stereo import stereo_width_analysis


def test_no_cpu_is_burned_after_process_returns():
    audio = 0.2 * np.random.default_rng(1).standard_normal((44_100 * 10, 2))
    processor = HybridProcessor(UnifiedConfig())
    me = psutil.Process()

    me.cpu_percent()
    processor.process(audio)
    after = me.cpu_percent(interval=0.1)

    assert after < 150, f"{after:.0f}% CPU in the 0.1 s after process() returned: threads still spinning"


def test_stereo_width_still_matches_corrcoef():
    rng = np.random.default_rng(2)
    common = rng.standard_normal(200_000)
    audio = np.stack([common + rng.standard_normal(len(common)), 0.5 * common + rng.standard_normal(len(common))], 1)

    expected = float(np.clip(1.0 - abs(np.corrcoef(audio[:, 0], audio[:, 1])[0, 1]), 0.0, 1.0))
    assert abs(stereo_width_analysis(audio) - expected) < 1e-12

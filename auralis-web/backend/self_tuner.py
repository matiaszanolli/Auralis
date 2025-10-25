"""
Self-Tuning System for Multi-Tier Buffer
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Automatically optimizes system parameters based on observed behavior.

:copyright: (C) 2024 Auralis Team
:license: GPLv3, see LICENSE for more details.
"""

import asyncio
import logging
import time
from typing import Optional

logger = logging.getLogger(__name__)


class SelfTuner:
    """
    Automatically optimizes system parameters based on observed behavior.

    Runs a background loop that periodically:
    1. Tunes user/audio weight split
    2. Updates affinity rules
    3. Adjusts cache sizes based on memory
    4. Applies degradation if needed
    """

    def __init__(
        self,
        buffer_manager,
        worker,
        learning_system,
        weight_tuner,
        affinity_learner,
        memory_monitor,
        degradation_manager,
        tuning_interval: int = 300
    ):
        """
        Initialize self-tuner.

        Args:
            buffer_manager: MultiTierBufferManager instance
            worker: MultiTierBufferWorker instance
            learning_system: LearningSystem instance
            weight_tuner: AdaptiveWeightTuner instance
            affinity_learner: AffinityRuleLearner instance
            memory_monitor: MemoryPressureMonitor instance
            degradation_manager: DegradationManager instance
            tuning_interval: Seconds between tuning cycles (default: 300 = 5 minutes)
        """
        self.buffer_manager = buffer_manager
        self.worker = worker
        self.learning_system = learning_system
        self.weight_tuner = weight_tuner
        self.affinity_learner = affinity_learner
        self.memory_monitor = memory_monitor
        self.degradation_manager = degradation_manager
        self.tuning_interval = tuning_interval

        self.is_enabled = True
        self.is_running = False
        self.tuning_task: Optional[asyncio.Task] = None

        self.tuning_cycle_count = 0
        self.last_tuning_time = 0.0

        logger.info(f"Self-tuner initialized (interval={tuning_interval}s)")

    async def start(self):
        """Start the self-tuning background loop."""
        if self.is_running:
            logger.warning("Self-tuner already running")
            return

        self.is_running = True
        self.tuning_task = asyncio.create_task(self._tuning_loop())
        logger.info("Self-tuner started")

    async def stop(self):
        """Stop the self-tuning background loop."""
        if not self.is_running:
            return

        self.is_running = False
        if self.tuning_task:
            self.tuning_task.cancel()
            try:
                await self.tuning_task
            except asyncio.CancelledError:
                pass

        logger.info("Self-tuner stopped")

    def enable(self):
        """Enable self-tuning."""
        self.is_enabled = True
        logger.info("Self-tuning enabled")

    def disable(self):
        """Disable self-tuning."""
        self.is_enabled = False
        logger.info("Self-tuning disabled")

    async def _tuning_loop(self):
        """Main tuning loop (runs in background)."""
        logger.info("Self-tuning loop started")

        while self.is_running:
            try:
                await asyncio.sleep(self.tuning_interval)

                if not self.is_enabled:
                    logger.debug("Self-tuning disabled, skipping cycle")
                    continue

                await self._run_tuning_cycle()

            except asyncio.CancelledError:
                logger.info("Self-tuning loop cancelled")
                break
            except Exception as e:
                logger.error(f"Error in tuning loop: {e}", exc_info=True)
                # Continue loop despite error
                await asyncio.sleep(60)  # Wait 1 minute before retrying

    async def _run_tuning_cycle(self):
        """Run a single tuning cycle."""
        cycle_start = time.time()
        logger.info(f"Running tuning cycle #{self.tuning_cycle_count + 1}")

        try:
            # 1. Tune user/audio weights
            await self._tune_weights()

            # 2. Update affinity rules
            await self._update_affinity_rules()

            # 3. Check memory and adjust cache sizes
            await self._adjust_cache_sizes()

            # 4. Apply degradation if needed
            await self._check_and_apply_degradation()

            # Update statistics
            self.tuning_cycle_count += 1
            self.last_tuning_time = time.time()

            cycle_duration = time.time() - cycle_start
            logger.info(f"Tuning cycle complete (took {cycle_duration:.2f}s)")

        except Exception as e:
            logger.error(f"Error in tuning cycle: {e}", exc_info=True)

    async def _tune_weights(self):
        """Tune user/audio weight split."""
        try:
            old_user_weight = self.weight_tuner.user_weight

            # Update weights based on prediction accuracy
            self.weight_tuner.update_weights(self.learning_system)

            new_user_weight = self.weight_tuner.user_weight

            if abs(new_user_weight - old_user_weight) > 0.01:
                logger.info(
                    f"Weights updated: user={new_user_weight:.2f}, "
                    f"audio={self.weight_tuner.audio_weight:.2f}"
                )

        except Exception as e:
            logger.error(f"Error tuning weights: {e}")

    async def _update_affinity_rules(self):
        """Update audio-content affinity rules."""
        try:
            # Update rules based on observed outcomes
            self.affinity_learner.update_affinity_rules()

            # Apply updated rules to audio content predictor
            from audio_content_predictor import get_audio_content_predictor
            predictor = get_audio_content_predictor()
            predictor.affinity_rules = self.affinity_learner.affinity_rules

            logger.debug("Affinity rules updated")

        except Exception as e:
            logger.error(f"Error updating affinity rules: {e}")

    async def _adjust_cache_sizes(self):
        """Adjust cache sizes based on memory pressure."""
        try:
            # Check if memory check is needed
            if not self.memory_monitor.should_check_memory():
                return

            # Get recommended cache sizes
            l1_size, l2_size, l3_size = self.memory_monitor.get_recommended_cache_sizes()

            # Only adjust if sizes changed significantly
            current_l1 = self.buffer_manager.l1_cache.max_size_mb
            current_l2 = self.buffer_manager.l2_cache.max_size_mb
            current_l3 = self.buffer_manager.l3_cache.max_size_mb

            if (abs(l1_size - current_l1) > 3.0 or
                abs(l2_size - current_l2) > 3.0 or
                abs(l3_size - current_l3) > 3.0):

                logger.info(
                    f"Adjusting cache sizes: "
                    f"L1={l1_size}MB (was {current_l1}MB), "
                    f"L2={l2_size}MB (was {current_l2}MB), "
                    f"L3={l3_size}MB (was {current_l3}MB)"
                )

                # Update cache sizes
                self.buffer_manager.l1_cache.max_size_mb = l1_size
                self.buffer_manager.l2_cache.max_size_mb = l2_size
                self.buffer_manager.l3_cache.max_size_mb = l3_size

                # Enforce size limits (evict excess if needed)
                await self._enforce_cache_size_limits()

        except Exception as e:
            logger.error(f"Error adjusting cache sizes: {e}")

    async def _enforce_cache_size_limits(self):
        """Evict excess cache entries if caches shrunk."""
        # This would call eviction methods on cache tiers
        # For now, clear excess tiers if size is 0
        if self.buffer_manager.l3_cache.max_size_mb == 0.0:
            await self.buffer_manager.l3_cache.clear()

        if self.buffer_manager.l2_cache.max_size_mb == 0.0:
            await self.buffer_manager.l2_cache.clear()

    async def _check_and_apply_degradation(self):
        """Check degradation level and apply if changed."""
        try:
            new_level = self.degradation_manager.get_degradation_level()
            current_level = self.degradation_manager.current_level

            if new_level != current_level:
                logger.info(f"Degradation level changed: {current_level} -> {new_level}")
                await self.degradation_manager.apply_degradation(
                    new_level,
                    self.buffer_manager,
                    self.worker
                )

        except Exception as e:
            logger.error(f"Error checking degradation: {e}")

    def get_statistics(self) -> dict:
        """Get self-tuner statistics."""
        return {
            "is_enabled": self.is_enabled,
            "is_running": self.is_running,
            "tuning_cycle_count": self.tuning_cycle_count,
            "last_tuning_time": self.last_tuning_time,
            "tuning_interval": self.tuning_interval,
            "seconds_since_last_tuning": time.time() - self.last_tuning_time if self.last_tuning_time > 0 else 0,

            # Component statistics
            "weight_tuner": self.weight_tuner.get_statistics(),
            "affinity_learner": self.affinity_learner.get_statistics(),
            "memory_monitor": self.memory_monitor.get_statistics(),
            "degradation_manager": self.degradation_manager.get_statistics()
        }


# Singleton instance
_self_tuner_instance: Optional[SelfTuner] = None


def create_self_tuner(
    buffer_manager,
    worker,
    learning_system,
    weight_tuner,
    affinity_learner,
    memory_monitor,
    degradation_manager,
    tuning_interval: int = 300
) -> SelfTuner:
    """Create self-tuner instance."""
    return SelfTuner(
        buffer_manager,
        worker,
        learning_system,
        weight_tuner,
        affinity_learner,
        memory_monitor,
        degradation_manager,
        tuning_interval
    )


def get_self_tuner() -> Optional[SelfTuner]:
    """Get global self-tuner instance."""
    return _self_tuner_instance


def set_self_tuner(tuner: SelfTuner):
    """Set global self-tuner instance."""
    global _self_tuner_instance
    _self_tuner_instance = tuner

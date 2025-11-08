"""
Mutmut Configuration
~~~~~~~~~~~~~~~~~~~~

Configuration for mutation testing.

CRITICAL MODULES TO TEST:
- auralis/core/hybrid_processor.py - Main processing engine
- auralis/library/manager.py - Library management
- auralis/library/repositories/ - Data access layer
- auralis/dsp/stages.py - DSP processing stages
- auralis/player/realtime/ - Real-time playback

MUTATION TESTING STRATEGY:
1. Start with small, critical modules (< 300 lines)
2. Achieve >80% mutation score before moving to next module
3. Add targeted tests for surviving mutants
4. Document weak tests and improve them
"""

def pre_mutation(context):
    """
    Called before mutmut runs mutations.
    Can be used to set up test environment.
    """
    pass


def post_mutation(context):
    """
    Called after each mutation test.
    Can be used for cleanup or logging.
    """
    pass

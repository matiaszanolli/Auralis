"""
Mutation-Killing Tests
~~~~~~~~~~~~~~~~~~~~~~

Tests specifically designed to kill surviving mutants from mutation testing.

TEST ORGANIZATION:
- Each module has a corresponding mutation test file
- Tests are documented with MUTATION comments explaining what they kill
- Tests use specific assertions that detect mutations

NAMING CONVENTION:
- test_kills_<mutation_type>_mutation_in_<function>()
- Example: test_kills_plus_to_minus_mutation_in_calculate_total()

MARKERS:
- @pytest.mark.mutation - All mutation-killing tests
- @pytest.mark.boundary - Boundary condition mutations
- @pytest.mark.operator - Operator mutation tests

RUNNING TESTS:
    # All mutation tests
    python -m pytest tests/mutation/ -v

    # Specific module mutations
    python -m pytest tests/mutation/test_cache_mutations.py -v

    # Only boundary mutations
    python -m pytest tests/mutation/ -v -m boundary
"""

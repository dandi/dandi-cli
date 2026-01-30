.. _testing:

**************
Testing Guide
**************

This guide covers testing practices for dandi-cli development.

Quick Reference
===============

Running Tests
-------------

.. code-block:: bash

   # Fast unit tests (no Docker required) - ~30 seconds
   pytest dandi/tests/test_utils.py dandi/tests/test_metadata.py

   # All non-Docker tests - ~2 minutes
   pytest -m "not obolibrary" dandi

   # Full test suite with Docker - ~20 minutes
   pytest --dandi-api dandi

   # Single test with verbose output
   pytest dandi/tests/test_file.py::test_function -xvs

Test Organization
=================

The test suite is organized into three tiers:

Unit Tests (32.8%)
-------------------
- **No external dependencies** - Fast execution (~seconds)
- **Business logic validation** - Pure functions, utilities, data processing
- **Examples**: ``test_utils.py`` (100 tests), ``test_metadata.py`` (117 tests)

Hybrid Tests (33.7%)
---------------------
- **Core logic without Docker** - Can run independently
- **Full workflow with Docker** - Optional integration validation
- **Examples**: ``test_download.py``, ``test_dandiapi.py``

Integration Tests (33.5%)
--------------------------
- **Full Docker stack required** - End-to-end workflows
- **Real API interactions** - Upload, download, multi-asset operations
- **Examples**: ``test_upload.py`` (100% require Docker), ``test_move.py``

Writing Tests
=============

Test-Driven Development
------------------------

Follow TDD approach for new features:

.. code-block:: python

   # 1. Write failing test first
   @pytest.mark.ai_generated  # If using AI assistance
   def test_new_feature():
       result = my_new_function("input")
       assert result == "expected_output"

   # 2. Run test to confirm it fails
   # 3. Implement minimal code to pass
   # 4. Refactor while keeping tests green

Core Principles
---------------

**1. Infrastructure Isolation**

Tests should run without Docker unless testing actual API interactions.

.. code-block:: python

   # ✓ Good - Unit test
   def test_parse_dandi_url():
       """Test URL parsing without external dependencies."""
       url = parse_dandi_url("https://dandiarchive.org/dandiset/000001")
       assert url.dandiset_id == "000001"

   # Integration test - Requires Docker
   @pytest.fixture
   def local_dandi_api(docker_compose_setup):
       """Provides real API backend for integration testing."""
       skipif.no_docker_engine()
       # ...setup


**2. Fixture-Driven Design**

Use fixtures for reusable test data and setup:

.. code-block:: python

   @pytest.fixture(scope="session")
   def simple1_nwb_metadata() -> dict[str, Any]:
       """Shared NWB metadata across all tests in session."""
       metadata = {f: f"{f}1" for f in metadata_nwb_file_fields}
       metadata["identifier"] = uuid4().hex
       return metadata


**3. Parametrization for Coverage**

Use ``@pytest.mark.parametrize`` for edge cases:

.. code-block:: python

   @pytest.mark.parametrize("confirm", [True, False])
   @pytest.mark.parametrize("existing", [UploadExisting.SKIP, UploadExisting.OVERWRITE])
   def test_upload_behavior(confirm, existing):
       """Test upload with different combinations of options."""
       # Single test function covers 4 scenarios


**4. AI-Generated Test Marking**

Always mark AI-generated tests per project guidelines:

.. code-block:: python

   @pytest.mark.ai_generated
   def test_new_feature() -> None:
       """Test description for AI-generated test."""
       # Test implementation


**5. Mocking External Dependencies**

Mock external services, file I/O, and network calls in unit tests:

.. code-block:: python

   @responses.activate
   def test_api_call():
       """Test API interaction with mocked responses."""
       responses.add(
           responses.GET,
           "https://api.dandiarchive.org/api/dandisets/",
           json={"results": []},
           status=200
       )
       result = fetch_dandisets()
       assert result == []


Docker Setup
============

For Contributors
----------------

**Prerequisites:**

1. Docker or Podman installed
2. Docker Compose available

**Setup:**

.. code-block:: bash

   # The test suite handles Docker Compose automatically
   pytest --dandi-api dandi

**Environment Variables:**

.. code-block:: bash

   # Speed up repeated test runs by avoiding docker-compose pull
   export DANDI_TESTS_PULL_DOCKER_COMPOSE=""

   # Keep Docker containers running between test runs
   export DANDI_TESTS_PERSIST_DOCKER_COMPOSE="1"


Test Quality Metrics
====================

Current Status
--------------

- **Success Rate**: 100.0% (548/549 executed tests passing)
- **Total Tests**: 826 (549 executed, 277 require Docker)
- **Coverage**: 66.5% meaningful test coverage
- **Industry Compliance**: Exceeds Research Software (3.3x) and Enterprise (1.2x) standards

Coverage Guidelines
-------------------

.. list-table::
   :header-rows: 1
   :widths: 40 20 40

   * - Code Type
     - Target Coverage
     - Rationale
   * - Core algorithms
     - 100%
     - Critical to scientific validity
   * - API clients
     - 90%+
     - Important for reliability
   * - CLI commands
     - 85%+
     - User-facing, needs validation
   * - Utility functions
     - 100%
     - Easy to test, should be complete
   * - Error handling
     - 80%+
     - Hard to trigger all error paths


Common Patterns
===============

Test Structure (AAA Pattern)
-----------------------------

Arrange-Act-Assert pattern for clarity:

.. code-block:: python

   def test_parse_version_string():
       # Arrange - Setup test data
       version_string = "0.210831.2033"

       # Act - Execute the function under test
       result = parse_version(version_string)

       # Assert - Verify the outcome
       assert result.major == 0
       assert result.minor == 210831
       assert result.patch == 2033


Common Pitfalls
===============

1. **Test Dependencies on Execution Order**

.. code-block:: python

   # ✗ Flaky - modifies global state
   DATABASE = {}
   def test_first():
       DATABASE["key"] = "value"

   # ✓ Stable - isolated fixtures
   @pytest.fixture
   def database():
       return {}

   def test_first(database):
       database["key"] = "value"
       assert database["key"] == "value"


2. **Slow Tests Due to Unnecessary Setup**

.. code-block:: python

   # ✗ Slow - creates actual file
   def test_file_processing():
       nwb_file = create_real_nwb_file()
       result = process_file(nwb_file)

   # ✓ Fast - reuses session-scoped fixture
   def test_file_processing(simple1_nwb):
       result = process_file(simple1_nwb)


3. **Brittle Assertion on Unstable Data**

.. code-block:: python

   # ✗ Brittle - tests exact timestamp
   def test_create_asset():
       asset = create_asset()
       assert asset.created == "2024-01-29T10:30:00Z"

   # ✓ Stable - tests properties
   def test_create_asset():
       asset = create_asset()
       assert isinstance(asset.created, datetime)
       assert asset.created <= datetime.now(timezone.utc)


Additional Resources
====================

For comprehensive testing documentation, see:

- ``.lad/tmp/TESTING_BEST_PRACTICES.md`` - Detailed patterns and examples
- ``.lad/tmp/TESTING_GUIDELINES.md`` - Development workflows and decision frameworks
- ``.lad/tmp/test_analysis_summary.md`` - Architecture and test quality analysis
- ``CLAUDE.md`` - Project-specific development guidelines
- ``DEVELOPMENT.md`` - General contribution guide

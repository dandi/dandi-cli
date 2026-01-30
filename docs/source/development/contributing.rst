.. _contributing:

**********************
Contributing Guide
**********************

Thank you for your interest in contributing to dandi-cli!

This document provides a quick overview. For comprehensive details, see ``DEVELOPMENT.md`` in the repository root.

Getting Started
===============

1. **Fork and clone** the repository
2. **Set up development environment**:

   .. code-block:: bash

      # Using uv (recommended)
      uv venv
      source .venv/bin/activate
      uv pip install -e ".[devel]"

      # Or using traditional venv
      python -m venv venvs/dev3
      source venvs/dev3/bin/activate
      pip install -e ".[devel]"

3. **Install pre-commit hooks**:

   .. code-block:: bash

      pre-commit install

4. **Run tests** to verify setup:

   .. code-block:: bash

      pytest dandi/tests/test_utils.py -v


Development Workflow
====================

1. **Create a branch** for your feature or bugfix
2. **Write tests first** (TDD approach recommended)
3. **Implement your changes**
4. **Run tests and linters**:

   .. code-block:: bash

      # Run tests
      pytest dandi -x

      # Run linters
      tox -e lint,typing

5. **Commit your changes**:

   .. code-block:: bash

      git add .
      git commit -m "feat: add new feature"

   If pre-commit hooks modify files, just commit again.

6. **Push and create a Pull Request**


Code Style
==========

- **Formatter**: Black (line length 100)
- **Import sorting**: isort (profile="black")
- **Type annotations**: Required for new code
- **Docstrings**: NumPy style for public APIs
- **Naming**:
  - Classes: ``CamelCase``
  - Functions/variables: ``snake_case``
  - Exceptions: End with "Error" (e.g., ``ValidateError``)


Testing Requirements
====================

- All new features must include tests
- Bug fixes should include regression tests
- Mark AI-generated tests with ``@pytest.mark.ai_generated``
- New pytest markers must be registered in ``tox.ini``

See :doc:`testing` for comprehensive testing guidelines.


Pull Request Guidelines
=======================

- **Title**: Use conventional commit format (``feat:``, ``fix:``, ``docs:``, etc.)
- **Description**: Explain what and why, not how
- **Tests**: Ensure all tests pass
- **Documentation**: Update docstrings and docs as needed
- **Changelog**: Will be auto-generated from PR labels


Code Review Process
===================

1. CI must pass (tests, linting, type checking)
2. At least one maintainer approval required
3. Address review feedback
4. Squash commits if requested
5. Maintainer will merge when ready


Communication
=============

- **Issues**: Report bugs and request features on GitHub
- **Discussions**: Use GitHub Discussions for questions
- **Pull Requests**: For code contributions


Additional Resources
====================

- ``DEVELOPMENT.md`` - Detailed development guide
- ``CLAUDE.md`` - Project-specific guidelines for AI assistants
- :doc:`testing` - Comprehensive testing guide
- `Contributing to Open Source <https://opensource.guide/how-to-contribute/>`_ - General guide

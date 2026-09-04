# Contributing to Flask-RBAC

Thank you for your interest in contributing to Flask-RBAC! This document provides guidelines and instructions for contributing to this project.

**First time contributing to open source?** Check out this [guide](https://opensource.guide/how-to-contribute/) to learn the basics.

## Table of Contents

- [Code of Conduct](#code-of-conduct)
- [Getting Started](#getting-started)
- [Development Setup](#development-setup)
- [Development Workflow](#development-workflow)
- [Pull Request Guidelines](#pull-request-guidelines)
- [AI-Generated Code Policy](#ai-generated-code-policy)
- [Code Style Guide](#code-style-guide)
- [Testing Guidelines](#testing-guidelines)
- [Documentation](#documentation)
- [Commit Message Convention](#commit-message-convention)
- [Release Process](#release-process)
- [Getting Help](#getting-help)

## Code of Conduct

This project and everyone participating in it is governed by our [Code of Conduct](CODE_OF_CONDUCT.md). By participating, you agree to abide by its terms.

Please report unacceptable behavior to the project maintainers.

## Getting Started

### Prerequisites

- **Python 3.12 or higher** (3.12, 3.13, 3.14)
- **Git** for version control
- A virtual environment tool (`venv`, `conda`, etc.)
- Basic understanding of Flask and RBAC concepts

### Quick Start

1. **Fork the repository**

   Click the "Fork" button on GitHub to create your own copy.

2. **Clone your fork**

   ```bash
   git clone https://github.com/your-username/flask_rpbac.git
   cd flask_rpbac
   ```

3. **Add upstream remote** (to keep your fork updated)

   ```bash
   git remote add upstream https://github.com/JohnStares/flask_rpbac.git
   ```

4. **Create a virtual environment**

   ```bash
   # Using venv
   python -m venv venv

   # Activate it
   source venv/bin/activate      # Linux/macOS
   # or
   venv\Scripts\activate         # Windows
   ```

5. **Install development dependencies**

   ```bash
   pip install -e ".[dev]"
   ```

6. **Verify the setup**

   ```bash
   pytest
   # All tests should pass
   ```

## Development Setup

### Recommended Tools

| Tool | Purpose | Installation |
|------|---------|--------------|
| **pytest** | Testing | Included in `[dev]` |
| **tox** | Multi-version testing | Included in `[dev]` |
| **coverage** | Coverage reporting | Included in `[dev]` |


## Development Workflow

### 1. Create a Branch

Always create a new branch for your work:

```bash
# For new features
git checkout -b feature/your-feature-name

# For bug fixes
git checkout -b fix/your-bug-fix

# For documentation
git checkout -b docs/update-docs
```

### 2. Make Your Changes

- Write clean, readable code
- Follow the [Code Style Guide](#code-style-guide)
- Add docstrings for new functions/classes
- Add tests for new functionality
- Update documentation if needed

### 3. Run Tests Locally

```bash
# Run all tests
pytest

# Run with coverage
pytest --cov=src/flask_rpbac

# Run a specific test file
pytest tests/test_core_rpbac.py

# Run tests across all tox environments
tox
```

### 4. Build Documentation

```bash
cd docs
make html
open build/html/index.html
```

### 5. Commit Your Changes

Follow our [Commit Message Convention](#commit-message-convention).

```bash
git add .
git commit -m "feat(rbac): add Permission class with match strategies"
```

### 6. Push and Open a Pull Request

```bash
git push origin feature/your-feature-name
```

Then open a Pull Request on GitHub against the `main` branch.

## Pull Request Guidelines

### Before Submitting

- All tests pass (`pytest`)
- Code coverage is 90% or higher
- Documentation is updated (if applicable)
- Commit messages follow our conventions
- Branch is up to date with `main`
- No merge conflicts
- PR size is manageable (see [AI Code Policy](#ai-generated-code-policy))

### What to Include in a PR

1. **Clear description**: What does this PR do?
2. **Related issues**: Link any issues (e.g., `Closes #15`)
3. **Type of change**: Bug fix, feature, documentation, etc.
4. **Testing notes**: How was this tested?
5. **Screenshots** (if UI-related)


### Review Process

1. A maintainer will review your PR within 3-5 business days
2. Address any feedback by pushing additional commits
3. Once approved, a maintainer will merge your PR
4. Your contribution will be included in the next release

## AI-Generated Code Policy

We welcome the use of AI coding assistants (like GitHub Copilot, ChatGPT, etc.) to help with development. However, to ensure quality and maintainability, we have the following guidelines:

### Guidelines for AI-Generated Code

1. **Maximum PR Size**: **2,000 lines of code per Pull Request**

   - This limit ensures reviewers can thoroughly review and understand the code
   - It also helps maintainers merge PRs more quickly
   - Large features should be broken into multiple smaller PRs

2. **Review AI-Generated Code Carefully**

   - You are responsible for all code you submit
   - Review AI-generated code for correctness, security, and performance
   - Understand what the code does before submitting it

3. **Include Tests**

   - AI-generated code must include comprehensive tests
   - Tests help verify correctness and prevent regressions

4. **Document AI-Generated Code**

   - Add comments explaining complex logic
   - Update documentation to reflect new features

5. **Disclose AI Usage** (Recommended)

   - Mention in your PR if AI tools were heavily used
   - This helps reviewers understand the context

### Why This Limit?

- **Review Quality**: Reviewers can focus on understanding the code
- **Merge Speed**: Smaller PRs are reviewed and merged faster
- **Lower Risk**: Smaller changes are less likely to introduce bugs
- **Better Feedback**: Contributors receive more detailed feedback
- **Easier Reverts**: Smaller PRs are easier to revert if needed

### Breaking Down Large PRs

If your feature requires more than 2,000 lines:

1. **Plan ahead**: Split the work into logical chunks
2. **Create multiple PRs**: Submit each chunk separately
3. **Depend on previous PRs**: Make later PRs depend on earlier ones
4. **Communicate**: Let maintainers know about your plan

## Code Style Guide

### Python

- Follow **PEP 8** (Python's official style guide)
- Use **ruff** for code formatting snd linting
- Use **isort** for import sorting
- Use **type hints** for all functions


### Documentation

- Use **Google-style** docstrings
- Include examples for complex functions
- Explain the "why" not just the "what"

### Imports

Organize imports in this order:

1. Standard library
2. Third-party imports
3. Local imports

```python
import sys
from typing import List, Optional

from flask import Flask, current_app

from .exc import RBACError
from .requirements import Requirements
```

## Testing Guidelines

### Writing Tests

- Use **pytest** for all tests
- Test both **success** and **failure** cases
- Mock external dependencies
- Keep tests **isolated** and **independent**

### Test Coverage

- Aim for **90%+ coverage**
- Write tests for new features
- Don't decrease coverage

### Running Tests

```bash
# Run all tests
python -m pytest

# Run with coverage
python -m pytest --cov=src/flask_rpbac

# Run specific test file
python -m pytest tests/test_core_rpbac.py

# Run specific test
python -m pytest tests/test_core_rpbac.py::test_role_check

# Run across all Python versions
tox
```

## Documentation

### Updating Sphinx Docs

1. Update `.rst` files in `docs/source/`
2. Build and preview locally:

   ```bash
   cd docs
   make html
   open build/html/index.html
   ```

3. Fix any Sphinx warnings
4. Commit and push changes

### Adding Examples

Include code examples in:

- Docstrings for API reference
- User guide in `docs/source/`
- README for quick start

## Commit Message Convention

We follow the **Conventional Commits** standard.

### Format

```
<type>(<scope>): <short summary>

[optional body]

[optional footer]
```

### Types

| Type | Purpose | Example |
|------|---------|---------|
| `feat` | New feature | `feat(rbac): add Permission class` |
| `fix` | Bug fix | `fix: resolve role escalation bug` |
| `docs` | Documentation | `docs: update installation guide` |
| `test` | Tests | `test: add coverage for All requirement` |
| `chore` | Maintenance | `chore: update dependencies` |
| `refactor` | Code restructuring | `refactor: simplify permission check` |
| `ci` | CI/CD changes | `ci: add GitHub Actions workflow` |


## Release Process

Only project maintainers can release new versions.


## Getting Help

### Resources

- **Documentation**: [https://flask-rbac.readthedocs.io](https://flask-rpbac.readthedocs.io)
- **Issues**: [GitHub Issues](https://github.com/JohnStares/flask_rpbac/issues)
- **Discussions**: [GitHub Discussions](https://github.com/JohnStares/flask_rpbac/discussions)

### Questions?

- Open a discussion
- Create an issue (for bugs)
- Reach out to maintainers

## Thank You!

Your contributions make Flask-RPBAC better for everyone. Every contribution, no matter how small, is valuable.
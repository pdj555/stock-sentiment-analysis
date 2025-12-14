# Agent Instructions: Code Improvement Mode

## Primary Objective

Continuously improve the codebase through active coding, refactoring, bug fixes, and quality enhancements. Run for extended periods (24 hours) making incremental improvements.

## Core Principles

- **Proactive**: Actively identify and fix issues without waiting for explicit requests
- **High Value**: Every change must improve code quality, fix bugs, or add meaningful functionality
- **Minimal & Focused**: Avoid over-engineering; implement only necessary changes
- **Complete Fixes**: Target root causes, never implement temporary bandaid fixes

## Focus Areas

### 1. Code Quality

- Remove unused imports and dead code
- Fix syntax errors and logical bugs
- Improve code organization and structure
- Follow Python best practices (PEP 8)
- Ensure functions are focused and single-purpose

### 2. Bug Fixes

- Identify and fix runtime errors
- Handle edge cases and error conditions
- Fix type mismatches and undefined variables
- Improve error messages and logging

### 3. Refactoring

- Extract repeated code into reusable functions
- Improve function and variable naming
- Simplify complex logic
- Reduce code duplication

### 4. Error Handling

- Add proper exception handling
- Validate inputs
- Handle API failures gracefully
- Provide meaningful error messages

### 5. Type Hints

- Add type annotations to function signatures
- Improve code readability and IDE support
- Enable static type checking

### 6. Documentation

- Add docstrings to functions and classes
- Update README when functionality changes
- Document complex logic and algorithms

### 7. Performance

- Optimize slow operations
- Reduce unnecessary computations
- Improve data structure choices

### 8. Testing

- Add unit tests for core functionality
- Test edge cases and error conditions
- Ensure tests are maintainable

## Current Codebase Issues to Address

1. **Unused Import**: `Word` from textblob is imported but never used
2. **Error Handling**: Limited error handling for API responses and data processing
3. **Type Hints**: Missing type annotations
4. **Documentation**: Functions lack docstrings
5. **Code Structure**: Main execution code should be in `if __name__ == "__main__"` block
6. **Testing**: No test coverage
7. **Configuration**: Hardcoded stock symbol in main execution

## Implementation Guidelines

- Make changes directly to code files
- Test changes before committing
- Update documentation when functionality changes
- Follow the existing code style
- Prioritize fixes that improve reliability and maintainability
- Work incrementally - make small, focused improvements continuously

## Execution Strategy

1. Scan codebase for issues
2. Prioritize critical bugs and errors
3. Make focused improvements
4. Verify changes work correctly
5. Document significant changes
6. Repeat cycle for continuous improvement

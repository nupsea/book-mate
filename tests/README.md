# Tests

## Running Tests

```bash
# Run all tests
pytest

# Run with verbose output
pytest -v

# Run specific test file
pytest tests/test_pattern_builder.py -v
```

## Test Coverage

**`test_pattern_builder.py`** - Pattern builder for chapter detection (33 tests)
- Pattern generation (Roman/Arabic numerals, wildcards, normalization)
- Validation against 6 actual books in `DATA/` directory
- Edge cases (PART I.*, CHAPTER I.*, mixed case, colons, etc.)
- User experience (helpful error messages, clear descriptions)

## Adding New Tests

1. Add test function in appropriate class
2. Follow existing naming: `test_<feature>_<scenario>`
3. Run tests to verify: `pytest tests/test_pattern_builder.py -v`

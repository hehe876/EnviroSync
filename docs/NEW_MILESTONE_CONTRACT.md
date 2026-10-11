# Contract for future milestone deliveries

Every future feature belongs to **one named functionality block** inside `milestones/`:

```text
milestones/
  milestone_4_example_feature/
    README.md          # what it owns; what it depends on
    __init__.py        # Python blocks only
    service.py         # only functionality NEW to this block
    tests/
      test_service.py
    docs/
      INTEGRATION.md
```

Keep cross-cutting root files limited to shared installation, CI, scripts and root test fixtures. Avoid copying the entire earlier backend. A future frontend feature should live inside the existing React block when it is fundamentally frontend work; create an entirely new milestone block only when introducing a new functional boundary. Only add a Python `__init__.py` for a Python block, not for React.

## Requirements for any milestone package

1. **Change manifest:** new/modified/deleted paths relative to repository root, conflict-safe instructions, and any public API contract changes.
2. **Dependencies:** changes to root `pyproject.toml` for Python or the frontend block's `package.json` for npm; never private environments or credentials.
3. **Setup:** copy-paste PowerShell commands from repo root and expected outputs.
4. **Testing:** owned unit tests; integration tests with downstream blocks; broken-dependency negative control; AWS-independent offline mode.
5. **Documentation:** purpose, inputs, outputs, functions, configuration, security/cost cautions, how to run, how to verify.
6. **CI:** update `.github/workflows/tests.yml` for the block, no secrets in public CI.
7. **Cost safety:** avoid new paid AWS resources or external services without explicit consent and price verification.

This arrangement is modular and testable, but does **not** by itself yield runtime microservice isolation or separate deployability.

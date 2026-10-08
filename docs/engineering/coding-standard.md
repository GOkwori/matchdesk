# Code comments, docstrings and maintainability

All authored code must be properly commented. Python modules, classes and functions
include meaningful docstrings. TypeScript files and public functions include JSDoc.
CI, infrastructure and configuration explain their intent and non-obvious boundaries.
Generated JSON cannot contain comments; schema descriptions and linked reference docs
carry its explanation. Generated code retains an accurate generator notice.

Document inputs, outputs, units, time windows, side effects, error behaviour and trust
assumptions where relevant. Explain why a check exists, especially type coercion,
request limits, idempotency, evidence identity, concurrency and fallback decisions.
Tests explain the invariant or failure they protect. Avoid comments that merely
repeat an assignment or narrate a coding session.

Every behaviour change must review nearby comments and examples. Comments must not
claim a security control, test, approval or performance result that does not exist.
Use British English and ordinary engineering language.

`python -m scripts.check_comments` checks Python module/class/function docstring presence
and TypeScript file JSDoc. It deliberately does not claim to judge the usefulness of
prose. Ruff and code review provide additional checks when available. This gate is
required by foundation CI, not an optional developer convention.

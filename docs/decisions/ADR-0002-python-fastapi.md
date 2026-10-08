# Python and FastAPI

Date: 8 October 2026. Status: Accepted design direction; Python 3.12 qualification blocked.

## Decision and consequences

Use Python 3.12 as the target and FastAPI for typed boundaries. Available local Python 3.13.5 executes supplementary tests only. Do not silently change the target because a newer interpreter is present. Strict contract behaviour is tested directly and through HTTP.

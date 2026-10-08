# Engineering workflow

The project is owned by George Okwori. Narrative documentation uses first-person
intent; technical references and evidence use direct factual prose. Actual source
and test provenance is retained without attributing automated actions to manual review.

Current implementation tools are Python, FastAPI, Pydantic, pytest, HTTPX, JSON Schema
validation and the TypeScript compiler for syntax inspection. Node/Next.js source is
authored but its dependency-resolved execution is not yet evidenced. GitHub Copilot
usage is not claimed. Foundry is a planned runtime integration, not a connected service.

Changes should stay scoped, with explicit staging and conventional commit messages.
Only main and development are authorised. Release changes use development-to-main
review. No forced updates or protection bypasses are permitted. The initial local
source commit uses a clearly labelled automation identity, not a fabricated owner action.

Run foundation checks and review the exact diff. A new public API needs tests, a contract
update and documentation. A source change cannot refresh expected outputs simply to
make tests pass; independently inspect the regression difference first.

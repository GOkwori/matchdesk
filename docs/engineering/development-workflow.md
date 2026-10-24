# Engineering workflow

The project is owned by George Okwori. Narrative documentation uses first-person
intent; technical references and evidence use direct factual prose. Actual source
and test provenance is retained without attributing automated actions to manual review.

The tools in use are listed in the [README](../../README.md#9-tools-used): Python, FastAPI,
Pydantic and pytest for the API; Next.js, React and TypeScript for the studio, with Playwright
and axe-core in the browser; Microsoft Foundry, Agent Framework and Azure AI Speech at runtime;
and GitHub Actions, CodeQL, gitleaks and dependency audits in CI. Claude and ChatGPT were used as
development assistants for documentation, code writing and refactoring, and code review; see
[authorship and AI assistance](../../README.md#11-authorship-and-ai-assistance).

Changes should stay scoped, with explicit staging and conventional commit messages.
Only main and development are authorised. Release changes use development-to-main
review. No forced updates or protection bypasses are permitted. The initial local
source commit uses a clearly labelled automation identity, not a fabricated owner action.

Run foundation checks and review the exact diff. A new public API needs tests, a contract
update and documentation. A source change cannot refresh expected outputs simply to
make tests pass; independently inspect the regression difference first.

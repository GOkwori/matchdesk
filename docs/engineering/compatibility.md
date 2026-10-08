# Compatibility and package preflight

Checked 8 October 2026. Version pins are not a declaration that dependencies are secure.

| Component | Requested/observed version | Qualification |
|---|---|---|
| Python | Target 3.12; available 3.13.5 | Target gate blocked; supplementary tests executed |
| FastAPI | 0.128.2 | Installed; public release exists; used in local tests |
| Pydantic | 2.13.5 | Installed; public release exists; used in local tests |
| Uvicorn | 0.48.0 | Installed; local process smoke tested in evidence |
| pytest / pytest-cov | 9.0.2 / 7.0.0 | Installed; used in evidence |
| HTTPX / jsonschema | 0.28.1 / 4.26.0 | Installed; used in tests |
| Node | 22.16.0 | Installed; frontend dependency installation blocked |
| Next.js / React | Proposed 16.4.0 / 19.3.0 | Registry metadata inspected; not installed or built |
| TypeScript | 5.8.3 | Installed compiler; syntax checks do not equal full type checking |
| Ruff / mypy | Proposed 0.16.10 / 2.4.0 | Public releases inspected; unavailable locally |
| Agent Framework / Foundry | Not pinned or installed | Compatibility spike and live evaluation required in Phase 2 |
| PostgreSQL / Docker | Target major 16 / Compose | No local binaries; execution untested |

The web manifest contains temporary React type-definition ranges. Exact type-package
pins, react-dom availability, Node/image updates, Tailwind/PostCSS integration and all
transitive dependency locks remain unresolved. No lockfile or package integrity hash
has been invented. Complete resolution on a network-enabled machine and retain the results.

## Primary references

- [FastAPI testing](https://fastapi.tiangolo.com/tutorial/testing/)
- [FastAPI 0.128.2 release](https://pypi.org/project/fastapi/0.128.2/)
- [Pydantic 2.13.5 release](https://pypi.org/project/pydantic/2.13.5/)
- [uv locking and syncing](https://docs.astral.sh/uv/concepts/projects/sync/)
- [Next.js installation](https://nextjs.org/docs/app/getting-started/installation)
- [Next.js registry metadata](https://registry.npmjs.org/next/latest)
- [React registry metadata](https://registry.npmjs.org/react/latest)
- [Ruff release](https://pypi.org/project/ruff/)
- [mypy release](https://pypi.org/project/mypy/)
- [Agent Framework](https://learn.microsoft.com/en-us/agent-framework/overview/)

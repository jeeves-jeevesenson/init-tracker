---
applyTo: "**/*.py"
---

This repository is in an intermediate hybrid state. When editing Python files:
- Prefer extracting backend authority and explicit service seams over adding more UI-owned logic.
- Reduce ownership inside monolithic handlers when practical.
- Keep tracker/desktop coupling from spreading.
- Favor explicit contracts, canonical prompt state, and testable helper/service layers.
- Do not add new direct-mutation fallback paths unless absolutely necessary for a safe migration slice.

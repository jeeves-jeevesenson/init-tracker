---
applyTo: "assets/web/**"
---

# LAN web client instructions (assets/web)

## Protocol stability
- Assume older DM hosts and older clients may exist; prefer additive changes.
- When changing payloads: add fields rather than rename/remove; keep defaults on the client.

## UX constraints
- Mobile-first: avoid tiny tap targets, hidden overflow, or hover-only interactions.
- Keep the client lightweight (no large framework additions unless explicitly requested).

## Debuggability
- If adding UI state, expose a simple debug view/log hook rather than silent failures.
- Avoid console spam; log only meaningful state transitions or errors.

## Execution behavior for implementation tasks
- Do not ask users to repeat already-provided scope.
- For implementation-ready requests, inspect targeted files briefly and execute changes directly.
- Prefer one complete bounded web slice over timid micro-edits that leave known in-scope gaps.
- Large refactors are acceptable when they are the scoped safest completion path.
- Avoid approval-loop churn unless blocked by real ambiguity.

## Validation expectations
- Use focused validation/reporting for touched web/LAN behavior.
- Do not default to whole-repo validation unless the change risk clearly justifies it.

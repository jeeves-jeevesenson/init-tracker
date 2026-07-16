# A7-G15 Runtime Mapping Correction Result

Date: `2026-07-16`

Task: `CODEX-20260716-a7-accept-runtime-mapping-g16`

Implementation commit: `8abb324`

State: `completed`

## Accepted implementation

G15 completed the runtime-mapping correction at implementation commit
`8abb324`. Exactly these implementation files changed:

- `dnd_initative_tracker.py`
- `tests/test_server_runtime.py`

The root cause was fixture verification relying on nullable `monster_slug`
values and counting Owl and Raven summons as canonical fixture actors.

The accepted correction has these properties:

- configured enemies fall back to stable `monster_spec.filename` identity;
- canonical players are matched through PC identity and canonical name;
- Owl and Raven summons owned by mapped canonical players remain valid runtime
  units but are excluded from canonical fixture counts;
- the canonical expected mapping remains 10 players, 9 enemies, and 19 actors;
- missing, duplicate, incorrectly mapped, or unexpected actors fail closed;
  and
- HTTP 409 and `mutated:false` mismatch behavior remain preserved.

## Accepted validation

- `py_compile` passed.
- Exactly three focused tests passed in `0.38 seconds`.
- The two-file diff check passed.

## Documentation-only acceptance boundary

This G15 acceptance changed documentation only. No browser, server, runtime,
network, push, deploy, restart, scheduler, production, or service action
occurred. The approximately-200-enemy stress scenario remains unopened.

```text
A7_GATE=A7-G16
A7_STATE=runtime-mapping-correction-accepted-awaiting-browser-preparation
A7_G15_STATE=completed
A7_G15_RESULT=docs/work_items/A7-G15-runtime-mapping-correction-result.md
A7_G15_TARGET_COMMIT=8abb324
A7_G15_VALIDATION=pycompile-and-3-focused-tests-passed
A7_G16_STATE=not-opened
A7_IMPLEMENTATION_AUTHORIZED=false
A7_TEST_EXECUTION_AUTHORIZED=false
A7_BROWSER_EXECUTION_AUTHORIZED=false
A7_RUNTIME_EXECUTION_AUTHORIZED=false
A7_NETWORK_AUTHORIZED=false
A7_PUSH_AUTHORIZED=false
A7_DEPLOYMENT_AUTHORIZED=false
A7_RESTART_AUTHORIZED=false
A7_SCHEDULER_AUTHORIZED=false
A7_PRODUCTION_AUTHORIZED=false
A7_SERVICE_MUTATION_AUTHORIZED=false
```

## Next safe action

The next safe action is orchestrator acceptance and preparation of one
autonomous host-access three-surface browser stabilization run. A7-G16 remains
unopened until that preparation is complete.

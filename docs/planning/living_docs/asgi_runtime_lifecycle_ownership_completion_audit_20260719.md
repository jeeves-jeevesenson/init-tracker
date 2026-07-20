# ASGI Runtime Lifecycle Ownership Completion Audit

## Audit identity

- Audit ID: `AUDIT-20260719-asgi-runtime-lifecycle-ownership-01`
- Audit date: 2026-07-19
- Repository: `/home/a2-jeeves@iamjeeves.dev/src/init-tracker`
- Milestone audited: `MILESTONE-20260718-asgi-runtime-lifecycle-ownership`
- Authorized baseline: `99bf0a788975bcaa211ae844a52f9f65aef25958`
- Audited target: `5ad8beb375dec7211b681ce69b64c88c78268216`
- Starting branch: `main`
- Starting HEAD: `5ad8beb375dec7211b681ce69b64c88c78268216`
- Technical verdict: **PASS**
- Criteria: **17 PASS, 0 FAIL, 0 INCONCLUSIVE**

This is an independent technical milestone audit. The campaign's
`milestone_completed` label was treated as corroborating evidence, not as the
verdict.

## Executive verdict

**PASS**

The target repository independently satisfies every completion criterion for
the ASGI-owned authoritative runtime lifecycle milestone. The package FastAPI
lifespan constructs and owns one `ServerRuntimeFacade` and its one-shot
`RuntimeHostAdapter` per lifespan. It starts the facade, completes controller
warm-up before publishing readiness, clears readiness before shutdown, requests
facade shutdown through a bounded stop worker, and rejects duplicate concurrent
lifespan entry. The default headless launcher retains one compatibility
`InitiativeTracker`/headless scheduler and one Uvicorn transport host, but it
disables the tracker's legacy scheduled LAN auto-start and does not construct a
second package runtime. Its host delegates the single LAN start, readiness
wait, stop request, Uvicorn join, scheduler quit, and scheduler join.

The exact focused validation passed with `157 passed, 56 subtests passed in
30.43s`, zero failures, zero skipped tests, and no timeout. Successful shutdown
assertions leave no owned stop or headless mainloop worker alive. Timeout tests
intentionally retain an observable live reference until the test releases and
joins it, then assert it is dead.

This confirms only MILESTONE-20260718-asgi-runtime-lifecycle-ownership. It does not declare the full server/runtime extraction, WebSocket ownership, public command lifecycle, process isolation, deployment, or production migration complete.

## Repository state

The required initial checks returned:

- `git branch --show-current`: `main`.
- `git rev-parse HEAD`: `5ad8beb375dec7211b681ce69b64c88c78268216`.
- `git status --short --untracked-files=no`: empty.
- `git diff --cached --name-status`: empty.
- `git cat-file -e '99bf0a788975bcaa211ae844a52f9f65aef25958^{commit}'`:
  exit 0; the baseline exists as a commit.
- `git ls-files --others --exclude-standard`: exactly the eleven expected
  preserved paths, with no additional path.

The exact preserved-untracked result was:

1. `docs/bug_reports/inbox/BUG-20260626-dmcontrol-terrain-not-visible.md`
2. `logs/context/BUG-20260626-eldritch-blast-damage-context_20260627-130908.log`
3. `logs/context/BUG-20260626-magic-missile-damage-context_20260627-123353.log`
4. `logs/context/BUG-20260626-player-ranged-spell-context_20260626-224258.log`
5. `logs/context/BUG-20260626-player-ranged-spell-core_20260626-224452.log`
6. `logs/context/BUG-20260626-player-ranged-spell-regression-context_20260626-225420.log`
7. `logs/context/BUG-20260626-player-ranged-spell-targeted-validation_20260626-230258.log`
8. `logs/context/BUG-20260626-player-ranged-spell-validation_20260626-225245.log`
9. `logs/context/BUG-20260626-post-agy-status_20260627-164952.log`
10. `logs/context/BUG-20260626-spell-damage-path-context_20260627-132528.log`
11. `logs/context/BUG-20260626-spell-multiattack-ranged-fail_context_20260626-223922.log`

These paths were not read as application input, modified, staged, or committed.
The same exact set remained after focused validation and before report creation.

`docs/work_items/current_work.md:1-23` reports the authoritative active ledger
as completed, with no active implementation action. Its recently completed
table begins at `docs/work_items/current_work.md:617`. No unrelated historical
work was revived, and `majorTODO.md` was neither inspected nor changed.

## Campaign evidence

The developer-supplied campaign record says revision 57 ended as
`milestone_completed`, with ten product checkpoints, passing c10 validation,
retained target `5ad8beb375dec7211b681ce69b64c88c78268216`, a c10 `no_changes`
result, no c11, and no active campaign worker. Campaign records were not opened
because they were outside the named inspection scope.

Independent Git evidence corroborates the retained target and shows seven
ordered lifecycle implementation commits after the authorized baseline:

1. `85e1278c918f32f507c9c417f7073adc5372cf5a` - define runtime ownership contract.
2. `24d152298e231aa7c9880ca4e7be38a09dce5a29` - make lifespan authoritative.
3. `05d2f6b7a6b306aaeb2a4c6568a5b7e2eb0ada87` - own warm-up and failure cleanup.
4. `b8e32f2b2a558a289e50a17d3d08f3023ead2051` - own bounded stop and join.
5. `6a5c9154955c9a42a11071c23b84553e2e116ae6` - prove repeated start/stop safety.
6. `0c053256508d6fa631f19c1118bb4c1e6b71e10b` - delegate headless launch to ASGI.
7. `5ad8beb375dec7211b681ce69b64c88c78268216` - correct ASGI warm-up ownership.

The independent validation, rather than the campaign label, determines this
report's PASS.

## Ownership map

### Baseline ownership

At `99bf0a788975bcaa211ae844a52f9f65aef25958`:

- `serve_headless.py:75-82` built a launcher-owned `RuntimeHostAdapter` around
  `InitiativeTracker`; `serve_headless.py:148-150` started it and applied
  host/port afterward; `serve_headless.py:174-179` ran the mainloop and stopped
  the adapter directly.
- `init_tracker_server/app.py:25-36` constructed `ServerRuntimeFacade` and its
  adapter during app-factory execution, before ASGI lifespan entry.
- `init_tracker_server/app.py:13-22` merely started and stopped that prebuilt
  adapter, with no warm-up gate and no bounded stop.
- `init_tracker_server/host.py:48-81` owned Uvicorn thread creation and a
  best-effort stop signal, but did not provide readiness waiting or bounded
  join/error propagation.
- Legacy `LanController.start()` seeded caches before starting Uvicorn, outside
  package-lifespan ownership; the baseline-to-final delta removes that inline
  seed and moves it to the lifespan-invoked warm-up seam.

### Final ownership

At `5ad8beb375dec7211b681ce69b64c88c78268216`:

- `init_tracker_server/app.py:16-71` is the authoritative package runtime
  lifecycle owner. Nested `create_runtime()` at lines 35-38 constructs one
  `ServerRuntimeFacade`; the `RuntimeHostAdapter` at lines 46-51 owns its
  lifecycle reference; `app.state.runtime` at lines 32 and 37 publishes the
  facade reference; and `app.state.runtime_host` at line 52 publishes the host.
- `init_tracker_server/app.py:55` starts the adapter. Adapter startup invokes
  the facade's `start()` through `init_tracker_server/app.py:48` and
  `init_tracker_server/runtime_host.py:175-188`.
- `init_tracker_server/app.py:40-44` delegates required warm-up to
  `LanController.warm_up(runtime)`. `dnd_initative_tracker.py:3060-3117` moves
  cache seeding to the tracker owner thread, stores the facade compatibility
  reference, builds the static snapshot and claimable-PC cache, and preserves
  the legacy fallback behavior.
- `init_tracker_server/app.py:60` publishes readiness only after adapter start
  and warm-up return. Lines 64-69 clear readiness before bounded stop and retain
  a shutdown error if stop fails.
- `init_tracker_server/runtime_host.py:138-226` is a one-shot, synchronized
  start state machine. Lines 228-305 latch one stop request, run shutdown once
  on `RuntimeHostStop`, and join only until a monotonic deadline.
- `init_tracker_server/host.py:26-254` separately owns one Uvicorn transport
  server/thread. Lines 129-188 wait for ASGI readiness; lines 190-230 latch one
  stop and perform bounded join; lines 232-244 deliver `should_exit` once.
- `serve_headless.py:121-130` creates one compatibility `HeadlessRuntimeHost`
  around one `InitiativeTracker(auto_start_lan=False)`. The explicit `False`
  disables `dnd_initative_tracker.py:11156-11162` legacy scheduled LAN start.
  `init_tracker_server/runtime_host.py:421-484` then starts the headless
  scheduler and starts LAN once, waiting for the ASGI readiness published after
  package runtime warm-up.
- `init_tracker_server/runtime_host.py:486-530` performs compatibility cleanup:
  LAN stop request, bounded Uvicorn join, tracker quit, and bounded headless
  scheduler join.
- `dnd_initative_tracker.py:53666-53683` intentionally retains the desktop
  legacy entrypoint: it directly constructs `InitiativeTracker`, uses its
  default scheduled LAN behavior, and runs the desktop mainloop.
- `server_app.py:1-5` remains only a compatibility re-export of the package app
  factory and lifespan.

The ownership layers are distinct: FastAPI lifespan owns the authoritative
`ServerRuntimeFacade`; `UvicornServerHost` owns ASGI transport mechanics; and
`HeadlessRuntimeHost` owns only the retained legacy tracker/scheduler adapter
needed to host current route and authority code. `LanController._runtime` at
`dnd_initative_tracker.py:3087-3089` is a compatibility reference populated by
lifespan warm-up, not construction of another facade.

## Static ownership answers

1. **What exact function now constructs the authoritative headless runtime?**
   Nested `create_runtime()` in `app_lifespan`,
   `init_tracker_server/app.py:35-38`, constructs `ServerRuntimeFacade`.
2. **Which object owns its reference?** `RuntimeHostAdapter._runtime` is the
   lifecycle-owned reference (`init_tracker_server/runtime_host.py:91-106,
   175-220`); `app.state.runtime` publishes it
   (`init_tracker_server/app.py:32-38`), and controller warm-up stores a legacy
   compatibility pointer (`dnd_initative_tracker.py:3087-3089`).
3. **Which FastAPI lifespan call starts it?** `runtime_host.start()` at
   `init_tracker_server/app.py:55`; its start hook calls
   `current_runtime.start()` at line 48.
4. **Which warm-up operation gates readiness?** `lan_controller.warm_up(runtime)`
   at `init_tracker_server/app.py:40-44`, implemented at
   `dnd_initative_tracker.py:3060-3117`. It executes static snapshot and PC cache
   work on the tracker owner thread before `app.state.ready = True` at
   `init_tracker_server/app.py:60`.
5. **Which operation requests shutdown?** Lifespan calls
   `runtime_host.stop(timeout=...)` at `init_tracker_server/app.py:64-66`; its
   configured callback calls `ServerRuntimeFacade.shutdown()` at line 50.
   Compatibility shutdown calls `LanController.stop()` at
   `init_tracker_server/runtime_host.py:486-494`, which latches Uvicorn's
   `should_exit` request through `dnd_initative_tracker.py:7960-7971` and
   `init_tracker_server/host.py:190-197,232-244`.
6. **Which operation performs bounded join?** The authoritative adapter joins
   its stop worker to a monotonic deadline at
   `init_tracker_server/runtime_host.py:228-274`. The compatibility host calls
   `LanController.join(timeout=5)` and joins the headless mainloop at
   `init_tracker_server/runtime_host.py:496-527`; Uvicorn join is
   `init_tracker_server/host.py:199-225` via
   `dnd_initative_tracker.py:7973-7976`.
7. **What happens on join timeout?** A typed timeout is raised, the error and
   live worker/runtime reference remain observable, and no duplicate stop is
   launched (`init_tracker_server/runtime_host.py:267-316` and
   `init_tracker_server/host.py:211-218`). The worker can finish later and move
   the adapter to STOPPED (`init_tracker_server/runtime_host.py:281-298`).
8. **What prevents a second start?** FastAPI rejects concurrent lifespan entry
   and a previous still-owned runtime (`init_tracker_server/app.py:18-29`);
   `RuntimeHostAdapter` serializes startup, reuses the single RUNNING runtime,
   and forbids restart after STOPPED (`init_tracker_server/runtime_host.py:138-172`);
   Uvicorn host returns its already-created thread
   (`init_tracker_server/host.py:86-92`).
9. **What prevents a second stop from failing unpredictably?** Adapter stop is
   latched and `_stop_invoked` starts only one worker; STOPPED is a no-op
   (`init_tracker_server/runtime_host.py:228-279`). Uvicorn's request is latched
   and `should_exit` is delivered once (`init_tracker_server/host.py:190-197,
   232-244`). A prior deterministic stop error is re-raised rather than retried
   (`init_tracker_server/runtime_host.py:318-320`).
10. **What does `serve_headless.py` do in the default path?** It forces headless
    mode, preserves debugging configuration, constructs one compatibility
    tracker with legacy auto-start disabled, applies host/port, lets
    `HeadlessRuntimeHost` start LAN once, waits for ASGI readiness, registers
    SIGINT/SIGTERM cleanup, and runs the hosted headless loop
    (`serve_headless.py:103-158`).
11. **Does default-path code still independently construct
    `InitiativeTracker`?** Yes, exactly once through the factory at
    `serve_headless.py:121-123`. This is the intentional retained legacy
    authority/scheduler adapter, not a second `ServerRuntimeFacade`; its
    scheduled LAN auto-start is explicitly disabled.
12. **Does any tested shutdown path leave a live owned thread?** No successful
    shutdown path does. `tests/test_server_runtime.py:862-927,
    1079-1124,1372-1592` and `tests/test_headless_host.py:33-71,132-195` assert
    dead owned workers or a clean subprocess exit. Timeout-only tests at
    `tests/test_server_runtime.py:1215-1257,1594-1640` and
    `tests/test_server_host.py:312-335` deliberately observe the retained live
    reference, then release/join it and assert it dies where applicable.
13. **Which desktop or legacy path intentionally retains legacy ownership?**
    `dnd_initative_tracker.main()` at `dnd_initative_tracker.py:53666-53683`.
14. **Is Uvicorn lifecycle ownership distinct from authoritative runtime
    ownership?** Yes. `UvicornServerHost` owns one transport thread
    (`init_tracker_server/host.py:26-127`); FastAPI lifespan owns the facade
    (`init_tracker_server/app.py:16-71`).
15. **Are ownership boundaries explicit enough to avoid double-start and
    double-stop?** Yes, within milestone scope. The explicit one-shot adapter,
    lifespan-entry guard, disabled legacy LAN callback, Uvicorn thread latch,
    and idempotent stop latches are independently tested. Residual naming risk
    remains because `HeadlessRuntimeHost` calls the compatibility tracker a
    runtime, but the concrete ownership and reference boundaries are explicit.

## Completion criteria

### Criterion 1 - PASS

**Default headless/server-first path has one authoritative lifecycle owner.**

- Scope: technical milestone.
- Source: `init_tracker_server/app.py:16-71`; `serve_headless.py:121-130`;
  `dnd_initative_tracker.py:11152-11162`.
- Evidence: `tests/test_server_runtime.py:1372-1592` proves each ASGI lifespan
  constructs one facade/host, rejects concurrent entry, and the launcher passes
  `auto_start_lan=False` before starting LAN only through its host.
- Residual risk: the legacy tracker remains real authority for unextracted
  route/gameplay code, by design; that broader extraction is not this criterion.

### Criterion 2 - PASS

**FastAPI lifespan owns runtime-host start and shutdown.**

- Scope: technical milestone.
- Source: `init_tracker_server/app.py:16-71`.
- Evidence: `tests/test_server_health.py:106-141,143-215` and
  `tests/test_server_runtime.py:1372-1489,1594-1640` assert start, warm-up,
  shutdown ordering, error retention, and bounded stop from lifespan.
- Residual risk: none within the package runtime lifecycle contract.

### Criterion 3 - PASS

**Default `serve_headless.py` does not independently own a second authoritative
runtime.**

- Scope: technical milestone.
- Source: `serve_headless.py:118-130`; `init_tracker_server/app.py:35-55`;
  `dnd_initative_tracker.py:11156-11162`.
- Evidence: `tests/test_server_runtime.py:1491-1592` observes one compatibility
  tracker per invocation, `auto_start_lan=False`, and only one delegated LAN
  start. `tests/test_server_runtime.py:1421-1478` counts one ASGI adapter per
  lifespan.
- Residual risk: the launcher necessarily constructs the single retained
  `InitiativeTracker`; this does not create a second package runtime.

### Criterion 4 - PASS

**Exactly one authoritative runtime instance exists per lifespan.**

- Scope: technical milestone.
- Source: `init_tracker_server/app.py:18-55`;
  `init_tracker_server/runtime_host.py:138-226`.
- Evidence: `tests/test_server_runtime.py:734-860,1372-1478` asserts a single
  factory/start/warm-up invocation, identical runtime returned by duplicate and
  concurrent starts, concurrent lifespan rejection, and distinct single
  runtimes only across sequential lifespans.
- Residual risk: none within one lifespan/process.

### Criterion 5 - PASS

**Readiness is false before successful startup and required warm-up.**

- Scope: technical milestone.
- Source: `init_tracker_server/app.py:30-60`.
- Evidence: `tests/test_server_health.py:75-141,143-215` asserts false readiness
  through construct/start/warm-up and for each startup failure stage.
- Residual risk: none in the tested state contract.

### Criterion 6 - PASS

**Readiness becomes true only when runtime is usable.**

- Scope: technical milestone.
- Source: `init_tracker_server/app.py:35-60`;
  `dnd_initative_tracker.py:3060-3117`;
  `init_tracker_server/host.py:129-188`.
- Evidence: `tests/test_server_health.py:106-141`,
  `tests/test_server_runtime.py:1642-1783`, and
  `tests/test_server_host.py:136-157` prove facade start, tracker-thread cache
  warm-up, and ASGI-ready probe completion before serving readiness.
- Residual risk: static cache warm-up preserves the existing non-static fallback;
  broader snapshot/cache ownership remains open.

### Criterion 7 - PASS

**Startup or warm-up failure cleans partial state and leaves readiness false.**

- Scope: technical milestone.
- Source: `init_tracker_server/app.py:53-71`;
  `init_tracker_server/runtime_host.py:175-213`.
- Evidence: `tests/test_server_health.py:75-105,143-215` and
  `tests/test_server_runtime.py:929-1124,1259-1323,1785-1811` cover construct,
  start, warm-up, fallback, rollback, rollback failure, original-error
  preservation, and dead failure-cleanup worker.
- Residual risk: if rollback itself fails, the runtime reference is intentionally
  retained and state is FAILED for diagnosis rather than falsely declared clean.

### Criterion 8 - PASS

**Shutdown requests stop and performs a bounded join.**

- Scope: technical milestone.
- Source: `init_tracker_server/app.py:63-69`;
  `init_tracker_server/runtime_host.py:228-316,486-530`;
  `init_tracker_server/host.py:190-230`;
  `dnd_initative_tracker.py:7960-7976`.
- Evidence: `tests/test_server_host.py:246-335` and
  `tests/test_server_runtime.py:862-927,1215-1257,1325-1369,1594-1640` assert a
  single stop request, exact timeout values, bounded join, and typed timeout.
- Residual risk: a timed-out cooperative shutdown cannot be force-killed in
  process; it remains observable, which is the defined bounded behavior.

### Criterion 9 - PASS

**Successful shutdown leaves no owned authority, Uvicorn, scheduler, polling,
or helper thread alive.**

- Scope: technical milestone.
- Source: `init_tracker_server/runtime_host.py:281-305,486-530`;
  `init_tracker_server/host.py:199-225`;
  `dnd_initative_tracker.py:7960-7976,8601-8604`.
- Evidence: `tests/test_server_runtime.py:862-927,1079-1124,1372-1592`,
  `tests/test_server_host.py:246-285`, and
  `tests/test_headless_host.py:33-71,132-195` assert stopped state, cleared
  runtime, `_polling=False`, dead stop/mainloop workers, joined host, and clean
  real subprocess exit.
- Residual risk: the real subprocess acceptance uses `--no-auto-lan`; default
  auto-LAN/Uvicorn cleanup is proven with injected hosts plus host-level worker
  tests, not a manual persistent server or browser smoke.

### Criterion 10 - PASS

**Repeated start and stop are deterministic and do not duplicate ownership or
raise uncontrolled errors.**

- Scope: technical milestone.
- Source: `init_tracker_server/runtime_host.py:138-172,228-320`;
  `init_tracker_server/host.py:86-92,190-244`.
- Evidence: `tests/test_server_runtime.py:734-927,929-1257` and
  `tests/test_server_host.py:159-310` cover sequential and concurrent duplicate
  start/stop, start/stop races, stable errors, and exactly one worker/signal.
- Residual risk: adapters are intentionally one-shot; restart requires a new
  lifespan/adapter rather than reusing a stopped one.

### Criterion 11 - PASS

**Host, port, debugging, signal handling, auto-LAN, no-auto-LAN, and retained
desktop behavior remain compatible.**

- Scope: technical milestone compatibility.
- Source: `serve_headless.py:65-100,103-158`;
  `dnd_initative_tracker.py:11152-11162,53666-53683`.
- Evidence: `tests/test_server_runtime.py:1491-1592` asserts host/port,
  no-auto/default-auto delegation and cleanup; `tests/test_headless_host.py:132-195`
  runs the real no-auto launcher and sends SIGINT. The baseline/final diff shows
  debugging resolution and output setup preserved while ownership mechanics
  changed.
- Residual risk: the focused modules exercise `--no-debugging`, not every truthy
  environment/CLI debugging permutation; no desktop GUI or browser smoke was
  authorized.

### Criterion 12 - PASS

**HTTP, static/browser route inventory, readiness, and health contracts remain
compatible.**

- Scope: technical milestone compatibility.
- Source: `init_tracker_server/app.py:74-104`;
  `dnd_initative_tracker.py:3144-3168`.
- Evidence: `tests/test_server_health.py:11-73` verifies package and compatibility
  factories plus exact health/readiness status and payloads.
  `tests/test_server_runtime.py:95-175` verifies the exact browser entry route
  inventory and registrations; lines 522-689 verify representative HTTP
  snapshot success/error mappings. All focused tests passed.
- Residual risk: manual browser smoke was explicitly forbidden and was not run.

### Criterion 13 - PASS

**WebSocket, snapshot, command, and focused gameplay/runtime contracts covered
by the milestone test envelope remain green.**

- Scope: technical milestone compatibility; universal ownership is broader
  migration scope.
- Source: package lifecycle binding at `init_tracker_server/app.py:35-66` and
  `dnd_initative_tracker.py:3060-3117`; the compatibility assertions themselves
  provide the exact route/runtime contract evidence without auditing unrelated
  route bodies.
- Evidence: the exact four-module envelope passed `157` tests and `56` subtests.
  Representative assertions are `tests/test_server_runtime.py:438-689`
  (snapshot shape, visibility, HTTP mappings), `1813-2490` (runtime command and
  snapshot readiness contracts), `5932-6213` (queued command authority and
  response ordering), and `6900-7436` (WebSocket fanout, claims, turn/snapshot
  authority).
- Residual risk: only contracts already covered by the named focused modules are
  claimed; full-suite, browser, and production acceptance are not claimed.

### Criterion 14 - PASS

**All campaign implementation changes are traceable and lifecycle-scoped.**

- Scope: technical milestone.
- Source: final lifecycle seams cited above; Git range
  `99bf0a788975bcaa211ae844a52f9f65aef25958..5ad8beb375dec7211b681ce69b64c88c78268216`.
- Evidence: name-status contains exactly nine modified files:
  `dnd_initative_tracker.py`, `init_tracker_server/app.py`,
  `init_tracker_server/host.py`, `init_tracker_server/runtime_host.py`,
  `serve_headless.py`, and the four named focused test modules. Stat is 2,131
  insertions and 289 deletions. The ordered path-limited log contains the seven
  lifecycle commits listed above.
- Residual risk: `dnd_initative_tracker.py` remains a monolith, but its campaign
  delta is confined to runtime reference, warm-up, readiness, stop/join,
  polling, and auto-start compatibility seams.

### Criterion 15 - PASS

**Exactly eleven preserved untracked paths remain, with no additional path.**

- Scope: audit repository-integrity criterion.
- Source: not a source-code criterion; exact Git output is recorded in
  [Repository state](#repository-state).
- Evidence: `git ls-files --others --exclude-standard` returned the same exact
  eleven-path ordered set initially and after validation.
- Residual risk: none; the paths were not opened or altered.

### Criterion 16 - PASS

**The tracked target tree is clean at the final commit.**

- Scope: audit repository-integrity criterion.
- Source: not a source-code criterion; Git index/worktree evidence applies.
- Evidence: initial and post-validation
  `git status --short --untracked-files=no` and
  `git diff --cached --name-status` were empty; target HEAD matched exactly.
- Residual risk: creation and the required documentation-only commit necessarily
  occur after this audited-target cleanliness check and do not alter target
  application/test content.

### Criterion 17 - PASS

**No audit evidence claims production or topology readiness.**

- Scope: audit authorization boundary; deployment/production is broader scope.
- Source: this report's [Executive verdict](#executive-verdict),
  [Broader migration](#broader-migration), and
  [Actions not authorized](#actions-not-authorized) sections.
- Evidence: no push, deployment, service access/restart, production access,
  credential access, DNS, firewall, proxy, hostname, port/topology mutation, or
  browser smoke command was run.
- Residual risk: deployment and production readiness remain completely
  unassessed.

## Validation results

### Required compilation

Command:

```bash
python3 -m py_compile \
  serve_headless.py \
  server_app.py \
  dnd_initative_tracker.py \
  init_tracker_server/app.py \
  init_tracker_server/host.py \
  init_tracker_server/runtime_host.py \
  tests/test_headless_host.py \
  tests/test_server_health.py \
  tests/test_server_host.py \
  tests/test_server_runtime.py
```

Result: exit 0, no output, command duration `1.473s`.

### Required focused tests

Command:

```bash
timeout 600s .venv/bin/python -m pytest -q \
  tests/test_headless_host.py \
  tests/test_server_health.py \
  tests/test_server_host.py \
  tests/test_server_runtime.py
```

Result: exit 0; `157 passed, 56 subtests passed in 30.43s`.

- Passed tests: 157.
- Passed subtests: 56.
- Failed tests/subtests: 0.
- Skipped tests/subtests: 0.
- Errors: 0.
- Timeout: no; the process completed under the explicit 600-second bound.
- Bounded subprocess acceptance: the included headless subprocess test started
  the no-auto compatibility launcher, sent SIGINT, and asserted exit code 0.

### Required diff and state checks

- `timeout 10s git diff --check`: exit 0, no output, no timeout.
- `git status --short --untracked-files=no`: empty.
- `git diff --cached --name-status`: empty.
- `git ls-files --others --exclude-standard`: exactly the eleven preserved paths.

No full test suite, manual browser smoke, or persistent development server was
run.

## Process and thread cleanup evidence

- Successful adapter stop starts one `RuntimeHostStop` helper and joins it
  within the caller's bound (`init_tracker_server/runtime_host.py:267-305`).
  Tests assert this worker is not alive after successful stop at
  `tests/test_server_runtime.py:916-927,1453-1463,1571-1575`.
- Startup/warm-up rollback tests use real temporary workers and assert they are
  dead at `tests/test_server_runtime.py:1079-1124`.
- The headless scheduler is quit and joined within five seconds at
  `init_tracker_server/runtime_host.py:506-527`; real scheduler tests assert
  dead threads at `tests/test_headless_host.py:33-71`.
- LAN polling is disabled before Uvicorn stop at
  `dnd_initative_tracker.py:7960-7965`; rescheduling is conditional on polling
  at `dnd_initative_tracker.py:8601-8604`.
- Uvicorn stop uses a one-time `should_exit` delivery and bounded join at
  `init_tracker_server/host.py:190-244`; host tests assert the exact signal and
  join bounds at `tests/test_server_host.py:246-310`.
- Timeout tests do not claim successful cleanup. They prove that a live worker
  remains observable with a typed error, release it, then assert its eventual
  death/state transition at `tests/test_server_runtime.py:1215-1257,1594-1640`.

Therefore no tested successful shutdown leaves an owned authority, Uvicorn,
scheduler, polling, or lifecycle-helper thread alive.

## Commit-delta scope

Name-status for the complete campaign range:

```text
M dnd_initative_tracker.py
M init_tracker_server/app.py
M init_tracker_server/host.py
M init_tracker_server/runtime_host.py
M serve_headless.py
M tests/test_headless_host.py
M tests/test_server_health.py
M tests/test_server_host.py
M tests/test_server_runtime.py
```

Stat:

```text
dnd_initative_tracker.py            | 108 +++-
init_tracker_server/app.py          |  73 ++-
init_tracker_server/host.py         | 239 +++++++--
init_tracker_server/runtime_host.py | 444 ++++++++++++++--
serve_headless.py                   |  52 +-
tests/test_headless_host.py         | 132 +++---
tests/test_server_health.py         | 149 ++++++
tests/test_server_host.py           | 238 ++++++++-
tests/test_server_runtime.py        | 985 +++++++++++++++++++++++++++++++++---
9 files changed, 2131 insertions(+), 289 deletions(-)
```

The product-file delta establishes the one-shot lifecycle state machine,
lifespan construction/ownership, tracker-owner-thread warm-up, readiness probe,
bounded stop/join, single-start Uvicorn host, compatibility headless host, and
disabled legacy scheduled auto-start. The test delta adds direct failure,
concurrency, timeout, cleanup, and integration proofs. No unrelated campaign
path changed.

No `_lan_apply_action()` command branch was migrated or assessed by this audit;
that gameplay/command-dispatch area was outside the named lifecycle seams.

## Broader migration

These items do not fail this milestone:

| Item | Classification | Assessment |
| --- | --- | --- |
| Package ownership of all route registration and route bodies | Partially advanced; intentionally out of scope for completion | Package app/lifespan and browser registrar boundaries exist, but most route bodies are still registered inside legacy `LanController.start()`. |
| Host ownership of WebSocket sessions, claims, reconnect state, subscriptions, and fanout | Still open; intentionally out of scope | The lifecycle host does not own these registries; they remain in `LanController`. |
| Public accepted-command and status lifecycle | Partially advanced; intentionally out of scope | Internal facade command/status contracts exist and focused tests pass, but a universal public asynchronous accepted/status API was not delivered. |
| Snapshot/cache ownership | Partially advanced; intentionally out of scope | Lifespan now gates readiness on warm-up, while most snapshot/cache state remains legacy/controller/tracker-owned. |
| Universal write-side queue containment | Partially advanced; intentionally out of scope | Focused queue-backed command paths are green, but the milestone did not migrate every write route. |
| Process isolation or broker transport | Still open; intentionally out of scope | Runtime, tracker authority, Uvicorn, and scheduler remain in one process with threads. |
| Full route migration | Still open; intentionally out of scope | The campaign was lifecycle-only, not route-body extraction. |
| Deployment and production readiness | Still open and unassessed; intentionally out of scope | No production, topology, service, browser, or deployment action/evidence was authorized. |

None of these broader lanes is classified as completed by this milestone.

## Exact commands run

### Required initial commands

```bash
git branch --show-current
git rev-parse HEAD
git status --short --untracked-files=no
git diff --cached --name-status
git ls-files --others --exclude-standard
git log --oneline -12
```

### Baseline and required campaign-delta commands

```bash
git cat-file -e '99bf0a788975bcaa211ae844a52f9f65aef25958^{commit}'
git diff --name-status \
  99bf0a788975bcaa211ae844a52f9f65aef25958..5ad8beb375dec7211b681ce69b64c88c78268216
git diff --stat \
  99bf0a788975bcaa211ae844a52f9f65aef25958..5ad8beb375dec7211b681ce69b64c88c78268216
git log --reverse --format='%H %s' \
  99bf0a788975bcaa211ae844a52f9f65aef25958..5ad8beb375dec7211b681ce69b64c88c78268216 \
  -- \
  dnd_initative_tracker.py \
  init_tracker_server/app.py \
  init_tracker_server/host.py \
  init_tracker_server/runtime_host.py \
  serve_headless.py \
  tests/test_headless_host.py \
  tests/test_server_health.py \
  tests/test_server_host.py \
  tests/test_server_runtime.py
```

### Targeted inspection commands

Only named files and the authorized commit range were inspected. Commands used
were bounded `wc`, `rg`, `sed`, `nl`, `git show`, and `git diff` invocations:

```bash
rg -n '^#{1,6} .*([Aa]ctive|[Cc]ompleted|ASGI|[Ll]ifecycle|MILESTONE-20260718)' docs/work_items/current_work.md
sed -n '1,55p' docs/work_items/current_work.md
rg -n -i 'MILESTONE-20260718|ASGI[- ]owned|ASGI.*lifecycle|runtime lifecycle ownership|lifecycle owner' docs/work_items/current_work.md
sed -n '617,690p' docs/work_items/current_work.md
wc -l serve_headless.py init_tracker_server/app.py init_tracker_server/host.py init_tracker_server/runtime_host.py server_app.py dnd_initative_tracker.py tests/test_headless_host.py tests/test_server_health.py tests/test_server_host.py tests/test_server_runtime.py
rg -n '^class |^def |^    def |lifespan|runtime_host|RuntimeHost|InitiativeTracker|HeadlessRoot|LanController|warm|ready|shutdown|join|signal|uvicorn|auto_lan|no_auto' serve_headless.py init_tracker_server/app.py init_tracker_server/host.py init_tracker_server/runtime_host.py server_app.py
rg -n '^class InitiativeTracker|^class HeadlessRoot|^class LanController|^def |^    def (.*(start|stop|join|warm|ready|shutdown)|run_server|main)|InitiativeTracker\(|HeadlessRoot\(|LanController\(|warm|readiness|authority|schedule|shutdown|signal|serve_headless|headless' dnd_initative_tracker.py
rg -n '^class |^def test_|^    def test_|lifespan|runtime_host|authoritative|readiness|ready|warm|shutdown|stop|join|thread|signal|auto.lan|no.auto|uvicorn|websocket|snapshot|command|route' tests/test_headless_host.py tests/test_server_health.py tests/test_server_host.py tests/test_server_runtime.py
nl -ba serve_headless.py
nl -ba init_tracker_server/app.py
nl -ba init_tracker_server/host.py
nl -ba server_app.py
sed -n '1,200p' init_tracker_server/runtime_host.py | nl -ba -v1
sed -n '201,400p' init_tracker_server/runtime_host.py | nl -ba -v201
sed -n '401,560p' init_tracker_server/runtime_host.py | nl -ba -v401
rg -n '^class (InitiativeTracker|HeadlessRoot|LanController)\b' dnd_initative_tracker.py
rg -n 'UvicornServerHost|create_app\(|POC_AUTO_START_LAN|auto_start_lan|INIT_TRACKER_HEADLESS|HeadlessRoot|signal\.signal|def main\(|if __name__ == .__main__.' dnd_initative_tracker.py
rg -n '^    def (__init__|start|stop|join|warm_up|wait_until_ready|shutdown|mainloop|quit|destroy|_tick|_start_server|_stop_server)\b' dnd_initative_tracker.py
rg -n 'ready_check|app\.state\.ready|_runtime_facade|runtime.*ready|authority|after\([^\n]*_tick|_tick\)' dnd_initative_tracker.py
sed -n '2410,3170p' dnd_initative_tracker.py | nl -ba -v2410
sed -n '3035,3170p' dnd_initative_tracker.py | nl -ba -v3035
sed -n '7890,7995p' dnd_initative_tracker.py | nl -ba -v7890
sed -n '7900,7978p' dnd_initative_tracker.py | nl -ba -v7900
sed -n '8170,8215p' dnd_initative_tracker.py | nl -ba -v8170
sed -n '8575,8615p' dnd_initative_tracker.py | nl -ba -v8575
sed -n '11020,11185p' dnd_initative_tracker.py | nl -ba -v11020
sed -n '53635,53690p' dnd_initative_tracker.py | nl -ba -v53635
nl -ba tests/test_headless_host.py
nl -ba tests/test_server_health.py
nl -ba tests/test_server_host.py
rg -n 'RuntimeHost(Adapter|State|Lifecycle|Stop|Protocol)|HeadlessRuntimeHost|runtime_host|warm_up|stop_thread|stop_timed_out' tests/test_server_runtime.py
rg -n '^    def test_.*(runtime|start|stop|warm|ready|shutdown|join|thread|ownership|lifespan)|^def test_.*(runtime|start|stop|warm|ready|shutdown|join|thread|ownership|lifespan)' tests/test_server_runtime.py
sed -n '680,1000p' tests/test_server_runtime.py | nl -ba -v680
sed -n '1001,1325p' tests/test_server_runtime.py | nl -ba -v1001
sed -n '1120,1260p' tests/test_server_runtime.py | nl -ba -v1120
sed -n '1255,1375p' tests/test_server_runtime.py | nl -ba -v1255
sed -n '1326,1605p' tests/test_server_runtime.py | nl -ba -v1326
sed -n '1372,1495p' tests/test_server_runtime.py | nl -ba -v1372
sed -n '1491,1595p' tests/test_server_runtime.py | nl -ba -v1491
sed -n '1606,1820p' tests/test_server_runtime.py | nl -ba -v1606
sed -n '80,175p' tests/test_server_runtime.py | nl -ba -v80
sed -n '430,690p' tests/test_server_runtime.py | nl -ba -v430
sed -n '5920,6220p' tests/test_server_runtime.py | nl -ba -v5920
sed -n '6890,7065p' tests/test_server_runtime.py | nl -ba -v6890
sed -n '7290,7441p' tests/test_server_runtime.py | nl -ba -v7290
rg -n '^    def test_.*(route|static|browser|health|ready|endpoint|factory)|^def test_.*(route|static|browser|health|ready|endpoint|factory)' tests/test_headless_host.py tests/test_server_health.py tests/test_server_host.py tests/test_server_runtime.py
rg -n '^    def test_.*(websocket|snapshot|command|combat|gameplay|claim|reconnect|fanout)|^def test_.*(websocket|snapshot|command|combat|gameplay|claim|reconnect|fanout)' tests/test_server_runtime.py
rg -n 'serve_headless|--host|--port|--no-auto-lan|debugging|SIGINT|SIGTERM|signal' tests/test_headless_host.py tests/test_server_health.py tests/test_server_host.py tests/test_server_runtime.py
git show 99bf0a788975bcaa211ae844a52f9f65aef25958:serve_headless.py | nl -ba
git show 99bf0a788975bcaa211ae844a52f9f65aef25958:init_tracker_server/app.py | nl -ba
git show 99bf0a788975bcaa211ae844a52f9f65aef25958:init_tracker_server/host.py | nl -ba
git show 99bf0a788975bcaa211ae844a52f9f65aef25958:init_tracker_server/runtime_host.py | nl -ba
git show 99bf0a788975bcaa211ae844a52f9f65aef25958:server_app.py | nl -ba
git diff --unified=35 99bf0a788975bcaa211ae844a52f9f65aef25958..5ad8beb375dec7211b681ce69b64c88c78268216 -- dnd_initative_tracker.py
git diff --unified=25 99bf0a788975bcaa211ae844a52f9f65aef25958..5ad8beb375dec7211b681ce69b64c88c78268216 -- serve_headless.py init_tracker_server/app.py server_app.py
git diff --unified=20 99bf0a788975bcaa211ae844a52f9f65aef25958..5ad8beb375dec7211b681ce69b64c88c78268216 -- init_tracker_server/host.py
git diff --stat 99bf0a788975bcaa211ae844a52f9f65aef25958..5ad8beb375dec7211b681ce69b64c88c78268216 -- tests/test_headless_host.py tests/test_server_health.py tests/test_server_host.py tests/test_server_runtime.py
git diff --unified=0 99bf0a788975bcaa211ae844a52f9f65aef25958..5ad8beb375dec7211b681ce69b64c88c78268216 -- tests/test_headless_host.py tests/test_server_health.py tests/test_server_host.py tests/test_server_runtime.py | rg '^\+\s*(def test_|    def test_)|^-\s*(def test_|    def test_)'
```

The symbol inventories above were run only across the named implementation and
focused test files to locate lifecycle definitions before exact ranges were
read. No recursive repository scan was run.

### Required validation commands

The exact compilation, focused pytest, diff-check, and final state commands are
recorded in [Validation results](#validation-results).

## Files inspected and changed

Inspected:

- `docs/work_items/current_work.md`, limited to active/completed and matching
  lifecycle references.
- `serve_headless.py`.
- `init_tracker_server/app.py`.
- `init_tracker_server/host.py`.
- `init_tracker_server/runtime_host.py`.
- `server_app.py`.
- `dnd_initative_tracker.py`, limited to the named lifecycle seams and campaign
  delta.
- `tests/test_headless_host.py`.
- `tests/test_server_health.py`.
- `tests/test_server_host.py`.
- Lifecycle and compatibility assertions in `tests/test_server_runtime.py`.
- Baseline versions/diffs of the same authorized files.

Changed: only
`docs/planning/living_docs/asgi_runtime_lifecycle_ownership_completion_audit_20260719.md`.

No handler, dispatcher, contract, route, command branch, source file, or test was
introduced or changed. `majorTODO.md`, `current_work.md`, campaign records, and
`_lan_apply_action()` were not changed.

## Smallest next action

No milestone repair is needed. Accept this documentation-only audit commit. If
the broader migration continues, the smallest useful next authorized action is
a separate bounded planning/evidence task that maps `LanController`-owned
WebSocket sessions, claims/reconnect state, subscriptions, and fanout into an
explicit package host ownership contract without implementing that move in the
same pass.

## Actions not authorized

This audit did not modify application code or tests, repair findings, alter the
active ledger or campaign records, create c11, open another campaign, migrate
routes or WebSockets, change command or snapshot schemas, change gameplay,
commit source/test changes, push, deploy, access production, restart a service,
access credentials, run browser smoke, start a persistent development server,
or change DNS, proxy, firewall, hostname, port, or topology. It did not run Git
reset, restore, checkout, stash, clean, rebase, or amend.

The required local commit contains this report only and is not a deployment or
production-readiness artifact.

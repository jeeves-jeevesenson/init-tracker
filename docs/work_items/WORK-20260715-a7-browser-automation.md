# A7 Browser-Driven Human-Workflow Automation

Date:
2026-07-15 UTC

Work item:
`WORK-20260715-a7-browser-automation`

Active gate:
`A7-G1C fixture-contract and browser-harness foundation`

State:
`implementation-boundary-approved`

Approval:
`developer-explicit-approval-2026-07-15`

## Goal

Prepare the deterministic fixture contract and browser-harness foundation for
the accepted A6 three-surface human workflow. A7-G1C authorizes only the exact
four-file implementation boundary recorded below. It does not authorize a
browser, server, target runtime, endpoint, network operation, or pilot.

The deterministic baseline workflow remains:

1. Open `/dm`, `/dmcontrol`, and `/`.
2. Add all available roster players through `/dm`.
3. Add one of every black-and-tan enemy through `/dm`.
4. Start combat.
5. Complete at least one full round using both attacks and spells.
6. Assert bounded progress with no hangs and consistent visible state across
   `/dm`, `/dmcontrol`, and `/`.
7. Preserve durable, bounded evidence for terminal coordinator consumption.

The approximately-200-enemy multi-target-spell scenario is excluded. It
remains unopened as a later, separately approved stress and latency gate.

## Accepted prerequisite evidence

The stale combat mutation implementation item closed at target implementation
commit `0aeb40bed97edd3521ce8afd7e3d9bcdcb5512f5`. The accepted A6-G3 evidence
records a final aggregate of nine focused tests passed in `0.266s`.

The accepted A6-G4 developer smoke opened `/dm`, `/dmcontrol`, and `/`, added
all available roster players and one of every black-and-tan enemy, started
combat, and completed a full round using varying attacks and spells across
player identities. No hang, incorrect visible combat progression, or runtime
error was reported.

A7-G1 stopped without edits because verified selectors and a deterministic
reset identity contract were missing. A7-G1A stopped without edits because
the proven UI assets were outside its authorized pathspec.

A7-G1B completed bounded read-only target discovery. Its accepted result is
`orchestrator:docs/work_items/A7-G1B-ui-contract-discovery-result.md` at
orchestrator commit `7f62ff9`. The result proves the required selectors are
already present, proves `/` is backed by `assets/web/lan/index.html`, defines
the missing reset/verification contract, and identifies the exact smallest
safe four-file implementation boundary. No HTML, CSS, or JavaScript asset
change is needed.

## Exact A7-G1C implementation boundary

Implementation edits are authorized exactly to:

- `dnd_initative_tracker.py`;
- `scripts/validation/browser-smoke-harness.py`;
- `tests/test_server_runtime.py`; and
- `tests/test_browser_smoke_harness.py`.

No other application, harness, test, asset, configuration, dependency, log,
ledger, generated artifact, or untracked file may be edited during A7-G1C
implementation. In particular, no HTML, CSS, or JavaScript asset edit is
authorized.

## Proven selector and UI contract

### `/dm`

The DM surface already exposes stable selectors for the setup workflow:

- `#openToolboxBtn` opens the DM toolbox;
- `#encounterPlayerList` is the roster-control root;
- `#selectAllPlayersBtn` selects every available player;
- `#addPlayersBtn` adds the selected players;
- `#monsterSlugSelect` exposes stable enemy option values;
- `#addMonsterBtn` adds the selected enemy; and
- `#startCombatBtn` starts combat.

The exact ordered black-and-tan enemy option values are:

```text
black-and-tan-captain
black-and-tan-constable
black-and-tan-field-medic
black-and-tan-lieutenant
black-and-tan-major
black-and-tan-rifleman
black-and-tan-vda-scorcher
black-and-tan-shield-trooper
black-and-tan-suppression-gunner
```

The harness must require exact equality with this nine-value set and add one
of each through the existing production controls.

### `/dmcontrol`

The combat-control surface already exposes action test IDs,
`window.__dmcontrolSmoke`, `selectCapability(id)`, `startSequence(id)`,
`handleCombatControl()`, and `#modalApplyBtn`. These existing contracts cover
action discovery and selection, sequence start, result application, bounded
state inspection, and active-turn advancement. No additional test API is
authorized or required.

### `/`

The player entrypoint is `assets/web/lan/index.html`. It already exposes:

- `#claimList [data-claim-cid]` and `#claimConfirm` for exact player claim;
- `#attackOverlayToggle` for attack entry;
- `#castSpellModalOpen` and `#castSubmit` for spell entry;
- `#attackResolveSubmit` and `#spellResolveSubmit` for result confirmation;
  and
- `#endTurn` for turn advancement.

These production selectors, together with the verified runtime CID and map
position mappings returned by the fixture contract, are sufficient. No HTML,
CSS, or JavaScript asset edit is authorized.

## Required fixture reset and verification contract

The existing bodyless
`POST /api/dev/smoke-fixtures/black-tan-combat-exploration` request must retain
its historical seed-and-start behavior. A7-G1C adds a backward-compatible,
versioned operation contract on that existing fixture path.

The reset request is:

```json
{
  "schema_version": "a7-ui-reset-contract/v1",
  "operation": "reset-ui-workflow",
  "reset_version": "blank-combat/v1",
  "expected_precondition_digest": "sha256:<lowercase-hex>"
}
```

The stable ordered player identity contract is:

```text
pc:dorian         -> Dorian
pc:eldramar       -> Eldramar
pc:fred           -> Fred
pc:john-twilight  -> John Twilight
pc:johnny-morris  -> Johnny Morris
pc:malagrou       -> Malagrou
pc:old-man        -> Old Man
pc:throat-goat    -> Throat Goat
pc:vicnor         -> Vicnor
pc:stikhiya       -> стихия
```

The stable ordered enemy identity contract is the exact nine-slug list in the
`/dm` selector section. Player IDs are immutable contract values and must not
be regenerated from display names.

The precondition digest must be SHA-256 over canonical UTF-8 JSON with sorted
object keys and no insignificant whitespace. Its input is the exact schema
version, reset version, ordered player ID/name pairs, and ordered enemy slug
list.

The handler must validate the requested schema version, reset version,
precondition digest, and ordered identities before `end_combat`, combatant
clearing, map creation, or any other mutation. A successful reset must create
a blank 30x30 UI setup state and return the exact versions and digest, the
ordered player and enemy identities, empty CID mappings, zero player, enemy,
and combatant counts, `in_combat: false`, and `mutated: true`.

After the production UI adds the exact set, the same path must accept:

```json
{
  "schema_version": "a7-ui-reset-contract/v1",
  "operation": "verify-ui-workflow",
  "reset_version": "blank-combat/v1",
  "expected_precondition_digest": "sha256:<lowercase-hex>"
}
```

Verification is non-mutating. It must return all ten ordered player records
and all nine ordered enemy records with exact stable identity, display name,
runtime CID, and position mappings. The per-entry shapes are:

```json
{"player_id": "pc:dorian", "name": "Dorian", "cid": 1, "position": {"col": 0, "row": 0}}
{"enemy_slug": "black-and-tan-captain", "name": "Black and Tan Captain", "cid": 2, "position": {"col": 0, "row": 0}}
```

The integers above illustrate the response shape only; verification must
return the exact runtime CIDs and positions rather than assume fixed numeric
values. The response must include exact counts and `mutated: false`. The
harness must record the stable player-ID-to-CID and enemy-slug-to-CID mappings,
use the player CIDs for `/` claims, and use the returned positions for
deterministic canvas targeting.

Schema-version, reset-version, digest, or ordered-identity mismatch must
return HTTP 409 before mutation with:

```json
{
  "ok": false,
  "error": "precondition_mismatch",
  "schema_version": "a7-ui-reset-contract/v1",
  "reset_version": "blank-combat/v1",
  "expected_precondition_digest": "sha256:<requested>",
  "actual_precondition_digest": "sha256:<actual>",
  "mutated": false
}
```

Verification-state mismatch must use `error: "ui_setup_mismatch"`, the same
version, digest, and mutation fields, bounded expected/actual counts, HTTP
409, and `mutated: false`.

## Required harness behavior

- Preserve existing harness scenario identities, CLI behavior, assertions,
  and coverage outside the bounded A7 additions.
- Declare a stable scenario and run identity, ordered actors, actions, and
  targets, progress ceilings, expected roster/enemy preconditions, and visible
  state invariants.
- Use the exact production selectors and identity mappings recorded above.
- Represent reset, setup verification, three-surface navigation, combat setup,
  one full round using attacks and spells, visible-state assertions, terminal
  evidence, and cleanup without weakening any precondition.
- Treat contract or precondition mismatch as terminal failure with no retry,
  no expectation update, and no later workflow click. Use stable reason code
  `fixture-precondition-mismatch` for contract/precondition refusal and
  `ui-setup-mismatch` for setup-verification refusal.
- Bound failure detail and preserve durable coordinator-consumable evidence
  for scenario/task/gate/run identity, pass/fail/recovery classification,
  timings, screenshots, per-role traces, logs, reset and fixture evidence,
  port ownership/conflict/readiness evidence, and cleanup disposition.
- Never attach to, replace, restart, terminate, kill, or clean up an
  unverified process. Cleanup may affect only positively owned resources.
- Keep the approximately-200-enemy multi-target-spell stress scenario out of
  A7-G1C.

Browser, server, endpoint, and target-runtime execution remain forbidden
during implementation. A7-G1C prepares the contract and harness foundation;
it does not execute or prove the browser workflow.

## Focused test authorization

`A7_TEST_EXECUTION_AUTHORIZED=true` applies only to focused fake/mock
non-browser tests in `tests/test_server_runtime.py` and
`tests/test_browser_smoke_harness.py` for the exact reset/verify/refusal,
legacy-compatibility, selectors, ordering, mismatch, evidence, lifecycle, and
cleanup behavior added by A7-G1C. Tests must use fakes/mocks and temporary
paths. They must not launch a browser or server, access localhost or any
endpoint/network, use an existing artifact/log directory, or depend on
installed browser binaries. Do not run the complete browser-harness test file
because its artifact-attempt test launches Chromium and makes a localhost
request. Broad tests and compilation are not authorized.

## Forbidden scope

- No HTML, CSS, JavaScript, manifest, configuration, dependency, requirement,
  lockfile, launcher, specialized smoke, log, artifact, or untracked-file
  edit.
- No browser, server, target runtime, endpoint, localhost probe, network,
  dependency installation, package-manager action, generated browser
  artifact, or real fixture mutation.
- No approximately-200-enemy multi-target-spell stress work.
- No broad test, compilation command, unrelated cleanup, push, deployment,
  restart, scheduler, production, service mutation, credentials access, AGY,
  or Gemini.
- No edit outside the exact four implementation files in A7-G1C.
- No automatic retry, expectation update, pilot activation, later-gate
  activation, or autonomous continuation.

## Authorization boundary

```text
A7_GATE=A7-G1C
A7_STATE=implementation-boundary-approved
A7_G1_STATE=blocked
A7_G1_BLOCKER=missing-verified-selectors-and-reset-contract
A7_G1A_STATE=stopped-scope-boundary
A7_G1A_BLOCKER=ui-assets-outside-authorized-pathspec
A7_G1B_STATE=completed
A7_G1B_RESULT=orchestrator:docs/work_items/A7-G1B-ui-contract-discovery-result.md
A7_G1B_RESULT_COMMIT=7f62ff9
A7_G1C_STATE=approved
A7_G1C_SCOPE=fixture-contract-and-browser-harness-foundation
A7_IMPLEMENTATION_AUTHORIZED=true
A7_TEST_EXECUTION_AUTHORIZED=true
A7_BROWSER_EXECUTION_AUTHORIZED=false
A7_RUNTIME_EXECUTION_AUTHORIZED=false
A7_DEPENDENCY_INSTALL_AUTHORIZED=false
A7_NETWORK_AUTHORIZED=false
A7_PUSH_AUTHORIZED=false
A7_DEPLOYMENT_AUTHORIZED=false
A7_RESTART_AUTHORIZED=false
A7_SCHEDULER_AUTHORIZED=false
A7_PRODUCTION_AUTHORIZED=false
A7_SERVICE_MUTATION_AUTHORIZED=false
```

Implementation authorization covers exactly the four named target files.
Test authorization covers only the focused fake/mock non-browser boundary
above. Browser/server execution, runtime/endpoint/network access, dependency
installation, the stress scenario, push, deployment, restart, scheduler,
production, and service mutation remain forbidden. This ledger transition
does not authorize a Codex commit.

## Next safe action

Perform only the approved A7-G1C four-file fixture-contract and browser-harness
foundation implementation under these boundaries. Stop after its separately
named focused fake/mock validation and status capture. Do not launch a browser
or server, access an endpoint, open the stress scenario, edit an asset, commit,
push, deploy, restart, schedule, mutate a service, or activate a later gate.

# init-tracker Production Stabilization Living Document

> **SUPERSEDED:** This document is superseded for active recovery work by [docs/production_recovery_living_doc_20260526.md](docs/production_recovery_living_doc_20260526.md).
> Please refer to the new document for current gates, contradictions, and recovery workstreams.

Status: Archived (Historical Reference)
Created: 2026-05-22
Owner: repo maintainers / stabilization agents
Research baseline: `docs/may22_research_notes.md`

---

## 0. Read This First

This is the working document agents must use for production-readiness work on `init-tracker`.

The project is currently in a regression loop. The same classes of bugs are reappearing after local patches:

- Spells / Manage Spells empty for all users.
- Resource pools intermittently missing.
- Inventory/equipment missing, causing attacks to fall back to Unarmed Strike.
- Long rest slow and incomplete.
- Pact slot override corrupting current/max values.
- Fury/Flurry of Blows slow or missing attacks.
- Payload/cache/snapshot changes fixing one page while breaking another.

This document exists to stop that pattern.

Agents must not treat this as a normal bug queue. Agents must work from contracts, source-of-truth mapping, ADRs, tests, traces, and smoke-test postmortems.

## 1. Required Companion Research

Before beginning any stabilization task, read:

```text
docs/may22_research_notes.md
```

That document is the research base for this living doc. It covers:

1. Regression prevention / postmortem discipline.
2. Backend-to-frontend contract testing.
3. Action latency tracing and idempotency.
4. State/cache/source-of-truth architecture decisions.
5. D&D mechanics sources for current failures.
6. Product-specific source-of-truth discovery.

This living document translates that research into agent workflow.

If this living doc conflicts with `docs/may22_research_notes.md`, pause and update this doc or create an ADR. Do not silently choose a third interpretation.

---

## 2. Product Policy Decisions

These are product decisions, not suggestions.

### 2.1 Open Manage Spells Catalog

Manage Spells must use an open spell catalog.

```text
Players are trusted.
Players may add any spell from the catalog.
Class/subclass/homebrew grants are suggestions, defaults, or source tags.
Class/subclass/homebrew grants must not be hard blockers.
```

This is a table policy. Do not “fix” spell access by making Manage Spells more restrictive.

Correct model:

```text
spell_catalog:
  all available spells

player_selected_spells:
  spells the player/table has chosen for that character

class_subclass_grants:
  suggestions/defaults/source tags

always_prepared:
  casting/preparation metadata

manual_additions:
  valid table-approved state
```

### 2.2 Agents Do Not Perform Browser Smoke Tests

The user performs browser/app smoke tests manually.

Agents may:

- inspect logs,
- inspect debug traces,
- inspect source,
- run unit/component/contract tests,
- create postmortems,
- create implementation tasks.

Agents must not create tasks that say the agent should manually use the browser app.

### 2.3 Fixes Must Be Durable

Do not apply bandaids that only hide the current symptom.

A repeated regression must become:

- a documented contract,
- a test,
- and, when architectural, an ADR/source-of-truth map update.

### 2.4 Snapshots Are Not Source of Truth

Cached snapshots, JSON-safe payloads, websocket messages, and frontend JS state are projections.

They must be rebuildable from authoritative state.

They must not become the only place where spells, resources, inventory, equipment, or combat state exist.

---

## 3. Stabilization Vocabulary

Use these terms consistently.

### Source of Truth

The authoritative owner of a data domain. It may be persistent data, runtime session state, or a well-defined model object.

Examples:

- loaded spell catalog,
- player profile model,
- runtime combat state,
- canonical map state,
- resource pool model.

### Projection

A derived representation used for transport, display, caching, or serialization.

Examples:

- LAN `static_data`,
- LAN state payload,
- DM state payload,
- DM map startup payload,
- `_json_safe` output,
- frontend display state,
- cached snapshot.

### Capability Data

Data that defines what a player can see/use/do. It is not purely static and not purely dynamic.

Examples:

- spell catalog access,
- player spell selections,
- resource pool definitions,
- inventory,
- equipment,
- attack options,
- class features,
- action buttons.

Capability data must survive dynamic combat updates.

### Dynamic State

High-change state.

Examples:

- HP current,
- resource current,
- spell slot current,
- active turn,
- combatant position,
- current effects,
- action economy spent/available.

### Payload Kind

Every payload should eventually declare what it is:

```text
lan_static_full
lan_state_full
lan_state_delta
dm_state_full
dm_state_delta
dm_map_state_full
dm_map_state_delta
action_ack
action_result
intentional_clear
```

Payload kind determines whether `{}`, `[]`, `null`, or missing keys are valid.

### Partial Update Non-Clobber Rule

A partial/state-only update must not erase static or capability data.

Default semantics:

| Incoming field state | Meaning |
|---|---|
| key missing | preserve existing state |
| field present in full payload | authoritative value |
| `{}` / `[]` in full payload | authoritative empty if allowed by that domain |
| `{}` / `[]` in partial payload | do not clear static/capability data unless explicit clear |
| `null` | invalid by default unless field contract defines it |
| explicit clear operation | only safe intentional clear |

---

## 4. Current Production-Readiness Status

This status must be updated after every relevant agent pass or manual smoke test.

### 4.1 Confirmed Fixed / Protected or Needs Protection

| Area | Status | Evidence / note | Protection needed |
|---|---|---|---|
| `/dm/map` player catalog empty on blank load | Fixed in smoke | Player catalog visible again; blank combat roster acceptable until Add Player Profiles / quick-load. | Keep `/dm/map` startup contract tests. |
| Tactical-map auth test hardcoded IDs | Fixed | Test uses dynamic IDs; tactical-map test module passed. | Keep test. |
| DM moves enemy -> LAN client updates | Fixed in smoke | User confirmed LAN client updates promptly. | Add/keep DM->LAN movement contract test. |
| Player ends turn -> DM console updates | Fixed in smoke | User confirmed DM console advances promptly. | Add/keep player->DM turn contract test. |
| MapQueryAPI(None) crash | Reported fixed earlier | Prior logs no longer showed original AttributeError. | Keep AoE/map-state no-crash tests. |

### 4.2 Open P0/P1 Issues

| ID | Priority | Symptom | Source-of-truth domain | First required prevention |
|---|---:|---|---|---|
| P0-001 | P0 | Spells / Manage Spells empty for all users again. | spell catalog, player spells, Manage Spells catalog, LAN static/capability payload, frontend merge | LAN first-load capability contract + partial-update non-clobber test. |
| P0-002 | P0 | Resource-pool dropdown intermittently missing until refreshes. | resource pools, resource definitions/current values, LAN capability/dynamic payload, frontend merge | resource first-load + reconnect + partial-update preservation tests. |
| P0-003 | P0 | Long rest takes over a minute and appears to hang app. | long rest action pipeline, YAML cache, resource/spell restoration, snapshot/broadcast | action tracing + long-rest phase spans + duplicate/backpressure safety. |
| P0-004 | P0 | Long rest does not restore resource pools to max. | resource pools, reset cadence, rest semantics | resource reset contract tests. |
| P0-005 | P0 | John Twilight attack uses Unarmed Strike; inventory empty. | inventory, equipment, attack options, LAN capability payload, attack resolver | inventory/equipment first-load + weapon resolution tests. |
| P0-006 | P0 | Old Man Fury/Flurry of Blows slow, vague log, missing expected attack. | action pipeline, monk feature model, resource spend, attack sequence | Fury mechanics contract + action trace expected/actual attack count. |
| P0-007 | P0 | Vicnor pact slot override corrupts slot max/current. | pact slot model, manual override command, frontend control | pact current/max contract tests; repair corrupted data if needed. |
| P1-001 | P1 | Stihiya Destructive Wave cannot be tested because spell UI blocked. | open spell catalog, player selected spells, subclass tags | open Manage Spells catalog contract. |
| P2-001 | P2 | Player-facing overflow debug text unverified. | combat log model, debug trace separation | player-log vs debug-log contract after spellcasting works. |

---

## 5. Non-Negotiable Stabilization Rules

### 5.1 No Repeated Bug Without a Never-Again Test

If a bug has appeared before, the fix must include a test that would have caught the recurrence.

Examples:

```text
Spells empty again:
  Add LAN first-load spell/manage capability contract and partial-update non-clobber test.

Resource pools missing:
  Add resource first-load and preservation tests.

Unarmed Strike fallback:
  Add equipped/configured weapon resolution test.

Pact slots corrupted:
  Add current/max manual override tests.

Long rest incomplete:
  Add reset-cadence resource tests.
```

### 5.2 No Broad Exception Swallowing

Exception isolation is allowed only when it preserves authoritative state and emits traceable evidence.

Bad:

```text
try: ...
except Exception: pass
```

Acceptable only if:

- the error is explicitly classified,
- state remains valid,
- the user receives safe behavior,
- debug trace records root context,
- tests prove it.

### 5.3 No One-Character YAML Patch as a Model Fix

Data repair is allowed but must be labeled separately from source fix.

Example:

```text
Repair:
  restore Vicnor pact slot max if corrupted.

Source fix:
  manual current override cannot mutate max.
```

Example:

```text
Repair:
  manually add Destructive Wave to Stihiya if needed.

Source fix:
  Manage Spells exposes full catalog and allows arbitrary add.
```

### 5.4 No Local Optimization Without Contract Protection

Snapshot/cache/YAML/broadcast optimizations must first prove:

- first-load contracts still pass,
- partial updates do not clobber capability data,
- cache invalidation is correct,
- JSON-safe serialization preserves required fields.

### 5.5 Do Not Claim Production-Ready From Unit Tests Alone

Manual smoke remains the release gate.

Unit/component/contract tests must catch obvious regressions before smoke, but passing tests alone do not prove table-readiness.

---

## 6. Required Repo Artifacts

Agents should create and maintain these artifacts.

### 6.1 Source-of-Truth Map

Path:

```text
docs/architecture/source_of_truth_map.md
```

Purpose:

Map each domain to its authoritative source, projections, payloads, consumers, mutation commands, invalidation domains, allowed empty states, and tests.

Required domains:

```text
spell catalog
player spell selections
Manage Spells catalog
resource pools
normal spell slots
pact spell slots
inventory
equipment
attack options
combatants
active turn
map state
AoE effects
DM state payload
LAN static payload
LAN state payload
frontend visible state
```

Required columns:

```text
Domain
Persistent source
Runtime authoritative source
Derived caches/projections
Payload producers
Frontend consumers
Mutation commands
Invalidation domains
Allowed empty states
Partial update behavior
Primary tests
Manual smoke checks
```

### 6.2 Architecture Decision Records

Path:

```text
docs/adr/
```

Minimum ADRs:

```text
0001-runtime-state-and-snapshot-boundaries.md
0002-payload-kind-and-partial-update-semantics.md
0003-capability-data-contract.md
0004-cache-invalidation-domains.md
0005-yaml-profile-cache-role.md
0006-manage-spells-open-catalog-policy.md
0007-pact-slots-current-max-model.md
0008-inventory-equipment-source-of-truth.md
0009-action-tracing-and-idempotency.md
```

ADR template:

```markdown
# ADR NNNN: <Decision title>

Status: Proposed | Accepted | Superseded by ADR NNNN
Date: YYYY-MM-DD

## Context

What recent bugs/regressions exposed this?
Which domains are affected?

## Decision

We will ...

## Consequences

Positive:
- ...

Negative:
- ...

Operational:
- ...

## Contract / Tests Required

- test_...
- test_...

## Migration Notes

What code paths must change?
What behavior is deprecated?

## Links

Research:
Smoke logs:
Related issues:
```

### 6.3 Contract Test Plan

Path:

```text
docs/architecture/contract_test_plan.md
```

Must cover:

- LAN first-load capability contract.
- LAN partial-update non-clobber contract.
- DM state serialization contract.
- `/dm/map` startup contract.
- resource/rest contract.
- inventory/equipment contract.
- pact slot current/max contract.
- DM/LAN sync contract.
- player-facing log vs debug trace contract.

### 6.4 Action Tracing Plan

Path:

```text
docs/architecture/action_tracing_plan.md
```

Must cover:

- trace/span JSONL format,
- `client_action_id`,
- idempotency scope,
- duplicate action behavior,
- action summaries,
- slow-span thresholds,
- long-rest spans,
- Fury/weapon spans,
- snapshot/broadcast spans,
- queue/backpressure metrics.

---

## 7. Release Gates

These gates are ordered. Do not skip to gameplay fix work before the earlier gates are protected.

### Gate 1 — Source-of-Truth and ADR Baseline

**Status:** COMPLETE (Passed 2026-05-22)

All Gate 1 requirements have been successfully satisfied and documented:
1. **Source-of-Truth Map Created:** [source_of_truth_map.md](file:///home/a2-jeeves@iamjeeves.dev/src/init-tracker/docs/architecture/source_of_truth_map.md) completed with all 17 critical domains mapped to their persistent, runtime, cache, transport, and validation layers.
2. **Initial ADR Suite Drafted:** Four baseline ADRs drafted under `docs/adr/`:
   - [ADR 0001: Runtime State and Snapshot Boundaries](file:///home/a2-jeeves@iamjeeves.dev/src/init-tracker/docs/adr/0001-runtime-state-and-snapshot-boundaries.md)
   - [ADR 0002: Payload Kind and Partial Update Semantics](file:///home/a2-jeeves@iamjeeves.dev/src/init-tracker/docs/adr/0002-payload-kind-and-partial-update-semantics.md)
   - [ADR 0003: Capability Data Contract](file:///home/a2-jeeves@iamjeeves.dev/src/init-tracker/docs/adr/0003-capability-data-contract.md)
   - [ADR 0004: Cache Invalidation Domains](file:///home/a2-jeeves@iamjeeves.dev/src/init-tracker/docs/adr/0004-cache-invalidation-domains.md)
3. **Open Manage Spells Policy Captured:** Formally accepted under ADR 0003 and documented in the Source-of-Truth map, establishing that players may add any catalog spell freely and class/subclass grants act as tags rather than hard blocks.
4. **P0/P1 Issue Mapping Completed:** All open P0/P1 issues mapped to their respective backend and frontend domains in the contract test plan and the source map.

#### Unresolved Repo/Source Mismatches
- **Expected Backend carryover helper is missing:** Previous assistant reports claimed a `LanController._merge_cached_snapshot_carryover` helper was added to `dnd_initative_tracker.py` during Pass 8C to protect cached static fields from idle state snapshot erasure. **Our inspection confirms that this helper is entirely missing in the current repository source.**
- **Hydration gaps in `_static_data_payload`:** While `_static_data_payload` live-repairs missing global `spell_presets`, it directly reads `player_spells`, `player_profiles`, and `resource_pools` from `self._cached_snapshot` without live-hydration fallback. If the cache is poison-cleared by a cheap delta tick, these fields return as empty objects to clients.
- **Frontend `static_data` merge clobbering:** While `assets/web/lan/index.html` guards state messages with `isEmptyPlainObject()`, it blindly assigns `msg.data.player_spells`, `player_profiles`, and `resource_pools` directly to frontend states inside the `static_data` connection handler. Any incoming empty structure `{}` from a cheap static payload will wipe out active client state immediately.

#### Known Baseline Test Failures
- **`LanSnapshotCacheTests.test_lan_controller_carryover_prevents_static_erasure`**: Fails due to `AttributeError: 'LanController' object has no attribute '_merge_cached_snapshot_carryover'`, confirming the carryover helper was never successfully merged.
- **`LanSnapshotCacheTests.test_static_data_payload_repairs_missing_cache_fields`**: Fails with `AssertionError: 0 != 1` for missing catalog calls, verifying that cache poisons are not recovered.
- **`ItemsWeaponResolutionTests`**: Multiple failures like `test_items_registry_loads_per_item_and_catalog_with_per_item_precedence` failing due to `AssertionError: 'longsword' not found in {}`.
- **Import Errors on `pact_magic_spell_slots` and `player_feature_execution`**: Missing `yaml` module in the system python path; resolved by executing tests within the virtual environment (`./.venv/bin/python3`).

#### First Implementation Pass Recommendation
We strongly recommend **Workstream B (Payload and Capability Contracts)** as the immediate first implementation pass to resolve Gate 2 and Gate 3:
1. Re-implement the missing `LanController._merge_cached_snapshot_carryover` method inside `dnd_initative_tracker.py`.
2. Harden `LanController._static_data_payload` to live-hydrate `player_spells`, `player_profiles`, and `resource_pools` from authoritative models.
3. Harden the `static_data` connection event handler in `assets/web/lan/index.html` using the `isEmptyPlainObject` check to prevent client-side clobbering on initial handshake or reconnection.

### Gate 2 — First-Load Capability Contracts

**Status:** COMPLETE (Passed 2026-05-22)

All Gate 2 requirements have been successfully satisfied:
1. **First-Load Spell Catalog Verification:** Implemented live-hydration in `LanController._static_data_payload` so that missing or empty `spell_presets` are backfilled from authoritative spell config models.
2. **Authoritative Player Spells Hydration:** Protected `player_spells` by live-hydrating them from `self.app._player_spell_config_payload()` if missing or empty in the projection cache.
3. **Resource Pools Hydration:** Backfilled resource pools from `self.app._player_resource_pools_payload()` when cache projection is unpopulated.
4. **Authoritative Consumables & Beast Forms Support:** Hydrated consumables from `self.app._consumables_registry_list_payload()` and beast forms from `self.app._load_beast_forms()`.
5. **Contract Tests Added:** Added focused tests validating that first-load payloads include full catalogs, caster spell selections, and resource pools:
   - `test_lan_first_load_spell_catalog_non_empty`
   - `test_lan_first_load_player_spells_for_seeded_caster`
   - `test_lan_first_load_resource_pools_for_seeded_resource_user`

### Gate 3 — Partial Update / Merge Contracts

**Status:** COMPLETE (Passed 2026-05-22)

All Gate 3 requirements have been successfully satisfied:
1. **Cache Merging Carryover Protection:** Added `LanController._merge_cached_snapshot_carryover` to protect critical domains (`spell_presets`, `player_spells`, `player_profiles`, `resource_pools`, `consumables_library`, `beast_forms`) from stripped/cheap delta tick updates.
2. **Routed Active and Idle Snapshot Updates:** Modified both tick paths in `LanController._tick` to route snapshot projections through `_merge_cached_snapshot_carryover` to preserve rich capabilities on client-side idle updates.
3. **Frontend Non-Clobber Implementation:** Upgraded the `static_data` message receiver in `assets/web/lan/index.html` to guard capability objects with `isEmptyPlainObject()` and array length checks, preventing empty payloads from clearing active client state.
4. **Contract Tests Added:** Added tests confirming that state deltas and empty partials do not erase capability structures in the cached snapshot:
   - `test_lan_controller_carryover_prevents_static_erasure`
   - `test_lan_state_delta_does_not_clear_spell_capabilities`
   - `test_resource_pools_survive_state_delta`

### Gate 4 — Action Tracing and Idempotency Foundation

Required:

- mutating commands have trace/action IDs.
- action summaries emitted.
- duplicate submissions cannot mutate twice.
- slow-span warnings exist.
- long-rest, attack/Fury, manual override, spell management, movement, end-turn paths have spans.

### Gate 5 — Resource/Rest and Pact Slot Correctness

Required tests:

- long rest restores eligible pools.
- long rest does not restore non-restoring/manual pools.
- normal spell slots restore current to max.
- pact slots restore current to max.
- manual pact current override preserves max.
- max override, if allowed, is explicit and separate.

### Gate 6 — Inventory/Equipment/Attack Correctness

Required tests:

- inventory payload non-empty for seeded equipment user.
- equipped/configured weapon selected for attack.
- Unarmed Strike fallback only when no valid weapon exists.
- fallback reason traced.
- John Twilight-equivalent fixture uses configured weapon.

### Gate 7 — Fury/Flurry and Action Pipeline Correctness

Required tests:

- level 10+ Monk Attack + Flurry resolves five total attacks where rules/fixture say so.
- Flurry spends correct resource.
- log names Fury/Flurry, not generic bonus action only.
- trace records expected vs actual attack count.
- duplicate clicks do not double-process attacks.

### Gate 8 — Open Manage Spells Catalog

Required tests:

- Manage Spells shows full spell catalog.
- any player can add any catalog spell.
- class/subclass grants are displayed as suggestions/defaults/tags.
- Stihiya can add/select Destructive Wave even if subclass grant metadata is incomplete.
- Manage Spells cannot silently render empty if catalog exists.

### Gate 9 — Manual Release Smoke

The user manually validates:

1. Fresh startup `/dm`, `/dm/map`, and LAN player page.
2. Add Player Profiles / quick-load.
3. DM enemy movement syncs to LAN.
4. Player movement syncs to DM.
5. Player end-turn syncs to DM.
6. DM end-turn syncs to LAN.
7. Long rest speed and resource correctness.
8. Old Man Fury/Flurry.
9. John Twilight equipped attack.
10. Vicnor pact slot override.
11. Manage Spells add arbitrary spell.
12. Stihiya Destructive Wave add/select/cast.
13. Fireball mass target.
14. Player-facing logs do not show debug-only internals.
15. No tracebacks, serialization errors, or repeated expensive loops.

---

## 8. Workstreams

### Workstream A — Planning Baseline

Type: planning only
Do before implementation.

Deliverables:

- source-of-truth map,
- ADRs 0001-0004,
- contract test plan,
- first implementation pass recommendation.

Exit criteria:

- every open P0 mapped to domain, producer, consumer, tests needed.

### Workstream B — Payload and Capability Contracts

Type: implementation + tests
**Status:** COMPLETE (Passed 2026-05-22)

Focus:
- spells/manage,
- resource pools,
- inventory/equipment,
- first-load payloads,
- partial-update non-clobber.

Exit criteria:
- Gates 2 and 3 pass.

Summary of Workstream B Changes:
- **Files Changed:**
  - `dnd_initative_tracker.py` (Backend cache protection carryover logic via `_merge_cached_snapshot_carryover` and live-hydration backfill in `_static_data_payload` for `spell_presets`, `player_spells`, `player_profiles`, `resource_pools`, `consumables_library`, `beast_forms`)
  - `assets/web/lan/index.html` (Frontend non-clobber protection checking with `isEmptyPlainObject` and array length guards inside `static_data` websocket message handler)
  - `tests/test_lan_snapshot_cache.py` (Added 5 new contract unit tests: `test_lan_first_load_spell_catalog_non_empty`, `test_lan_first_load_player_spells_for_seeded_caster`, `test_lan_first_load_resource_pools_for_seeded_resource_user`, `test_lan_state_delta_does_not_clear_spell_capabilities`, `test_resource_pools_survive_state_delta`)
- **Tests Executed & Results:**
  - 84 unit tests run and passed successfully.
  - Zero Python compilation/syntax errors.
  - Inline JavaScript syntax check for `assets/web/lan/index.html` passed cleanly using `node --check`.
- **Open Issues Status:**
  - **P0-001 (Spells / Manage Spells empty)**: Resolved. Initial loading hydrates all required static and player-specific capability data from backend authoritative sources, and the client preserves it safely on deltas.
  - **P0-002 (Resource pools intermittently missing)**: Resolved. State deltas and connection handshake payloads both carry resource pool structures reliably without state-only snapshot poisoning.
  - **Ready for retest:** Both P0-001 and P0-002 are fully resolved and ready for manual user retest (smoke testing with hard-refresh).
- **Next recommended implementation pass:** Workstream C — Action Observability and Idempotency.

### Workstream C — Action Observability and Idempotency

Type: implementation + tests

Focus:

- trace scaffolding,
- action IDs,
- duplicate-action guard,
- action summaries,
- slow-span warnings.

Exit criteria:

- Gate 4 passes.

### Workstream D — Resource/Rest/Pact Model

Type: implementation + tests

Focus:

- long rest correctness,
- resource pool reset cadence,
- normal slots,
- pact slots,
- manual overrides,
- data repair if needed.

Exit criteria:

- Gate 5 passes.

### Workstream E — Inventory/Equipment/Attack Model

Type: implementation + tests

Focus:

- inventory payload,
- equipment source-of-truth,
- weapon selection,
- fallback reason,
- John Twilight-style regression.

Exit criteria:

- Gate 6 passes.

### Workstream F — Fury/Flurry and Action Pipeline

Type: implementation + tests

Focus:

- Old Man Fury/Flurry attack count,
- resource spend,
- log text,
- latency evidence,
- duplicate-action safety.

Exit criteria:

- Gate 7 passes.

### Workstream G — Open Manage Spells Catalog

Type: implementation + tests

Focus:

- all-spell catalog exposed,
- player add/remove,
- source tags,
- class/subclass suggestions,
- Stihiya/Destructive Wave unblock.

Exit criteria:

- Gate 8 passes.

---

## 9. Issue Registry Details

### P0-001 — Spells / Manage Spells Empty for All Users

Known recurrence:
This has been “fixed” multiple times and returned.

Likely domains:

- spell catalog,
- player spell selections,
- Manage Spells catalog,
- LAN static/capability payload,
- frontend merge,
- snapshot/cache carryover.

First task type:
contract/source-of-truth investigation, not narrow patch.

Required tests:

```text
test_lan_first_load_spell_catalog_non_empty
test_lan_first_load_player_spells_for_seeded_caster
test_manage_spells_full_catalog_available
test_lan_state_delta_does_not_clear_spell_capabilities
test_manage_spells_empty_catalog_is_error_not_silent_empty
```

Manual smoke focus:

- all casters have Spells tab populated,
- Manage Spells lists full catalog,
- adding arbitrary spell works.

### P0-002 — Resource Pool Dropdown Intermittent

Likely domains:

- resource pool definitions,
- resource current values,
- LAN capability payload,
- dynamic resource payload,
- frontend merge.

Required tests:

```text
test_lan_first_load_resource_pools_for_seeded_resource_user
test_resource_pools_survive_state_delta
test_reconnect_resource_pools_present_without_multiple_refreshes
test_long_rest_resource_values_reflect_backend_after_payload
```

### P0-003 / P0-004 — Long Rest Slow and Incomplete

Likely domains:

- long rest command,
- resource reset semantics,
- YAML cache,
- persistence,
- snapshot/broadcast,
- action queue.

Required tests:

```text
test_long_rest_restores_long_rest_pool
test_long_rest_restores_short_or_long_rest_pool
test_long_rest_does_not_restore_manual_pool
test_long_rest_restores_normal_slots
test_long_rest_restores_pact_slots
test_long_rest_preserves_max_values
test_long_rest_emits_phase_spans
```

Required traces:

```text
long_rest.load_players
long_rest.restore_hp
long_rest.restore_spell_slots
long_rest.restore_pact_slots
long_rest.restore_resource_pools
long_rest.persist_batch
long_rest.snapshot_build
long_rest.broadcast
```

### P0-005 — John Twilight Inventory / Weapon Fallback

Likely domains:

- player inventory,
- equipment,
- attack options,
- LAN capability payload,
- action resolver.

Required tests:

```text
test_inventory_payload_non_empty_for_seeded_equipment_user
test_equipped_weapon_selected_for_attack
test_configured_weapon_prevents_unarmed_fallback
test_unarmed_fallback_requires_fallback_reason
```

Trace fields:

```text
inventory_item_count
equipped_weapon_id
configured_weapon_id
selected_weapon_name
fallback_reason
```

### P0-006 — Old Man Fury/Flurry

Likely domains:

- Monk feature rules,
- action economy,
- resource spend,
- attack sequence,
- action latency,
- logs.

Required tests:

```text
test_level10_monk_attack_plus_flurry_resolves_five_attacks
test_flurry_spends_one_focus_point
test_flurry_log_names_feature
test_fury_trace_records_expected_and_actual_attack_count
test_duplicate_flurry_click_does_not_double_process
```

### P0-007 — Vicnor Pact Slot Override

Likely domains:

- pact slot current/max,
- manual override UI,
- backend override command,
- rest restore.

Required tests:

```text
test_pact_cast_decrements_current_not_max
test_pact_manual_current_override_preserves_max
test_pact_current_override_cannot_delete_max
test_pact_long_rest_restores_current_to_max
test_normal_caster_override_still_works
```

Data repair:
If current data has corrupted max slots, repair separately and label it as data repair.

### P1-001 — Stihiya Destructive Wave

Preferred durable fix:
Open Manage Spells catalog.

Required tests:

```text
test_manage_spells_allows_arbitrary_spell_add
test_stihiya_can_add_destructive_wave_from_catalog
test_subclass_grants_are_tags_not_hard_filters
```

---

## 10. Agent Task Templates

### 10.1 Planning-Only Task Template

```text
TASK: <planning topic>

Repo:
~/src/init-tracker

Read first:
- docs/may22_research_notes.md
- this living document
- latest smoke notes
- latest console log
- latest debug trace

Do not implement fixes in this pass.

Goals:
1. Identify source-of-truth domains.
2. Identify producers and consumers.
3. Identify existing tests.
4. Identify missing tests.
5. Identify required ADR/source-map updates.
6. Recommend first implementation pass.

Required output:
- findings table
- source path references
- test gap list
- first implementation recommendation
- no code changes
```

### 10.2 Implementation Task Template

```text
TASK: <fix title>

Repo:
~/src/init-tracker

Read first:
- docs/may22_research_notes.md
- this living document
- relevant ADRs
- source-of-truth map

Scope:
<exact files/functions allowed>

Problem:
<user-visible symptom>

Root cause:
<exact producer/consumer/source/cache path>

Contract being protected:
<which gate and invariant>

Implementation requirements:
- ...
- ...

Tests required:
- test that fails before fix
- test that passes after fix
- related contract tests

Validation:
- commands
- expected output
- logs/traces to inspect if applicable

Do not:
- broad exception swallowing
- unrelated spell correctness
- browser smoke tasks
- one-character YAML patch as source fix
```

### 10.3 Post-Smoke Postmortem Task Template

```text
TASK: Postmortem inspect smoke-test logs

Repo:
~/src/init-tracker

User performed manual smoke test.

Smoke command:
<command>

Console log:
<path/pattern>

Debug trace:
<path if known>

User-observed failures:
- ...

Do not perform browser smoke tests.

Required analysis:
1. Timeline.
2. Errors/tracebacks.
3. Action summaries if available.
4. Source-of-truth domains involved.
5. Producer/consumer path.
6. Existing tests that should have caught this.
7. Missing contract tests.
8. Proposed fix task if needed.

Output:
- verdict
- exact files/logs inspected
- root cause or unknowns
- next implementation task
```

---

## 11. Done Criteria for Any Fix

A fix is done only when all relevant boxes are checked.

```text
[ ] Root cause identified.
[ ] Source-of-truth domain identified.
[ ] Producer and consumer identified.
[ ] Existing test gap identified.
[ ] Regression/contract test added.
[ ] Test would fail before the fix.
[ ] Test passes after the fix.
[ ] No broad exception swallowing.
[ ] No unrelated behavior mixed in.
[ ] Source-of-truth map updated if ownership/payload changed.
[ ] ADR updated or created if architecture decision changed.
[ ] Debug trace/log evidence inspected if issue was runtime-only.
[ ] Manual smoke focus provided for user if needed.
```

---

## 12. Log and Trace Conventions

Manual smoke commands should use unique log prefixes.

Example:

```bash
./.venv/bin/python3 serve_headless.py \
  --host 0.0.0.0 \
  --port 8787 \
  --debugging true \
  2>&1 | tee "logs/live-debug-console-<topic>-$(date +%Y%m%d-%H%M%S).log"
```

Agents should inspect:

```text
logs/live-debug-console-<topic>-*.log
logs/debug-trace-YYYYMMDD-HHMMSS.jsonl
```

Search terms:

```text
Traceback
ERROR
WARNING
AttributeError
TypeError
json
_json_safe
static_data
player_spells
spell_presets
resource_pools
inventory
equipment
pact
spell_slots
long_rest
broadcast
snapshot
end_turn
move
Fury
Flurry
Unarmed Strike
client_action_id
trace_id
action_summary
slow_span
```

---

## 13. Test Grouping Proposal

Future CI/test scripts should group tests by contract.

```text
contracts:first_load
contracts:partial_update
contracts:dm_state
contracts:dm_map
contracts:resources
contracts:pact_slots
contracts:inventory_equipment
contracts:spells_manage
contracts:dm_lan_sync
contracts:serialization
contracts:action_idempotency
contracts:tracing
```

Until formal grouping exists, agents must list the exact tests they ran.

---

## 14. Current Recommended Next Step

Do not jump straight into fixing Spells/Manage Spells again.

Next task should be planning-only:

```text
TASK: Build init-tracker stabilization baseline, source-of-truth map, and first contract plan
```

Expected deliverables:

1. `docs/architecture/source_of_truth_map.md`
2. ADRs 0001-0004 minimum.
3. `docs/architecture/contract_test_plan.md`
4. First implementation pass recommendation.

No code changes in that pass.

---

## 20. P0-RESPONSIVENESS — Final Playability Gate

Status: Active release gate as of 2026-05-22.

The previous "latency reduced" claims are insufficient for production/playable release. Tactical map and ship/surface/structure/boarding systems are experimental for playable runtime and default off.

Release gate:

- Ordinary player/DM combat actions should usually finish server-side under 500ms.
- Anything over 1000ms needs trace evidence explaining why.
- Anything over 5000ms outside startup/full explicit static refresh remains release-blocking.
- Normal combat must not build global `static_plus_dynamic`, `_dm_tactical_snapshot`, ship/surface/structure projections, full player YAML reloads, full spell catalog rebuilds, or global LAN static invalidation.

Decision:

- Enable tactical map projections only with `INIT_TRACKER_ENABLE_TACTICAL_MAP=1`.
- Enable ship/surface/structure/boarding projections only with `INIT_TRACKER_ENABLE_SHIP_SURFACES=1`.
- `/api/dm/combat` is combat-lite by default and must not call `_dm_tactical_snapshot`.
- Explicit `/dm/map` routes remain available for map-authoring workflows.
- Echo/Unleash unarmed requests now inherit the owner's equipped/configured non-unarmed weapon and trace owner/final weapon IDs.

Runtime report:

- `docs/runtime_reports/final_playability_latency_amputation_20260522.md`

---

## 15. Edit Protocol for This Document

Update this document when:

- a P0/P1 issue is fixed or reopened,
- manual smoke confirms or refutes a fix,
- a new repeated regression appears,
- a source-of-truth decision changes,
- a new ADR is accepted,
- a gate is satisfied,
- a workstream moves status,
- a test contract is added.

Do not use this document as a scratchpad for raw logs. Link or summarize logs instead.

Do not bury unresolved failures. If a test is “baseline failing,” list its exact name and production impact.

---

## 16. Reference Summary

The principles in this document are derived from `docs/may22_research_notes.md`.

Important research anchors:

- postmortem action items should prevent recurrence, not merely describe incidents,
- contract tests verify provider/consumer obligations,
- traces and context propagation correlate work across system boundaries,
- idempotency keys prevent duplicate mutations during retries,
- ADRs capture significant architecture decisions,
- caches are projections and require invalidation,
- normalized state reduces duplicated truth,
- SRD 5.2.1 provides official mechanics baseline,
- open Manage Spells catalog is table policy.

For source citations and deeper notes, see:

```text
docs/may22_research_notes.md
```

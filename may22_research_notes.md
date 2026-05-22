# init-tracker Research Notes — Consolidated

Status: Consolidated research baseline  
Date: 2026-05-22  
Project: `init-tracker`

## Purpose

This file collects the planning research needed before returning to implementation work on `init-tracker`.

The immediate problem is not a single bug. The app has entered a regression loop: one issue is patched, then another core surface breaks. Recent smoke tests showed repeated failures in first-load spell data, resource pools, inventory/equipment, long rest, pact slot overrides, and action latency. Some fixes worked, such as `/dm/map` player catalog bootstrap, DM enemy movement syncing to LAN, and player-ended turns updating the DM console, but adjacent areas kept regressing.

This document converts the research into a stable planning baseline for agents. It is intentionally scoped to `init-tracker`; it should not become generic engineering notes detached from the project.

## Research Scope

Six research areas were covered:

1. Regression prevention / “whack-a-mole” engineering.
2. Backend-to-frontend contract testing.
3. Latency, tracing, and action pipeline observability.
4. State/cache/source-of-truth architecture decisions.
5. D&D mechanics sources for current gameplay failures.
6. Product-specific source-of-truth discovery inside the repo.

## Non-Goals

This document does not implement fixes.

This document does not start the spell-correctness backlog.

This document does not replace manual smoke tests. The user performs browser/app smoke tests manually. Agents should inspect logs, traces, source code, and tests.

This document does not enforce authoritarian class/spell restrictions. The table policy is an open Manage Spells catalog: players are trusted to add any spell they know they should have.

---

# Executive Synthesis

## Core Diagnosis

The current recurring failures are mostly not isolated feature bugs. They are violations of unstable contracts between:

- persistent player data,
- runtime authoritative state,
- cached snapshots,
- backend payload producers,
- JSON serialization,
- frontend state merge logic,
- and user-visible surfaces.

The same data domains keep breaking:

| Domain | Recent failure |
|---|---|
| Spell catalog / Manage Spells | Empty for all users again. |
| Player spells | Missing from LAN first load and/or clobbered by updates. |
| Resource pools | Intermittent dropdown, missing until refresh, not restored on long rest. |
| Inventory/equipment | LAN inventory empty; John Twilight falls back to Unarmed Strike. |
| Pact slots | Vicnor override mutates/removes max slots. |
| Action pipeline | Old Man Fury of Blows slow/missing attack; duplicate-click risk. |
| Long rest | Over one minute, app appears hung, incomplete resource recovery. |
| DM/LAN sync | Recently fixed, must now be protected with tests. |
| `/dm/map` bootstrap | Recently fixed, must remain protected with tests. |

The common pattern is missing or unclear source-of-truth and payload semantics.

## Operating Principle

No repeated regression should be fixed again without a durable prevention mechanism.

A fix is not complete unless it includes:

- root cause,
- source-of-truth domain,
- producer and consumer,
- payload/cache/merge path,
- test that would have failed before the fix,
- validation result,
- and a note if an ADR/source-of-truth map entry must change.

---

# Pass 1 — Regression Prevention / Postmortem Discipline

## Research Anchors

- Google SRE Workbook: Postmortem Practices for Incident Management.
- Google SRE: Postmortem Action Items.
- Martin Fowler / Ham Vocke: Practical Test Pyramid.
- Martin Fowler: Software Testing Guide.

## Init-tracker Finding

A repeated bug should be treated as an incident class, not a normal isolated bug.

For example:

```text
Bad framing:
Fix Manage Spells empty again.

Better framing:
Prevent recurrence of first-load/capability-state loss where seeded players receive empty spell catalog, player spells, resource pools, or inventory because static/capability data is missing or clobbered by partial updates.
```

## Required Postmortem Pattern

Every manual smoke failure that blocks gameplay should produce:

```text
Incident title:
Date/time:
Smoke command:
Console log:
Debug trace:
Affected surface:
Affected user/character:
Expected behavior:
Actual behavior:

Impact:
- Gameplay impact:
- Production risk:
- Recurrence history:

Timeline:
- server start:
- page load:
- action:
- visible failure:
- relevant log events:

Root cause:
- source-of-truth domain:
- producer:
- consumer:
- state/cache/payload path:
- exact function(s):

Why existing tests missed it:

Preventative action items:
1. Contract/test:
2. Source-of-truth fix:
3. Instrumentation:
4. Documentation/ADR if needed:

Acceptance criteria:
- automated:
- manual smoke:
```

## Action Item Categories

Use the Google SRE-style categories to avoid vague “fix it” work:

| Category | Meaning for init-tracker |
|---|---|
| Investigate this incident | Inspect logs, debug trace, payloads, exact call path. |
| Mitigate this incident | Restore table-play usability quickly. |
| Repair damage | Fix corrupted data such as pact slot max values or bad YAML writes. |
| Detect future incidents | Add tests, runtime health checks, trace warnings. |
| Mitigate future incidents | Graceful degradation, clear UI error, duplicate-action safety. |
| Prevent future incidents | Contract tests, ADRs, source-of-truth cleanup, frontend merge semantics. |

## Never-Again Test Examples

| Recurring failure | Never-again test |
|---|---|
| Spells / Manage Spells empty | Seeded casters receive non-empty spell catalog and Manage Spells catalog on first load; state-only updates cannot erase it. |
| Resource pools missing | Resource pools present on first load and preserved through partial updates. |
| Inventory empty / Unarmed Strike fallback | Seeded equipped player receives inventory/equipment payload and attack resolves with configured weapon. |
| Vicnor pact override corrupts slots | Manual current override changes current only; max remains intact. |
| Long rest incomplete | Long rest restores eligible resource pools and leaves non-restoring pools unchanged. |
| DM/LAN sync regression | DM movement updates LAN; player end-turn updates DM. |

---

# Pass 2 — Backend-to-Frontend Contract Testing

## Research Anchors

- Martin Fowler: Contract Test.
- Martin Fowler / Ian Robinson: Consumer-Driven Contracts.
- Pact Docs: Introduction to Contract Testing.
- JSON Schema: Getting Started.
- OpenAPI-style contract testing references.

## Init-tracker Finding

The app needs consumer-focused payload contracts.

The key consumers are:

| Consumer | Provider |
|---|---|
| LAN player page | LAN websocket/static-data payload |
| Spells tab | spell catalog + player spell payload |
| Manage Spells | full spell catalog + player selected spells |
| Resource dropdown | resource pool payload |
| Inventory / attack UI | inventory/equipment payload |
| DM console | DM state payload |
| `/dm/map` | DM map startup payload + tactical map APIs |

## Schema Contract vs Capability Contract

Schema validation is necessary but not enough.

Example:

```text
Schema says:
player_spells is an object.

But:
player_spells = {} is still wrong for a seeded caster.
```

Use two layers:

1. Schema contract:
   - required keys,
   - JSON-safe types,
   - serializable payloads.

2. Capability contract:
   - seeded casters have spell data,
   - seeded resource users have pools,
   - seeded equipped players have inventory/equipment,
   - partial updates do not clobber known capability data.

## Minimum Contract Tests

### LAN First-Load Capability Contract

Must prove:

- `spell_presets` / spell catalog exists and is non-empty.
- `player_spells` exists and has entries for seeded casters.
- `player_profiles` exists and includes seeded players.
- `resource_pools` exists for players with pools.
- inventory/equipment exists for players with configured/equipped items.
- payload serializes with `json.dumps`.

### LAN Partial Update Non-Clobber Contract

Must prove:

- apply full static/capability payload,
- apply stripped/state-only payload,
- spell list remains,
- Manage Spells remains,
- resource pools remain,
- inventory/equipment remains.

### DM State Serialization Contract

Must prove:

- nested sets/unsupported types become JSON-safe,
- sibling fields survive serialization,
- combatants survive serialization,
- player catalog survives serialization.

### `/dm/map` Startup Contract

Must prove:

- blank combat snapshot does not hide player catalog/session setup,
- Add Player Profiles updates combatant roster,
- route/page-specific payload does not diverge from DM state contract.

### Resource/Rest Contract

Must prove:

- long-rest-eligible pools restore,
- non-restoring pools do not restore,
- normal spell slots restore current to max,
- pact slots restore current to max,
- next state payload reflects restored backend values.

### Inventory/Equipment Contract

Must prove:

- seeded inventory appears in LAN payload,
- equipped weapon appears,
- attack selection uses equipped/configured weapon,
- fallback Unarmed Strike only happens when no valid weapon exists.

## Partial Update Rule

The app needs an explicit rule:

| Incoming field state | Meaning |
|---|---|
| key missing | no update; preserve existing state |
| field present in full payload | authoritative value |
| `{}` / `[]` in full payload | authoritative empty value if allowed by domain |
| `{}` / `[]` in partial payload | dangerous; must not clear static/capability data unless explicitly marked |
| `null` | invalid by default unless field contract defines it |
| explicit clear marker | only safe intentional clear |

---

# Pass 3 — Latency, Tracing, Action Pipeline Observability, and Idempotency

## Research Anchors

- OpenTelemetry: Traces.
- OpenTelemetry: Context Propagation.
- OpenTelemetry Python instrumentation.
- W3C Trace Context.
- Google SRE: Monitoring Distributed Systems.
- Google SRE: Handling Overload.
- Stripe: Idempotent Requests.
- Stripe Engineering: Designing Robust and Predictable APIs with Idempotency.

## Init-tracker Finding

Slow actions are not only UX problems. They are correctness and data-integrity risks.

Current symptoms:

- Old Man Fury of Blows is slow and may miss attacks.
- John Twilight actions are slow enough to invite duplicate clicks.
- Long rest blocks the app for over a minute.
- Fireball into a large crowd was fast, proving the bottleneck is not simply “many targets.”

The next implementation foundation should be instrumentation-first:

```text
Add native action tracing, action summaries, and duplicate-action idempotency scaffolding for mutating commands.
```

## Required Action Trace Shape

Every mutating command should have:

```text
trace_id
client_action_id
surface
actor_id / actor_name
action_type
turn_id / round
status
duration_ms
```

Recommended trace hierarchy:

```text
action.root
  transport.receive
  command.parse
  command.idempotency
  command.dispatch
  command.authorize
  command.resolve
    mechanics.validate
    resources.validate
    equipment.resolve
    targets.resolve
    rolls.resolve
    damage.resolve
  state.apply
  persistence.maybe_write
  cache.invalidate
  snapshot.build
  snapshot.serialize
  broadcast.enqueue
  websocket.send
  action.ack_or_result
```

## Action Summary

Every mutating action should emit one summary record:

```json
{
  "kind": "action_summary",
  "trace_id": "...",
  "client_action_id": "...",
  "surface": "lan",
  "actor_name": "Old Man",
  "action_type": "fury_of_blows",
  "status": "completed",
  "duration_ms": 1261.4,
  "slowest_span": "snapshot.build.lan_state",
  "slowest_span_ms": 822.7,
  "snapshot_count": 4,
  "broadcast_count": 3,
  "yaml_reads": 0,
  "yaml_writes": 1,
  "duplicate_count": 0
}
```

## Golden Signals for init-tracker

| Signal | init-tracker version |
|---|---|
| Latency | action duration, ack duration, result duration, slowest span |
| Traffic | command count, websocket messages, broadcast count |
| Errors | exceptions, rejected commands, failed broadcasts, serialization errors |
| Saturation | action queue depth, tick duration, in-flight actions, broadcast backlog |

## Duplicate-Action Safety

Frontend pending state is required but insufficient. The server must be idempotent.

Required semantics:

```text
same scope + same client_action_id + same payload while processing
=> duplicate_in_flight, no second mutation

same scope + same client_action_id + same payload after completion
=> duplicate_completed / cached result, no second mutation

same scope + same client_action_id + different payload
=> conflict, no mutation
```

Suggested idempotency scope:

```text
encounter_id + actor_id + client_action_id
```

or:

```text
server_session_id + combat_round + turn_id + actor_id + client_action_id
```

## Long Rest Trace

Required spans:

```text
long_rest.receive
long_rest.load_players
long_rest.restore_hp
long_rest.restore_spell_slots
long_rest.restore_pact_slots
long_rest.restore_resource_pools
long_rest.persist_batch
long_rest.snapshot_invalidate
long_rest.broadcast
```

Required counts:

```text
player_count
pool_count
pools_restored_count
pools_skipped_count
normal_slot_count
pact_slot_count
yaml_read_count
yaml_write_count
cache_validation_count
broadcast_count
duration_ms
```

## Fury / Weapon Trace

Required fields:

```text
feature_id
expected_attack_count
actual_attack_count
bonus_action_spent
resource_before
resource_after
weapon_id
weapon_name
fallback_reason
```

This makes Old Man and John Twilight postmortems evidence-based.

---

# Pass 4 — State, Cache, Source-of-Truth, and ADRs

## Research Anchors

- Michael Nygard / Cognitect: Documenting Architecture Decisions.
- Martin Fowler: Architecture Decision Record.
- Microsoft Azure: Cache-Aside Pattern.
- Microsoft Azure: Caching Guidance.
- Redux Docs: Normalizing State Shape.
- IETF RFC 7386: JSON Merge Patch.
- IETF RFC 6902: JSON Patch.

## Init-tracker Finding

The project needs explicit architecture decisions for source-of-truth and payload semantics.

Agents keep re-deciding:

- what owns player spells,
- what owns resource pools,
- what owns inventory/equipment,
- whether snapshots are authoritative,
- whether `{}` means empty or stripped,
- whether frontend state may overwrite capability data,
- and when caches are invalidated.

These are ADR-level decisions.

## High-Priority ADRs

```text
ADR 0001 — Runtime state vs transport snapshots
ADR 0002 — Payload kind and partial update semantics
ADR 0003 — Capability data contract
ADR 0004 — Cache invalidation domains
ADR 0005 — YAML/profile cache role
ADR 0006 — Manage Spells open catalog policy
ADR 0007 — Pact slots and resource current/max model
ADR 0008 — Inventory/equipment source of truth
```

## Core Architecture Decisions Proposed

### Snapshots Are Projections

```text
_cached_snapshot is not truth.
DM state payload is not truth.
LAN static_data payload is not truth.
Frontend JS state is not truth.
_json_safe output is not truth.
```

They are derived transport/read models and must be rebuildable from authoritative state.

### Payloads Need Kind/Version/Epoch

Suggested fields:

```json
{
  "payload_kind": "lan_static_full",
  "payload_version": 3,
  "state_epoch": 42,
  "source": "server",
  "trace_id": "...",
  "data": {}
}
```

Payload kinds:

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

### Capability Data Is a Separate Category

The recurring empty UI failures are not purely static-vs-dynamic. They are capability-data failures.

Suggested domains:

```text
catalog_static:
  spell presets, global spell catalog

profile_capabilities:
  player spells, inventory, equipment, class features, resource pool definitions

dynamic_state:
  HP, current slots, current resource values, active turn, positions

map_state:
  map objects, terrain, tokens, AoEs

ui_state:
  selected tab, filters, pending actions
```

Dynamic updates must not clear catalog/static or profile-capability data.

### Domain-Based Cache Invalidation

Every mutation should declare invalidated domains.

Example:

```text
long_rest:
  resource_pools
  spell_slots
  pact_slots
  combat_state
  dm_payload
  lan_payload

equip_weapon:
  inventory_equipment
  attack_options
  player_profiles
  lan_capabilities

manage_spells_add:
  player_spells
  spell_capabilities
  lan_static_or_capability
```

---

# Pass 5 — D&D Mechanics Sources for Current Gameplay Failures

## Research Anchors

- Wizards of the Coast / D&D Beyond: SRD 5.2.1.
- D&D Beyond SRD overview.
- D&D Beyond 2024 Monk and Warlock summaries where useful.
- Secondary non-official Tempest Domain references only where SRD does not contain the subclass.

## Source Priority

Use this source hierarchy:

```text
official_srd_5_2_1
official_dnd_beyond_basic_rules
official_book/manual_entry
table_homebrew
manual_player_override
app_fallback
```

The app should tag source kind where possible.

## Monk / Fury of Blows

For a level 10+ Monk:

```text
Attack action: 2 attacks via Extra Attack.
Flurry of Blows: 3 Unarmed Strikes via Heightened Focus.
Expected total: 5 attacks.
```

Required app contract:

```text
Attack action attack count = 2.
Flurry/Fury spends 1 Focus Point.
Flurry/Fury grants exactly 3 bonus-action Unarmed Strikes at the relevant level.
Log names the feature, not only “used a bonus action.”
Trace records expected_attack_count and actual_attack_count.
```

## Pact Magic

Required app contract:

```text
pact_slots_current and pact_slots_max are distinct.
casting changes current only.
manual current override changes current only.
manual max override, if supported, is explicit and separate.
short rest restores current to max.
long rest restores current to max.
current override cannot turn 2/2 into 0/0.
```

## Long Rest

Required app contract:

```text
Long Rest restores HP.
Long Rest restores normal spell slot current values to max.
Long Rest restores Pact Magic current values to max.
Long Rest restores resource pools whose reset cadence includes long rest.
Long Rest does not blindly reset every pool.
Long Rest never silently skips eligible pools.
Long Rest does not change max values unless a feature explicitly changes max.
```

Every resource pool needs metadata:

```text
resource_id
display_name
current
max
reset_cadence
source_feature
source_class
source_rule_note
```

## Always-Prepared / Source-Granted Spells

Required app model:

```text
spell_catalog
known_or_selected_spells
prepared_spells
always_prepared_spells
source_granted_spells
manually_added_spells
```

Always-prepared spells should not count against prepared limits.

## Open Manage Spells Catalog

This is a project/table policy:

```text
Players are trusted.
Manage Spells must expose the full spell catalog for manual add/select.
Class/subclass grants are suggestions/defaults/tags, not restrictions.
Manual additions are valid table-approved state, not hacks.
```

This policy prevents Stihiya/Destructive Wave and similar cases from becoming production blockers.

## Weapon / Inventory

Required app contract:

```text
If a player has configured/equipped weapon data, attack UI and backend action resolution use that weapon.
Fallback to Unarmed Strike requires an explicit fallback_reason.
Inventory/equipment must be present in first-load capability payload.
```

Selection order:

```text
1. user-selected attack/weapon in current action
2. equipped/configured weapon
3. default unarmed/class option only if no valid weapon exists
4. error/warning if configured weapon exists but cannot be resolved
```

---

# Pass 6 — Product-Specific Source-of-Truth Discovery Inside the Repo

## Research Anchors

- Single Source of Truth.
- Red Hat: Single Source of Truth in enterprise architecture.
- Microsoft: Cache-Aside Pattern and Caching Guidance.
- Martin Fowler: Bounded Context and Domain-Driven Design.
- Redux Docs: Normalized State Shape.
- Docs-as-code references.

## Init-tracker Finding

The next serious planning artifact should be a repo-specific source-of-truth map built from code inspection and logs, not guessed from symptoms.

## Required Source-of-Truth Domains

The repo map must cover:

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

## Required Columns

For each domain:

```text
persistent source
runtime authoritative source
derived caches/projections
payload producers
frontend consumers
mutation commands
invalidation domains
allowed empty states
partial update behavior
primary tests
manual smoke checks
```

## Bounded Contexts

The project should distinguish contexts:

```text
Profile context
Spell context
Resource context
Inventory/equipment context
Combat context
Map context
Transport context
Frontend context
```

One context should not silently overwrite another’s authoritative data.

## Open Manage Spells Source-of-Truth Policy

Explicitly include:

```text
Domain: Manage Spells catalog

Persistent source:
  global spell catalog / spell preset data

Runtime source:
  loaded spell catalog

Player-specific source:
  player selected/known/prepared/manual spell list

Class/subclass grants:
  suggestions/defaults/source tags only

Policy:
  players may add any spell from the catalog
```

## Data Repair vs Source Fix

Agents must separate data repair from durable source fixes.

Example:

```text
Repair:
  Restore Vicnor pact slot max if corrupted.

Source fix:
  Manual current override cannot mutate max.
```

Example:

```text
Repair:
  Add Destructive Wave to Stihiya manually if needed.

Source fix:
  Manage Spells exposes full catalog and allows arbitrary add.
```

---

# Consolidated Planning Outputs Recommended

After this research, the next non-coding planning pass should produce these repo artifacts.

## 1. Source-of-Truth Map

```text
docs/architecture/source_of_truth_map.md
```

Must be built from repo inspection, not guesses.

## 2. ADR Set

```text
docs/adr/0001-runtime-state-and-snapshot-boundaries.md
docs/adr/0002-payload-kind-and-partial-update-semantics.md
docs/adr/0003-capability-data-contract.md
docs/adr/0004-cache-invalidation-domains.md
docs/adr/0005-yaml-profile-cache-role.md
docs/adr/0006-manage-spells-open-catalog-policy.md
docs/adr/0007-pact-slots-current-max-model.md
docs/adr/0008-inventory-equipment-source-of-truth.md
docs/adr/0009-action-tracing-and-idempotency.md
```

## 3. Contract Test Plan

```text
docs/architecture/contract_test_plan.md
```

Must include:

- LAN first-load capability contract.
- LAN partial-update non-clobber contract.
- DM state serialization contract.
- `/dm/map` startup contract.
- resource/rest contract.
- inventory/equipment contract.
- pact slot current/max contract.
- DM/LAN sync contract.

## 4. Action Observability Plan

```text
docs/architecture/action_tracing_plan.md
```

Must include:

- trace/span shape,
- action IDs,
- idempotency rules,
- slow-span thresholds,
- action summaries,
- long-rest spans,
- Fury/weapon spans,
- snapshot/broadcast spans.

---

# Planning-Only Agent Task

Use this after the research phase, before more implementation.

```text
TASK: Build init-tracker stabilization baseline, source-of-truth map, and first contract plan

Repo:
~/src/init-tracker

Read first:
- init_tracker_research_notes.md
- latest user smoke notes
- latest live-debug console log
- latest debug trace

Do not implement fixes in this pass.

Primary goals:
1. Build docs/architecture/source_of_truth_map.md from actual source inspection.
2. Draft ADRs 0001-0004 at minimum:
   - runtime state vs snapshots
   - payload kind / partial update semantics
   - capability data contract
   - cache invalidation domains
3. Produce a contract test plan mapping current P0/P1 failures to tests.
4. Identify the first implementation pass, but do not start it.

Current table policy:
- Manage Spells must use an open spell catalog.
- Players are trusted to add any spell.
- Class/subclass grants are suggestions/defaults/tags, not hard blockers.

Required issue mapping:
- Spells/Manage Spells empty for all users.
- Resource-pool dropdown intermittent/missing.
- Long rest slow and incomplete.
- John Twilight inventory/equipment and Unarmed Strike fallback.
- Old Man Fury of Blows latency/missing attack/log text.
- Vicnor pact slot current/max corruption.
- Stihiya Destructive Wave blocked by spell UI.
- DM movement and player end-turn sync fixed but needing contract protection.

Required output:
- source-of-truth map,
- domain ownership table,
- current tests vs missing tests,
- proposed ADR list,
- first implementation pass recommendation,
- no code changes.
```

---

# Final Consolidated Guidance

The next implementation pass should not be another isolated patch.

The correct order is:

1. Build the source-of-truth map from the repo.
2. Accept the first ADRs about snapshots, payloads, capability data, and cache invalidation.
3. Add backend payload contract tests for first-load/capability state.
4. Add or extract frontend merge tests for partial updates.
5. Add action tracing and idempotency scaffolding.
6. Then fix the P0s using evidence and contracts.

The open Manage Spells catalog is now a core product decision:

```text
Trust the players.
Expose the full spell catalog.
Let class/subclass/homebrew data annotate and suggest, not restrict.
```

This directly supports the table workflow and prevents the app from becoming unusable because one class/subclass grant path is incomplete.

---

# Source Index

## Process / Postmortems / Regression Prevention

- Google SRE Workbook — Postmortem Practices for Incident Management  
  https://sre.google/workbook/postmortem-culture/

- Google SRE — Postmortem Action Items  
  https://sre.google/static/pdf/login_spring17_09_lunney.pdf

- Martin Fowler / Ham Vocke — The Practical Test Pyramid  
  https://martinfowler.com/articles/practical-test-pyramid.html

- Martin Fowler — Software Testing Guide  
  https://martinfowler.com/testing/

## Contract Testing

- Martin Fowler — Contract Test  
  https://martinfowler.com/bliki/ContractTest.html

- Martin Fowler / Ian Robinson — Consumer-Driven Contracts  
  https://martinfowler.com/articles/consumerDrivenContracts.html

- Pact Docs — Introduction to Contract Testing  
  https://docs.pact.io/

- JSON Schema — Getting Started  
  https://json-schema.org/learn/getting-started-step-by-step

## Tracing / Observability / Idempotency

- OpenTelemetry — Traces  
  https://opentelemetry.io/docs/concepts/signals/traces/

- OpenTelemetry — Context Propagation  
  https://opentelemetry.io/docs/concepts/context-propagation/

- W3C — Trace Context  
  https://www.w3.org/TR/trace-context/

- Google SRE — Monitoring Distributed Systems  
  https://sre.google/sre-book/monitoring-distributed-systems/

- Google SRE — Handling Overload  
  https://sre.google/sre-book/handling-overload/

- Stripe Docs — Idempotent Requests  
  https://docs.stripe.com/api/idempotent_requests

- Stripe Engineering — Designing Robust and Predictable APIs with Idempotency  
  https://stripe.com/blog/idempotency

## Architecture Decisions / State / Cache

- Michael Nygard / Cognitect — Documenting Architecture Decisions  
  https://www.cognitect.com/blog/2011/11/15/documenting-architecture-decisions

- Martin Fowler — Architecture Decision Record  
  https://martinfowler.com/bliki/ArchitectureDecisionRecord.html

- Microsoft Azure — Cache-Aside Pattern  
  https://learn.microsoft.com/en-us/azure/architecture/patterns/cache-aside

- Microsoft Azure — Caching Guidance  
  https://learn.microsoft.com/en-us/azure/architecture/best-practices/caching

- Redux Docs — Normalizing State Shape  
  https://redux.js.org/usage/structuring-reducers/normalizing-state-shape

- IETF RFC 7386 — JSON Merge Patch  
  https://datatracker.ietf.org/doc/html/rfc7386

- IETF RFC 6902 — JSON Patch  
  https://datatracker.ietf.org/doc/html/rfc6902

## D&D Mechanics

- Wizards of the Coast / D&D Beyond — System Reference Document 5.2.1 PDF  
  https://media.dndbeyond.com/compendium-images/srd/5.2/SRD_CC_v5.2.1.pdf

- D&D Beyond — SRD overview  
  https://www.dndbeyond.com/srd

- D&D Beyond — 2024 Monk vs. 2014 Monk  
  https://www.dndbeyond.com/posts/1758-2024-monk-vs-2014-monk-whats-new

- D&D Beyond — 2024 Warlock vs. 2014 Warlock  
  https://www.dndbeyond.com/posts/1756-2024-warlock-vs-2014-warlock-whats-new

## Source-of-Truth / Docs-as-Code

- Single Source of Truth  
  https://en.wikipedia.org/wiki/Single_source_of_truth

- Red Hat — Single Source of Truth Architecture  
  https://www.redhat.com/en/blog/single-source-truth-architecture

- Martin Fowler — Bounded Context  
  https://martinfowler.com/bliki/BoundedContext.html

- Martin Fowler — Domain-Driven Design  
  https://martinfowler.com/bliki/DomainDrivenDesign.html

- Kong — What is Docs as Code?  
  https://konghq.com/blog/learning-center/what-is-docs-as-code

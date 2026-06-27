# BUG-20260614-weapon-attacks-reload-fail Smoke Failure 2026-06-26

## Smoke status

Failed developer browser smoke.

## Smoke evidence

- Smoke server log: logs/smoke/BUG-20260614-weapon-attacks-reload-fail_smoke-server_20260626-112213.log
- Debug trace: logs/debug-trace-20260626-112213.jsonl

## Developer-observed behavior

The DM reload UI remains confusing:

- The UI allows attacking even when the weapon needs reload.
- Reload still appears not to do anything.
- Clicking reload appears to behave like an attack, or it is unclear how to trigger reload.
- The developer could not identify an intuitive successful reload path from the DM UI.

## Current interpretation

The backend service path and focused unit tests may be correct, but the browser/DM UI action flow still fails product smoke.

This likely needs a bounded UI/action-flow pass, not broad weapon architecture work.

## Required next classification

Determine whether the remaining failure is:

1. DM UI never emits `reload_weapon`;
2. DM UI emits `attack_request` despite reload intent;
3. DM UI renders reload affordance in the wrong state/location;
4. server snapshot does not expose enough ammo/reload state for the UI;
5. the reload route works only for player LAN, not DM action flow.

## Product expectation

When a weapon requires reload, the UI should make the next valid action obvious and should not make an unavailable attack look valid.

## Developer product correction after failed follow-up smoke

The previous DM reload UI pass still did not meet the intended behavior.

Required behavior:

- If a reload is needed, the damage resolution modal must not open.
- The attack/damage flow must be hard-gated before resolution begins.
- Reload must be a distinct reload confirmation modal/action.
- Reload must not be tagged, labeled, styled, or treated as an "attack".
- The UI should clearly guide the DM to reload first, then allow attack/damage resolution after reload succeeds.

Developer note:

> I don't understand what that even changed. Everything acted exactly the same. My idea was to not even allow the damage resolution modal to pop up if a reload is needed, and the reload button should pop up a confirm modal instead of being tagged as an "attack".

## Developer root-cause correction: monster action accounting / Multiattack

The developer discovered the observed failure is not primarily reload.

Browser console evidence from dmcontrol:

- Apply begins successfully.
- Repeated resolution attempts fail with: `No actions left, matey.`
- Error path:
  - `applyLocalResolutionResults`
  - `applyLocalResolutionResultsFromModal`
  - damage/effects apply path

Developer interpretation:

- The app is trying to apply player-style "turns" or "actions left" accounting to enemies/monsters.
- That should never block DM monster attack resolution this way.
- Multiattack is likely broken because each component attack is being treated as another consumed action rather than as part of one monster stat-block action.

Product direction:

- Monster/enemy attacks should not use player-character action-left bookkeeping.
- Multiattack should be modeled as a single monster action with selectable component attacks.
- A future UI improvement should provide a Multiattack modal where the DM can select/resolve separate component attacks clearly, instead of forcing dropdowns in the small bottom menu.

Rule model to preserve:

- Monsters have stat-block action options.
- Multiattack is one monster action that specifies multiple attacks/components.
- Component attacks inside Multiattack must not individually fail because "No actions left" after the first component.

## Final findings & implementation details

### 1. Root Cause
The backend method `_dm_spend_combatant_turn_resource` called `_use_action` (or bonus action/reaction) for all combatants, including monsters/enemies. This decremented `combatant.action_remaining`. Since Multiattack components are resolved as separate target resolutions, subsequent component attacks failed with `"No actions left, matey."` because the first component attack consumed the monster's only action.

### 2. Resolution
- Modified `_dm_spend_combatant_turn_resource` in `dnd_initative_tracker.py` to check `not bool(getattr(combatant, "is_pc", False))` and immediately return `True, ""` for non-PCs (monsters/enemies).
- This bypasses player-style action budget limits for monsters, ensuring Multiattack component attacks can resolve successfully.
- Preserved the existing PC-style turn/action resource blocking and verification for player characters.
- Modified `tests/test_monster_sequence_state.py` to fix unit test mock setups (`_monster_modifier_state`, `_name_role_memory`, and signature of `_monster_capability_damage_roll_packet`) and added a comprehensive regression test `test_monster_turn_resource_bypass` proving:
  1. A monster/enemy bypasses action budget checks and succeeds.
  2. A player character (PC) is still correctly checked and blocked when they run out of actions.

### 3. Reload changes context
The prior reload and modal changes were kept intact as they were correct and did not obscure the root cause.

## Developer smoke result: monster action-budget fix passed

Developer browser smoke passed for the root-cause fix:

- Multiattack works.
- The previous `No actions left, matey.` failure is no longer blocking monster/enemy Multiattack resolution.

## Remaining reload modal edge case

The reload weapon UI is broadly acceptable, but it has a remaining edge case:

- If a configured enemy has more than one weapon, the reload UI must clearly identify which weapon will be reloaded.
- The UI must not offer a fake/generic reload for a capability with no real ammunition model.
- Observed bad modal copy:

```text
The weapon Reload is out of ammunition or needs reload.

Current Ammo: 0 / 0
Reload Cost: action
Clicking Reload will consume the cost and fill the magazine to max capacity.

Reload failed: This capability does not use ammunition.
Monster reload / Multiattack product rule

For Black and Tans and similar configured enemies with reloadable weapons:

If the monster uses Multiattack, it cannot also reload as part of that Multiattack flow.
The monster gets either:
one attack and a reload, or
Multiattack.
Reload should be treated as an explicit alternative action choice in the DM UI, not as a component inside Multiattack.

## Codex fix pass: reload modal weapon targeting and Multiattack guard

Date: 2026-06-26

### Root cause of `Current Ammo: 0 / 0`

- The backend summary exposed generic `firearm_reload` placeholder capabilities such as `Reload` without weapon-target ammo metadata.
- The DM UI treated any capability with a reload-like name as a direct reload target and defaulted missing ammo fields to `0 / 0`.
- That produced a fake reload confirmation modal, then the backend resource operation correctly rejected the placeholder with `This capability does not use ammunition.`

### Fix implemented

- Added backend reload-target resolution in `dnd_initative_tracker.py` so generic reload actions now resolve to real reloadable weapon capabilities only.
- Filtered placeholder reload actions out of the DM capability summary when no real reloadable weapon exists.
- Added explicit reload metadata for multiple-weapon monsters so the DM UI can present weapon selection instead of guessing.
- Updated `assets/web/dmcontrol/index.html` to:
  - use explicit `action_type == firearm_reload` / reload-target metadata instead of `name.includes("reload")`;
  - show a weapon-selection modal when a reload action can target multiple weapons;
  - show weapon-specific reload confirmation copy;
  - block reload attempts during an active Multiattack sequence with a clear message.

### Focused validation

- `.venv/bin/python3 -m py_compile dnd_initative_tracker.py` — passed
- inline JS syntax check for `assets/web/dmcontrol/index.html` via extracted `<script>` blocks + `node --check` — passed
- `.venv/bin/python3 -m unittest tests/test_monster_sequence_state.py` — passed
- `.venv/bin/python3 -m unittest tests/test_firearm_reload.py tests/test_items_weapon_resolution.py` — passed
- `timeout 10s git diff --check` — passed

## Developer smoke failure: ammo does not decrement

Developer browser smoke failed after the reload-target cleanup.

Passed observations:

- The invalid `Current Ammo: 0 / 0` reload modal no longer appears.
- Multiattack no longer fails with `No actions left, matey.`

Failed observation:

- When attacking with a rifle, ammo count does not decrement.
- This happens for both single-shot rifle attacks and rifle use inside Multiattack.
- The UI/state continues showing the same ammo count after attack resolution.

Required behavior:

- A successful rifle/loaded-ammo attack should decrement current loaded ammo.
- Ammo decrement must apply to both single attack and Multiattack component resolution.
- Multiattack component attacks should still not consume separate PC-style actions.
- Reload remains mutually exclusive with active Multiattack.

## Codex fix pass: monster rifle ammo decrement and DM refresh

Date: 2026-06-26

### Root cause

This was multiple causes:

- Backend preview mutation:
  - `_dm_monster_capability_execute(... spend='none')` for simple monster attacks was decrementing ammo during preview generation, before the DM clicked Apply.
- Frontend stale capability summary:
  - after a successful `/resolve-targets` apply, `dmcontrol` updated the combat snapshot but did not refresh `capabilitySummary`, so the action panel kept rendering old ammo values.
- Backend apply timing risk:
  - `_dm_monster_capability_resolve_targets` spent ammo before target damage application finished, which could spend ammo even when apply later failed.

### Fix implemented

- In `dnd_initative_tracker.py`:
  - simple attack preview (`spend='none'`) no longer decrements ammo;
  - assisted apply now decrements ammo only after successful resolution/application, not before;
  - failed apply paths no longer reduce ammo;
  - Multiattack component apply uses the component capability id (for example `armalite-rifle`) so the correct weapon resource key is decremented.
- In `assets/web/dmcontrol/index.html`:
  - after successful local resolution apply, the UI now forces a capability-summary refresh for the active monster while preserving selection/sequence state so the ammo badges and detail panel show updated values immediately.

### Focused validation

- `.venv/bin/python3 -m py_compile dnd_initative_tracker.py` — passed
- inline JS syntax check for `assets/web/dmcontrol/index.html` via extracted `<script>` blocks + `node --check` — passed
- `.venv/bin/python3 -m unittest tests/test_monster_sequence_state.py` — passed
- `.venv/bin/python3 -m unittest tests/test_firearm_reload.py tests/test_items_weapon_resolution.py` — passed
- `timeout 10s git diff --check` — passed

## Final developer smoke pass: ammo decrement and reload flow

Developer browser smoke passed.

Validated behavior:

- Single rifle attack decrements rifle ammo after Apply.
- Multiattack rifle component decrements rifle ammo after Apply.
- Preview/target selection does not decrement ammo before Apply.
- Failed/canceled apply does not decrement ammo.
- Reload fills the selected weapon after ammo has been spent.
- Multiattack no longer triggers `No actions left, matey.`
- Invalid `Current Ammo: 0 / 0` reload modal no longer appears.

Final smoke evidence:

- Smoke server log: logs/smoke/BUG-20260614-weapon-attacks-reload-fail_ammo-decrement-final-smoke-server_20260626-221553.log
- Debug trace: logs/debug-trace-20260626-221553.jsonl

Final status:

BUG-20260614-weapon-attacks-reload-fail is fixed and browser-smoke-passed.

Follow-up recommendation:

Open a separate work item for a dedicated Multiattack modal UI. That follow-up should not be part of this bug closeout.

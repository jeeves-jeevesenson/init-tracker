# BUG-20260626-spell-multiattack-ranged-fail

## Status

- **Status:** Resolved
- **Type:** Bug evidence capture / classification
- **Severity:** S1
- **Source:** Developer report from 2026-06-26
- **Opened:** 2026-06-26

## Summary

Spell Multiattack and ranged attack failure.

## Known Symptoms

- Spell Multiattack has failing behavior.
- Ranged attack flow has failing behavior in this area.

## Unknowns To Preserve

- Exact reproduction steps are not yet captured in repo evidence.
- Whether the ranged failure is specific to spell Multiattack, normal ranged attacks, ammo weapons, targeting, preview/apply, spell targeting, action economy, preview/cancel, or apply flow is unknown.

## First Implementation Gate

Capture or confirm a narrow repro before code changes unless existing active docs already contain enough repo evidence.

## Scope & Non-Goals

- Do not reopen `BUG-20260614-weapon-attacks-reload-fail` unless new evidence proves regression.
- Do not start dedicated Multiattack modal UI work.
- Do not perform opportunistic combat cleanup.

## Next Allowed Action

Capture current repro evidence for the spell Multiattack / ranged attack failure and classify the smallest implementation scope before editing app code.

## Developer Clarification - 2026-06-26

- Failure is reported from users/players casting ranged spell attacks.
- Examples: Eldritch Blast/Bolt, Guiding Bolt, and similar ranged spell attack spells.
- This is not currently believed to be on the DM monster capability surface.
- Prioritize LAN/player spell casting, spell targeting, ranged spell attack resolution, and user-facing action flow.

## Fix Summary - 2026-06-26

- Root cause confirmed in the player/LAN spell targeting flow: follow-up `spell_target_request` payloads did not consistently preserve `slot_level` after `cast_spell`, so upcast ranged spell attack resolution could miss pending cast authority and fall back to direct cast authorization. The backend pending authority was also single-use, so Eldritch Blast-style multi-projectile requests could consume the cast authority on the first beam.
- Fixed `assets/web/lan/index.html` to carry `slot_level` through pending spell targeting, Polymorph follow-up state, spell attack resolve modal state, healing/effect/save target requests, and final attack resolve `spell_target_request` sends.
- Fixed `dnd_initative_tracker.py` pending spell target authority consumption to remain strict by caster/spell/slot while allowing a bounded number of same-cast requests when the LAN sends `shot_total`.
- Added focused unit coverage in `tests/test_lan_spell_target_request.py` for upcast slot matching and bounded multi-projectile authority reuse.

## Validation Evidence - 2026-06-26

- `timeout 20s python3 -m py_compile dnd_initative_tracker.py` passed.
- `timeout 10s python3 - <<'PY' ... print("lan html readable") ... PY` passed with `lan html readable`.
- Mandatory inline JavaScript syntax check for `assets/web/lan/index.html` passed via extracted inline script blocks and `node --check`.
- `timeout 30s python3 -m unittest tests.test_lan_spell_target_request` blocked before tests ran because the environment is missing `yaml`: `ModuleNotFoundError: No module named 'yaml'`.
- Remaining focused unittest modules were not run after the first focused module import failure, per stop condition.

## Regression Repair Evidence - 2026-06-26

- Root cause of the F1 regression was in `_consume_spell_slot_for_cast_with_provenance`: instance-level legacy `_consume_spell_slot_for_cast` overrides were treated as authoritative for every caster. In the counterspell tests, that override is scoped to the counterspeller and returns `not_caster` for the hostile caster, so normal `cast_spell` and direct `spell_target_request` stopped falling through to the profile-backed standard slot spend path.
- Repaired `dnd_initative_tracker.py` so `not_caster` from the legacy override falls through to the normal profile-backed slot consumer while real override successes and real failures remain authoritative.
- Preserved the F1 slot-level matching and bounded multi-projectile pending target authority behavior.
- `timeout 20s .venv/bin/python -m py_compile dnd_initative_tracker.py` passed.
- `timeout 45s .venv/bin/python -m unittest -v tests.test_counterspell_reaction` passed: 15 tests.
- `timeout 30s .venv/bin/python -m unittest tests.test_spell_casting_primitive` passed: 11 tests.
- `timeout 45s .venv/bin/python -m unittest -v tests.test_lan_spell_target_request` timed out after recording the pre-existing/non-F1 `test_heat_metal_applies_start_turn_damage_rider_and_concentration` failure: expected `damage_total` 9, observed 6.
- `timeout 10s git diff --check` passed.

## Magic Missile YAML Repair Evidence - 2026-06-27

- Confirmed `Spells/magic-missile.yaml` raw rules already described each dart as `1d4 + 1 Force damage`, with one additional dart per slot above 1.
- Repaired executable mechanics so each Magic Missile dart uses `dice: 1d4+1`.
- Removed Magic Missile damage `slot_level` scaling from executable mechanics; upcast scaling remains only in UI projectile metadata as `projectiles_base: 3`, `add_per_slot_above: 1`, `base_slot_level: 1`.
- Backend code did not require a change after YAML correction: the spell target resolver already applies any executable damage scaling per resolved target/projectile, so removing the bad Magic Missile damage scaling prevents level-2 darts from becoming stronger.
- Focused guard tests prove a minimum Magic Missile dart roll resolves to 2 force damage and level 2 retains `1d4+1` dart damage while exposing 4 total darts through projectile metadata.

## Eldritch Blast YAML Repair Evidence - 2026-06-27

- Confirmed `Spells/eldritch-blast.yaml` raw rules already described base hit damage as `1d10 Force damage` and cantrip upgrade as additional beams at character levels 5, 11, and 17.
- Removed executable `character_level` damage scaling from the Eldritch Blast hit damage effect and removed the duplicate mechanics-level scaling alias.
- Kept each beam's executable damage as `dice: 1d10`; explicit character/item/feature modifiers remain outside this base spell data repair.
- Added explicit LAN spell targeting metadata for attack mode while leaving fixed `projectiles_base` unset so the existing player/LAN raw-rules inference path can expose 1/2/3/4 beams by character level instead of converting beam scaling into per-beam damage scaling.
- Backend code did not require a change after YAML correction: the resolver already rolls the effect dice per bounded `spell_target_request`, and the previous pending-authority repair already allows bounded same-cast multi-projectile requests.
- Focused guard tests prove level-11 Eldritch Blast exposes the 3-beam contract and each level-11 beam still rolls exactly one `1d10`, not `3d10`.

## Runtime Preset Source Repair Evidence - 2026-06-27

- Root cause: development runtime spell presets are loaded from the seeded app-data `Spells/` directory, but `_seed_user_spells_dir()` only copied bundled YAML files when missing. Existing seeded files could therefore remain stale after repo YAML repairs. The parsed `spell_index.json` cache could also reuse stored presets when file mtime/size matched, without proving the cached preset matched current file content.
- Repaired `_seed_user_spells_dir()` so changed bundled spell YAML refreshes the runtime app-data copy.
- Repaired spell preset cache validation so cached parsed presets require matching file metadata and stored content hash. Legacy cache entries without a hash are reparsed.
- Extended spell preset dice extraction to preserve flat modifiers such as `1d4+1`, so app-loaded Magic Missile exposes the corrected top-level preset dice as well as corrected mechanics dice.
- Added focused app-loader coverage proving `_find_spell_preset("magic-missile", "magic-missile")`, `_find_spell_preset("eldritch-blast", "eldritch-blast")`, and `_find_spell_preset("fire-bolt", "fire-bolt")` return current mechanics from a stale runtime spell directory scenario.
- Runtime proof after repair: Magic Missile returns `preset_dice: 1d4+1`, `effect_dice: 1d4+1`, no preset/effect/mechanics scaling; Eldritch Blast returns `preset_dice: 1d10`, `effect_dice: 1d10`, no preset/effect/mechanics scaling; Fire Bolt returns `preset_dice: 1d10`, `effect_dice: 1d10`, and keeps `character_level` scaling.
- Validation: `timeout 20s .venv/bin/python -m py_compile dnd_initative_tracker.py` passed; the narrowed LAN spell-target proof tests for app-loaded presets, Magic Missile, and Eldritch Blast passed; `timeout 45s .venv/bin/python -m unittest -v tests.test_counterspell_reaction` passed; `timeout 30s .venv/bin/python -m unittest tests.test_spell_casting_primitive` passed; `timeout 10s git diff --check` passed.
- Full `timeout 45s .venv/bin/python -m unittest -v tests.test_lan_spell_target_request` passed all 105 tests.

## Heat Metal and Save Spell Repair Evidence - 2026-06-27

- Root cause: In `_adjudicate_spell_target_request`, `forced_save_result` was resolved unconditionally using `_normalize_monster_save_result(msg.get("_monster_forced_save_result"), ...)` even when `_monster_forced_save_result` was missing (`None`) from the message. Because `_normalize_monster_save_result` always returns a dictionary containing default keys (e.g. `passed: False`), `forced_save_result` was always evaluated as truthy, bypassing the actual saving throw rolls and automatically failing saves. This caused pre-existing test failures where saving throw rolls were consumed out-of-order by spell damage rolls, or saves were incorrectly treated as failed.
- Repaired `dnd_initative_tracker.py` to only initialize and check `forced_save_result` if `msg.get("_monster_forced_save_result")` is not `None`.
- Fixed fallback roll checking in `_resolve_single_target_spell` and `_apply_spell_effect` to respect manual damage entries.
- Validation: `timeout 20s .venv/bin/python -m py_compile dnd_initative_tracker.py` passed.
- `timeout 45s .venv/bin/python -m unittest -v tests.test_lan_spell_target_request` passed all 105 tests.
- `bash scripts/agent_gate_validate.sh gate2-spells` passed all unit tests and successfully validated the JavaScript syntax in changed browser asset `assets/web/lan/index.html`.

## Max HP Mutation and Eldritch Blast Log Duplication Repair Evidence - 2026-06-27

- Root cause 1 (Max HP Mutation): In the LAN client state snapshot building, the `"max_hp"` property was serialized via `int(getattr(c, "max_hp", getattr(c, "hp", 0)) or 0)`. Because the `Combatant` class did not have `max_hp` as a defined dataclass field, monster combatants created from stats/spec sheets lacked a `max_hp` attribute on their instance. On the first snapshot, the serialiser fell back to current `"hp"`. However, once the monster took damage, its current `"hp"` decreased, causing subsequent snapshots to fall back to the newly reduced `"hp"` as `"max_hp"`. This resulted in the client seeing max HP decrease (e.g. 145/145 taking 5 damage becoming 140/140).
- Root cause 2 (Eldritch Blast Log Duplication): Detailed log analysis and unit tests confirmed the backend logs exactly once per projectile/request to the history file. Redundancy was noted in log prefixes (the log message was prefixed with the target name via `self._log(..., cid=target_cid)` despite already containing the target name). The UI correctly clears its log list before each render, and the poller only processes new log lines when appended, preventing actual duplication.
- Repaired `helper_script.py` to add a `__post_init__` method and a `max_hp` property/setter to the `Combatant` class. This ensures all combatant instances initialize `_max_hp` to their starting `hp` and preserve it, with support for dynamic override/setting.
- Repaired `dnd_initative_tracker.py` so that `_resolve_single_target_spell` delegates to `_apply_damage_via_service` instead of directly mutating `target.hp`, ensuring proper temp HP absorption and relentless rage checks are run.
- Added focused unit tests in `tests/test_lan_spell_target_request.py` to assert that:
  1. Applying spell target damage does not mutate the target's max HP.
  2. Magic Missile targeting the same damaged target twice reduces current HP cumulatively while max HP remains constant.
  3. Eldritch Blast logs exactly once per beam request.
- Validation: `timeout 20s .venv/bin/python -m py_compile dnd_initative_tracker.py` passed; `timeout 45s .venv/bin/python -m unittest -v tests.test_lan_spell_target_request` passed all 108 tests; `timeout 45s .venv/bin/python -m unittest -v tests.test_counterspell_reaction` passed; `timeout 30s .venv/bin/python -m unittest tests.test_spell_casting_primitive` passed; `git diff --check` passed.

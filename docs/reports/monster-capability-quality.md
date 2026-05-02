# Monster Capability Quality Report

## Summary
- Total overlays scanned: 16
- Total capabilities scanned: 56
- Hard errors: 0
- Warnings: 12

## Per-Monster Summary

| Slug | File | Capabilities | Errors | Warnings |
|------|------|--------------|--------|----------|
| adult-red-dragon | `monster_capabilities/samples/adult-red-dragon.yaml` | 10 | 0 | 2 |
| archmage | `monster_capabilities/samples/archmage.yaml` | 3 | 0 | 0 |
| bandit | `monster_capabilities/samples/bandit.yaml` | 2 | 0 | 0 |
| bugbear | `monster_capabilities/samples/bugbear.yaml` | 4 | 0 | 1 |
| bugbear-warrior | `monster_capabilities/samples/bugbear-warrior.yaml` | 4 | 0 | 1 |
| cultist | `monster_capabilities/samples/cultist.yaml` | 2 | 0 | 0 |
| goblin | `monster_capabilities/samples/goblin.yaml` | 3 | 0 | 1 |
| goblin-warrior | `monster_capabilities/samples/goblin-warrior.yaml` | 3 | 0 | 1 |
| kobold | `monster_capabilities/samples/kobold.yaml` | 4 | 0 | 2 |
| kobold-warrior | `monster_capabilities/samples/kobold-warrior.yaml` | 4 | 0 | 2 |
| ogre | `monster_capabilities/samples/ogre.yaml` | 2 | 0 | 0 |
| orc | `monster_capabilities/samples/orc.yaml` | 3 | 0 | 1 |
| skeleton | `monster_capabilities/samples/skeleton.yaml` | 2 | 0 | 0 |
| troll | `monster_capabilities/samples/troll.yaml` | 5 | 0 | 0 |
| wolf | `monster_capabilities/samples/wolf.yaml` | 3 | 0 | 1 |
| zombie | `monster_capabilities/samples/zombie.yaml` | 2 | 0 | 0 |

## Detailed Findings

### adult-red-dragon

- File: `monster_capabilities/samples/adult-red-dragon.yaml`
- WARNING `manual_action_without_warning` `legendary-resistance`: Display-only/manual capability has no warning or reason.
- WARNING `manual_action_without_warning` `tail-attack`: Display-only/manual capability has no warning or reason.

### bugbear

- File: `monster_capabilities/samples/bugbear.yaml`
- WARNING `manual_action_without_warning` `brute`: Display-only/manual capability has no warning or reason.

### bugbear-warrior

- File: `monster_capabilities/samples/bugbear-warrior.yaml`
- WARNING `manual_action_without_warning` `brute`: Display-only/manual capability has no warning or reason.

### goblin

- File: `monster_capabilities/samples/goblin.yaml`
- WARNING `manual_action_without_warning` `nimble-escape`: Display-only/manual capability has no warning or reason.

### goblin-warrior

- File: `monster_capabilities/samples/goblin-warrior.yaml`
- WARNING `manual_action_without_warning` `nimble-escape`: Display-only/manual capability has no warning or reason.

### kobold

- File: `monster_capabilities/samples/kobold.yaml`
- WARNING `manual_action_without_warning` `pack-tactics`: Display-only/manual capability has no warning or reason.
- WARNING `manual_action_without_warning` `sunlight-sensitivity`: Display-only/manual capability has no warning or reason.

### kobold-warrior

- File: `monster_capabilities/samples/kobold-warrior.yaml`
- WARNING `manual_action_without_warning` `pack-tactics`: Display-only/manual capability has no warning or reason.
- WARNING `manual_action_without_warning` `sunlight-sensitivity`: Display-only/manual capability has no warning or reason.

### orc

- File: `monster_capabilities/samples/orc.yaml`
- WARNING `manual_action_without_warning` `aggressive`: Display-only/manual capability has no warning or reason.

### wolf

- File: `monster_capabilities/samples/wolf.yaml`
- WARNING `manual_action_without_warning` `pack-tactics`: Display-only/manual capability has no warning or reason.

## Rules Checked

### Hard Errors

- YAML unreadable or malformed.
- Missing top-level name, slug, or capabilities list.
- Duplicate capability ids within one overlay.
- Executable attack missing attack_bonus or damage entries.
- Executable damage entry missing formula.
- Save ability missing save_dc or save_ability.
- Save ability damage missing explicit on_save metadata.
- Composite child missing both action_id and name.
- Applyable condition effect uses an unsupported condition.
- Recharge or limited-use metadata is impossible to interpret.

### Warnings

- Save ability text mentions area/range but mechanics.shape is missing.
- Damage type missing or unspecified.
- Executable action carries importer uncertainty warning.
- Composite child is unmatched to a local capability.
- Spellcasting group references a local-unmatched spell slug.
- Condition rider appears time-bound but has no duration metadata.
- Condition effect is missing condition metadata.
- Capability has no desc/display text.
- Display-only/manual capability has no warning or reason.
- Source/license fields are missing or vague.
- Duplicate monster slug across overlay files.
- Overlay file path slug does not match top-level slug.

# Runtime Regression Capture: BUG-20260626-player-map-drag-pan-broken

- **Date**: 2026-06-26
- **Discovered during**: BUG-20260614-reactions-hold-combat browser smoke
- **Severity**: Smoke blocker / player-surface navigation regression
- **Surface affected**: Player/LAN root surface at http://127.0.0.1:8787/
- **Surface not affected**: DM control surface
- **Observed**: Drag panning the map is broken.
- **Observed**: Lock Map makes no difference.
- **Observed**: WASD panning still works.
- **Required action**: Hard stop reactions closeout until this is fixed or explicitly waived.

## Git status at capture

```text
 M dnd_initative_tracker.py
 M docs/work_items/active/BUG-20260614-reactions-hold-combat.md
 M player_command_service.py
?? docs/runtime_reports/BUG-20260614-reactions-hold-combat_gate2_implementation_20260619.md
?? docs/runtime_reports/BUG-20260614-reactions-hold-combat_gate2b_ally_filter_20260620.md
?? docs/runtime_reports/BUG-20260626-player-map-drag-pan-broken_capture_20260626-084603.md
?? tests/test_reaction_prompt_ally_filter.py
?? tests/test_reaction_prompt_expiry_resume.py
```

## Diff stat at capture

```text
 dnd_initative_tracker.py                           |  7 ++
 .../active/BUG-20260614-reactions-hold-combat.md   | 38 ++++++++---
 player_command_service.py                          | 75 +++++++++++++++++++++-
 3 files changed, 107 insertions(+), 13 deletions(-)
```

## Latest smoke log

- **Path**: logs/smoke/BUG-20260614-reactions-hold-combat_smoke-server_20260626-084055.log

```text
[2026-06-26 08:40:56] WARNING Spell YAML level-0-5-tag-review.yaml missing name; skipping preset.
[2026-06-26 08:40:59] WARNING Player YAML Fred: inventory item 'dagger' is missing explicit instance_id; using fallback 'derived:dagger__001'.
[2026-06-26 08:40:59] WARNING Player YAML unknown: inventory item 'dagger' is missing explicit instance_id; using fallback 'derived:dagger__001'.
[2026-06-26 08:41:02] WARNING Player YAML Throat Goat: inventory item 'sword_of_wounding' is missing explicit instance_id; using fallback 'derived:sword_of_wounding__001'.
[2026-06-26 08:41:02] WARNING Player YAML unknown: inventory item 'sword_of_wounding' is missing explicit instance_id; using fallback 'derived:sword_of_wounding__001'.
[2026-06-26 08:41:05] INFO YAML player cache refreshed: enabled_profiles=10
Headless tracker started.
  Debug trace: logs/debug-trace-20260626-084055.jsonl
  DM operator surface: http://10.3.25.235:8787/dm
  Player LAN surface:  http://10.3.25.235:8787/
Press Ctrl+C to stop.
[2026-06-26 08:41:15] INFO LAN server hoisted at http://10.3.25.235:8787/  (open on yer phone, matey)
[2026-06-26 08:41:16] INFO Update available (headless mode); desktop prompt skipped: New commits available on main branch
Your commit: c56602f
Latest commit: de9ec7d
Message: Add AGY token burn research brief...
[2026-06-26 08:42:39] INFO LAN session connected ws_id=140461620146448 host=127.0.0.1:45248 ua=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/149.0.0.0 Safari/537.36
[2026-06-26 08:42:42] INFO LAN session connected ws_id=140461620289936 host=127.0.0.1:45282 ua=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/149.0.0.0 Safari/537.36
[2026-06-26 08:42:44] INFO LAN session disconnected ws_id=140461620289936
[2026-06-26 08:43:45] INFO LAN session ws_id=140461620146448 claimed Dorian (Assigned.)
[2026-06-26 08:43:47] INFO LAN session connected ws_id=140461527650096 host=127.0.0.1:42876 ua=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/149.0.0.0 Safari/537.36
[2026-06-26 08:43:49] INFO LAN session ws_id=140461527650096 claimed Eldramar (Assigned.)

```

# BUG-20260627-manage-spells-free-spell-limit-and-save-failures-evidence-AGY-20260627-manage-spells-evidence-01

- **Task ID**: AGY-20260627-manage-spells-evidence-01
- **Timestamp**: 2026-06-27T17:20:18-05:00

---

## 1. Current Git Status Summary

```
 M Spells/eldritch-blast.yaml
 M Spells/magic-missile.yaml
 M assets/web/lan/index.html
 M dnd_initative_tracker.py
RM docs/work_items/active/BUG-20260626-spell-multiattack-ranged-fail.md -> docs/work_items/completed/BUG-20260626-spell-multiattack-ranged-fail.md
 M docs/work_items/current_work.md
 M helper_script.py
 M tests/test_lan_spell_target_request.py
```

---

## 2. Source Docs Read

1. [inbox/BUG-20260627-manage-spells-free-spell-limit-and-save-failures.md](file:///home/a2-jeeves@iamjeeves.dev/src/init-tracker/docs/bug_reports/inbox/BUG-20260627-manage-spells-free-spell-limit-and-save-failures.md)
2. [active/BUG-20260627-manage-spells-free-spell-limit-and-save-failures.md](file:///home/a2-jeeves@iamjeeves.dev/src/init-tracker/docs/work_items/active/BUG-20260627-manage-spells-free-spell-limit-and-save-failures.md)
3. [current_work.md](file:///home/a2-jeeves@iamjeeves.dev/src/init-tracker/docs/work_items/current_work.md)
4. [task-packet.md](file:///home/a2-jeeves@iamjeeves.dev/src/init-tracker/docs/agent_tasks/templates/task-packet.md)

---

## 3. Relevant Files and Code Paths Identified

1. **[assets/web/lan/index.html](file:///home/a2-jeeves@iamjeeves.dev/src/init-tracker/assets/web/lan/index.html)**:
   - `applySpellbookAddWithMode`: Lines 21369–21411 (limit policy check blocks free spells if limit is already met).
   - `applySpellbookRemove`: Lines 21413–21445 (removing spells from lists).
   - `renderSpellbook`: Lines 21178–21250 (locks free spells lists rendering with `{locked: true}`).
   - `characterSlugify`: Lines 6329–6333 (strips Cyrillic characters, returning `""`).
2. **[dnd_initative_tracker.py](file:///home/a2-jeeves@iamjeeves.dev/src/init-tracker/dnd_initative_tracker.py)**:
   - `_save_player_spellbook`: Lines 30524–30690 (endpoints and profile updates).
   - `_find_player_profile_path`: Lines 25321–25359 (profile path resolution by name/slug).
   - `_sanitize_player_filename`: Lines 25530–25534 (sanitizer that converts Cyrillic names to `"player"`).
3. **[tests/test_spellbook_free_spells.py](file:///home/a2-jeeves@iamjeeves.dev/src/init-tracker/tests/test_spellbook_free_spells.py)**:
   - Pre-existing tests for spellbook free spells. Currently has 5 failures due to mock lambdas for `_write_player_yaml_atomic` lacking the `invalidation_domains` argument.

---

## 4. Log Evidence Found

### Trace Log: `logs/debug-trace-20260627-122507.jsonl`
Eldramar's `POST /api/players/Eldramar/spellbook` request returned `200 OK` successfully:
```json
{"ts":"2026-06-27T17:27:57.899Z","level":"debug","event":"http.request.start","trace_id":"trace-7eeba9c6347c4d79aba48bb268f969e7","span":null,"action_id":"action-74938c9604fa41f9ab2ce03e92a5d651","route":"/api/players/Eldramar/spellbook","method":"POST","query_keys":[]}
{"ts":"2026-06-27T17:28:02.898Z","level":"debug","event":"http.request.end","trace_id":"trace-7eeba9c6347c4d79aba48bb268f969e7","span":null,"action_id":"action-74938c9604fa41f9ab2ce03e92a5d651","status_code":200,"duration_ms":4998.776,"ok":true,"sizes":{"response_bytes":15915},"route":"/api/players/Eldramar/spellbook","method":"POST","query_keys":[]}
```

There are **no** POST requests logged for `Ctihiya` or Cyrillic `%D1%81%D1%82%D0%B8%D1%85%D0%B8%D1%8F` in the trace files.

---

## 5. Reproduction and Evidence Gaps

1. **Browser Console Output**: We lack browser console trace logs from Stikhiya/Ctihiya's browser when saving fails.
2. **UI Interactivity Check**: We need browser smoke testing to verify whether a JavaScript error is thrown on click or if the Save button remains disabled.

---

## 6. Diagnosis Hypothesis (Hypothesis Only)

1. **Free Spell Addition Blocked**: 
   When adding a free spell, `delta` is `0`. However, the limit check in the frontend client does:
   `getSpellbookCurrentCount(limitKey) + delta > limitPolicy.max`
   If the limit is already met or exceeded (e.g., 19 prepared spells when max is 18), `current_count + 0 > max` evaluates to `true`, causing the add to be incorrectly blocked despite not consuming any non-free slots.
   
2. **Free Spell Removal Locked**: 
   In `renderSpellbook`, free prepared spells are filtered out of the Selected Spells list (`rightSlugs`) and placed in a dedicated Free Spells list (`spellbookFreePreparedList`). However, this list is rendered with the option `{locked: true}`, which prevents click listeners and item selection. Since these items cannot be selected, the user cannot click the "Remove" button to remove them.

3. **Ctihiya/Stikhiya Save Failure**: 
   - The character is named `"стихия"` (Cyrillic), transliterated as `"Ctihiya"`.
   - On the client-side, `characterSlugify` uses a regex `/[^\w\s-]/g` to strip non-alphanumeric characters. Because JS regex `\w` is ASCII-only, it strips all Cyrillic characters, producing an empty string `""` as the slug. This breaks client-side player profile lookup (`getPlayerProfile`), mapping, and state validation.
   - If a save request is made with the name `"Ctihiya"` (Latin), `_find_player_profile_path` returns `None` since the file is named `"стихия.yaml"`. The fallback path `_sanitize_player_filename` strips all Cyrillic characters, returning `"player.yaml"`, causing a file collision or lookup failure on reload.

---

## 7. Recommended Next Task

An **implementation repair** task is recommended to address these three bugs, as the root causes and exact line ranges have been identified.

---

## 8. Exact Files to Inspect in Next Task
1. [assets/web/lan/index.html](file:///home/a2-jeeves@iamjeeves.dev/src/init-tracker/assets/web/lan/index.html)
2. [dnd_initative_tracker.py](file:///home/a2-jeeves@iamjeeves.dev/src/init-tracker/dnd_initative_tracker.py)
3. [tests/test_spellbook_free_spells.py](file:///home/a2-jeeves@iamjeeves.dev/src/init-tracker/tests/test_spellbook_free_spells.py)

---

## 9. Exact Validation Commands Recommended for Next Task
1. `timeout 20s .venv/bin/python -m py_compile dnd_initative_tracker.py`
2. `timeout 45s .venv/bin/python -m unittest tests/test_spellbook_free_spells.py` (after fixing the mock lambdas to accept `invalidation_domains`)
3. JavaScript syntax validation:
   - Extract script blocks from `assets/web/lan/index.html` and run `node --check`.
4. `git status --short`
5. `git diff --check`

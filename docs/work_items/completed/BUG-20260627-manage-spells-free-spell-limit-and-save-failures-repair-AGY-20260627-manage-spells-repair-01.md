# BUG-20260627-manage-spells-free-spell-limit-and-save-failures-repair-AGY-20260627-manage-spells-repair-01

- **Task ID**: AGY-20260627-manage-spells-repair-01
- **Timestamp**: 2026-06-27T17:24:32-05:00

---

## 1. Files Changed

- [assets/web/lan/index.html](file:///home/a2-jeeves@iamjeeves.dev/src/init-tracker/assets/web/lan/index.html)
- [dnd_initative_tracker.py](file:///home/a2-jeeves@iamjeeves.dev/src/init-tracker/dnd_initative_tracker.py)
- [tests/test_spellbook_free_spells.py](file:///home/a2-jeeves@iamjeeves.dev/src/init-tracker/tests/test_spellbook_free_spells.py)

---

## 2. Summary of Each Repair

### A. Free Spell Addition Limit
- **Bug**: Free spell additions were blocked when the normal known/prepared count reached or exceeded max limits, because the check evaluated `current_count + 0 > max`.
- **Fix**: Adjusted the condition in `applySpellbookAddWithMode(addAsFree)` inside [assets/web/lan/index.html](file:///home/a2-jeeves@iamjeeves.dev/src/init-tracker/assets/web/lan/index.html) to:
  `if (delta > 0 && Number.isFinite(Number(limitPolicy.max)) && getSpellbookCurrentCount(limitKey) + delta > limitPolicy.max)`
  This bypasses limit checks entirely for free spells (where `delta === 0`), while preserving limit validation for standard non-free spells.

### B. Free Spell Removal
- **Bug**: Free prepared spells were rendered in a separate Free Spells list (`spellbookFreePreparedList`) with `{locked: true}` and an empty selection set, making them unselectable and impossible to remove.
- **Fix**: Updated the rendering logic in `renderSpellbook` inside [assets/web/lan/index.html](file:///home/a2-jeeves@iamjeeves.dev/src/init-tracker/assets/web/lan/index.html) to render the list with `spellbookRightSelection` as the selection set and `locked: !modeActions.remove`. When removal is permitted in the current mode, the free spells list becomes interactive, enabling the user to select and remove these spells.

### C. Unicode/Cyrillic Player Profile Save
- **Bug**: 
  1. Client-side `characterSlugify` stripped Cyrillic letters to produce an empty string `""` due to JS `\w` matching ASCII-only.
  2. Backend `_sanitize_player_filename` stripped Cyrillic characters to produce `"player.yaml"` filename write collisions.
- **Fix**:
  1. Updated client-side `characterSlugify` in [assets/web/lan/index.html](file:///home/a2-jeeves@iamjeeves.dev/src/init-tracker/assets/web/lan/index.html) to use Unicode property escapes: `.replace(/[^\p{L}\p{N}]+/gu, "-")`.
  2. Updated backend `_sanitize_player_filename` in [dnd_initative_tracker.py](file:///home/a2-jeeves@iamjeeves.dev/src/init-tracker/dnd_initative_tracker.py) to use a Unicode-aware regex allowing word characters, dot, and hyphen: `re.sub(r"[^\w.-]+", "-", name)`.

### D. Mock Signature Hardening in Unit Tests
- **Bug**: Standard tests failed due to parameter mismatches when mock lambdas for `_write_player_yaml_atomic` and `_schedule_player_yaml_refresh` did not accept optional keyword parameters (like `invalidation_domains` or `include_static`).
- **Fix**: Updated the mocked functions in [tests/test_spellbook_free_spells.py](file:///home/a2-jeeves@iamjeeves.dev/src/init-tracker/tests/test_spellbook_free_spells.py) to accept `*args` and `**kwargs`.

---

## 3. Preservation of Behavior

- **Free spell limit**: Limits continue to be strictly enforced for standard non-free spell additions.
- **Unicode/Cyrillic mapping**: Preserves all existing ASCII player matching and filename structures without change.

---

## 4. Validation Commands and Output

### 1. Git short status
- **Command**: `git status --short`
- **Result**: Checked and listed below.

### 2. Python Compile check
- **Command**: `timeout 20s ./.venv/bin/python3 -m py_compile dnd_initative_tracker.py`
- **Result**: Passed (exited successfully with code 0).

### 3. Pytest check (Missing module)
- **Command**: `timeout 90s ./.venv/bin/python3 -m pytest tests/test_spellbook_free_spells.py -q`
- **Result**: Failed (exit code 1) because `pytest` is not installed in the `.venv` virtual environment:
  `/home/a2-jeeves@iamjeeves.dev/src/init-tracker/.venv/bin/python3: No module named pytest`
- **Fallback verification**: Ran the test suite via python standard `unittest` module:
  `./.venv/bin/python3 -m unittest tests/test_spellbook_free_spells.py`
  - **Result**: `OK` (Ran 11 tests in 0.004s).

### 4. Git diff check
- **Command**: `timeout 10s git diff --check`
- **Result**: Passed (exited successfully with code 0).

### 5. Inline JavaScript syntax check
- **Command**: `bash scripts/agent_gate_validate.sh A0`
- **Result**: Passed.
  `JS syntax check passed for assets/web/lan/index.html`

---

## 5. Remaining Evidence or Browser-Smoke Needs

- Developer browser smoke testing is required on the player surface `/` to verify:
  1. Eldramar can prepare a free spell when at or over the maximum prepared count.
  2. Eldramar can select and remove/unprepare a free spell.
  3. Saving changes for Cyrillic-named characters (e.g. `стихия`) works and persists correctly across client reload.

---

## 6. Current Git Status

```
 M assets/web/lan/index.html
 M dnd_initative_tracker.py
 M docs/work_items/current_work.md
 M tests/test_spellbook_free_spells.py
?? docs/bug_reports/inbox/BUG-20260626-dmcontrol-terrain-not-visible.md
?? docs/bug_reports/inbox/BUG-20260627-manage-spells-free-spell-limit-and-save-failures.md
?? docs/work_items/active/BUG-20260627-manage-spells-free-spell-limit-and-save-failures-evidence-AGY-20260627-manage-spells-evidence-01.md
?? docs/work_items/active/BUG-20260627-manage-spells-free-spell-limit-and-save-failures-repair-AGY-20260627-manage-spells-repair-01.md
?? docs/work_items/active/BUG-20260627-manage-spells-free-spell-limit-and-save-failures.md
?? logs/context/
```

---

## 7. Recommended Next Action

The active work item `BUG-20260627-manage-spells-free-spell-limit-and-save-failures` is ready for the developer's live browser smoke testing.

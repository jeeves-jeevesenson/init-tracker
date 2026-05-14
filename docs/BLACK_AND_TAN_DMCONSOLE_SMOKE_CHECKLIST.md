# Black and Tan DM Console Smoke Checklist

This checklist is for verifying that all Black and Tan enemies are ready for live-play usage in the `/dmcontrol` console.

## Test Setup

1.  Start the application: `INIT_TRACKER_HEADLESS=1 ./venv/bin/python3 serve_headless.py`
2.  Open the DM Cockpit: `http://localhost:8000/dm` (to authenticate and setup combat).
3.  Open the DM Control page: `http://localhost:8000/dmcontrol`
4.  Add a Player character to the combat.
5.  Add at least one of each Black and Tan enemy to the combat.
6.  Start combat and advance initiative to each Black and Tan enemy.

## General Checks (All Enemies)

- [ ] **Selection:** Clicking an enemy action card selects it and shows the summary.
- [ ] **Targeting:** Entering "Target Preview" shows the correct range/reach circle on the map.
- [ ] **Target Selection:** Clicking the Player token on the map selects it as a target.
- [ ] **Resolution Modal:** Clicking "Preview Result" (or auto-preview) opens the resolution modal.
- [ ] **Outcome Selection:** Modal shows "Hit/Miss" for attacks and "Failed Save/Successful Save" for saves.
- [ ] **Apply Result:** Clicking "Apply Result" updates the Player's HP/state and clears the modal.
- [ ] **Multiattack:** "Start Sequence" button appears for Multiattack. Children can be executed individually.
- [ ] **Traits & Reminders:** Passive traits and manual-only actions are correctly collapsed and readable.

## Enemy-Specific Checks

### 1. Constable
- [ ] **Baton Hit:** Verify that "Rough Arrest" rider prompt appears in the modal after a Hit.
- [ ] **Multiattack:** Verify `choose_n: 2` allows any combination of Pistol and Baton.

### 2. Rifleman
- [ ] **Armalite Rifle:** Verify range (120/360) and damage (1d12+4).
- [ ] **Controlled Burst:** Verify it can be armed, adds a die to the next hit, and clears after use.
- [ ] **Jam Risk:** Verify that a natural 1 after Controlled Burst marks the weapon as "Jammed".

### 3. Shield Trooper
- [ ] **Shield Bash:** Verify "Shield Bash Save" rider prompt appears after a Hit.
- [ ] **Multiattack:** Verify `choose_n: 2` allows Pistol, Baton, and Shield Bash.

### 4. Suppression Gunner
- [ ] **Suppressive Fire / Automatic Sweep:** Verify these appear in "Traits & Reminders" with a "Manual Assist" badge.
- [ ] **Brace / Reload:** Verify these are executable utility actions.

### 5. Field Medic
- [ ] **Field Treatment:** Verify it appears in "Traits & Reminders" with "Manual Assist" and "1/encounter" summary.
- [ ] **Multiattack:** Verify `choose_n: 2` allows Pistol and Field Treatment (reminder).

### 6. Lieutenant
- [ ] **Multiattack:** Verify `choose_n: 3` allows flexible combination of 3 attacks.
- [ ] **Direct Fire:** Verify it is a "Manual Assist" bonus action.

### 7. Captain
- [ ] **Multiattack:** Verify 3 flexible attacks.
- [ ] **Condemn the Target:** Verify it is a "Manual Assist" action.

### 8. Major
- [ ] **Multiattack:** Verify 3 flexible attacks.
- [ ] **Make an Example:** Verify it is a "Manual Assist" action with DC 16 WIS summary.

## Performance & UX

- [ ] **Latency:** Apply Result should feel responsive (under 2 seconds).
- [ ] **Stability:** No page reloads or layout jumps when applying results.
- [ ] **Mobile/Small Screen:** Bottom bar height can be adjusted using the split handle.

## Pass/Fail Criteria

- **Pass:** All primary actions can be resolved and applied. All manual actions have clear instructions.
- **Fail:** Any server-side error (500), UI crash (white screen), or failure to update combat state.

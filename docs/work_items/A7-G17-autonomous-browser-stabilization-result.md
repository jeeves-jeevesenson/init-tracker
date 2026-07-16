# A7-G17 Autonomous Browser Stabilization Result

Date: `2026-07-16`

Task ID: `CODEX-20260716-a7-autonomous-browser-stabilization-g17`

Work item: `WORK-20260715-a7-browser-automation`

Gate: `A7-G17`

Starting commit: `c0b3ef4582cf540ce61b8c1bce07754c2e1791a6`

Terminal classification: `controlled-stop-application-defect`

Browser result: `fail`

## Result

G17 re-applied the accepted G13 start-combat correction and then continued
through evidence-proven harness defects with one focused test and a complete
bounded validation pass before each later browser attempt. Sixteen changed-code
attempts ran; unchanged code was never retried. The final attempt proved that
backend combat authority successfully accepted Malagrou's End Turn command and
advanced to John Twilight, while John's already-connected player surface
remained stale on Malagrou and kept `#endTurn` disabled. Correcting or working
around that behavior requires application scope outside the two authorized
harness/test files, so the application-defect boundary required a controlled
stop.

All unaccepted candidate changes in
`scripts/validation/browser-smoke-harness.py` and
`tests/test_browser_smoke_harness.py` were restored to their exact bytes at the
starting commit. No application file was modified. The approximately-200-enemy
stress scenario was not activated.

## Attempts

| Attempt | Artifact directory | Terminal classification |
| --- | --- | --- |
| 1 | `20260716_175122` | Fail at Dorian's player attack: the static actor ordering disagreed with live combat authority, which had Rifleman `cid=18` active. |
| 2 | `20260716_175709` | Fail at Fred's player attack: the map transform helper was inaccessible outside its lexical scope. |
| 3 | `20260716_175931` | Fail at Fred's player attack: `gridToScreen` was likewise not exposed from the page IIFE. |
| 4 | `20260716_180329` | Fail at Fred's player attack: the attack-resolution control was obscured by a visible turn modal. |
| 5 | `20260716_180605` | Fail on the Scorcher enemy turn: cached Constable capabilities disagreed with the live active `cid=103`. |
| 6 | `20260716_180909` | Fail on Constable: the harness used an invalid positional argument for Playwright `wait_for_function`. |
| 7 | `20260716_181039` | Fail at Dorian: the harness selected an inactive, always-mounted turn modal rather than the modal with `.show`. |
| 8 | `20260716_181239` | Fail at Johnny Morris: the selected target was out of range. |
| 9 | `20260716_181500` | Fail at стихия: the harness targeted the obsolete hidden `#castPreset` control instead of the visible Cast Spell modal. |
| 10 | `20260716_182259` | Fail at Dorian: the nearest melee target was 10 feet away and no adjacent enemy was available. |
| 11 | `20260716_182614` | Fail at Vicnor: a normal movement click did not drag the token, so the attack remained out of range. |
| 12 | `20260716_182921` | Fail at Old Man: the next player step began before Malagrou's turn transition became enabled on the player surface. |
| 13 | `20260716_183159` | Fail at стихия: Sacred Flame's save succeeded immediately, so no resolution modal appeared. |
| 14 | `20260716_183431` | Fail at Captain: active-CID state was read before the DM-control surface applied the transition. |
| 15 | `20260716_183624` | Fail at Raven: summon state was read before the DM-control surface applied the transition. |
| 16 | `20260716_183806` | Fail at `player-spell-pc:john-twilight`: backend authority advanced to John Twilight, but John's connected player page stayed stale and `#endTurn:not([disabled])` timed out after 10 seconds. Application defect; controlled stop. |

Every attempt used changed candidate code, and each candidate was derived from
the preceding attempt's preserved evidence. All attempt artifacts are beneath
`logs/smoke/CODEX-20260716-a7-autonomous-browser-stabilization-g17_browser-artifacts/black-tan-three-surface-workflow/`.

## Candidate Harness Corrections Evaluated

The initial correction performed exactly one normal Playwright click on
`#closeToolboxBtn`, then exactly one normal Playwright click on
`#startCombatBtn`, and awaited a successful `POST /api/dm/combat/start`
response before returning or verifying the post-start fixture. The three
specified start-combat tests covered click order/count, the absence of force or
DOM-bypass clicks, and the successful-response wait.

Later evidence-proven candidates added runtime actor ordering, summon-aware
ordering checks, page-coordinate approximation and nearest-target selection,
visible turn-modal dismissal, live capability synchronization, visible spell
modal controls, real targeted spells, noncaster attack fallback, normal token
drag staging for melee, an enabled-player-turn barrier, immediate spell-save
handling, and DM-control/summon transition barriers. Each received one focused
test before execution. These corrections were diagnostic candidates only and
were all reverted because the terminal result was a controlled stop.

The start-combat correction used no `force=True`, `evaluate`,
`eval_on_selector`, `dispatch_event`, JavaScript/DOM click, coordinate click,
or other pointer-event bypass.

## Focused Validation

The exact initial compile command passed:

```text
timeout 30s .venv/bin/python3 -m py_compile scripts/validation/browser-smoke-harness.py tests/test_browser_smoke_harness.py
```

The task packet's exact 20-node G10 selection plus the two G12 nodes and G13
response-wait node passed: `23 passed in 1.72s`.

After each evidence-proven candidate, the same exact 23 initial nodes plus all
then-applicable exact focused regression nodes passed. Recorded results, in
execution order, were:

```text
24 passed in 1.76s
25 passed in 1.74s
25 passed in 1.76s
26 passed in 1.80s
27 passed in 1.77s
27 passed in 1.73s
27 passed in 1.77s
28 passed in 1.75s
30 passed in 1.77s
31 passed in 1.77s
31 passed in 1.87s
32 passed in 1.79s
33 passed in 1.79s
34 passed in 1.79s
35 passed in 1.77s
```

The exact compile command passed before every candidate browser attempt. The
required two-file check also passed after every candidate:

```text
timeout 10s git diff --check -- scripts/validation/browser-smoke-harness.py tests/test_browser_smoke_harness.py
```

No full test file, broad suite, collection-based discovery, or unbounded test
command ran. After the controlled-stop reversion, an exact diff comparison
against the starting commit confirmed that both candidate files matched their
starting bytes.

## Proven Application Defect

The terminal screenshot shows John Twilight claimed on his player page while
the visible combat state still identifies Malagrou as active and leaves End
Turn disabled. Malagrou's role trace records the normal click on enabled
`#endTurn` as actionable, stable, receiving the input point, and completing
without error.

The G17 debug trace records Malagrou's `end_turn` command for player `cid=322`
as received and queued at `23:38:36.525`, dispatched at `23:38:36.675`, and
completed with `ok:true` at `23:38:36.828`. Immediately after the player-page
timeout, `GET /api/dm/combat` returned HTTP 200 with:

```json
{
  "in_combat": true,
  "active_cid": 320,
  "turn": 7,
  "round": 1,
  "turn_order_prefix": [335, 331, 332, 336, 329, 322, 320],
  "pending_prompts": []
}
```

`turn_order_prefix` labels the excerpted leading entries of the returned
`turn_order` list. They are sufficient to prove that authority advanced from
Malagrou `cid=322` to John Twilight `cid=320`. This separates a successful
request/backend mutation from the stale connected player UI. Reloading the
page would be an unaccepted application workaround rather than a harness
correction.

## Evidence

- Server log: `logs/smoke/CODEX-20260716-a7-autonomous-browser-stabilization-g17_smoke-server_20260716-175018.log`
- Debug trace: `logs/debug-trace-20260716-175018.jsonl`, including records `257943` through `258259` for the terminal End Turn mutation
- Artifact root: `logs/smoke/CODEX-20260716-a7-autonomous-browser-stabilization-g17_browser-artifacts/`
- Terminal attempt: `logs/smoke/CODEX-20260716-a7-autonomous-browser-stabilization-g17_browser-artifacts/black-tan-three-surface-workflow/20260716_183806/`
- Terminal screenshot: `terminal-selector-failure-player-spell-pc:john-twilight.png`
- Malagrou role trace: `role-trace-player-pc-malagrou.zip`, call `call@661`

## Server Ownership and Cleanup

Before startup, host port 8787 was proven free. G17 started exactly one server
using the packet's command. Before browser execution and again before cleanup,
the listener was positively identified as current-user Python process `69394`,
running this repository's `.venv` command from this repository, with shell
process `69393` and tee process `69395` in process group/session `69393`.
`ss` attributed `0.0.0.0:8787` to that Python process.

The owned process group accepted SIGINT. The shell, Python, and tee processes
were reaped; a bounded `ps` check found none of PIDs `69393`, `69394`, or
`69395`, and the final bounded `ss` check showed no listener on port 8787.
No unverified process was adopted or stopped, and SIGKILL was not used.

## Human Gate

The developer/orchestrator must review the application-defect evidence and
authorize additional application client/state-broadcast implementation and
focused test scope. The required correction must ensure that an already-
connected claimed player surface applies the new active actor after another
player's successful End Turn mutation. No further harness, browser, runtime,
network, push, deployment, restart, scheduler, production, or service action is
authorized by this result.

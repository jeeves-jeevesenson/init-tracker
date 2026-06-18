# Using Gemini on init-tracker (Temporary Migration Tool)

**Gemini is currently a temporary migration tool.** The primary agent
executor for this repository is **AGY (Antigravity CLI)**.

Gemini CLI / Gemini Code Assist should be used primarily for:

- migrating existing workflows to AGY-default execution
- broad analysis passes that benefit from large context windows
  (architecture snapshots, repo maps, contract surveys)
- producing handoff reports that AGY can pick up cold
- evidence-first bug investigation when paired with the
  measured-debugger subagent
- cross-file consistency reads (e.g. "where does this contract field
  flow end-to-end?")

For active product work, use AGY with a bounded task packet.

## AGY Token Budget & Discipline

When using AGY (or Gemini during the migration), follow these rules to
minimize token burn:

- **No broad repo scans:** Do not scan the whole repo unless explicitly allowed.
- **Read-first:** Read only named files first.
- **Source preference:** Prefer `docs/work_items/current_work.md` and active
  task documents over historical or archived docs.
- **Minimal inspection:** Do not inspect `majorTODO.md`, old plans, or
  historical reports unless they are named in the task packet.
- **Log efficiency:** Use `grep`, `head`, `tail`, or `sed` for logs instead
  of reading full log files.
- **Scope limit:** Identify the minimal file list needed before editing.
- **Stop early:** Stop immediately after bounded validation/report.

## Getting set up

1. Install Gemini CLI per upstream docs (out of scope here).
2. Copy the settings template and adjust locally:

   ```
   cp .gemini/settings.example.json .gemini/settings.json
   ```

   The example excludes a conservative set of risky shell commands
   (`rm -rf`, `git push --force`, `git reset --hard`, `sudo`, `curl`,
   `wget`, package-manager installs, etc.). Tighten or relax to taste,
   but err on the side of more exclusions when running unattended.
   Do not commit `settings.json` if it has machine-specific paths or
   private MCP server config; keep `settings.example.json` portable.

3. Confirm Gemini picks up `GEMINI.md` as the repo context file.
4. Confirm slash commands resolve: `/init:repo-map`, `/init:bug-pass`,
   `/init:perf-pass`, `/init:tk-map`, `/init:lan-contract-review`,
   `/init:spellbook-review`, `/init:handoff-report`.

## When to use Gemini

Gemini is good at:

- broad analysis passes that benefit from large context windows
  (architecture snapshots, repo maps, contract surveys)
- producing handoff reports that downstream agents can pick up cold
- evidence-first bug investigation when paired with the
  measured-debugger subagent
- cross-file consistency reads (e.g. "where does this contract field
  flow end-to-end?")

## When NOT to use Gemini

Skip Gemini for:

- one-line edits in a single known file (just edit it)
- ad-hoc commands you can run in a normal shell
- YAML data churn — the `yaml-data` instructions apply: do not bulk
  reformat or touch unrelated YAML files
- any work that wants destructive shell access (`rm -rf`, force pushes,
  global package installs) — the example settings exclude these
- product slice implementation when a bounded-pass agent (Claude or
  Codex) is already mid-stream and would lose context

## Plan mode

Use plan mode when:

- the task touches more than one file family
- the user asked for analysis/sequencing rather than a code change
- a bug is unmeasured and the next pass will be evidence capture, not
  a fix
- the proposed change crosses a contract boundary
  (`player_command_contracts.py`, `spellbook_contract`, LAN payloads)

Skip plan mode when:

- the change is a single bounded edit in a single file
- the user explicitly said "just do it" and the scope is implementation-
  ready

## Subagents

Route via the `.gemini/agents/` definitions:

- **init-tracker-architect** — broad architecture / migration analysis,
  next-bounded-pass sequencing, headless/browser-first direction.
- **measured-debugger** — any bug or perf issue. No fixes without
  evidence. Default for "this is broken" / "this is slow" reports.
- **lan-contract-specialist** — `_lan_apply_action()` extraction,
  `PlayerCommandService` work, contract builders, reaction-flow seams,
  LAN websocket protocol stability.
- **spellbook-specialist** — `spellbook_contract`, wizard automation,
  multiclass slot/prep boundaries, LAN Manage Spells surface.
- **tk-removal-investigator** — Tk/desktop dependency inventory,
  load-bearing-vs-vestigial classification, bounded removal slices.
  Analysis only.
- **docs-tracker-maintainer** — keep `majorTODO.md` and migration
  narrative under `docs/` honest with current repo reality.

## Slash commands

Each command under `.gemini/commands/init/*.toml` encodes a workflow
and an explicit do-not list. Use them as the entry point so the rules
travel with the request.

- `/init:repo-map` — grounded architecture snapshot, no edits.
- `/init:bug-pass` — measured bug pass: capture evidence first.
- `/init:perf-pass` — hot-path / latency pass aligned with
  `majorTODO.md` §3.1.a / §3.3.
- `/init:tk-map` — Tk-surface inventory and bounded removal slices,
  analysis only.
- `/init:lan-contract-review` — review LAN/player-command contracts and
  propose one bounded extraction or contract-shape slice.
- `/init:spellbook-review` — review the spell-management contract
  surface and propose one bounded corrective slice.
- `/init:handoff-report` — produce a paste-ready report for a downstream
  Claude or Codex prompt.

## Runtime Debugging

For complex bugs or performance issues, use the live runtime-debug workflow
before attempting a fix pass. This allows Gemini to observe the application
while you connect from a real browser.

See [docs/ai-workflows/runtime-debugging.md](runtime-debugging.md) for details.

## How to run a measured bug pass

1. Start with `/init:bug-pass`. Paste the user's symptom verbatim.
2. Let Gemini restate the symptom evidence-only and split confirmed vs.
   suspected.
3. If unmeasured, accept that this pass is evidence capture. Use:
   - `LAN_PERF_DEBUG=1` for latency timing
   - `INITTRACKER_WS_DEBUG=1` for websocket lifecycle JSONL
   - `INIT_TRACKER_HEADLESS=1 python3 serve_headless.py --no-auto-lan`
     for a Tk-free runtime repro
   - focused `python3 -m unittest tests.<module>` runs
4. Capture the output, then re-run `/init:bug-pass` with the new
   evidence in scope.
5. Only when the cause is narrowed, accept a fix proposal. The fix
   should be bounded, focused-tested, and free of unrelated cleanup.

## How to run a broad architecture pass

1. Start with `/init:repo-map` for a grounded snapshot.
2. Pick one of the suggested next bounded passes.
3. If the work is contract / LAN-shaped, follow with
   `/init:lan-contract-review` (or route to
   `lan-contract-specialist`).
4. If the work is spell-management, follow with
   `/init:spellbook-review` (or route to `spellbook-specialist`).
5. If the work is about retiring Tk surfaces, follow with
   `/init:tk-map`.
6. Hand off to a coding agent (Claude / Codex) via
   `/init:handoff-report`. Do not ask Gemini to land the implementation
   if the slice is already analysis-saturated and the user prefers
   another agent for code edits.

## How to hand off Gemini findings to Claude or Codex

Use `/init:handoff-report` and paste the resulting report into a fresh
prompt for the chosen downstream agent.

For Claude Code:

- start a new conversation in `~/src/init-tracker`
- paste the handoff report as the first user message
- mention which `.gemini/agents/` subagent shaped the analysis so the
  context is preserved (e.g. "this came out of `lan-contract-specialist`")

For Codex:

- the `.codex/config.toml` at repo root sets sensible defaults
  (`gpt-5.4`, `xhigh` reasoning, `workspace-write` sandbox, no network)
- paste the handoff report as the prompt body; Codex will follow the
  scope/do-not list directly

For another Gemini session:

- the handoff report is enough by itself, but mention which
  slash command to re-enter (e.g. "resume with `/init:bug-pass`")
  so the rules travel with the request

## How to validate Gemini's changes

If Gemini wrote code, validate it the same way any other agent would:

1. `python3 -m py_compile <edited files>`
2. The most relevant focused suite, e.g.
   `python3 -m unittest tests.test_player_command_contracts`
3. If the change crosses LAN protocol boundaries, run the closest
   focused LAN tests (e.g. `tests/test_lan_*`) and the websocket /
   reconnect-relevant ones.
4. If the change touched the headless host seam, run a quick
   `INIT_TRACKER_HEADLESS=1 python3 serve_headless.py --no-auto-lan`
   smoke and confirm clean shutdown.
5. If the change cannot be validated headlessly (UI-only frontend
   change), say so explicitly in the report rather than claiming
   success.

Do not default to whole-repo `unittest` sweeps unless the change risk
clearly justifies it. Pre-existing failures should be called out as
pre-existing, not blamed on the current pass.

## Things to never do via Gemini in this repo

- rename `dnd_initative_tracker.py`
- bulk-reformat YAML data files
- commit or push without an explicit user request
- introduce desktop-first fallback paths as the long-term shape
- invent files, branches, or `majorTODO.md` items that are not in
  the repo
- add secrets, tokens, or machine-specific paths to anything checked in

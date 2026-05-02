# Live Debug Findings

This document is a living record of findings from runtime observation and live debugging sessions.

## How to Use This Document

- Record confirmed root causes, performance bottlenecks, and stability notes here.
- Use the **Findings Template** for new entries.
- Reference these findings in `majorTODO.md` or before starting a fix pass.

## Findings Template

### [YYYY-MM-DD] - [Brief Summary of Issue]
- **Symptom**: What was observed in the browser/logs.
- **Evidence**: Specific log excerpts or timing values.
- **Root Cause**: (Proven / Likely / Unproven)
- **Resolution**: (If fixed, link to commit or PR)
- **Remaining Risk**: What is still unaddressed.

---

## Historical Findings

### 2026-04-25 - LAN/DM Stabilization (WebSocket Recovery Loop)
- **Symptom**: LAN clients were stuck in a repeating reconnect/recovery loop; map would not render even after connection.
- **Evidence**: `logs/websocket_debug.jsonl` showed `AssertionError` on concurrent sends; client logs showed recovery gate failing.
- **Root Causes**:
    - **Proven**: Concurrent WebSocket sends caused `websockets` library `AssertionError`.
    - **Proven**: Null/no-map recovery gate failed because the grid was not marked as "seen" before recovery checked it.
    - **Proven**: Headless map readiness incorrectly depended on the existence of a Tk `MapWindow` rather than backend authority.
- **Resolution**:
    - Serialized per-WebSocket sends in `LanController`.
    - Updated recovery gate to allow completion even if grid is null.
    - Switched headless tactical readiness to use backend state.
- **Remaining Risk**: 
    - Startup/YAML cache latency remains high.
    - Potential edge cases in multi-user map sync.

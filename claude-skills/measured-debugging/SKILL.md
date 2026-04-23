---
name: measured-debugging
description: Debug bugs and performance issues by collecting evidence first. Use when the problem is unmeasured, anecdotal, or missing a confirmed root cause. Prefer instrumentation, logs, and targeted reproduction before proposing a fix.
---

# Measured Debugging

## Purpose
Handle bug and performance work only from evidence.

## Workflow
1. Restate the observed symptom using only explicit evidence.
2. Identify what is confirmed and what is still unknown.
3. If the issue is unmeasured, make the pass about instrumentation or evidence capture first.
4. Choose the smallest inspection surface that can disambiguate the likely causes.
5. Do not mix root-cause discovery with unrelated cleanup.
6. If evidence is still incomplete after inspection, report that clearly instead of guessing.

## Pass types

### Evidence-first pass
Use when:
- no timings exist
- logs are missing
- reproduction is weak
- multiple causes are still plausible

Output:
- instrumentation target
- files to inspect
- minimal validation to capture evidence
- what decision the evidence should unlock

### Fix pass
Use only after evidence narrows the issue enough to justify a bounded fix.

See also:
- [INSTRUMENTATION_CHECKLIST.md](INSTRUMENTATION_CHECKLIST.md)
- [LOG_CAPTURE_TEMPLATE.md](LOG_CAPTURE_TEMPLATE.md)

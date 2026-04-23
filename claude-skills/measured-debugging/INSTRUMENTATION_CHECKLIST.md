# Instrumentation Checklist

- Define the exact symptom being measured.
- Add timings/logs only around the suspected hot path.
- Keep the pass behavior-neutral unless a tiny fix is required.
- Capture at least one concrete sample.
- Use the evidence to name the next bounded pass.

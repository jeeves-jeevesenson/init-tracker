# Workflow: review agent output

Run:

    scripts/agy/review_ready.sh

Do not commit if:
- tests pass with warnings
- context/output limit was hit
- files outside allowed list changed
- coverage is claimed without coverage output
- deployment/runtime paths changed unexpectedly

# AGY Token Discipline Checklist

Use this checklist before sending any task to AGY.

## Before AGY

- Can the Orchestrator produce a safe shell patch instead?
- Is this actual init-tracker work, not AGY optimization for its own sake?
- Is there an active work item or explicit developer authorization?
- Are exact files to inspect listed?
- Are exact allowed files listed?
- Is forbidden scope explicit?
- Is validation bounded?
- Is the token budget explicit?
- Are stop conditions explicit?

## Do not send AGY

Do not send AGY tasks that say:
- look around
- review the repo
- find anything else
- clean up related things
- run all tests
- continue until done

## AGY should stop when

- needed context is outside the packet
- app code is required but not allowed
- validation is missing
- validation passes
- the task needs a developer decision

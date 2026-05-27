# Session Refresher Template

Use this template as the first message in a fresh ChatGPT session to establish context.

```text
I’m continuing init-tracker. Here is the current context refresher.

[PASTE OUTPUT OF scripts/chatgpt_context_refresher.sh HERE]

First summarize current status, dirty state, unknowns, and next safe action. Do not write an implementation task until context is established.
```

## Protocol Reminder

1. **Summarize First**: The GPT must show it understands the current state and gate.
2. **One Task**: Do not accept multi-task plans.
3. **Unique ID**: Ensure the task has an `ITR-YYYYMMDD-AX-NN` ID.
4. **Validation**: The task MUST include the `scripts/agent_gate_validate.sh` command.

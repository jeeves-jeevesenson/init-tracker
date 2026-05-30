# Long-Term Planning and Research

This directory contains the strategic planning, research agendas, and deep architectural investigations for the `init-tracker` project.

## Directory Structure

- `research/`: Individual research passes for specific technical questions.
- `living_docs/`: Durable plans for broad migrations or new subsystems.
- `templates/`: Templates for new research passes and living plans.

## Workflow

1. **Agenda Setting**: The developer identifies a need for deep research or broad planning.
2. **Research Pass**: A focused investigation is performed (often by the **Planning Tool GPT**). This results in a `research_pass_template.md` document in `research/`.
3. **Evidence Matrix**: Research MUST include a matrix of repo evidence vs. external/web findings.
4. **Decision & Non-Goals**: Every pass must end with clear decisions, a set of non-goals, and identified gates.
5. **Living Plan Creation**: If the research results in a new subsystem or major migration, a `living_plan_template.md` is created in `living_docs/`.
6. **Promotion**: Once the plan is ready for implementation, it spawns **Work Items** in `docs/work_items/`.
7. **Handoff**: The Orchestrator picks up the Work Items and begins execution.

## The Planning Tool GPT

Deep planning and research are best handled by the specialized **init-tracker Planning Tool** Custom GPT. This agent is designed for:
- High-context repo analysis.
- Web research (D&D rules, VTT design patterns, accessibility standards).
- Architecture mapping and decision-making.

The Planning Tool DOES NOT execute code. It produces the **Living Documents** that the Orchestrator then executes.

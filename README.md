# Design System Governance Workflow

An AI-native workflow for Figma-based design systems built for existing company orgs and review processes. It audits, optimizes, refactors, and syncs design tokens to code outputs while also producing visual reports that support internal alignment, stakeholder reviews, and structured handoffs.

## Overview

`Design System Governance Workflow` is a structured workflow for managing the lifecycle of a design system inside an established organization. Unlike a one-shot generate-from-scratch flow, it is designed for staged delivery across audit, refactor, and sync phases, with artifacts that are useful not only for production output but also for governance, internal communication, and reporting.

The skill package lives at `skills/design-system-governance-workflow`, while the skill's user-facing name is `Design System Governance Workflow`.

## Architecture

- **Phase 1: Audit & Optimization** (`audit`)
  - **Figma Variable Extraction**: Pulls raw data via Figma MCP.
  - **Token Coverage Analysis**: Identifies missing tokens against standards.
  - **Design System Audit**: Scores the system on accessibility, structure, and AI-readiness.
- **Phase 2: Refactoring** (`refactor`)
  - Consolidates tokens, repairs accessibility issues, and generates dark mode sets.
- **Phase 3: Code Sync** (`sync`)
  - Translates tokens into Tailwind, CSS Custom Properties, and W3C Token format.

## Project Structure

```text
.
├── skills/
│   └── design-system-governance-workflow/
│   ├── SKILL.md
│   ├── scripts/
│   └── templates/
├── 0_optimizer-report/      # Generated optimization reports
├── 1_audit-report/          # Generated audit reports
└── ...
```

## Install

This skill is published with the install slug `design-system-governance-workflow` and the user-facing display name `Design System Governance Workflow`.

```bash
# Install from a GitHub repository in the Vercel skills ecosystem
npx skills add <github-owner>/<repo-name>

# List skills exposed by the repository
npx skills add <github-owner>/<repo-name> --list
```

## Compatibility

- Designed to be agent-agnostic within the Vercel skills ecosystem.
- Best suited for agents that can follow multi-stage workflows, work with repository files, and handle structured output artifacts.
- Intended for established organization workflows with review cycles, stakeholder alignment, and reporting needs, rather than one-shot generate-from-scratch usage.
- Recommended to validate behavior in your target clients such as Claude Code, Codex, and Cursor before broad rollout.

## Getting Started

### Prerequisites
- Python 3.10+
- Figma Access Token or configured MCP.

### Running a Phase
```bash
# Phase 1: Audit
python skills/design-system-governance-workflow/scripts/run_pipeline.py audit --figma-url <LINK>

# Phase 2: Refactor (requires Run ID from Phase 1)
python skills/design-system-governance-workflow/scripts/run_pipeline.py refactor --run-id <RUN_ID>

# Phase 3: Sync (requires Run ID from Phase 2)
python skills/design-system-governance-workflow/scripts/run_pipeline.py sync --run-id <RUN_ID>
```

## License
This project is licensed under the MIT License.

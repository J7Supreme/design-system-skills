# Design System Governance Workflow

An AI-native workflow for Figma-based design systems built for existing company orgs and review processes. It audits, optimizes, refactors, and syncs design tokens to code outputs while also producing visual reports that support internal alignment, stakeholder reviews, and structured handoffs.

## Overview

`Design System Governance Workflow` is a structured workflow for managing the lifecycle of a design system inside an established organization. Unlike a one-shot generate-from-scratch flow, it is designed for staged delivery across audit, refactor, and sync phases, with artifacts that are useful not only for production output but also for governance, internal communication, and reporting.

The current package directory remains `ds-governance-expert`, while the skill's user-facing name is `Design System Governance Workflow`.

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
├── ds-governance-expert/
│   ├── SKILL.md
│   ├── scripts/
│   └── templates/
├── 0_optimizer-report/      # Generated optimization reports
├── 1_audit-report/          # Generated audit reports
└── ...
```

## Getting Started

### Prerequisites
- Python 3.10+
- Figma Access Token or configured MCP.

### Running a Phase
```bash
# Phase 1: Audit
python ds-governance-expert/scripts/run_pipeline.py audit --figma-url <LINK>

# Phase 2: Refactor (requires Run ID from Phase 1)
python ds-governance-expert/scripts/run_pipeline.py refactor --run-id <RUN_ID>

# Phase 3: Sync (requires Run ID from Phase 2)
python ds-governance-expert/scripts/run_pipeline.py sync --run-id <RUN_ID>
```

## License
This project is licensed under the MIT License.

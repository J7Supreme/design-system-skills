# Design System Governance Expert

An AI-native governance pipeline for Figma-based design systems. It audits, optimizes, refactors, and syncs design tokens to code outputs while preserving accessibility and token architecture quality.

## Overview

`ds-governance-expert` is a structured pipeline for managing the lifecycle of a design system. It bridges Figma variables and production code outputs such as Tailwind, CSS custom properties, and W3C design token formats.

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

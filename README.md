# 🤖 Design System Agents

An AI-native governance pipeline for Figma-based design systems. Automatically audit, gap-analyze, refactor, and sync design tokens to code with multi-agent orchestration.

## 🚀 Overview

Design System Agents is a structured pipeline that uses specialized AI agents to manage the lifecycle of a design system. It bridges the gap between Figma design variables and production code (Tailwind, CSS, W3C) while ensuring accessibility and architectural integrity.

## 🏛️ Architecture

- **Phase 1: Audit & Analysis** (`audit`)
  - **Figma Variable Extraction**: Pulls raw data via Figma MCP.
  - **Token Gap Analysis**: Identifies missing tokens against standards.
  - **Design System Audit**: Scores the system on accessibility, structure, and AI-readiness.
- **Phase 2: Refactoring** (`refactor`)
  - Consolidates tokens, repairs accessibility issues, and generates dark mode sets.
- **Phase 3: Code Sync** (`sync`)
  - Translates tokens into Tailwind, CSS Custom Properties, and W3C Token format.

## 📦 Project Structure

```text
.
├── .agent/skills/           # Atomic AI Agent skill definitions
│   ├── ds-audit-agent/      # Audit logic & instructions
│   ├── ds-refactor-agent/   # Refactoring logic
│   └── code-sync-agent/     # Code generation logic
├── scripts/                 # Core execution scripts
├── run_pipeline.py          # Main entry point (CLI)
└── ...
```

## 🛠️ Getting Started

### Prerequisites
- Python 3.10+
- Figma Access Token or configured MCP.

### Running a Phase
```bash
# Phase 1: Audit
python run_pipeline.py audit --figma-url <LINK>

# Phase 2: Refactor (requires Run ID from Phase 1)
python run_pipeline.py refactor --run-id <RUN_ID>

# Phase 3: Sync (requires Run ID from Phase 2)
python run_pipeline.py sync --run-id <RUN_ID>
```

## 📄 License
This project is licensed under the MIT License.

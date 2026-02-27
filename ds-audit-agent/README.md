# ds-audit-agent

Evaluates the health, structural integrity, accessibility compliance, semantic clarity, and AI-readiness of a Figma-based Design System.

## Features
- **Token Integrity**: Analyzes mapping between raw values and tokens.
- **Accessibility**: Validates contrast (WCAG AA) and interaction states.
- **Component Health**: Checks Auto Layout usage and instance integrity.
- **AI Readiness**: Scores how "programmable" and stable the design system is for AI generation.

## Usage
Add this skill to your workspace and use the provided commands to audit your Figma files.

```bash
# In your local environment
python scripts/run_pipeline.py audit --figma-url <YOUR_FIGMA_URL>
```

## Configuration
Requires a Figma Access Token/MCP Setup and access to the profiles included in the skill folder.

# ds-token-gap-agent

Analyzes design color scales for missing definitions and proposes brand-anchored fills based on existing palette luminosity and saturation.

## Phase 1 (Part A)
This agent is responsible for scanning the Figma variable export and identifying completeness gaps.

## Usage
```bash
python scripts/run_pipeline.py audit --figma-url <URL>
```
The gap analysis runs as the first step of the audit process.

---
name: apimart-gpt-image-2
version: 1.0.0
description: |
  Use when Codex needs to generate images through APIMart GPT Image 2, submit or poll
  asynchronous image-generation tasks, save returned images to local files, or
  troubleshoot APIMart image-task failures. Defaults to 1k resolution and a local
  compatibility quality preset of low.
triggers:
  - "apimart生图"
  - "gpt-image-2生图"
  - "用apimart生成图片"
  - "generate image with apimart"
tools:
  - python3
  - curl
mutating: true
---

# APIMart GPT Image 2

## Contract

This skill guarantees:
- APIMart `gpt-image-2` requests are sent to the documented async endpoint at `POST /v1/images/generations`.
- The helper polls task status through `GET /v1/tasks/{task_id}` until success, failure, or timeout.
- Returned image URLs are downloaded to local files with deterministic output paths.
- The default generation profile uses `resolution=1k`.
- The helper keeps a local default `quality=low` setting for operator consistency, but does not send it because the APIMart docs state the server ignores `quality`.

## Quick Start

Run the bundled helper:

```bash
python3 /Users/lidechi/.codex/skills/apimart-gpt-image-2/scripts/generate_image.py \
  --prompt "A realistic tea shop storefront on a rainy evening" \
  --out ./output/imagegen/apimart-tea-shop.png
```

List models:

```bash
python3 /Users/lidechi/.codex/skills/apimart-gpt-image-2/scripts/generate_image.py --list-models
```

Submit without waiting:

```bash
python3 /Users/lidechi/.codex/skills/apimart-gpt-image-2/scripts/generate_image.py \
  --prompt "A clean product shot of a silver mechanical keyboard" \
  --submit-only
```

Poll an existing task:

```bash
python3 /Users/lidechi/.codex/skills/apimart-gpt-image-2/scripts/generate_image.py \
  --task-id task_1234567890
```

## Workflow

1. Read the API key from `APIMART_API_KEY` or the skill-local `.env` file.
2. Submit `POST /v1/images/generations` with `model=gpt-image-2`, `prompt`, and `resolution`.
3. Capture the returned `task_id`.
4. Poll `GET /v1/tasks/{task_id}` until terminal state.
5. Download the returned image URL to the requested output path.
6. Report the saved file path plus the final task status.

## Defaults

- Base URL: `https://api.apimart.ai/v1`
- Model: `gpt-image-2`
- Resolution: `1k`
- Local quality preset: `low`
- Poll interval: `3s`
- Timeout: `300s`

## Notes

- APIMart documents this route as asynchronous. A successful submit response is not the final image.
- The docs indicate `quality` is ignored for this endpoint. Keep it as a local operator preset only; do not rely on it for output changes.
- Use `--resolution 2k` or another supported value only when the user explicitly asks for larger output.
- Save files under the current workspace, usually `output/imagegen/`, unless the user gives a different path.

## Output Format

Report:
- Route: `APIMart /v1/images/generations`
- Task ID
- Final status
- Saved file path
- Prompt used

## Anti-Patterns

- Do not hardcode API keys into source files or commit them to a repo.
- Do not assume the submit response already contains image bytes.
- Do not send unsupported or doc-ignored parameters as if they were effective.
- Do not leave results only as remote URLs when the user asked for a usable local file.
- Do not print secrets in logs or terminal output.

## Files

- `scripts/generate_image.py`: submit, poll, and download helper.
- `references/api-reference.md`: APIMart endpoint notes and current defaults.
- `agents/openai.yaml`: short routing metadata.

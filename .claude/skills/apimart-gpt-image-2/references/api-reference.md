# APIMart GPT Image 2 Notes

Source checked: [APIMart GPT Image 2 Generation](https://docs.apimart.ai/en/api-reference/images/gpt-image-2/generation) on 2026-05-13.

## Endpoint

- Submit image task: `POST https://api.apimart.ai/v1/images/generations`
- Poll task status: `GET https://api.apimart.ai/v1/tasks/{task_id}`
- Auth header: `Authorization: Bearer ${APIMART_API_KEY}`

## Submit Payload

Observed documented fields:

```json
{
  "model": "gpt-image-2",
  "prompt": "A cute baby sea otter",
  "resolution": "1k"
}
```

## Response Shape

Submit returns an async task envelope with a `task_id`. Polling returns task status plus the final image URL on success.

## Operational Notes

- This route is asynchronous; always poll after submit unless the caller wants `--submit-only`.
- The docs state that `quality` is ignored for this endpoint. Keep local defaults simple and rely on `resolution` as the real default control.
- Default local profile for this skill:
  - `model=gpt-image-2`
  - `resolution=1k`
  - local quality preset `low` for operator consistency only
- Download the final image URL immediately if the user needs a durable local artifact.

#!/usr/bin/env python3
"""Submit, poll, and download APIMart GPT Image 2 tasks."""

from __future__ import annotations

import argparse
import json
import os
import pathlib
import re
import sys
import time
import urllib.error
import urllib.request
from typing import Any


DEFAULT_BASE_URL = "https://api.apimart.ai/v1"
DEFAULT_MODEL = "gpt-image-2"
DEFAULT_RESOLUTION = "1k"
DEFAULT_QUALITY = "low"
DEFAULT_TIMEOUT = 300
DEFAULT_POLL_INTERVAL = 3
SKILL_DIR = pathlib.Path(__file__).resolve().parents[1]
DEFAULT_ENV_FILE = SKILL_DIR / ".env"
TERMINAL_STATUSES = {"succeeded", "failed", "canceled", "cancelled", "completed"}


def die(message: str) -> None:
    raise SystemExit(message)


def load_env_file(path: pathlib.Path) -> None:
    if not path.exists():
        return
    values: dict[str, str] = {}
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("export "):
            line = line[len("export ") :].strip()
        if "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip("'").strip('"')
        if key:
            values[key] = value

    def expand(value: str) -> str:
        def replace(match: re.Match[str]) -> str:
            name = match.group(1) or match.group(2)
            return os.environ.get(name, values.get(name, match.group(0)))

        return re.sub(r"\$\{([A-Za-z_][A-Za-z0-9_]*)\}|\$([A-Za-z_][A-Za-z0-9_]*)", replace, value)

    for key, value in values.items():
        if key not in os.environ:
            os.environ[key] = expand(value)
    for key in values:
        os.environ[key] = expand(os.environ[key])


def normalize_base_url(base_url: str) -> str:
    return base_url.rstrip("/")


def get_api_key(args: argparse.Namespace) -> str:
    env_name = args.api_key_env or "APIMART_API_KEY"
    api_key = os.environ.get(env_name, "")
    if not api_key:
        die(f"Missing {env_name}. Set it in the environment or {args.env_file}.")
    return api_key


def request_json(
    method: str,
    url: str,
    api_key: str,
    timeout: int,
    payload: dict[str, Any] | None = None,
) -> dict[str, Any]:
    data = None
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Accept": "application/json",
        "User-Agent": (
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/136.0.0.0 Safari/537.36"
        ),
    }
    if payload is not None:
        data = json.dumps(payload).encode("utf-8")
        headers["Content-Type"] = "application/json"

    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            body = resp.read().decode("utf-8")
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        die(f"HTTP {exc.code} from {url}: {body[:1200]}")
    except urllib.error.URLError as exc:
        die(f"Request failed for {url}: {exc.reason}")
    except TimeoutError:
        die(f"Request timed out after {timeout}s for {url}")

    try:
        return json.loads(body)
    except json.JSONDecodeError:
        die(f"Non-JSON response from {url}: {body[:1200]}")


def extract_task_id(data: dict[str, Any]) -> str:
    candidates = [
        data.get("task_id"),
        data.get("id"),
        data.get("data", {}).get("task_id") if isinstance(data.get("data"), dict) else None,
        data.get("result", {}).get("task_id") if isinstance(data.get("result"), dict) else None,
    ]
    for candidate in candidates:
        if isinstance(candidate, str) and candidate.strip():
            return candidate.strip()
    data_list = data.get("data")
    if isinstance(data_list, list):
        for item in data_list:
            if isinstance(item, dict):
                candidate = item.get("task_id") or item.get("id")
                if isinstance(candidate, str) and candidate.strip():
                    return candidate.strip()
    die(f"Could not find task_id in submit response: {json.dumps(data, ensure_ascii=False)[:1200]}")


def extract_status(data: dict[str, Any]) -> str:
    candidates = [
        data.get("status"),
        data.get("task_status"),
        data.get("data", {}).get("status") if isinstance(data.get("data"), dict) else None,
        data.get("result", {}).get("status") if isinstance(data.get("result"), dict) else None,
    ]
    for candidate in candidates:
        if isinstance(candidate, str) and candidate.strip():
            return candidate.strip()
    return "unknown"


def extract_image_url(data: dict[str, Any]) -> str | None:
    direct_candidates = [
        data.get("url"),
        data.get("image_url"),
        data.get("result_url"),
    ]
    for candidate in direct_candidates:
        if isinstance(candidate, str) and candidate.startswith("http"):
            return candidate

    nested_objects = [data.get("data"), data.get("result")]
    for obj in nested_objects:
        if not isinstance(obj, dict):
            continue
        for key in ("url", "image_url", "result_url"):
            candidate = obj.get(key)
            if isinstance(candidate, str) and candidate.startswith("http"):
                return candidate
        images = obj.get("images")
        if isinstance(images, list):
            for item in images:
                if isinstance(item, str) and item.startswith("http"):
                    return item
                if isinstance(item, dict):
                    for key in ("url", "image_url"):
                        candidate = item.get(key)
                        if isinstance(candidate, str) and candidate.startswith("http"):
                            return candidate
                        if isinstance(candidate, list):
                            for entry in candidate:
                                if isinstance(entry, str) and entry.startswith("http"):
                                    return entry
        result = obj.get("result")
        if isinstance(result, dict):
            images = result.get("images")
            if isinstance(images, list):
                for item in images:
                    if isinstance(item, dict):
                        for key in ("url", "image_url"):
                            candidate = item.get(key)
                            if isinstance(candidate, str) and candidate.startswith("http"):
                                return candidate
                            if isinstance(candidate, list):
                                for entry in candidate:
                                    if isinstance(entry, str) and entry.startswith("http"):
                                        return entry
    return None


def submit_task(args: argparse.Namespace, api_key: str) -> str:
    payload: dict[str, Any] = {
        "model": args.model,
        "prompt": args.prompt,
        "resolution": args.resolution,
    }
    if args.quality and args.send_quality:
        payload["quality"] = args.quality
    data = request_json(
        "POST",
        f"{args.base_url}/images/generations",
        api_key,
        args.http_timeout,
        payload,
    )
    task_id = extract_task_id(data)
    print(json.dumps({"task_id": task_id, "submit_response": data}, ensure_ascii=False, indent=2))
    return task_id


def get_task(args: argparse.Namespace, api_key: str, task_id: str) -> dict[str, Any]:
    return request_json(
        "GET",
        f"{args.base_url}/tasks/{task_id}",
        api_key,
        args.http_timeout,
    )


def wait_for_task(args: argparse.Namespace, api_key: str, task_id: str) -> dict[str, Any]:
    deadline = time.time() + args.timeout
    last_status = ""
    while True:
        data = get_task(args, api_key, task_id)
        status = extract_status(data).lower()
        if status != last_status:
            print(f"task {task_id}: {status}", file=sys.stderr)
            last_status = status
        if status in TERMINAL_STATUSES:
            return data
        if time.time() >= deadline:
            die(f"Timed out waiting for task {task_id} after {args.timeout}s")
        time.sleep(args.poll_interval)


def choose_output_path(args: argparse.Namespace, task_id: str, image_url: str) -> pathlib.Path:
    if args.out:
        return pathlib.Path(args.out)
    ext = pathlib.Path(image_url.split("?", 1)[0]).suffix or ".png"
    safe_time = time.strftime("%Y%m%d-%H%M%S")
    return pathlib.Path(args.out_dir) / f"{args.model}-{safe_time}-{task_id}{ext}"


def download_file(url: str, out_path: pathlib.Path, timeout: int) -> None:
    req = urllib.request.Request(
        url,
        headers={
            "Accept": "*/*",
            "User-Agent": (
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/136.0.0.0 Safari/537.36"
            ),
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            data = resp.read()
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        die(f"HTTP {exc.code} while downloading {url}: {body[:1200]}")
    except urllib.error.URLError as exc:
        die(f"Download failed for {url}: {exc.reason}")
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_bytes(data)
    print(f"Wrote {out_path} ({len(data)} bytes)")


def list_models(args: argparse.Namespace, api_key: str) -> None:
    data = request_json("GET", f"{args.base_url}/models", api_key, args.http_timeout)
    for item in data.get("data", []):
        model_id = item.get("id")
        if model_id:
            print(model_id)


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--prompt", help="Text prompt for image generation.")
    parser.add_argument("--task-id", help="Existing APIMart task id to poll.")
    parser.add_argument("--out", help="Output file path.")
    parser.add_argument("--out-dir", default="output/imagegen", help="Output directory when --out is not set.")
    parser.add_argument("--base-url", default=DEFAULT_BASE_URL, help="OpenAI-compatible APIMart base URL ending in /v1.")
    parser.add_argument("--model", default=DEFAULT_MODEL, help="Image model id.")
    parser.add_argument("--resolution", default=DEFAULT_RESOLUTION, help="Resolution to request. Default: 1k.")
    parser.add_argument("--quality", default=DEFAULT_QUALITY, help="Local quality preset. Ignored by APIMart unless --send-quality is used.")
    parser.add_argument("--send-quality", action="store_true", help="Actually send quality to the API. Disabled by default because APIMart docs say it is ignored.")
    parser.add_argument("--api-key-env", help="Environment variable holding the bearer token.")
    parser.add_argument("--env-file", default=str(DEFAULT_ENV_FILE), help="Env file to load before calling.")
    parser.add_argument("--submit-only", action="store_true", help="Submit the task and print task_id without polling.")
    parser.add_argument("--list-models", action="store_true", help="List available model ids.")
    parser.add_argument("--poll-interval", type=int, default=DEFAULT_POLL_INTERVAL, help="Polling interval in seconds.")
    parser.add_argument("--timeout", type=int, default=DEFAULT_TIMEOUT, help="Total wait timeout in seconds.")
    parser.add_argument("--http-timeout", type=int, default=60, help="Per-request HTTP timeout in seconds.")
    args = parser.parse_args(argv)

    args.base_url = normalize_base_url(args.base_url)
    if args.list_models:
        return args
    if not args.prompt and not args.task_id:
        parser.error("--prompt or --task-id is required unless --list-models is used")
    return args


def main(argv: list[str]) -> int:
    args = parse_args(argv)
    load_env_file(pathlib.Path(args.env_file).expanduser())
    api_key = get_api_key(args)

    if args.list_models:
        list_models(args, api_key)
        return 0

    task_id = args.task_id
    if not task_id:
        task_id = submit_task(args, api_key)
        if args.submit_only:
            return 0

    task_data = wait_for_task(args, api_key, task_id)
    status = extract_status(task_data).lower()
    if status not in {"succeeded", "completed"}:
        print(json.dumps(task_data, ensure_ascii=False, indent=2))
        die(f"Task {task_id} finished with status: {status}")

    image_url = extract_image_url(task_data)
    if not image_url:
        print(json.dumps(task_data, ensure_ascii=False, indent=2))
        die(f"Task {task_id} succeeded but no image URL was found in the task payload")

    out_path = choose_output_path(args, task_id, image_url)
    download_file(image_url, out_path, args.http_timeout)
    print(
        json.dumps(
            {
                "task_id": task_id,
                "status": status,
                "output_path": str(out_path.resolve()),
                "image_url": image_url,
                "prompt": args.prompt,
                "resolution": args.resolution,
                "quality": args.quality,
                "quality_sent": args.send_quality,
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))

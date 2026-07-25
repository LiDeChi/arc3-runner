#!/usr/bin/env python3
"""Apply a narrow, backed-up local-security patch to CLIProxyAPI YAML.

No third-party YAML dependency is used. The editor only touches a small set of
well-known top-level/nested fields and refuses ambiguous duplicate structures.
Secret values are never printed.
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import re
import secrets
import shutil
import sys
import tempfile
from pathlib import Path
from typing import Optional


TEMPLATE_KEYS = {"your-api-key-1", "your-api-key-2", "your-api-key-3"}
TOP_KEY = re.compile(r"^([A-Za-z0-9_-]+):(?:[ \t]*(.*))?$")


def scalar(value: Optional[str]) -> str:
    if value is None:
        return ""
    value = value.strip()
    if not value:
        return ""
    if value.startswith('"'):
        match = re.match(r'^"((?:[^"\\]|\\.)*)"', value)
        if match:
            try:
                return str(json.loads('"' + match.group(1) + '"'))
            except ValueError:
                pass
    if value.startswith("'"):
        end = value.find("'", 1)
        if end >= 1:
            return value[1:end].replace("''", "'")
    return re.split(r"\s+#", value, maxsplit=1)[0].strip()


def top_blocks(lines: list[str], key: str) -> list[tuple[int, int, str]]:
    found: list[tuple[int, int, str]] = []
    for index, line in enumerate(lines):
        if line.startswith((" ", "\t", "#")) or not line.strip():
            continue
        match = TOP_KEY.match(line.rstrip("\r\n"))
        if not match or match.group(1) != key:
            continue
        end = len(lines)
        for cursor in range(index + 1, len(lines)):
            probe = lines[cursor]
            if probe.startswith((" ", "\t")) or not probe.strip():
                continue
            # Preserve top-level comments that introduce the next section.
            if probe.startswith("#") or TOP_KEY.match(probe.rstrip("\r\n")):
                end = cursor
                break
        found.append((index, end, match.group(2) or ""))
    return found


def one_block(lines: list[str], key: str) -> Optional[tuple[int, int, str]]:
    blocks = top_blocks(lines, key)
    if len(blocks) > 1:
        raise ValueError(f"配置包含重复的顶层 {key!r}，拒绝自动修改")
    return blocks[0] if blocks else None


def top_value(lines: list[str], key: str, default: str = "") -> str:
    block = one_block(lines, key)
    return scalar(block[2]) if block else default


def sequence_values(lines: list[str], key: str) -> list[str]:
    block = one_block(lines, key)
    if not block:
        return []
    values: list[str] = []
    for line in lines[block[0] + 1 : block[1]]:
        match = re.match(r"^[ \t]+-[ \t]+(.+)$", line.rstrip("\r\n"))
        if match:
            values.append(scalar(match.group(1)))
    return values


def replace_top_scalar(lines: list[str], key: str, value: str) -> list[str]:
    block = one_block(lines, key)
    line = f"{key}: {value}\n"
    if block:
        lines[block[0]] = line
        return lines
    insert_at = next(
        (index for index, item in enumerate(lines) if item and not item.startswith(("#", " ", "\t", "\r", "\n"))),
        len(lines),
    )
    lines.insert(insert_at, line)
    return lines


def replace_sequence(lines: list[str], key: str, values: list[str]) -> list[str]:
    block = one_block(lines, key)
    replacement = [f"{key}:\n"] + [f"  - {json.dumps(value, ensure_ascii=False)}\n" for value in values]
    if block:
        return lines[: block[0]] + replacement + lines[block[1] :]
    if lines and lines[-1].strip():
        lines.append("\n")
    lines.extend(replacement)
    return lines


def replace_nested(lines: list[str], parent: str, updates: dict[str, str]) -> list[str]:
    block = one_block(lines, parent)
    if not block:
        if lines and lines[-1].strip():
            lines.append("\n")
        lines.append(f"{parent}:\n")
        lines.extend(f"  {key}: {value}\n" for key, value in updates.items())
        return lines

    start, end, inline = block
    if scalar(inline):
        lines[start] = f"{parent}:\n"
        end = start + 1
    seen: set[str] = set()
    for index in range(start + 1, end):
        match = re.match(r"^([ \t]+)([A-Za-z0-9_-]+):", lines[index])
        if not match:
            continue
        key = match.group(2)
        if key in updates:
            if key in seen:
                raise ValueError(f"{parent}.{key} 重复，拒绝自动修改")
            lines[index] = f"  {key}: {updates[key]}\n"
            seen.add(key)
    missing = [key for key in updates if key not in seen]
    if missing:
        lines[start + 1 : start + 1] = [f"  {key}: {updates[key]}\n" for key in missing]
    return lines


def auth_dir_from(lines: list[str]) -> Path:
    raw = top_value(lines, "auth-dir", "~/.cli-proxy-api").strip() or "~/.cli-proxy-api"
    path = Path(raw).expanduser()
    if not path.is_absolute():
        raise ValueError("auth-dir 是相对路径；请先改为绝对路径或 ~/...，避免误改错误目录")
    return path


def write_secret(path: Path, value: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    os.chmod(path.parent, 0o700)
    fd, temporary = tempfile.mkstemp(prefix=f".{path.name}.", dir=str(path.parent), text=True)
    try:
        os.fchmod(fd, 0o600)
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            handle.write(value + "\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
        os.chmod(path, 0o600)
    except BaseException:
        try:
            os.close(fd)
        except OSError:
            pass
        try:
            os.unlink(temporary)
        except OSError:
            pass
        raise


def read_or_create_local_key(path: Path) -> tuple[str, str]:
    if path.is_file():
        value = path.read_text(encoding="utf-8").strip()
        if len(value.encode("utf-8")) >= 32 and "\n" not in value and "\r" not in value:
            return value, "复用"
    return "cpa_" + secrets.token_urlsafe(48), "生成"


def backup_path(path: Path) -> Path:
    stamp = dt.datetime.now().astimezone().strftime("%Y%m%d-%H%M%S")
    candidate = path.with_name(f"{path.name}.bak-{stamp}")
    counter = 1
    while candidate.exists():
        candidate = path.with_name(f"{path.name}.bak-{stamp}-{counter}")
        counter += 1
    return candidate


def atomic_write(path: Path, text: str) -> None:
    fd, temporary = tempfile.mkstemp(prefix=f".{path.name}.", dir=str(path.parent), text=True)
    try:
        os.fchmod(fd, 0o600)
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            handle.write(text)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
        os.chmod(path, 0o600)
    except BaseException:
        try:
            os.close(fd)
        except OSError:
            pass
        try:
            os.unlink(temporary)
        except OSError:
            pass
        raise


def main() -> int:
    os.umask(0o077)
    parser = argparse.ArgumentParser(description="保守加固 CLIProxyAPI 本机配置；默认仅预检")
    parser.add_argument("--config", required=True, type=Path, help="活动配置文件")
    parser.add_argument("--api-key-file", type=Path, help="本地客户端密钥文件；默认放在 auth-dir 下")
    parser.add_argument("--apply", action="store_true", help="实际写入；不指定时只做预检")
    args = parser.parse_args()

    requested = args.config.expanduser()
    if not requested.is_file():
        print("错误: 配置文件不存在", file=sys.stderr)
        return 2
    try:
        config = requested.resolve(strict=True)
        original = config.read_text(encoding="utf-8")
        lines = original.splitlines(keepends=True)
        auth_dir = auth_dir_from(lines)
        key_file = (args.api_key_file.expanduser() if args.api_key_file else auth_dir / "client-api-key")
        if not key_file.is_absolute():
            raise ValueError("api-key-file 必须是绝对路径或 ~/... 路径")
        local_key, key_action = read_or_create_local_key(key_file)

        existing = sequence_values(lines, "api-keys")
        retained: list[str] = []
        for value in existing:
            if value and value not in TEMPLATE_KEYS and value not in retained:
                retained.append(value)
        if local_key not in retained:
            retained.append(local_key)

        lines = replace_top_scalar(lines, "host", '"127.0.0.1"')
        lines = replace_top_scalar(lines, "debug", "false")
        lines = replace_top_scalar(lines, "ws-auth", "true")
        lines = replace_nested(
            lines,
            "remote-management",
            {"allow-remote": "false", "secret-key": '""', "disable-control-panel": "true"},
        )
        lines = replace_sequence(lines, "api-keys", retained)
        updated = "".join(lines)

        check_lines = updated.splitlines(keepends=True)
        if top_value(check_lines, "host") != "127.0.0.1":
            raise ValueError("host 修改后校验失败")
        if any(value in TEMPLATE_KEYS for value in sequence_values(check_lines, "api-keys")):
            raise ValueError("模板 API key 未被完全移除")
        if local_key not in sequence_values(check_lines, "api-keys"):
            raise ValueError("本地客户端密钥未写入内存配置")
    except (OSError, UnicodeError, ValueError) as exc:
        print(f"错误: {exc}", file=sys.stderr)
        return 3

    removed_templates = sum(1 for value in existing if value in TEMPLATE_KEYS)
    print("CLIProxyAPI 安全配置预检")
    print(f"- 请求路径: {requested}")
    print(f"- 实际配置: {config}")
    print(f"- auth-dir: {auth_dir}")
    print(f"- 本地密钥文件: {key_file}（将{key_action}；值不输出）")
    print(f"- 保留已有非模板 API key: {len(retained) - 1 if local_key in retained else len(retained)} 个")
    print(f"- 移除模板 API key: {removed_templates} 个")
    print("- 将设置: host=127.0.0.1, remote management=disabled, debug=false, ws-auth=true")

    if not args.apply:
        print("- 模式: dry-run；未写入任何文件。确认后加 --apply")
        return 0

    backup = backup_path(config)
    try:
        shutil.copy2(config, backup)
        os.chmod(backup, 0o600)
        atomic_write(config, updated)
        auth_dir.mkdir(parents=True, exist_ok=True, mode=0o700)
        os.chmod(auth_dir, 0o700)
        write_secret(key_file, local_key)
        tightened = 0
        for path in auth_dir.rglob("*.json"):
            if path.is_file():
                os.chmod(path, 0o600)
                tightened += 1
    except OSError as exc:
        print(f"错误: 写入失败: {exc}", file=sys.stderr)
        print(f"备份（若已创建）: {backup}", file=sys.stderr)
        return 4

    print("- 模式: apply；写入完成")
    print(f"- 配置备份: {backup}")
    print(f"- 已收紧 OAuth JSON 权限: {tightened} 个；文件名和内容未输出")
    print("- 密钥值从未输出；下一步重启正确实例并运行 verify.py")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

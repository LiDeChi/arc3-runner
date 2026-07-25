#!/usr/bin/env python3
"""Redacted local inspection for CLIProxyAPI.

This script never opens OAuth JSON files and never prints API-key values or auth
filenames. It only reports paths, counts, permissions, safe scalar settings, and
loopback listener state.
"""

from __future__ import annotations

import argparse
import os
import re
import shlex
import shutil
import socket
import stat
import subprocess
import sys
from pathlib import Path
from typing import Iterable, Optional


BINARY_NAMES = ("cliproxyapi", "cli-proxy-api", "CLIProxyAPI")
TEMPLATE_KEYS = {"your-api-key-1", "your-api-key-2", "your-api-key-3"}
TOP_KEY = re.compile(r"^([A-Za-z0-9_-]+):(?:[ \t]*(.*))?$")


def run(args: list[str], timeout: int = 5) -> tuple[int, str]:
    try:
        proc = subprocess.run(
            args,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            timeout=timeout,
            check=False,
        )
        return proc.returncode, proc.stdout
    except (OSError, subprocess.TimeoutExpired):
        return 127, ""


def mode_string(path: Path) -> str:
    try:
        return f"{stat.S_IMODE(path.stat().st_mode):04o}"
    except OSError:
        return "unknown"


def scalar(value: Optional[str]) -> str:
    if value is None:
        return ""
    value = value.strip()
    if not value:
        return ""
    if value.startswith('"'):
        match = re.match(r'^"((?:[^"\\]|\\.)*)"', value)
        if match:
            import json

            try:
                return str(json.loads('"' + match.group(1) + '"'))
            except ValueError:
                pass
    if value.startswith("'"):
        end = value.find("'", 1)
        if end >= 1:
            return value[1:end].replace("''", "'")
    return re.split(r"\s+#", value, maxsplit=1)[0].strip()


def top_block(lines: list[str], key: str) -> Optional[tuple[int, int, str]]:
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
            # A non-indented comment belongs to the following top-level
            # section, not to this value. Stop here so edits preserve it.
            if probe.startswith("#") or TOP_KEY.match(probe.rstrip("\r\n")):
                end = cursor
                break
        return index, end, match.group(2) or ""
    return None


def top_value(lines: list[str], key: str, default: str = "") -> str:
    block = top_block(lines, key)
    return scalar(block[2]) if block else default


def nested_value(lines: list[str], parent: str, key: str, default: str = "") -> str:
    block = top_block(lines, parent)
    if not block:
        return default
    for line in lines[block[0] + 1 : block[1]]:
        match = re.match(rf"^[ \t]+{re.escape(key)}:[ \t]*(.*)$", line.rstrip("\r\n"))
        if match:
            return scalar(match.group(1))
    return default


def sequence_values(lines: list[str], key: str) -> list[str]:
    block = top_block(lines, key)
    if not block:
        return []
    values: list[str] = []
    for line in lines[block[0] + 1 : block[1]]:
        match = re.match(r"^[ \t]+-[ \t]+(.+)$", line.rstrip("\r\n"))
        if match:
            values.append(scalar(match.group(1)))
    return values


def is_true(value: str) -> bool:
    return value.strip().lower() in {"true", "yes", "on", "1"}


def find_binary() -> Optional[Path]:
    for name in BINARY_NAMES:
        found = shutil.which(name)
        if found:
            return Path(found).resolve()
    candidates = []
    for directory in (
        Path("/opt/homebrew/bin"),
        Path("/usr/local/bin"),
        Path.home() / ".local/bin",
        Path.home() / "bin",
        Path.cwd(),
    ):
        for name in BINARY_NAMES:
            candidates.append(directory / name)
    return next((path.resolve() for path in candidates if path.is_file()), None)


def process_config_candidates() -> list[Path]:
    code, output = run(["ps", "-axo", "args="], timeout=5)
    if code != 0:
        return []
    found: list[Path] = []
    for raw in output.splitlines():
        try:
            args = shlex.split(raw)
        except ValueError:
            continue
        binary_tokens = {Path(arg).name.lower() for arg in args if not arg.startswith("-")}
        if not binary_tokens.intersection(name.lower() for name in BINARY_NAMES):
            continue
        for index, arg in enumerate(args):
            if arg in {"-config", "--config"} and index + 1 < len(args):
                found.append(Path(args[index + 1]).expanduser())
            elif arg.startswith(("-config=", "--config=")):
                found.append(Path(arg.split("=", 1)[1]).expanduser())
    return found


def help_default_config(binary: Optional[Path]) -> Optional[Path]:
    if not binary:
        return None
    _, output = run([str(binary), "-help"])
    match = re.search(r"Configure File Path \(default ([^)]+)\)", output)
    return Path(match.group(1)).expanduser() if match else None


def brew_config() -> Optional[Path]:
    brew = shutil.which("brew")
    if not brew:
        return None
    code, output = run([brew, "--prefix"])
    if code == 0 and output.strip():
        return Path(output.strip()) / "etc/cliproxyapi.conf"
    return None


def unique_paths(paths: Iterable[Optional[Path]]) -> list[Path]:
    result: list[Path] = []
    seen: set[str] = set()
    for path in paths:
        if not path:
            continue
        text = str(path.expanduser())
        if text not in seen:
            seen.add(text)
            result.append(Path(text))
    return result


def resolve_auth_dir(raw: str) -> Optional[Path]:
    raw = raw.strip() or "~/.cli-proxy-api"
    expanded = Path(raw).expanduser()
    if not expanded.is_absolute():
        return None
    return expanded


def listener_names(port: int) -> list[str]:
    lsof = shutil.which("lsof") or ("/usr/sbin/lsof" if Path("/usr/sbin/lsof").exists() else None)
    if not lsof:
        return []
    _, output = run([lsof, "-nP", f"-iTCP:{port}", "-sTCP:LISTEN"])
    names: list[str] = []
    for line in output.splitlines()[1:]:
        fields = line.split()
        if fields:
            name = fields[-2] if fields[-1] == "(LISTEN)" and len(fields) >= 2 else fields[-1]
            names.append(name)
    return sorted(set(names))


def service_status() -> str:
    brew = shutil.which("brew")
    if brew:
        _, output = run([brew, "services", "list"], timeout=8)
        for line in output.splitlines():
            fields = line.split()
            if fields and fields[0].lower() == "cliproxyapi":
                return "Homebrew: " + " ".join(fields[:3])
    systemctl = shutil.which("systemctl")
    if systemctl:
        for name in ("cli-proxy-api", "cliproxyapi"):
            code, output = run([systemctl, "--user", "is-active", name])
            if code == 0:
                return f"systemd --user: {name} {output.strip()}"
    return "未识别到受支持的服务管理器；可能是前台进程或容器"


def can_connect(port: int) -> bool:
    try:
        with socket.create_connection(("127.0.0.1", port), timeout=0.5):
            return True
    except OSError:
        return False


def main() -> int:
    parser = argparse.ArgumentParser(description="脱敏检测本机 CLIProxyAPI")
    parser.add_argument("--config", type=Path, help="显式指定配置文件")
    args = parser.parse_args()

    binary = find_binary()
    candidates = unique_paths(
        [
            args.config,
            *process_config_candidates(),
            help_default_config(binary),
            brew_config(),
            Path.home() / ".cli-proxy-api/config.yaml",
            Path.cwd() / "config.yaml",
        ]
    )
    existing = [path for path in candidates if path.is_file()]
    config = (args.config.expanduser() if args.config else (existing[0] if existing else None))

    print("CLIProxyAPI 脱敏检测")
    print(f"- 平台: {sys.platform} / {os.uname().machine if hasattr(os, 'uname') else 'unknown'}")
    if binary:
        _, help_text = run([str(binary), "-help"])
        first = next((line.strip() for line in help_text.splitlines() if "Version:" in line), "版本未知")
        print(f"- 二进制: {binary}")
        print(f"- 版本: {first}")
    else:
        print("- 二进制: 未找到")
    print(f"- 服务: {service_status()}")

    if len(existing) > 1 and not args.config:
        print("- 警告: 发现多个配置候选；写入前必须确认活动配置")
        for path in existing:
            print(f"  - 候选: {path}")
    if not config or not config.is_file():
        print(f"- 配置: 未找到（首选候选: {config or '无'}）")
        return 2 if not binary else 3

    try:
        target = config.resolve(strict=True)
        lines = target.read_text(encoding="utf-8").splitlines(keepends=True)
    except (OSError, UnicodeError) as exc:
        print(f"- 配置: 无法安全读取元数据: {type(exc).__name__}")
        return 4

    host = top_value(lines, "host", "")
    port_text = top_value(lines, "port", "8317")
    try:
        port = int(port_text)
    except ValueError:
        port = 8317
    auth_raw = top_value(lines, "auth-dir", "~/.cli-proxy-api")
    auth_dir = resolve_auth_dir(auth_raw)
    keys = sequence_values(lines, "api-keys")
    template_count = sum(1 for key in keys if key in TEMPLATE_KEYS)
    remote = nested_value(lines, "remote-management", "allow-remote", "false")
    management_secret = nested_value(lines, "remote-management", "secret-key", "")
    debug = top_value(lines, "debug", "false")
    ws_auth = top_value(lines, "ws-auth", "false")

    print(f"- 活动配置候选: {config}")
    if target != config.absolute():
        print(f"- 配置实际目标: {target}")
    print(f"- 配置权限: {mode_string(target)}")
    print(f"- host: {host!r}")
    print(f"- port: {port}")
    print(f"- remote-management.allow-remote: {str(is_true(remote)).lower()}")
    print(f"- remote-management.secret-key: {'已配置（已脱敏）' if management_secret else '空/禁用'}")
    print(f"- api-keys: {len(keys)} 个；模板值 {template_count} 个；值未输出")
    print(f"- debug: {str(is_true(debug)).lower()}")
    print(f"- ws-auth: {str(is_true(ws_auth)).lower()}")
    print(f"- auth-dir: {auth_raw}")

    oauth_count: Optional[int] = None
    if auth_dir is None:
        print("- OAuth 文件: auth-dir 为相对路径，无法在不确定服务工作目录时安全检查")
    elif auth_dir.is_dir():
        try:
            json_files = [path for path in auth_dir.rglob("*.json") if path.is_file()]
            oauth_count = len(json_files)
            unsafe_modes = sum(1 for path in json_files if stat.S_IMODE(path.stat().st_mode) & 0o077)
            print(f"- auth-dir 权限: {mode_string(auth_dir)}")
            print(f"- OAuth JSON: {len(json_files)} 个；权限过宽 {unsafe_modes} 个；文件名和内容未输出")
        except OSError:
            print(f"- auth-dir 权限: {mode_string(auth_dir)}")
            print("- OAuth JSON: 无法读取目录元数据；未读取任何文件内容")
    else:
        print("- OAuth JSON: auth-dir 不存在")

    codex_auth = Path.home() / ".codex/auth.json"
    print(
        "- Codex CLI auth.json: "
        + (f"存在；权限 {mode_string(codex_auth)}；内容未读取" if codex_auth.is_file() else "不存在")
    )

    listeners = listener_names(port)
    connected = can_connect(port)
    print(f"- 127.0.0.1:{port} 连通: {str(connected).lower()}")
    print(f"- 监听: {', '.join(listeners) if listeners else '未检测到'}")

    warnings: list[str] = []
    if host not in {"127.0.0.1", "localhost", "::1"}:
        warnings.append("host 不是明确的回环地址")
    if any(name.startswith(("*:", "0.0.0.0:", "[::]:")) for name in listeners):
        warnings.append("服务正在通配地址监听")
    if not connected:
        warnings.append("本机端口未连通，服务可能未运行或端口配置不一致")
    if not keys:
        warnings.append("未配置顶层 API key")
    if template_count:
        warnings.append("顶层 API key 仍含模板值，代理端点会进入安全模式")
    if is_true(remote):
        warnings.append("已允许远程管理")
    if management_secret:
        warnings.append("Management API 已启用；最小本机配置应将 secret-key 留空")
    if is_true(debug):
        warnings.append("debug 已开启，可能扩大敏感日志面")
    if not is_true(ws_auth):
        warnings.append("ws-auth 未开启")
    if auth_dir and auth_dir.is_dir() and mode_string(auth_dir) != "0700":
        warnings.append("auth-dir 权限不是 0700")
    if oauth_count == 0:
        warnings.append("auth-dir 中没有 OAuth JSON；尚未完成 CLIProxyAPI 的 provider 登录")
    try:
        if stat.S_IMODE(target.stat().st_mode) & 0o077:
            warnings.append("配置文件包含本地 API key，但组/其他用户仍有权限")
    except OSError:
        pass

    if warnings:
        print("- 安全结论: 需要修复")
        for warning in warnings:
            print(f"  - {warning}")
        return 1
    print("- 安全结论: 静态配置与监听检查通过")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

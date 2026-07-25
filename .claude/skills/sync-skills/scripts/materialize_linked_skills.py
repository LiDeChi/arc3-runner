#!/usr/bin/env python3
"""Materialize linked central skills and track their original sources."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import stat
import tempfile
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


SCHEMA_VERSION = 1
MANIFEST_NAME = ".materialized-sources.json"


def lexical_link_target(link: Path) -> Path:
    raw = Path(os.readlink(link))
    if not raw.is_absolute():
        raw = link.parent / raw
    return Path(os.path.normpath(raw))


def scan_tree(root: Path) -> dict[str, Any]:
    digest = hashlib.sha256()
    file_count = 0
    byte_count = 0
    symlink_count = 0

    def update(*parts: str) -> None:
        for part in parts:
            digest.update(part.encode("utf-8", errors="surrogateescape"))
            digest.update(b"\0")

    def visit(directory: Path) -> None:
        nonlocal file_count, byte_count, symlink_count
        for child in sorted(directory.iterdir(), key=lambda path: path.name):
            relative = child.relative_to(root).as_posix()
            if child.is_symlink():
                update("L", relative, os.readlink(child))
                symlink_count += 1
                continue

            mode = stat.S_IMODE(child.stat(follow_symlinks=False).st_mode)
            if child.is_dir():
                update("D", relative, f"{mode:o}")
                visit(child)
                continue

            if child.is_file():
                update("F", relative, f"{mode:o}")
                with child.open("rb") as handle:
                    for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                        digest.update(chunk)
                        byte_count += len(chunk)
                digest.update(b"\0")
                file_count += 1
                continue

            update("O", relative, f"{mode:o}")

    root_mode = stat.S_IMODE(root.stat(follow_symlinks=False).st_mode)
    update("ROOT", f"{root_mode:o}")
    visit(root)
    return {
        "sha256_tree": digest.hexdigest(),
        "files": file_count,
        "bytes": byte_count,
        "symlinks": symlink_count,
    }


def hardcoded_source_references(root: Path, source: Path) -> list[str]:
    needles = {str(source).encode(), str(source.resolve()).encode()}
    matches: list[str] = []
    for current, dirs, files in os.walk(root, followlinks=False):
        dirs[:] = [name for name in dirs if not (Path(current) / name).is_symlink()]
        current_path = Path(current)
        for name in files:
            path = current_path / name
            if path.is_symlink() or not path.is_file():
                continue
            data = path.read_bytes()
            if any(needle and needle in data for needle in needles):
                matches.append(path.relative_to(root).as_posix())
    return matches


def load_manifest(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {"schema_version": SCHEMA_VERSION, "entries": {}}
    data = json.loads(path.read_text(encoding="utf-8"))
    if data.get("schema_version") != SCHEMA_VERSION:
        raise RuntimeError(f"Unsupported manifest schema: {data.get('schema_version')!r}")
    if not isinstance(data.get("entries"), dict):
        raise RuntimeError("Manifest entries must be an object")
    return data


def write_json_atomic(path: Path, data: dict[str, Any]) -> None:
    temporary = path.with_name(f".{path.name}.tmp-{os.getpid()}")
    try:
        temporary.write_text(
            json.dumps(data, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        os.replace(temporary, path)
    finally:
        if temporary.exists():
            temporary.unlink()


def discover_links(central: Path) -> list[tuple[Path, Path]]:
    result: list[tuple[Path, Path]] = []
    central_resolved = central.resolve()
    for entry in sorted(central.iterdir(), key=lambda path: path.name):
        if not entry.is_symlink():
            continue
        source = lexical_link_target(entry)
        if not source.is_dir() or not (source / "SKILL.md").is_file():
            raise RuntimeError(f"Invalid central skill link: {entry} -> {source}")
        source_resolved = source.resolve()
        try:
            source_resolved.relative_to(central_resolved)
        except ValueError:
            pass
        else:
            raise RuntimeError(f"Refusing central-to-central skill link: {entry} -> {source}")
        result.append((entry, source))
    return result


def default_backup_dir(home: Path) -> Path:
    timestamp = datetime.now().astimezone().strftime("%Y%m%d-%H%M%S")
    parent = home / ".skills-backups"
    candidate = parent / f"{timestamp}-materialize-linked"
    suffix = 1
    while candidate.exists() or candidate.is_symlink():
        candidate = parent / f"{timestamp}-materialize-linked-{suffix}"
        suffix += 1
    return candidate


def materialize(central: Path, backup_dir: Path | None) -> int:
    links = discover_links(central)
    if not links:
        print(json.dumps({"materialized": 0, "status": "no-linked-skills"}, indent=2))
        return 0

    home = Path.home()
    backup = backup_dir or default_backup_dir(home)
    if backup.exists() or backup.is_symlink():
        raise RuntimeError(f"Backup destination already exists: {backup}")

    manifest_path = central / MANIFEST_NAME
    existing_manifest = load_manifest(manifest_path)
    now = datetime.now(timezone.utc).isoformat()
    backup_links = backup / "central-links"
    backup_links.mkdir(parents=True, exist_ok=False)
    if manifest_path.exists():
        shutil.copy2(manifest_path, backup / MANIFEST_NAME)

    staging = Path(tempfile.mkdtemp(prefix=".materialize-staging-", dir=central))
    records: dict[str, dict[str, Any]] = {}
    converted: list[str] = []

    try:
        for link, source in links:
            raw_target = os.readlink(link)
            source_metrics = scan_tree(source)
            if source_metrics["symlinks"]:
                raise RuntimeError(
                    f"Refusing non-independent source with internal links: {link.name}"
                )
            hardcoded = hardcoded_source_references(source, source)
            if hardcoded:
                raise RuntimeError(
                    f"Refusing source with hardcoded source paths: {link.name}: {hardcoded}"
                )
            staged = staging / link.name
            shutil.copytree(source, staged, symlinks=True, copy_function=shutil.copy2)
            staged_metrics = scan_tree(staged)
            if staged_metrics != source_metrics:
                raise RuntimeError(f"Copy verification failed for {link.name}")

            os.symlink(raw_target, backup_links / link.name)
            records[link.name] = {
                "central_path": str(link),
                "materialized_at": now,
                "materialized_hash": staged_metrics["sha256_tree"],
                "original_link_target": raw_target,
                "source": str(source),
                "source_hash": source_metrics["sha256_tree"],
                "files": source_metrics["files"],
                "bytes": source_metrics["bytes"],
            }

        write_json_atomic(
            backup / "materialization-plan.json",
            {
                "schema_version": SCHEMA_VERSION,
                "created_at": now,
                "entries": records,
            },
        )

        merged_entries = dict(existing_manifest["entries"])
        merged_entries.update(records)
        next_manifest = {
            "schema_version": SCHEMA_VERSION,
            "updated_at": now,
            "entries": dict(sorted(merged_entries.items())),
        }

        for link, _source in links:
            original_target = records[link.name]["original_link_target"]
            link.unlink()
            try:
                os.replace(staging / link.name, link)
            except Exception:
                os.symlink(original_target, link)
                raise
            converted.append(link.name)

        write_json_atomic(manifest_path, next_manifest)
    except Exception:
        for name in reversed(converted):
            active = central / name
            rollback_copy = staging / name
            if active.is_dir() and not active.is_symlink():
                os.replace(active, rollback_copy)
            original_target = records[name]["original_link_target"]
            os.symlink(original_target, active)
        if staging.exists():
            failed_staging = backup / "failed-staging"
            if not failed_staging.exists():
                os.replace(staging, failed_staging)
        raise

    try:
        staging.rmdir()
    except OSError:
        pass

    total_bytes = sum(int(record["bytes"]) for record in records.values())
    print(
        json.dumps(
            {
                "status": "materialized",
                "materialized": len(records),
                "files": sum(int(record["files"]) for record in records.values()),
                "bytes": total_bytes,
                "backup": str(backup),
                "manifest": str(manifest_path),
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


def source_status(central: Path) -> int:
    manifest_path = central / MANIFEST_NAME
    if not manifest_path.exists():
        print(json.dumps({"status": "no-manifest", "tracked": 0}, indent=2))
        return 0

    manifest = load_manifest(manifest_path)
    summary: Counter[str] = Counter()
    details: dict[str, list[str]] = {
        "central_modified": [],
        "central_missing": [],
        "central_linked_again": [],
        "source_changed": [],
        "source_missing": [],
    }

    for name, record in sorted(manifest["entries"].items()):
        active = central / name
        if not active.exists():
            summary["central_missing"] += 1
            details["central_missing"].append(name)
        elif active.is_symlink():
            summary["central_linked_again"] += 1
            details["central_linked_again"].append(name)
        elif scan_tree(active)["sha256_tree"] == record["materialized_hash"]:
            summary["central_unchanged"] += 1
        else:
            summary["central_modified"] += 1
            details["central_modified"].append(name)

        source = Path(record["source"])
        if not source.is_dir():
            summary["source_missing"] += 1
            details["source_missing"].append(name)
        elif scan_tree(source)["sha256_tree"] == record["source_hash"]:
            summary["source_unchanged"] += 1
        else:
            summary["source_changed"] += 1
            details["source_changed"].append(name)

    print(
        json.dumps(
            {
                "status": "checked",
                "tracked": len(manifest["entries"]),
                "summary": dict(sorted(summary.items())),
                "details": {key: value for key, value in details.items() if value},
                "manifest": str(manifest_path),
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Materialize linked central skills and track source drift."
    )
    parser.add_argument("command", choices=("apply", "status"))
    parser.add_argument(
        "--central",
        type=Path,
        default=Path.home() / ".skills",
        help="Central skill directory. Default: ~/.skills",
    )
    parser.add_argument(
        "--backup-dir",
        type=Path,
        help="Explicit backup directory for apply.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    central = args.central.expanduser()
    if not central.is_dir():
        raise RuntimeError(f"Central skill directory not found: {central}")
    if args.command == "apply":
        return materialize(central, args.backup_dir.expanduser() if args.backup_dir else None)
    return source_status(central)


if __name__ == "__main__":
    raise SystemExit(main())

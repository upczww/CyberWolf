from __future__ import annotations

import argparse
import json
from collections import Counter, defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable

ROOT = Path(__file__).resolve().parents[1]
MANIFEST_PATH = ROOT / "desktop" / "werewolf_asset_manifest_v5.json"
ASSET_ROOT = ROOT / "desktop" / "public"


@dataclass(frozen=True)
class AssetResource:
    id: str
    path: str
    file: str
    full_path: str
    type: str
    usage: str
    size: str | None = None
    format: str | None = None
    transparent: bool | None = None
    priority: str | None = None
    prompt: str | None = None
    negative_prompt: str | None = None
    pages: tuple[str, ...] = ()
    modes: tuple[str, ...] = ()
    notes: str | None = None

    @property
    def output_path(self) -> Path:
        return ASSET_ROOT / self.full_path


def load_manifest() -> dict[str, Any]:
    return json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))


def manifest_resources() -> list[AssetResource]:
    manifest = load_manifest()
    resources: list[AssetResource] = []
    for raw in manifest["resources"]:
        resources.append(
            AssetResource(
                id=raw["id"],
                path=raw["path"],
                file=raw["file"],
                full_path=raw["full_path"],
                type=raw["type"],
                usage=raw.get("usage", ""),
                size=raw.get("size"),
                format=raw.get("format"),
                transparent=raw.get("transparent"),
                priority=raw.get("priority"),
                prompt=raw.get("prompt"),
                negative_prompt=raw.get("negative_prompt"),
                pages=tuple(raw.get("pages", ())),
                modes=tuple(raw.get("modes", ())),
                notes=raw.get("notes"),
            )
        )
    return resources


def resources_by_type(asset_type: str | None = None) -> list[AssetResource]:
    items = manifest_resources()
    if asset_type is None:
        return items
    return [resource for resource in items if resource.type == asset_type]


def resource_map() -> dict[str, AssetResource]:
    return {resource.id: resource for resource in manifest_resources()}


def ensure_parent(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)


def parse_size(size: str | None, default: tuple[int, int]) -> tuple[int, int]:
    if not size:
        return default
    digits = []
    current = ""
    for ch in size:
        if ch.isdigit():
            current += ch
        elif current:
            digits.append(int(current))
            current = ""
    if current:
        digits.append(int(current))
    if len(digits) >= 2:
        return digits[0], digits[1]
    return default


def validate_manifest_outputs(only_types: Iterable[str] | None = None) -> dict[str, Any]:
    wanted = set(only_types or [])
    resources = manifest_resources()
    if wanted:
        resources = [resource for resource in resources if resource.type in wanted]

    present = []
    missing = []
    by_type = Counter()
    missing_by_type: dict[str, list[dict[str, str]]] = defaultdict(list)

    for resource in resources:
        by_type[resource.type] += 1
        item = {"id": resource.id, "path": resource.full_path}
        if resource.output_path.exists():
            present.append(item)
        else:
            missing.append(item)
            missing_by_type[resource.type].append(item)

    return {
        "manifest": str(MANIFEST_PATH),
        "asset_root": str(ASSET_ROOT),
        "total_resources": len(resources),
        "present_resources": len(present),
        "missing_resources": len(missing),
        "per_type": dict(by_type),
        "missing_by_type": dict(missing_by_type),
        "missing": missing,
    }


def write_report(path: Path, report: dict[str, Any]) -> None:
    ensure_parent(path)
    path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")


def print_summary(report: dict[str, Any]) -> None:
    print(f"manifest: {report['manifest']}")
    print(f"asset_root: {report['asset_root']}")
    print(f"total: {report['total_resources']}")
    print(f"present: {report['present_resources']}")
    print(f"missing: {report['missing_resources']}")
    print("per_type:")
    for asset_type, count in sorted(report["per_type"].items()):
        print(f"  - {asset_type}: {count}")
    if report["missing_resources"]:
        print("missing_by_type:")
        for asset_type, items in sorted(report["missing_by_type"].items()):
            print(f"  - {asset_type}: {len(items)}")
            for item in items[:8]:
                print(f"      {item['id']} -> {item['path']}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Manifest-driven asset utility helpers.")
    parser.add_argument(
        "--types",
        nargs="*",
        help="Optional asset types to include in validation, e.g. background icon panel.",
    )
    parser.add_argument(
        "--validate",
        action="store_true",
        help="Validate manifest outputs and print a grouped summary.",
    )
    parser.add_argument(
        "--report",
        type=Path,
        help="Optional JSON report output path.",
    )
    args = parser.parse_args()

    if args.validate or args.report:
        report = validate_manifest_outputs(args.types)
        print_summary(report)
        if args.report:
            write_report(args.report, report)
        return

    resources = manifest_resources()
    counts = Counter(resource.type for resource in resources)
    print(f"manifest: {MANIFEST_PATH}")
    print(f"resources: {len(resources)}")
    for asset_type, count in sorted(counts.items()):
        print(f"{asset_type}: {count}")


if __name__ == "__main__":
    main()

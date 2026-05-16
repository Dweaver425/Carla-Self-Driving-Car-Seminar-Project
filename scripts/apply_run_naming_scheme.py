from __future__ import annotations

import argparse
import json
import os
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


EPISODE_RENAMES: dict[str, str] = {
    "guidedSpawn1Chase_v1": "guidedSpawn1Chase_v1",
    "guidedSpawn1Chase_v2": "guidedSpawn1Chase_v2",
    "trafficTest_v1": "trafficTest_v1",
    "trafficPed30min_v1": "trafficPed30min_v1",
    "trafficPed1hr_v1": "trafficPed1hr_v1",
    "guidedBalanced1hr_v1": "guidedBalanced1hr_v1",
    "laneCorrectionSpawn1Speed4_v1": "laneCorrectionSpawn1Speed4_v1",
    "laneCorrectedGuided_v1": "laneCorrectedGuided_v1",
    "laneFinetunedGuided_v1": "laneFinetunedGuided_v1",
    "recoveryRightYaw_v1": "recoveryRightYaw_v1",
    "recoveryLeftYaw_v1": "recoveryLeftYaw_v1",
    "recoveryRightCounter_v1": "recoveryRightCounter_v1",
    "recoveryLeftCounter_v1": "recoveryLeftCounter_v1",
    "laneRecoveryGuided_v1": "laneRecoveryGuided_v1",
    "teacherSpawn1_30min_v1": "teacherSpawn1_30min_v1",
    "testRefinedModel_v1": "testRefinedModel_v1",
    "quick10cars5min_v1": "quick10cars5min_v1",
    "quick10cars5min_v2": "quick10cars5min_v2",
    "testQuick10cars5min_v2": "testQuick10cars5min_v2",
    "quick10carsContinue_v1": "quick10carsContinue_v1",
    "quick10carsContinue_v2": "quick10carsContinue_v2",
    "stable1hr_v1": "stable1hr_v1",
    "ultra1hr_v1": "ultra1hr_v1",
    "ultraOvernight_v1": "ultraOvernight_v1",
    "overnight2cars_v1": "overnight2cars_v1",
    "overnight2cars_v2": "overnight2cars_v2",
    "overnight2cars_v3": "overnight2cars_v3",
    "quick2cars_v1": "quick2cars_v1",
    "quick2cars_v2": "quick2cars_v2",
    "10hr2cars_v1": "10hr2cars_v1",
    "stopSigns_v1": "stopSigns_v1",
    "stopSigns_v2": "stopSigns_v2",
    "stopSigns_v3": "stopSigns_v3",
    "stopSigns_v4": "stopSigns_v4",
    "stopSigns_v5": "stopSigns_v5",
    "stopSigns_v6": "stopSigns_v6",
    "stopSigns_v7": "stopSigns_v7",
    "stopSigns_v8": "stopSigns_v8",
    "stopSigns_v9": "stopSigns_v9",
    "stopSigns_v10": "stopSigns_v10",
    "shadow2cars_v1": "shadow2cars_v1",
    "5hr2cars_v1": "5hr2cars_v1",
}

RAW_SHARD_BASE_RENAMES: dict[str, str] = {
    "earlyRuns_v1": "earlyRuns_v1",
    "shadow2cars_v1": "shadow2cars_v1",
    "overnight2cars_v3": "overnight2cars_v3",
    "10hr2cars_v1": "10hr2cars_v1",
}

MODEL_STEM_RENAMES: dict[str, str] = {
    "trafficPed1hrBalanced_v1_cuda": "trafficPed1hrBalanced_v1_cuda",
    "quick10carsContinue_v1_iter_1_cuda": "quick10carsContinue_v1_chunk_1_cuda",
    "quick10carsContinue_v2_iter_1_cuda": "quick10carsContinue_v2_chunk_1_cuda",
    "quick10cars5min_v1_cuda": "quick10cars5min_v1_cuda",
    "quick10cars5min_v2_cuda": "quick10cars5min_v2_cuda",
    "quick2cars_v1_iter_1_cuda": "quick2cars_v1_chunk_1_cuda",
    "quick2cars_v2_iter_1_cuda": "quick2cars_v2_chunk_1_cuda",
    "10hr2cars_v1_cuda": "10hr2cars_v1_cuda",
    "shadow2cars_v1_cuda": "shadow2cars_v1_cuda",
    "stopSignsTargeted_v1_cuda": "stopSignsTargeted_v1_cuda",
    "overnight2cars_v3_cuda": "overnight2cars_v3_cuda",
    "stopSignsMixed_v1_cuda": "stopSignsMixed_v1_cuda",
    "trafficPedWeekend_v1_cuda": "trafficPedWeekend_v1_cuda",
    "stable1hr_v1_iter_1_cuda": "stable1hr_v1_chunk_1_cuda",
    "weekendTarIndex_v1_cuda": "weekendTarIndex_v1_cuda",
    "laneCorrected_v1_cuda": "laneCorrected_v1_cuda",
    "laneFinetuned_v1_cuda": "laneFinetuned_v1_cuda",
    "laneRecovery_v1_cuda": "laneRecovery_v1_cuda",
    "teacherRefined_v1_cuda": "teacherRefined_v1_cuda",
    "allData_v1_mps": "allData_v1_mps",
}

LOG_PREFIX_RENAMES: dict[str, str] = {
    **EPISODE_RENAMES,
    "overnight2cars_v3": "overnight2cars_v3",
    "overnight2cars_v1": "overnight2cars_v1",
    "overnight2cars_v2": "overnight2cars_v2",
    "5hr2cars_v1": "5hr2cars_v1",
    "stopSignsTargeted_v1": "stopSignsTargeted_v1",
    "stopSignsMixed_v1": "stopSignsMixed_v1",
    "quick2cars_v1_iter_1": "quick2cars_v1_chunk_1",
    "quick2cars_v2_iter_1": "quick2cars_v2_chunk_1",
    "stable1hr_v1_iter_1": "stable1hr_v1_chunk_1",
    "ultra1hr_v1_iter_1": "ultra1hr_v1_chunk_1",
    "ultraOvernight_v1_iter_1": "ultraOvernight_v1_chunk_1",
}

SPECIAL_MOVES: dict[str, str] = {
    "!RUN_ROOT!": "data/episodes/badExpansionChunks_v1",
    "!COLLECT_LOG!": "logs/badExpansion_v1_collect.log",
    "!DATASET_FILE!": "logs/badExpansion_v1_datasets.txt",
    "!TRAIN_LOG!": "logs/badExpansion_v1_train.log",
}

TEXT_SUFFIXES = {
    ".bat",
    ".cmd",
    ".csv",
    ".gitignore",
    ".json",
    ".log",
    ".md",
    ".py",
    ".txt",
}
TEXT_DIRS = ["scripts", "docs", "logs", "data/raw"]


def inside_workspace(path: Path) -> Path:
    resolved = path.resolve()
    if not resolved.is_relative_to(ROOT):
        raise ValueError(f"Path is outside the workspace: {resolved}")
    return resolved


def rename_path(src_rel: str, dst_rel: str, *, apply: bool) -> dict[str, str]:
    src = inside_workspace(ROOT / src_rel)
    dst = inside_workspace(ROOT / dst_rel)
    if not src.exists():
        return {"action": "missing", "src": src_rel, "dst": dst_rel}
    if dst.exists():
        return {"action": "exists", "src": src_rel, "dst": dst_rel}
    if apply:
        dst.parent.mkdir(parents=True, exist_ok=True)
        src.rename(dst)
    return {"action": "renamed" if apply else "would_rename", "src": src_rel, "dst": dst_rel}


def rename_children_by_token(root_rel: str, old: str, new: str, *, apply: bool) -> list[dict[str, str]]:
    root = inside_workspace(ROOT / root_rel)
    if not root.exists():
        return []
    actions: list[dict[str, str]] = []
    for child in sorted(root.iterdir(), key=lambda item: len(item.name), reverse=True):
        if old not in child.name:
            continue
        new_name = child.name.replace(old, new)
        actions.append(rename_path(str(child.relative_to(ROOT)), str((root / new_name).relative_to(ROOT)), apply=apply))
    return actions


def rename_model_files(*, apply: bool) -> list[dict[str, str]]:
    model_dir = inside_workspace(ROOT / "models")
    actions: list[dict[str, str]] = []
    if not model_dir.exists():
        return actions
    for path in sorted(model_dir.glob("*.pt")):
        for old, new in MODEL_STEM_RENAMES.items():
            if path.stem.startswith(old):
                dst_name = new + path.stem[len(old):] + path.suffix
                actions.append(rename_path(str(path.relative_to(ROOT)), f"models/{dst_name}", apply=apply))
                break
    return actions


def rename_log_files(*, apply: bool) -> list[dict[str, str]]:
    log_dir = inside_workspace(ROOT / "logs")
    actions: list[dict[str, str]] = []
    if not log_dir.exists():
        return actions
    ordered = sorted(LOG_PREFIX_RENAMES.items(), key=lambda pair: len(pair[0]), reverse=True)
    for path in sorted(log_dir.iterdir()):
        if not path.is_file():
            continue
        for old, new in ordered:
            if path.name.startswith(old):
                actions.append(rename_path(str(path.relative_to(ROOT)), f"logs/{path.name.replace(old, new, 1)}", apply=apply))
                break
    return actions


def replacement_pairs() -> list[tuple[str, str]]:
    pairs: dict[str, str] = {}
    for mapping in (EPISODE_RENAMES, RAW_SHARD_BASE_RENAMES, MODEL_STEM_RENAMES, LOG_PREFIX_RENAMES):
        pairs.update(mapping)
    pairs.update({
        "teacherRefined_v1_cuda": "teacherRefined_v1_cuda",
        "laneRecovery_v1_cuda": "laneRecovery_v1_cuda",
        "quick2cars_v1_iter_1_cuda": "quick2cars_v1_chunk_1_cuda",
    })
    return sorted(pairs.items(), key=lambda pair: len(pair[0]), reverse=True)


def iter_text_files() -> list[Path]:
    files: list[Path] = []
    for direct in [ROOT / "README.md", ROOT / ".gitignore"]:
        if direct.exists():
            files.append(direct)
    for directory in TEXT_DIRS:
        root = ROOT / directory
        if not root.exists():
            continue
        for dirpath, dirnames, filenames in os.walk(root):
            dirnames[:] = [
                dirname for dirname in dirnames
                if dirname not in {".git", ".venv", "__pycache__", "images"}
            ]
            for filename in filenames:
                path = Path(dirpath) / filename
                if path.name == "tar_image_index.jsonl" or path.suffix == ".jsonl":
                    continue
                if path.suffix.lower() in TEXT_SUFFIXES or path.name == ".gitignore":
                    files.append(path)
    return sorted(set(files))


def update_text_files(*, apply: bool) -> list[dict[str, str]]:
    actions: list[dict[str, str]] = []
    pairs = replacement_pairs()
    for path in iter_text_files():
        try:
            text = path.read_text(encoding="utf-8-sig")
        except UnicodeDecodeError:
            continue
        updated = text
        for old, new in pairs:
            updated = updated.replace(old, new)
        if updated == text:
            continue
        if apply:
            path.write_text(updated, encoding="utf-8")
        actions.append({
            "action": "updated" if apply else "would_update",
            "path": str(path.relative_to(ROOT)),
        })
    return actions


def update_tar_metadata(*, apply: bool) -> list[dict[str, str]]:
    actions: list[dict[str, str]] = []
    for metadata_path in (ROOT / "data/raw").rglob("tar_image_index_metadata.json"):
        try:
            metadata = json.loads(metadata_path.read_text(encoding="utf-8-sig"))
        except json.JSONDecodeError:
            continue
        before = json.dumps(metadata, sort_keys=True)
        dataset_root = metadata_path.parent
        archive_path = Path(str(metadata.get("archive_path", "")))
        expected_archive = dataset_root.parent / f"{dataset_root.name}_images.tar"
        if expected_archive.exists():
            metadata["archive_path"] = str(expected_archive)
        metadata["dataset_name"] = dataset_root.name
        metadata["index_path"] = str(dataset_root / "tar_image_index.jsonl")
        after = json.dumps(metadata, sort_keys=True)
        if after == before:
            continue
        if apply:
            metadata_path.write_text(json.dumps(metadata, indent=2) + "\n", encoding="utf-8")
        actions.append({
            "action": "updated_tar_metadata" if apply else "would_update_tar_metadata",
            "path": str(metadata_path.relative_to(ROOT)),
        })
    return actions


def apply_renames(*, apply: bool) -> list[dict[str, str]]:
    actions: list[dict[str, str]] = []
    for old, new in EPISODE_RENAMES.items():
        actions.append(rename_path(f"data/episodes/{old}", f"data/episodes/{new}", apply=apply))
    for old, new in SPECIAL_MOVES.items():
        actions.append(rename_path(old, new, apply=apply))
    for old, new in RAW_SHARD_BASE_RENAMES.items():
        old_root = f"data/raw/{old}_tar_shards"
        new_root = f"data/raw/{new}_tar_shards"
        actions.append(rename_path(old_root, new_root, apply=apply))
        actions.extend(rename_children_by_token(new_root if apply else old_root, old, new, apply=apply))

    actions.append(rename_path("data/raw/carla_weekend_combined", "data/raw/weekendCombined_v1", apply=apply))
    actions.append(rename_path("data/raw/weekendCombined_v1/carla_weekend_combined", "data/raw/weekendCombined_v1/weekendCombined_v1", apply=apply))
    actions.extend(rename_model_files(apply=apply))
    actions.extend(rename_log_files(apply=apply))
    actions.extend(update_text_files(apply=apply))
    actions.extend(update_tar_metadata(apply=apply))
    return actions


def main() -> None:
    parser = argparse.ArgumentParser(description="Rename existing CARLA runs to the short v1/v2 naming scheme.")
    parser.add_argument("--apply", action="store_true", help="Actually rename and update files. Without this, only prints a dry run.")
    parser.add_argument("--output-json", default="logs/run_rename_map_20260516.json")
    args = parser.parse_args()

    actions = apply_renames(apply=args.apply)
    output_path = inside_workspace(ROOT / args.output_json)
    if args.apply:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(json.dumps(actions, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({
        "applied": args.apply,
        "actions": len(actions),
        "renamed": sum(1 for action in actions if action["action"] == "renamed"),
        "updated": sum(1 for action in actions if action["action"].startswith("updated")),
        "exists": sum(1 for action in actions if action["action"] == "exists"),
        "missing": sum(1 for action in actions if action["action"] == "missing"),
        "output_json": str(output_path.relative_to(ROOT)) if args.apply else None,
    }, indent=2))


if __name__ == "__main__":
    main()

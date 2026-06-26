#!/usr/bin/env python3
"""Prepare the OpenMontage NAS storage layout and sync generated outputs.

The NAS layout mirrors existing NewUnivers project conventions:

    /mnt/newunivers-sdb/nu-openmontage/
      projects/<project-name>/...
      runs/<run-id>/...
      exports/
      outputs/
      pipeline/

This script is intentionally file-copy based. It does not delete source files
or prune NAS directories.
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
from datetime import datetime
from pathlib import Path
from typing import Any


DEFAULT_NAS_ROOT = Path(
    os.environ.get("OPENMONTAGE_NAS_ROOT", "/mnt/newunivers-sdb/nu-openmontage")
)
DEFAULT_PROJECT_NAME = "qa-e2e-test"
DEFAULT_PROJECT_ID = "qa_e2e_test"


def _copy_file(src: Path, dst: Path) -> str:
    dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(src, dst)
    return str(dst)


def _copytree_contents(src: Path, dst: Path) -> list[str]:
    copied: list[str] = []
    if not src.exists():
        return copied

    dst.mkdir(parents=True, exist_ok=True)
    for child in sorted(src.iterdir()):
        target = dst / child.name
        if child.is_dir():
            if target.exists():
                shutil.rmtree(target)
            shutil.copytree(child, target, symlinks=True)
            copied.append(str(target))
        else:
            copied.append(_copy_file(child, target))
    return copied


def ensure_layout(nas_root: Path) -> dict[str, Path]:
    """Create the stable OpenMontage directories on NAS."""
    dirs = {
        "root": nas_root,
        "projects": nas_root / "projects",
        "runs": nas_root / "runs",
        "exports": nas_root / "exports",
        "outputs": nas_root / "outputs",
        "pipeline": nas_root / "pipeline",
        "qa_output": nas_root / "qa-output",
        "logs": nas_root / "logs",
        "tmp": nas_root / "tmp",
    }
    for path in dirs.values():
        path.mkdir(parents=True, exist_ok=True)
    return dirs


def ensure_project_layout(project_dir: Path) -> dict[str, Path]:
    """Create the standard OpenMontage project workspace directories."""
    dirs = {
        "project": project_dir,
        "artifacts": project_dir / "artifacts",
        "assets": project_dir / "assets",
        "images": project_dir / "assets" / "images",
        "video": project_dir / "assets" / "video",
        "audio": project_dir / "assets" / "audio",
        "music": project_dir / "assets" / "music",
        "pipeline": project_dir / "pipeline",
        "renders": project_dir / "renders",
        "review_frames": project_dir / "review_frames",
        "logs": project_dir / "logs",
    }
    for path in dirs.values():
        path.mkdir(parents=True, exist_ok=True)
    return dirs


def _write_json(path: Path, data: Any) -> str:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
    return str(path)


def _export_checkpoint_artifacts(checkpoint_dir: Path, artifact_dir: Path) -> list[str]:
    written: list[str] = []
    for checkpoint_path in sorted(checkpoint_dir.glob("checkpoint_*.json")):
        try:
            checkpoint = json.loads(checkpoint_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            continue
        stage = checkpoint.get("stage", checkpoint_path.stem.replace("checkpoint_", ""))
        artifacts = checkpoint.get("artifacts", {})
        for artifact_name, artifact_data in artifacts.items():
            artifact_path = artifact_dir / f"{stage}__{artifact_name}.json"
            written.append(_write_json(artifact_path, artifact_data))
    return written


def sync_existing_qa_outputs(
    *,
    repo_root: Path,
    nas_root: Path,
    run_id: str,
    project_name: str = DEFAULT_PROJECT_NAME,
    project_id: str = DEFAULT_PROJECT_ID,
) -> dict[str, Any]:
    """Sync the current QA/E2E outputs into the NAS OpenMontage layout."""
    layout = ensure_layout(nas_root)
    project_dirs = ensure_project_layout(layout["projects"] / project_name)

    source_output = repo_root / "tests" / "qa" / "output"
    source_projects = repo_root / "projects"
    source_assets = source_output / "e2e_assets"
    source_pipeline = source_output / "e2e_pipeline" / project_id
    source_final = source_output / "e2e_final_output.mp4"
    source_review_frames = source_output / ".final_review_frames"

    copied: list[str] = []
    run_snapshot = layout["runs"] / run_id / "tests" / "qa" / "output"
    copied.extend(_copytree_contents(source_output, run_snapshot))
    if source_projects.exists() and not source_projects.is_symlink():
        copied.extend(_copytree_contents(source_projects, layout["projects"]))

    if source_final.exists():
        copied.append(_copy_file(source_final, project_dirs["renders"] / "final.mp4"))
        copied.append(_copy_file(source_final, layout["exports"] / f"{project_name}.mp4"))

    copied.extend(_copytree_contents(source_assets, project_dirs["assets"] / "e2e"))
    copied.extend(_copytree_contents(source_pipeline, project_dirs["pipeline"] / project_id))
    copied.extend(_copytree_contents(source_pipeline, layout["pipeline"] / project_id))
    copied.extend(_copytree_contents(source_review_frames, project_dirs["review_frames"]))
    copied.extend(_export_checkpoint_artifacts(source_pipeline, project_dirs["artifacts"]))

    manifest = {
        "version": "1.0",
        "created_at": datetime.now().astimezone().isoformat(),
        "nas_root": str(nas_root),
        "project_name": project_name,
        "project_id": project_id,
        "source_output": str(source_output),
        "source_projects": str(source_projects),
        "run_snapshot": str(run_snapshot),
        "project_dir": str(project_dirs["project"]),
        "final_render": str(project_dirs["renders"] / "final.mp4"),
        "export_render": str(layout["exports"] / f"{project_name}.mp4"),
        "copied_count": len(copied),
    }
    copied.append(_write_json(project_dirs["project"] / "storage_manifest.json", manifest))
    copied.append(_write_json(layout["runs"] / run_id / "storage_manifest.json", manifest))
    manifest["copied"] = copied
    return manifest


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--nas-root", type=Path, default=DEFAULT_NAS_ROOT)
    parser.add_argument("--repo-root", type=Path, default=Path.cwd())
    parser.add_argument("--project-name", default=DEFAULT_PROJECT_NAME)
    parser.add_argument("--project-id", default=DEFAULT_PROJECT_ID)
    parser.add_argument(
        "--run-id",
        default=f"qa-e2e-{datetime.now().astimezone().strftime('%Y%m%dT%H%M%S')}",
    )
    parser.add_argument(
        "--layout-only",
        action="store_true",
        help="Only create the NAS layout; do not copy existing QA outputs.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    layout = ensure_layout(args.nas_root)
    if args.layout_only:
        print(json.dumps({k: str(v) for k, v in layout.items()}, indent=2))
        return 0

    manifest = sync_existing_qa_outputs(
        repo_root=args.repo_root.resolve(),
        nas_root=args.nas_root.resolve(),
        run_id=args.run_id,
        project_name=args.project_name,
        project_id=args.project_id,
    )
    print(json.dumps(manifest, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

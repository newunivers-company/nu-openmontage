from __future__ import annotations

import json
from pathlib import Path

from tools.storage.prepare_nas_storage import ensure_layout, sync_existing_qa_outputs


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


def test_ensure_layout_creates_openmontage_nas_dirs(tmp_path):
    layout = ensure_layout(tmp_path / "nas" / "nu-openmontage")

    for key in ("projects", "runs", "exports", "outputs", "pipeline", "qa_output"):
        assert layout[key].is_dir()


def test_sync_existing_qa_outputs_materializes_project_layout(tmp_path):
    repo_root = tmp_path / "repo"
    qa_output = repo_root / "tests" / "qa" / "output"
    assets = qa_output / "e2e_assets"
    pipeline = qa_output / "e2e_pipeline" / "qa_e2e_test"

    assets.mkdir(parents=True)
    (assets / "scene_sc1.mp4").write_bytes(b"video")
    (qa_output / "e2e_final_output.mp4").write_bytes(b"final")
    _write_json(
        pipeline / "checkpoint_compose.json",
        {
            "stage": "compose",
            "artifacts": {
                "render_report": {"version": "1.0"},
                "final_review": {"version": "1.0"},
            },
        },
    )

    manifest = sync_existing_qa_outputs(
        repo_root=repo_root,
        nas_root=tmp_path / "nas" / "nu-openmontage",
        run_id="qa-e2e-test-run",
    )

    project_dir = Path(manifest["project_dir"])
    assert (project_dir / "renders" / "final.mp4").read_bytes() == b"final"
    assert (project_dir / "assets" / "e2e" / "scene_sc1.mp4").read_bytes() == b"video"
    assert (project_dir / "pipeline" / "qa_e2e_test" / "checkpoint_compose.json").exists()
    assert (project_dir / "artifacts" / "compose__render_report.json").exists()
    assert (project_dir / "artifacts" / "compose__final_review.json").exists()
    assert (project_dir / "storage_manifest.json").exists()
    assert (tmp_path / "nas" / "nu-openmontage" / "runs" / "qa-e2e-test-run").is_dir()

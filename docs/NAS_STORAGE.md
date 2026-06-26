# NAS Storage Layout

OpenMontage writes generated outputs to the NewUnivers NAS when available.

## Root

Default NAS root:

```text
/mnt/newunivers-sdb/nu-openmontage
```

This follows the existing NAS convention used by sibling projects:

- `outputs/runs/` for repeatable run snapshots
- `projects/` for project workspaces
- `exports/` for final deliverables
- `pipeline/` for durable checkpoint archives

## Layout

```text
/mnt/newunivers-sdb/nu-openmontage/
├── projects/
│   └── <project-name>/
│       ├── artifacts/
│       ├── assets/
│       │   ├── images/
│       │   ├── video/
│       │   ├── audio/
│       │   └── music/
│       ├── pipeline/
│       ├── renders/
│       │   └── final.mp4
│       ├── review_frames/
│       └── storage_manifest.json
├── runs/
│   └── <run-id>/
├── exports/
├── outputs/
├── pipeline/
├── qa-output/
├── logs/
└── tmp/
```

## Preparation

Create the layout and sync the current QA/E2E output:

```bash
python3 tools/storage/prepare_nas_storage.py
```

Create directories only:

```bash
python3 tools/storage/prepare_nas_storage.py --layout-only
```

Override the NAS root:

```bash
OPENMONTAGE_NAS_ROOT=/path/to/nu-openmontage \
python3 tools/storage/prepare_nas_storage.py
```

## Current Policy

- Production project workspaces should use `paths.projects_dir`.
- Checkpoint archives should use `paths.pipeline_dir`.
- Scratch or QA snapshots can go under `runs/<run-id>/`.
- Final user-facing deliverables should also be copied to `exports/`.
- If `/mnt/newunivers-sdb` is not mounted, do not silently write large outputs
  locally. Surface it as a storage blocker and ask before using local fallback.

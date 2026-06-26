"""Repository-wide integrity checks for pipeline manifests.

These tests catch declarative pipeline drift: invalid manifest schema,
missing director skills, tool names that are not registered BaseTool
instances, and artifact references that cannot validate downstream.
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any, Iterable

import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from lib.pipeline_loader import list_pipelines, load_pipeline
from schemas.artifacts import list_schemas
from tools.tool_registry import registry


PIPELINE_NAMES = sorted(list_pipelines())
SKILLS_DIR = PROJECT_ROOT / "skills"
EXTERNAL_INPUT_ARTIFACTS = {"source_media_review", "video_analysis_brief"}
TOOL_FIELDS = (
    "tools_available",
    "required_tools",
    "optional_tools",
    "preferred_tools",
    "fallback_tools",
)


def _tool_refs(manifest: dict[str, Any]) -> Iterable[tuple[str, str, str]]:
    """Yield (location, field, tool_name) for every manifest-declared tool."""
    for tool_name in manifest.get("reference_input", {}).get("analysis_tools", []) or []:
        yield "reference_input", "analysis_tools", tool_name

    for index, mode in enumerate(manifest.get("production_modes", []) or []):
        location = f"production_modes[{index}]"
        for field in ("required_tools", "optional_tools"):
            for tool_name in mode.get(field, []) or []:
                yield location, field, tool_name

    for stage in manifest.get("stages", []):
        stage_name = stage["name"]
        for field in TOOL_FIELDS:
            for tool_name in stage.get(field, []) or []:
                yield stage_name, field, tool_name
        for sub_stage in stage.get("sub_stages", []) or []:
            location = f"{stage_name}.{sub_stage['name']}"
            for tool_name in sub_stage.get("tools_available", []) or []:
                yield location, "tools_available", tool_name


def _artifact_refs(stage: dict[str, Any]) -> Iterable[tuple[str, str]]:
    for field in ("required_artifacts_in", "optional_artifacts_in", "produces"):
        for artifact_name in stage.get(field, []) or []:
            yield field, artifact_name


@pytest.mark.parametrize("pipeline_name", PIPELINE_NAMES)
def test_all_pipeline_manifests_load(pipeline_name: str) -> None:
    manifest = load_pipeline(pipeline_name)
    assert manifest["name"] == pipeline_name


@pytest.mark.parametrize("pipeline_name", PIPELINE_NAMES)
def test_each_stage_has_existing_director_skill(pipeline_name: str) -> None:
    manifest = load_pipeline(pipeline_name)
    for stage in manifest["stages"]:
        skill_ref = stage.get("skill")
        assert skill_ref, f"{pipeline_name}.{stage['name']} is missing skill"
        skill_path = SKILLS_DIR / f"{skill_ref}.md"
        assert skill_path.is_file(), (
            f"{pipeline_name}.{stage['name']} references missing skill: {skill_ref}"
        )


@pytest.mark.parametrize("pipeline_name", PIPELINE_NAMES)
def test_manifest_tool_references_are_registered(pipeline_name: str) -> None:
    registry.ensure_discovered()
    known_tools = set(registry.list_all())
    manifest = load_pipeline(pipeline_name)

    missing = [
        f"{location}.{field}: {tool_name}"
        for location, field, tool_name in _tool_refs(manifest)
        if tool_name not in known_tools
    ]

    assert not missing, (
        f"{pipeline_name} references tools not registered in ToolRegistry: "
        + ", ".join(missing)
    )


@pytest.mark.parametrize("pipeline_name", PIPELINE_NAMES)
def test_manifest_artifact_references_have_schemas(pipeline_name: str) -> None:
    artifact_schemas = set(list_schemas())
    manifest = load_pipeline(pipeline_name)

    missing = [
        f"{stage['name']}.{field}: {artifact_name}"
        for stage in manifest["stages"]
        for field, artifact_name in _artifact_refs(stage)
        if artifact_name not in artifact_schemas
    ]

    assert not missing, (
        f"{pipeline_name} references artifacts without schemas: "
        + ", ".join(missing)
    )


@pytest.mark.parametrize("pipeline_name", PIPELINE_NAMES)
def test_required_artifacts_are_produced_before_use(pipeline_name: str) -> None:
    manifest = load_pipeline(pipeline_name)
    produced: set[str] = set()
    errors: list[str] = []

    for stage in manifest["stages"]:
        for artifact_name in stage.get("required_artifacts_in", []) or []:
            if artifact_name in produced or artifact_name in EXTERNAL_INPUT_ARTIFACTS:
                continue
            errors.append(f"{stage['name']} requires {artifact_name} before it is produced")
        produced.update(stage.get("produces", []) or [])

    assert not errors, f"{pipeline_name} has impossible artifact flow: {', '.join(errors)}"

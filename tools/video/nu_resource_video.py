"""Video-generation selector provider backed by nu-resource-gen-lib."""

from __future__ import annotations

from typing import Any

from tools.base_tool import Determinism, ExecutionMode, ToolRuntime, ToolStability, ToolTier
from tools.generation._resource_category import NuResourceCategoryMixin
from tools.generation.resource_generator import NuResourceGenerator


PROMPT_VIDEO_CANDIDATES = (
    "seedance1_5",
    "minimax_hailuo",
    "kling3_0_turbo",
    "kling3_0",
    "wan2_7",
    "veo3_1_lite",
    "seedance_2_0_mini",
    "seedance_2_0",
)
MEDIA_VIDEO_CANDIDATES = (
    "bytedance_video_upscale",
    "video_background_remover",
    "sam_3_video",
    "video_upscale",
    "video_deflicker",
    "topaz_video",
)


class NuResourceVideo(NuResourceCategoryMixin, NuResourceGenerator):
    name = "nu_resource_video"
    version = "0.1.0"
    tier = ToolTier.GENERATE
    capability = "video_generation"
    provider = "nu_resource_gen_lib"
    stability = ToolStability.BETA
    execution_mode = ExecutionMode.SYNC
    determinism = Determinism.STOCHASTIC
    runtime = ToolRuntime.HYBRID
    resource_category = "video_generation"

    capabilities = [
        "text_to_video",
        "image_to_video",
        "reference_to_video",
        "resource_catalog_candidate",
    ]
    supports = {
        "catalog_candidates": True,
        "candidate_id_override": True,
        "resource_provider_override": True,
        "reference_image": True,
        "cost_metadata": True,
    }
    best_for = [
        "using nu-resource-gen-lib video candidates through video_selector",
        "shared catalog access to Higgsfield, BytePlus, and other registered video models",
    ]
    not_good_for = ["offline generation", "local GPU video generation"]

    input_schema = {
        "type": "object",
        "required": ["prompt"],
        "properties": {
            "prompt": {"type": "string"},
            "operation": {
                "type": "string",
                "enum": ["text_to_video", "image_to_video", "reference_to_video"],
                "default": "text_to_video",
            },
            "candidate_id": {"type": "string"},
            "resource_provider": {"type": "string"},
            "aspect_ratio": {"type": "string"},
            "duration": {"type": "string"},
            "resolution": {"type": "string"},
            "reference_image_path": {"type": "string"},
            "reference_image_url": {"type": "string"},
            "reference_image_paths": {"type": "array", "items": {"type": "string"}},
            "reference_image_urls": {"type": "array", "items": {"type": "string"}},
            "image_url": {"type": "string"},
            "params": {"type": "object"},
            "media": {"type": "object"},
            "output_path": {"type": "string"},
        },
    }

    def _passthrough_param_keys(self) -> tuple[str, ...]:
        return ("operation", "aspect_ratio", "duration", "resolution", "output_path")

    def _passthrough_media_keys(self) -> tuple[str, ...]:
        return (
            "reference_image_path",
            "reference_image_url",
            "reference_image_paths",
            "reference_image_urls",
            "image_url",
        )

    def _select_candidate_id(self, inputs: dict[str, Any], generator: Any) -> str:
        explicit = inputs.get("candidate_id")
        if explicit:
            return str(explicit)

        candidates = generator.list_candidates(category=self.resource_category)
        preferred_provider = inputs.get("resource_provider")
        if preferred_provider:
            candidates = [spec for spec in candidates if spec.provider == preferred_provider]
        if not candidates:
            raise ValueError(f"No resource candidates for category {self.resource_category!r}")

        health = generator.health()
        healthy = [spec for spec in candidates if health.get(spec.provider)]
        pool = healthy or candidates
        by_id = {spec.candidate_id: spec for spec in pool}

        preferred_ids = (
            MEDIA_VIDEO_CANDIDATES
            if inputs.get("media", {}).get("video") or inputs.get("video")
            else PROMPT_VIDEO_CANDIDATES
        )
        for candidate_id in preferred_ids:
            if candidate_id in by_id:
                return candidate_id
        return pool[0].candidate_id

    def _adapt_resource_inputs(self, inputs: dict[str, Any], candidate_id: str) -> dict[str, Any]:
        adapted = super()._adapt_resource_inputs(inputs, candidate_id)
        if candidate_id in MEDIA_VIDEO_CANDIDATES:
            adapted["prompt"] = ""
        return adapted

    def get_info(self) -> dict[str, Any]:
        info = super().get_info()
        info["resource_category"] = self.resource_category
        return info

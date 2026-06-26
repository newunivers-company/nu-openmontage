"""Image-generation selector provider backed by nu-resource-gen-lib."""

from __future__ import annotations

from typing import Any

from tools.base_tool import Determinism, ExecutionMode, ToolRuntime, ToolStability, ToolTier
from tools.generation._resource_category import NuResourceCategoryMixin
from tools.generation.resource_generator import NuResourceGenerator


class NuResourceImage(NuResourceCategoryMixin, NuResourceGenerator):
    name = "nu_resource_image"
    version = "0.1.0"
    tier = ToolTier.GENERATE
    capability = "image_generation"
    provider = "nu_resource_gen_lib"
    stability = ToolStability.BETA
    execution_mode = ExecutionMode.SYNC
    determinism = Determinism.STOCHASTIC
    runtime = ToolRuntime.HYBRID
    resource_category = "image_generation"

    capabilities = ["generate_image", "text_to_image", "resource_catalog_candidate"]
    supports = {
        "catalog_candidates": True,
        "candidate_id_override": True,
        "resource_provider_override": True,
        "cost_metadata": True,
    }
    best_for = [
        "using nu-resource-gen-lib image candidates through image_selector",
        "switching between shared catalog image models without adding provider-specific tools",
    ]
    not_good_for = [
        "offline generation",
        "provider-specific advanced controls not represented in params",
    ]

    input_schema = {
        "type": "object",
        "required": ["prompt"],
        "properties": {
            "prompt": {"type": "string"},
            "candidate_id": {"type": "string"},
            "resource_provider": {"type": "string"},
            "negative_prompt": {"type": "string"},
            "width": {"type": "integer"},
            "height": {"type": "integer"},
            "seed": {"type": "integer"},
            "n": {"type": "integer"},
            "aspect_ratio": {"type": "string"},
            "resolution": {"type": "string"},
            "generation_mode": {"type": "string"},
            "image_url": {"type": "string"},
            "image_path": {"type": "string"},
            "image_urls": {"type": "array", "items": {"type": "string"}},
            "image_paths": {"type": "array", "items": {"type": "string"}},
            "params": {"type": "object"},
            "media": {"type": "object"},
            "output_path": {"type": "string"},
        },
    }

    def _passthrough_param_keys(self) -> tuple[str, ...]:
        return (
            "negative_prompt",
            "width",
            "height",
            "seed",
            "n",
            "aspect_ratio",
            "resolution",
            "generation_mode",
            "output_path",
        )

    def _passthrough_media_keys(self) -> tuple[str, ...]:
        return ("image_url", "image_path", "image_urls", "image_paths")

    def get_info(self) -> dict[str, Any]:
        info = super().get_info()
        info["resource_category"] = self.resource_category
        return info

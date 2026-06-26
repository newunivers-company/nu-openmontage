"""TTS selector provider backed by nu-resource-gen-lib voice candidates."""

from __future__ import annotations

from typing import Any

from tools.base_tool import Determinism, ExecutionMode, ToolRuntime, ToolStability, ToolTier
from tools.generation._resource_category import NuResourceCategoryMixin
from tools.generation.resource_generator import NuResourceGenerator


class NuResourceTTS(NuResourceCategoryMixin, NuResourceGenerator):
    name = "nu_resource_tts"
    version = "0.1.0"
    tier = ToolTier.VOICE
    capability = "tts"
    provider = "nu_resource_gen_lib"
    stability = ToolStability.BETA
    execution_mode = ExecutionMode.SYNC
    determinism = Determinism.STOCHASTIC
    runtime = ToolRuntime.HYBRID
    resource_category = "voice_audio"

    capabilities = ["text_to_speech", "resource_catalog_candidate"]
    supports = {
        "catalog_candidates": True,
        "candidate_id_override": True,
        "resource_provider_override": True,
        "multilingual": True,
        "cost_metadata": True,
    }
    best_for = [
        "using nu-resource-gen-lib voice candidates through tts_selector",
        "shared catalog access to OpenAI and ElevenLabs voice models",
    ]
    not_good_for = ["offline TTS", "voice cloning workflows"]
    fallback_tools = ["piper_tts"]

    input_schema = {
        "type": "object",
        "required": ["text"],
        "properties": {
            "text": {"type": "string"},
            "candidate_id": {"type": "string"},
            "resource_provider": {"type": "string"},
            "voice_id": {"type": "string"},
            "voice": {"type": "string"},
            "model_id": {"type": "string"},
            "model": {"type": "string"},
            "stability": {"type": "number"},
            "similarity_boost": {"type": "number"},
            "style": {"type": "number"},
            "output_format": {"type": "string"},
            "format": {"type": "string"},
            "speed": {"type": "number"},
            "params": {"type": "object"},
            "media": {"type": "object"},
            "output_path": {"type": "string"},
        },
    }

    def _resource_prompt(self, inputs: dict[str, Any]) -> str:
        return str(inputs.get("text") or inputs.get("prompt") or "")

    def _passthrough_param_keys(self) -> tuple[str, ...]:
        return (
            "voice_id",
            "voice",
            "model_id",
            "model",
            "stability",
            "similarity_boost",
            "style",
            "output_format",
            "format",
            "speed",
            "output_path",
        )

    def get_info(self) -> dict[str, Any]:
        info = super().get_info()
        info["resource_category"] = self.resource_category
        return info

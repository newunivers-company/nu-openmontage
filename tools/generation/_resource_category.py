"""Shared helpers for category-specific nu-resource-gen-lib provider tools."""

from __future__ import annotations

from typing import Any

from tools.base_tool import ToolResult, ToolStatus


class NuResourceCategoryMixin:
    """Mixin for exposing one resource catalog category as a selector provider."""

    resource_category: str = ""

    def get_status(self) -> ToolStatus:
        if not self._integration_status()["available"]:
            return ToolStatus.UNAVAILABLE
        try:
            generator = self._build_generator({})
            health = generator.health()
            candidates = generator.list_candidates(category=self.resource_category)
        except Exception:
            return ToolStatus.UNAVAILABLE
        if any(health.get(spec.provider) for spec in candidates):
            return ToolStatus.AVAILABLE
        return ToolStatus.UNAVAILABLE

    def estimate_cost(self, inputs: dict[str, Any]) -> float:
        try:
            generator = self._build_generator(inputs)
            candidate_id = self._select_candidate_id(inputs, generator)
            spec = generator.get_candidate(candidate_id)
        except Exception:
            return 0.0
        if spec.cost is not None and spec.cost_unit == "usd":
            return float(spec.cost)
        return 0.0

    def execute(self, inputs: dict[str, Any]) -> ToolResult:
        try:
            generator = self._build_generator(inputs)
            candidate_id = self._select_candidate_id(inputs, generator)
        except Exception as exc:  # noqa: BLE001 - adapter returns ToolResult
            return ToolResult(success=False, error=f"{self.name} failed: {exc}")
        adapted = self._adapt_resource_inputs(inputs, candidate_id)
        return super().execute(adapted)

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
        selected = (healthy or candidates)[0]
        return selected.candidate_id

    def _adapt_resource_inputs(self, inputs: dict[str, Any], candidate_id: str) -> dict[str, Any]:
        return {
            **inputs,
            "operation": "generate",
            "candidate_id": candidate_id,
            "prompt": self._resource_prompt(inputs),
            "params": self._resource_params(inputs),
            "media": self._resource_media(inputs),
        }

    def _resource_prompt(self, inputs: dict[str, Any]) -> str:
        return str(inputs.get("prompt") or "")

    def _resource_params(self, inputs: dict[str, Any]) -> dict[str, Any]:
        params = dict(inputs.get("params") or {})
        for key in self._passthrough_param_keys():
            if inputs.get(key) is not None:
                params.setdefault(key, inputs[key])
        return params

    def _resource_media(self, inputs: dict[str, Any]) -> dict[str, Any]:
        media = dict(inputs.get("media") or {})
        for key in self._passthrough_media_keys():
            if inputs.get(key) is not None:
                media.setdefault(key, inputs[key])
        return media

    def _passthrough_param_keys(self) -> tuple[str, ...]:
        return ()

    def _passthrough_media_keys(self) -> tuple[str, ...]:
        return ()

"""OpenMontage adapter for nu-resource-gen-lib."""

from __future__ import annotations

import time
from dataclasses import asdict
from pathlib import Path
from typing import Any

from lib.nu_integrations import ensure_sibling_src, package_status
from tools.base_tool import (
    BaseTool,
    Determinism,
    ExecutionMode,
    ResourceProfile,
    ToolResult,
    ToolRuntime,
    ToolStability,
    ToolStatus,
    ToolTier,
)


PACKAGE_NAME = "nu_resource_gen_lib"
SIBLING_DIR = "nu-resource-gen-lib"


class NuResourceGenerator(BaseTool):
    """Expose nu-resource-gen-lib's provider catalog and generation API."""

    name = "nu_resource_generator"
    version = "0.1.0"
    tier = ToolTier.GENERATE
    capability = "resource_generation"
    provider = "nu_resource_gen_lib"
    stability = ToolStability.BETA
    execution_mode = ExecutionMode.SYNC
    determinism = Determinism.STOCHASTIC
    runtime = ToolRuntime.HYBRID

    dependencies: list[str] = []
    install_instructions = (
        "Install `../nu-resource-gen-lib` with `pip install -e ../nu-resource-gen-lib` "
        "or keep that sibling checkout next to this repo. Provider API keys are "
        "reported by the `health` operation."
    )

    capabilities = [
        "list_resource_candidates",
        "resource_provider_health",
        "generate_resource",
        "image_generation",
        "video_generation",
        "voice_audio",
        "three_d_generation",
    ]
    supports = {
        "sibling_checkout_fallback": True,
        "catalog_filtering": True,
        "candidate_cost_metadata": True,
        "provider_health": True,
    }
    best_for = [
        "catalog-driven selection across image, video, audio, and 3D generation candidates",
        "checking provider credential coverage before planning asset generation",
        "running a chosen candidate through the shared resource generation library",
    ]
    not_good_for = [
        "selector scoring; this tool exposes catalog candidates and explicit generation",
        "offline generation when the selected candidate needs cloud credentials",
    ]
    resource_profile = ResourceProfile(
        cpu_cores=1, ram_mb=256, vram_mb=0, disk_mb=100, network_required=True
    )
    side_effects = [
        "may call provider APIs and create remote generation jobs for generate operations",
    ]
    user_visible_verification = [
        "Review returned asset_uri/output_text and provider status before using generated assets",
    ]

    input_schema = {
        "type": "object",
        "properties": {
            "operation": {
                "type": "string",
                "enum": ["list_candidates", "health", "show_candidate", "generate"],
                "default": "list_candidates",
            },
            "provider": {"type": "string"},
            "category": {"type": "string"},
            "candidate_id": {"type": "string"},
            "prompt": {"type": "string"},
            "params": {"type": "object"},
            "media": {"type": "object"},
            "catalog_path": {"type": "string"},
            "timeout": {"type": "number", "default": 120.0},
            "wait_timeout": {"type": "string", "default": "12m"},
            "max_polls": {"type": "integer", "default": 120},
            "poll_interval": {"type": "number", "default": 5.0},
            "poll_timeout": {"type": "number", "default": 120.0},
            "max_retries": {"type": "integer", "default": 2},
            "retry_backoff": {"type": "number", "default": 1.0},
            "retry_submit": {"type": "boolean", "default": False},
        },
    }
    output_schema = {
        "type": "object",
        "properties": {
            "candidates": {"type": "array"},
            "candidate": {"type": "object"},
            "provider_health": {"type": "object"},
            "result": {"type": "object"},
        },
    }

    def get_status(self) -> ToolStatus:
        return ToolStatus.AVAILABLE if self._integration_status()["available"] else ToolStatus.UNAVAILABLE

    def get_info(self) -> dict[str, Any]:
        info = super().get_info()
        info["integration"] = self._integration_status()
        return info

    def estimate_cost(self, inputs: dict[str, Any]) -> float:
        candidate_id = inputs.get("candidate_id")
        if not candidate_id:
            return 0.0
        try:
            spec = self._build_generator(inputs).get_candidate(candidate_id)
        except Exception:
            return 0.0
        if spec.cost is not None and spec.cost_unit == "usd":
            return float(spec.cost)
        return 0.0

    def dry_run(self, inputs: dict[str, Any]) -> dict[str, Any]:
        result = super().dry_run(inputs)
        candidate_id = inputs.get("candidate_id")
        if result["status"] == ToolStatus.AVAILABLE.value and candidate_id:
            try:
                spec = self._build_generator(inputs).get_candidate(candidate_id)
                result["candidate"] = self._spec_dict(spec)
                result["estimated_cost_usd"] = self.estimate_cost(inputs)
            except Exception as exc:  # noqa: BLE001 - dry-run diagnostic
                result["candidate_error"] = str(exc)
        return result

    def execute(self, inputs: dict[str, Any]) -> ToolResult:
        operation = inputs.get("operation", "list_candidates")
        start = time.time()
        try:
            generator = self._build_generator(inputs)

            if operation == "health":
                return ToolResult(
                    success=True,
                    data={
                        "integration": self._integration_status(),
                        "provider_health": generator.health(),
                    },
                    duration_seconds=round(time.time() - start, 2),
                )

            if operation == "list_candidates":
                specs = generator.list_candidates(
                    provider=inputs.get("provider"),
                    category=inputs.get("category"),
                )
                return ToolResult(
                    success=True,
                    data={
                        "candidates": [self._spec_dict(spec) for spec in specs],
                        "count": len(specs),
                        "filters": {
                            "provider": inputs.get("provider"),
                            "category": inputs.get("category"),
                        },
                    },
                    duration_seconds=round(time.time() - start, 2),
                )

            if operation == "show_candidate":
                candidate_id = self._required_candidate_id(inputs)
                spec = generator.get_candidate(candidate_id)
                return ToolResult(
                    success=True,
                    data={"candidate": self._spec_dict(spec)},
                    cost_usd=self.estimate_cost(inputs),
                    duration_seconds=round(time.time() - start, 2),
                    model=spec.model,
                )

            if operation != "generate":
                return ToolResult(success=False, error=f"Unsupported operation: {operation}")

            candidate_id = self._required_candidate_id(inputs)
            request = self._resource_request(inputs)
            result = generator.generate(candidate_id, request)
            cost_usd = float(result.cost or 0.0) if result.cost_unit == "usd" else 0.0
            artifacts = [result.asset_uri] if result.asset_uri else []
            return ToolResult(
                success=True,
                data={"result": self._result_dict(result)},
                artifacts=artifacts,
                cost_usd=cost_usd,
                duration_seconds=round(time.time() - start, 2),
                model=result.model,
            )
        except Exception as exc:  # noqa: BLE001 - adapters must return ToolResult
            return ToolResult(
                success=False,
                error=f"{self.name} failed: {exc}",
                duration_seconds=round(time.time() - start, 2),
            )

    def _integration_status(self) -> dict[str, Any]:
        return package_status(PACKAGE_NAME, SIBLING_DIR).to_dict()

    def _build_generator(self, inputs: dict[str, Any]):
        ensure_sibling_src(PACKAGE_NAME, SIBLING_DIR)
        from nu_resource_gen_lib import ResourceGenerator  # type: ignore[import-not-found]

        catalog_path = inputs.get("catalog_path")
        if catalog_path:
            path = Path(catalog_path)
            if not path.is_file():
                raise FileNotFoundError(f"resource catalog not found: {path}")
            return ResourceGenerator(candidates=path)
        return ResourceGenerator()

    def _resource_request(self, inputs: dict[str, Any]):
        ensure_sibling_src(PACKAGE_NAME, SIBLING_DIR)
        from nu_resource_gen_lib import ResourceRequest  # type: ignore[import-not-found]

        return ResourceRequest(
            prompt=inputs.get("prompt") or "",
            params=dict(inputs.get("params") or {}),
            media=dict(inputs.get("media") or {}),
            timeout=float(inputs.get("timeout", 120.0)),
            wait_timeout=str(inputs.get("wait_timeout", "12m")),
            max_polls=int(inputs.get("max_polls", 120)),
            poll_interval=float(inputs.get("poll_interval", 5.0)),
            poll_timeout=float(inputs.get("poll_timeout", 120.0)),
            max_retries=int(inputs.get("max_retries", 2)),
            retry_backoff=float(inputs.get("retry_backoff", 1.0)),
            retry_submit=bool(inputs.get("retry_submit", False)),
        )

    @staticmethod
    def _required_candidate_id(inputs: dict[str, Any]) -> str:
        candidate_id = inputs.get("candidate_id")
        if not candidate_id:
            raise ValueError("candidate_id is required")
        return str(candidate_id)

    @staticmethod
    def _spec_dict(spec: Any) -> dict[str, Any]:
        return asdict(spec)

    @staticmethod
    def _result_dict(result: Any) -> dict[str, Any]:
        data = asdict(result)
        if hasattr(result, "to_artifact_run"):
            data["artifact_run"] = result.to_artifact_run()
        return data

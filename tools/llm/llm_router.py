"""OpenMontage adapter for nu-llm-routing-lib."""

from __future__ import annotations

import os
import time
from dataclasses import replace
from pathlib import Path
from typing import Any, Mapping, Sequence

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


PACKAGE_NAME = "nu_llm_routing_lib"
SIBLING_DIR = "nu-llm-routing-lib"


class NuLLMRouter(BaseTool):
    """Route chat and prompt-rewrite requests through nu-llm-routing-lib."""

    name = "nu_llm_router"
    version = "0.1.0"
    tier = ToolTier.CORE
    capability = "llm_routing"
    provider = "nu_llm_routing_lib"
    stability = ToolStability.BETA
    execution_mode = ExecutionMode.SYNC
    determinism = Determinism.STOCHASTIC
    runtime = ToolRuntime.HYBRID

    dependencies: list[str] = []
    install_instructions = (
        "Install `../nu-llm-routing-lib` with `pip install -e ../nu-llm-routing-lib` "
        "or keep that sibling checkout next to this repo. Optional: set "
        "NU_LLM_ROUTER_CONFIG to a router JSON config."
    )

    capabilities = [
        "chat",
        "structured_json",
        "provider_routing",
        "prompt_rewrite",
        "prompt_enhancement",
        "provider_health",
    ]
    supports = {
        "sibling_checkout_fallback": True,
        "route_profiles": True,
        "structured_output_metadata": True,
        "generation_prompt_rewrite": True,
        "no_provider_call_route_order": True,
    }
    best_for = [
        "central language-model routing for agent tasks",
        "checking route profiles before making a provider call",
        "rewriting image/video generation prompts for encoder families",
    ]
    not_good_for = [
        "guaranteed cost estimates; provider costs are not normalized here",
        "offline inference unless an available local provider is configured",
    ]
    resource_profile = ResourceProfile(
        cpu_cores=1, ram_mb=256, vram_mb=0, disk_mb=10, network_required=True
    )
    side_effects = [
        "may call configured LLM providers for chat/json/rewrite operations",
    ]
    user_visible_verification = [
        "Inspect selected provider/model and returned content before using generated text",
    ]

    input_schema = {
        "type": "object",
        "properties": {
            "operation": {
                "type": "string",
                "enum": [
                    "chat",
                    "json",
                    "route_order",
                    "health",
                    "generation_prompt_rewrite",
                    "prompt_enhancement",
                ],
                "default": "chat",
            },
            "prompt": {"type": "string"},
            "system": {"type": "string"},
            "history": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "role": {"type": "string"},
                        "content": {"type": "string"},
                    },
                    "required": ["role", "content"],
                },
            },
            "messages": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "role": {"type": "string"},
                        "content": {"type": "string"},
                    },
                    "required": ["role", "content"],
                },
            },
            "provider": {"type": "string"},
            "model": {"type": "string"},
            "temperature": {"type": "number", "default": 0.2},
            "max_tokens": {"type": "integer"},
            "timeout_seconds": {"type": "number", "default": 120.0},
            "workload": {"type": "string"},
            "hardware_profile": {"type": "string"},
            "content_profile": {"type": "string"},
            "tags": {"type": "array", "items": {"type": "string"}},
            "metadata": {"type": "object"},
            "json_schema": {"type": "object"},
            "json_schema_name": {"type": "string", "default": "structured_response"},
            "strict_json_schema": {"type": "boolean", "default": True},
            "encoder_family": {
                "type": "string",
                "enum": ["clip", "t5", "llm"],
                "default": "t5",
            },
            "model_profile": {"type": "object"},
            "reference_context": {"type": "string"},
            "constraints": {"type": "array", "items": {"type": "string"}},
            "source_project": {"type": "string"},
            "local_only": {"type": "boolean", "default": False},
            "strict_determinism": {"type": "boolean", "default": False},
            "router_config": {"type": "object"},
            "config_path": {"type": "string"},
        },
    }
    output_schema = {
        "type": "object",
        "properties": {
            "provider": {"type": "string"},
            "model": {"type": "string"},
            "content": {"type": "string"},
            "parsed": {"type": "object"},
            "route_order": {"type": "array", "items": {"type": "string"}},
            "provider_status": {"type": "object"},
        },
    }

    def get_status(self) -> ToolStatus:
        return ToolStatus.AVAILABLE if self._integration_status()["available"] else ToolStatus.UNAVAILABLE

    def get_info(self) -> dict[str, Any]:
        info = super().get_info()
        info["integration"] = self._integration_status()
        return info

    def estimate_cost(self, inputs: dict[str, Any]) -> float:
        return 0.0

    def dry_run(self, inputs: dict[str, Any]) -> dict[str, Any]:
        result = super().dry_run(inputs)
        if result["status"] == ToolStatus.AVAILABLE.value and inputs.get("operation") != "health":
            try:
                router = self._build_router(inputs)
                request = self._build_request(inputs)
                result["route_order"] = router.route_order_for(request)
                result["would_call_provider"] = inputs.get("operation", "chat") not in {"route_order"}
            except Exception as exc:  # noqa: BLE001 - dry-run diagnostic
                result["route_error"] = str(exc)
        return result

    def execute(self, inputs: dict[str, Any]) -> ToolResult:
        operation = inputs.get("operation", "chat")
        start = time.time()
        try:
            router = self._build_router(inputs)

            if operation == "health":
                return ToolResult(
                    success=True,
                    data={
                        "integration": self._integration_status(),
                        "provider_status": {
                            name: self._provider_status_dict(status)
                            for name, status in router.status().items()
                        },
                    },
                    duration_seconds=round(time.time() - start, 2),
                )

            request = self._build_request(inputs)
            if operation == "route_order":
                return ToolResult(
                    success=True,
                    data={
                        "route_order": router.route_order_for(request),
                        "metadata": dict(request.metadata),
                    },
                    duration_seconds=round(time.time() - start, 2),
                )

            if operation not in {
                "chat",
                "json",
                "generation_prompt_rewrite",
                "prompt_enhancement",
            }:
                return ToolResult(success=False, error=f"Unsupported operation: {operation}")

            response = router.chat(request)
            data = {
                "provider": response.provider,
                "model": response.model,
                "content": response.content,
                "usage": dict(response.usage or {}),
                "metadata": dict(request.metadata),
            }
            parsed = response.parsed
            if parsed is not None:
                data["parsed"] = parsed
            if response.raw:
                data["raw"] = dict(response.raw)
            return ToolResult(
                success=True,
                data=data,
                duration_seconds=round(time.time() - start, 2),
                model=response.model,
            )
        except Exception as exc:  # noqa: BLE001 - adapters must return ToolResult
            return ToolResult(
                success=False,
                error=f"{self.name} failed: {exc}",
                duration_seconds=round(time.time() - start, 2),
            )

    def _integration_status(self) -> dict[str, Any]:
        return package_status(PACKAGE_NAME, SIBLING_DIR).to_dict()

    def _build_router(self, inputs: dict[str, Any]):
        ensure_sibling_src(PACKAGE_NAME, SIBLING_DIR)
        from nu_llm_routing_lib.config import (  # type: ignore[import-not-found]
            build_default_router,
            load_router_from_dict,
            load_router_from_file,
        )

        inline_config = inputs.get("router_config")
        if inline_config:
            if not isinstance(inline_config, dict):
                raise ValueError("router_config must be a dict")
            return load_router_from_dict(inline_config)

        config_path = inputs.get("config_path") or os.environ.get("NU_LLM_ROUTER_CONFIG")
        if config_path:
            path = Path(config_path)
            if not path.is_file():
                raise FileNotFoundError(f"router config not found: {path}")
            return load_router_from_file(path)

        return build_default_router()

    def _build_request(self, inputs: dict[str, Any]):
        ensure_sibling_src(PACKAGE_NAME, SIBLING_DIR)
        from nu_llm_routing_lib.prompting import generation_prompt_rewrite_request  # type: ignore[import-not-found]
        from nu_llm_routing_lib.types import ChatMessage, ChatRequest  # type: ignore[import-not-found]
        from nu_llm_routing_lib.usecases import (  # type: ignore[import-not-found]
            prompt_enhancement_request,
            route_metadata,
            structured_output_metadata,
        )

        operation = inputs.get("operation", "chat")
        prompt = inputs.get("prompt") or inputs.get("user_request") or ""
        provider = inputs.get("provider")
        model = inputs.get("model")
        temperature = float(inputs.get("temperature", 0.2))
        max_tokens = inputs.get("max_tokens")
        timeout_seconds = float(inputs.get("timeout_seconds", 120.0))
        tags = self._string_list(inputs.get("tags"))

        if operation == "generation_prompt_rewrite":
            request = generation_prompt_rewrite_request(
                user_request=prompt,
                encoder_family=inputs.get("encoder_family", "t5"),
                model_profile=inputs.get("model_profile"),
                provider=provider,
                model=model,
                hardware_profile=inputs.get("hardware_profile"),
                tags=tags,
                reference_context=inputs.get("reference_context"),
                constraints=self._string_list(inputs.get("constraints")),
                temperature=temperature,
                max_tokens=int(max_tokens) if max_tokens is not None else 512,
                timeout_seconds=timeout_seconds,
            )
            return self._merge_metadata(request, inputs.get("metadata"))

        if operation == "prompt_enhancement":
            request = prompt_enhancement_request(
                user=prompt,
                encoder_family=inputs.get("encoder_family", "t5"),
                system=inputs.get("system"),
                provider=provider,
                model=model,
                hardware_profile=inputs.get("hardware_profile"),
                local_only=bool(inputs.get("local_only", False)),
                tags=tags,
                source_project=inputs.get("source_project"),
                strict_determinism=bool(inputs.get("strict_determinism", False)),
                temperature=temperature,
                max_tokens=int(max_tokens) if max_tokens is not None else None,
                timeout_seconds=timeout_seconds,
                extra=inputs.get("metadata"),
            )
            return request

        if operation == "json":
            metadata = structured_output_metadata(
                hardware_profile=inputs.get("hardware_profile"),
                tags=tags,
                json_schema=inputs.get("json_schema"),
                json_schema_name=inputs.get("json_schema_name", "structured_response"),
                strict_json_schema=bool(inputs.get("strict_json_schema", True)),
            )
            metadata.update(dict(inputs.get("metadata") or {}))
            system = inputs.get("system") or "Return one valid JSON object and no markdown fences."
        else:
            metadata = self._route_metadata(inputs, route_metadata)
            system = inputs.get("system")

        messages = self._messages(inputs.get("messages"), ChatMessage)
        if messages:
            if system and not any(message.role == "system" for message in messages):
                messages.insert(0, ChatMessage(role="system", content=system))
            return ChatRequest(
                messages=messages,
                provider=provider,
                model=model,
                temperature=temperature,
                max_tokens=max_tokens,
                timeout_seconds=timeout_seconds,
                metadata=metadata,
            )

        if not prompt:
            raise ValueError("prompt is required for chat/json/rewrite operations")

        return ChatRequest.from_turns(
            prompt,
            system=system,
            history=inputs.get("history") or (),
            provider=provider,
            model=model,
            temperature=temperature,
            max_tokens=max_tokens,
            timeout_seconds=timeout_seconds,
            metadata=metadata,
        )

    def _route_metadata(self, inputs: dict[str, Any], route_metadata) -> dict[str, Any]:
        explicit = dict(inputs.get("metadata") or {})
        workload = inputs.get("workload")
        if workload:
            return route_metadata(
                workload=workload,
                hardware_profile=inputs.get("hardware_profile"),
                content_profile=inputs.get("content_profile"),
                tags=self._string_list(inputs.get("tags")),
                extra=explicit,
            )
        metadata = explicit
        if inputs.get("hardware_profile"):
            metadata["hardware_profile"] = inputs["hardware_profile"]
        if inputs.get("content_profile"):
            metadata["content_profile"] = inputs["content_profile"]
        tags = self._string_list(inputs.get("tags"))
        if tags:
            metadata["tags"] = tags
        return metadata

    @staticmethod
    def _messages(raw: Any, message_cls) -> list[Any]:
        messages: list[Any] = []
        for item in raw or ():
            if not isinstance(item, Mapping):
                continue
            role = str(item.get("role") or "user")
            content = str(item.get("content") or "")
            if content:
                messages.append(message_cls(role=role, content=content))
        return messages

    @staticmethod
    def _string_list(raw: Any) -> list[str]:
        if raw is None:
            return []
        if isinstance(raw, str):
            return [raw]
        if isinstance(raw, Sequence):
            return [str(item) for item in raw if item]
        return []

    @staticmethod
    def _merge_metadata(request: Any, extra: Any) -> Any:
        if not extra:
            return request
        return replace(request, metadata={**dict(request.metadata), **dict(extra)})

    @staticmethod
    def _provider_status_dict(status: Any) -> dict[str, Any]:
        return {
            "name": status.name,
            "available": status.available,
            "detail": status.detail,
        }

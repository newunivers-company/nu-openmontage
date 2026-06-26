from __future__ import annotations

from lib.nu_integrations import package_status
from tools.base_tool import ToolStatus
from tools.generation.resource_generator import (
    PACKAGE_NAME as RESOURCE_PACKAGE,
    SIBLING_DIR as RESOURCE_SIBLING,
    NuResourceGenerator,
)
from tools.graphics.nu_resource_image import NuResourceImage
from tools.llm.llm_router import (
    PACKAGE_NAME as LLM_PACKAGE,
    SIBLING_DIR as LLM_SIBLING,
    NuLLMRouter,
)
from tools.audio.nu_resource_tts import NuResourceTTS
from tools.video.nu_resource_video import NuResourceVideo


def test_sibling_integrations_are_importable():
    llm_status = package_status(LLM_PACKAGE, LLM_SIBLING)
    resource_status = package_status(RESOURCE_PACKAGE, RESOURCE_SIBLING)

    assert llm_status.available, llm_status.error
    assert resource_status.available, resource_status.error


def test_llm_router_route_order_uses_profiles_without_provider_call():
    tool = NuLLMRouter()
    router_config = {
        "providers": {
            "fast_local": {"type": "ollama", "model": "local-test"},
            "json_cloud": {
                "type": "gemini",
                "model": "gemini-test",
                "api_key_env": "NU_TEST_MISSING_GEMINI_KEY",
            },
        },
        "route_order": ["fast_local", "json_cloud"],
        "route_profiles": [
            {
                "workload": "structured_output",
                "tags": ["json"],
                "route_order": ["json_cloud", "fast_local"],
            }
        ],
    }

    result = tool.execute(
        {
            "operation": "route_order",
            "prompt": "Return a JSON object with a title.",
            "workload": "structured_output",
            "tags": ["json"],
            "router_config": router_config,
        }
    )

    assert result.success, result.error
    assert result.data["route_order"] == ["json_cloud", "fast_local"]
    assert result.data["metadata"]["workload"] == "structured_output"


def test_llm_router_reports_integration_status():
    tool = NuLLMRouter()
    assert tool.get_status() == ToolStatus.AVAILABLE
    info = tool.get_info()
    assert info["integration"]["available"] is True
    assert info["capability"] == "llm_routing"


def test_resource_generator_lists_catalog_candidates():
    tool = NuResourceGenerator()
    result = tool.execute({"operation": "list_candidates", "category": "image_generation"})

    assert result.success, result.error
    ids = {candidate["candidate_id"] for candidate in result.data["candidates"]}
    assert "byteplus_seedream_4_5" in ids
    assert "gpt_image_2" in ids


def test_resource_generator_shows_candidate_cost_metadata():
    tool = NuResourceGenerator()
    result = tool.execute(
        {"operation": "show_candidate", "candidate_id": "byteplus_seedream_4_5"}
    )

    assert result.success, result.error
    candidate = result.data["candidate"]
    assert candidate["provider"] == "byteplus"
    assert candidate["category"] == "image_generation"
    assert candidate["cost_unit"] == "usd"
    assert tool.estimate_cost({"candidate_id": "byteplus_seedream_4_5"}) == 0.0


def test_resource_generator_generate_path_with_fake_provider():
    class FakeProvider:
        def has_credentials(self) -> bool:
            return True

        def generate(self, spec, request):
            from nu_resource_gen_lib import ResourceResult

            assert spec.candidate_id == "fake_image"
            assert request.prompt == "A clean product photo"
            assert request.params["size"] == "1024x1024"
            return ResourceResult(
                candidate_id=spec.candidate_id,
                provider=spec.provider,
                model=spec.model,
                output_text="done",
                asset_uri="/tmp/fake-image.png",
                status="succeeded",
                latency_ms=12.0,
                cost=0.25,
                cost_unit="usd",
            )

    class FakeResourceGeneratorTool(NuResourceGenerator):
        def _build_generator(self, inputs):
            from lib.nu_integrations import ensure_sibling_src

            ensure_sibling_src(RESOURCE_PACKAGE, RESOURCE_SIBLING)
            from nu_resource_gen_lib import CandidateSpec, ResourceGenerator

            return ResourceGenerator(
                candidates={
                    "fake_image": CandidateSpec(
                        candidate_id="fake_image",
                        provider="fake",
                        category="image_generation",
                        adapter="fake_provider",
                        model="fake-model",
                        cost=0.25,
                        cost_unit="usd",
                    )
                },
                providers={"fake": FakeProvider()},
            )

    result = FakeResourceGeneratorTool().execute(
        {
            "operation": "generate",
            "candidate_id": "fake_image",
            "prompt": "A clean product photo",
            "params": {"size": "1024x1024"},
        }
    )

    assert result.success, result.error
    assert result.artifacts == ["/tmp/fake-image.png"]
    assert result.cost_usd == 0.25
    assert result.data["result"]["asset_uri"] == "/tmp/fake-image.png"


def test_resource_selector_wrappers_expose_existing_capabilities():
    wrappers = [
        (NuResourceImage(), "image_generation", "image_generation"),
        (NuResourceVideo(), "video_generation", "video_generation"),
        (NuResourceTTS(), "tts", "voice_audio"),
    ]

    for tool, capability, category in wrappers:
        info = tool.get_info()
        assert info["provider"] == "nu_resource_gen_lib"
        assert info["capability"] == capability
        assert info["resource_category"] == category


def test_resource_image_wrapper_maps_selector_inputs_to_resource_request():
    class FakeProvider:
        def has_credentials(self) -> bool:
            return True

        def generate(self, spec, request):
            from nu_resource_gen_lib import ResourceResult

            assert spec.candidate_id == "fake_image"
            assert request.prompt == "A product on a white background"
            assert request.params["width"] == 1024
            assert request.params["aspect_ratio"] == "1:1"
            assert request.media["image_path"] == "/tmp/reference.png"
            return ResourceResult(
                candidate_id=spec.candidate_id,
                provider=spec.provider,
                model=spec.model,
                asset_uri="/tmp/wrapper-image.png",
                status="succeeded",
                cost=0.5,
                cost_unit="usd",
            )

    class FakeImageTool(NuResourceImage):
        def _build_generator(self, inputs):
            from lib.nu_integrations import ensure_sibling_src

            ensure_sibling_src(RESOURCE_PACKAGE, RESOURCE_SIBLING)
            from nu_resource_gen_lib import CandidateSpec, ResourceGenerator

            return ResourceGenerator(
                candidates={
                    "fake_image": CandidateSpec(
                        candidate_id="fake_image",
                        provider="fake",
                        category="image_generation",
                        adapter="fake_provider",
                        model="fake-image-model",
                        cost=0.5,
                        cost_unit="usd",
                    )
                },
                providers={"fake": FakeProvider()},
            )

    result = FakeImageTool().execute(
        {
            "prompt": "A product on a white background",
            "width": 1024,
            "aspect_ratio": "1:1",
            "image_path": "/tmp/reference.png",
        }
    )

    assert result.success, result.error
    assert result.artifacts == ["/tmp/wrapper-image.png"]
    assert result.cost_usd == 0.5


def test_resource_video_wrapper_routes_text_and_media_modes():
    calls: list[tuple[str, str]] = []

    class FakeProvider:
        def has_credentials(self) -> bool:
            return True

        def generate(self, spec, request):
            from nu_resource_gen_lib import ResourceResult

            calls.append((spec.candidate_id, request.prompt))
            if spec.candidate_id == "seedance1_5":
                assert request.prompt == "A tiny moving blue title card"
            if spec.candidate_id == "bytedance_video_upscale":
                assert request.prompt == ""
                assert request.media["video"] == "/tmp/input.mp4"
            return ResourceResult(
                candidate_id=spec.candidate_id,
                provider=spec.provider,
                model=spec.model,
                asset_uri=f"/tmp/{spec.candidate_id}.mp4",
                status="succeeded",
                cost=spec.cost,
                cost_unit=spec.cost_unit,
            )

    class FakeVideoTool(NuResourceVideo):
        def _build_generator(self, inputs):
            from lib.nu_integrations import ensure_sibling_src

            ensure_sibling_src(RESOURCE_PACKAGE, RESOURCE_SIBLING)
            from nu_resource_gen_lib import CandidateSpec, ResourceGenerator

            return ResourceGenerator(
                candidates={
                    "bytedance_video_upscale": CandidateSpec(
                        candidate_id="bytedance_video_upscale",
                        provider="fake",
                        category="video_generation",
                        adapter="fake_provider",
                        model="bytedance_video_upscale",
                        cost=0.16,
                        cost_unit="credits",
                    ),
                    "seedance1_5": CandidateSpec(
                        candidate_id="seedance1_5",
                        provider="fake",
                        category="video_generation",
                        adapter="fake_provider",
                        model="seedance1_5",
                        cost=4.8,
                        cost_unit="credits",
                    ),
                },
                providers={"fake": FakeProvider()},
            )

    tool = FakeVideoTool()
    text_result = tool.execute(
        {
            "operation": "text_to_video",
            "prompt": "A tiny moving blue title card",
        }
    )
    media_result = tool.execute(
        {
            "operation": "text_to_video",
            "prompt": "This prompt must not be passed to the media-only model",
            "media": {"video": "/tmp/input.mp4"},
        }
    )

    assert text_result.success, text_result.error
    assert media_result.success, media_result.error
    assert calls == [
        ("seedance1_5", "A tiny moving blue title card"),
        ("bytedance_video_upscale", ""),
    ]

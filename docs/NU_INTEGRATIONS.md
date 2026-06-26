# NewUnivers Shared Library Integrations

OpenMontage can use two sibling NewUnivers libraries when this repository is
checked out next to them:

- `../nu-llm-routing-lib`: language-model routing, route profiles, structured
  JSON metadata, and prompt rewrite helpers.
- `../nu-resource-gen-lib`: catalog-driven image, video, voice, and 3D resource
  generation candidates.

The integration prefers normal Python packages when installed. If the packages
are not installed, `lib/nu_integrations.py` falls back to `../<library>/src`.
That keeps local multi-repo development usable without forcing editable installs.

## Tools

### `nu_llm_router`

Location: `tools/llm/llm_router.py`

Operations:

- `health`: report router provider status.
- `route_order`: resolve the provider order for a request without making a
  provider call.
- `chat`: call the routed language model.
- `json`: call the routed language model with structured-output metadata.
- `generation_prompt_rewrite`: build a generation prompt rewrite request for
  CLIP, T5, or LLM encoder families.
- `prompt_enhancement`: use the shared deterministic prompt-enhancement helper.

Configuration:

- Pass `router_config` inline for tests or local experiments.
- Pass `config_path`, or set `NU_LLM_ROUTER_CONFIG`, for a JSON router config.
- With neither provided, the shared library's default router is used.

### `nu_resource_generator`

Location: `tools/generation/resource_generator.py`

Operations:

- `health`: report provider credential availability.
- `list_candidates`: list catalog candidates, optionally filtered by provider
  or category.
- `show_candidate`: return one candidate's model, adapter, cost, credential,
  endpoint, and extras metadata.
- `generate`: submit an explicit candidate request through the shared library.

Configuration:

- Pass `catalog_path` to use a custom resource catalog.
- Provider credentials are owned by the shared resource library and reported by
  `health`; missing credentials do not prevent catalog inspection.

### Selector Provider Wrappers

The common catalog tool is also exposed through selector-compatible provider
wrappers:

- `nu_resource_image` (`tools/graphics/nu_resource_image.py`) participates in
  `image_selector` as `capability="image_generation"`.
- `nu_resource_video` (`tools/video/nu_resource_video.py`) participates in
  `video_selector` as `capability="video_generation"`.
- `nu_resource_tts` (`tools/audio/nu_resource_tts.py`) participates in
  `tts_selector` as `capability="tts"`.

These wrappers select a catalog candidate from the matching category. Pass
`candidate_id` to force a specific model, or `resource_provider` to prefer a
provider inside the shared catalog. Their status is available only when the
shared library imports and at least one candidate provider for that category has
credentials.

## Test Scope

The focused tests in `tests/tools/test_nu_integrations.py` avoid live provider
calls. They verify sibling-package import fallback, route-profile selection,
catalog inspection, candidate metadata, selector-wrapper registration, and the
generate path with a fake provider.

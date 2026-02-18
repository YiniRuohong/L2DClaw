# Upstream analysis - Open-LLM-VTuber

## LLM access configuration (OpenAI-compatible endpoint)

- Config template: `_upstream_reference/config_templates/conf.default.yaml`
- The OpenAI-compatible entry is under `llm_configs.openai_compatible_llm`.
- Typical keys include:
  - `base_url` (endpoint for OpenAI-compatible API)
  - `llm_api_key`
  - `model`
  - `timeout`
- This suggests L2DClaw should mirror an OpenAI-compatible client using the same fields.

## WebSocket protocol and JSON payloads

- WebSocket handler: `_upstream_reference/src/open_llm_vtuber/websocket_handler.py`
- API routes: `_upstream_reference/src/open_llm_vtuber/routes.py`
- The server accepts message types such as:
  - `full-text` (text-only responses)
  - `set-model-and-conf` (send model config from client)
  - `control` (connection control)
- Audio payloads are assembled via `_upstream_reference/src/open_llm_vtuber/utils/stream_audio.py`.
- L2DClaw should keep the Live2D frontend protocol aligned with these types and payload shapes.

## TTS interface abstraction

- Interface: `_upstream_reference/src/open_llm_vtuber/tts/tts_interface.py`
- Providers are implemented as subclasses under `_upstream_reference/src/open_llm_vtuber/tts/`.
- A factory pattern is used to select providers.
- L2DClaw can implement its own `TTSBase` with a similar subclass structure.

## Screen sensing implementation

- Screen-related input types appear in `_upstream_reference/src/open_llm_vtuber/agent/input_types.py`.
- The upstream app includes screen capture support for VLM inputs and OCR.
- L2DClaw should implement screen sensing in adapters, with explicit opt-in for screenshot upload.

## Desktop pet mode (transparent/topmost/click-through)

- The upstream README mentions a desktop client with transparent desktop mascot mode.
- Actual Electron/Tauri configuration is not in the Python backend; the frontend repo is a built submodule.
- The built frontend assets are in `_upstream_reference/frontend/` and need inspection to locate window flags.
- L2DClaw should extract desktop pet mode settings when integrating the frontend.

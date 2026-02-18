# L2DClaw

## OpenClaw Gateway setup

L2DClaw talks to the local OpenClaw Gateway (OpenAI-compatible endpoint). Before running:

1. Enable the OpenAI endpoint in OpenClaw:
   - Set `gateway.openai.enabled = true` in your OpenClaw config.
2. Retrieve your gateway token:
   - From `openclaw dashboard`, or
   - From `~/.openclaw/openclaw.json`.

Set the token in your environment as `OPENCLAW_GATEWAY_TOKEN`.

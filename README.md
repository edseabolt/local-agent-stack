# local-agent-stack

My local agentic coding setup: open-weight LLMs served by oMLX on a Mac Studio, driven by [OpenCode](https://opencode.ai) with a multi-agent pipeline where each role gets the model that suits it. Nothing leaves the machine.

The pipeline gates themselves (plan approval, test evidence before review, reviewer round caps) are enforced by [turnstile](https://github.com/edseabolt/turnstile). This repo is the model and server side.

## Hardware

- Mac Studio, M3 Ultra, 512 GB unified memory
- One oMLX server on port 8000, reachable on the LAN, API-key protected

## Models

All four are quantized with oMLX's oQ format, and all run with MTP (multi-token prediction) speculative decoding. Decode speeds are typical single-request numbers I see on this machine with MTP on. They aren't a formal benchmark.

| Model | Quant | Context | Input | Decode speed | Notes |
|---|---|---|---|---|---|
| GLM-5.3-Flash | oQ4 | 1M | text, image | ~35–40 tok/s | Adaptive MTP depth 3. Pinned in memory. |
| Qwen3.8-Flash-Next | oQ4 | 256K | text, image | ~55–60 tok/s | |
| Ornith-1.5-35B-A3B | oQ8 | 256K | text, image, video | 100+ tok/s | MoE, about 3B active parameters. Pinned in memory. |
| Qwen3.8-27B | oQ8 | 256K | text, image, video | not measured | Dense. Defined but not assigned to a pipeline role. |

Server-side defaults for every model: temperature 1.0, top-p 0.95, top-k 20 (not set for GLM), thinking enabled with `reasoning_effort: low`. `force_sampling` is off, so the temperature OpenCode sends with each request wins.

## Agent roles

Defined in [`opencode/opencode.jsonc`](opencode/opencode.jsonc).

| Role | Model | Why |
|---|---|---|
| default, plan-reviewer, reviewer, debugger | GLM-5.3-Flash | The judging roles. It's the slowest model here, but these roles produce short verdicts, and the 1M context holds a whole plan, diff, and test log at once. |
| planner | Qwen3.8-Flash-Next | Fast drafting of plans and decompositions. |
| executor, test-runner | Ornith-1.5-35B-A3B | High-volume edit and test loops. At 100+ tok/s it's the fastest model here, and oQ8 keeps quality up. |
| title, summary | Ornith-1.5-35B-A3B | Cheap housekeeping calls. |

Each model also has three OpenCode variants: `precise` (0.1), `balanced` (0.5), and `creative` (0.9). turnstile further clamps executor, test-runner, and debugger to ≤ 0.2 and both reviewers to 0.

## oMLX tuning

From [`omlx/settings.json`](omlx/settings.json) and [`omlx/model_settings.json`](omlx/model_settings.json):

- **Memory:** aggressive memory guard with a 384 GB custom ceiling. That leaves headroom on a 512 GB machine for the OS and tooling.
- **Cache:** 128 GB hot (in-memory) prefix cache with hot-cache-only mode, plus a 37 GB SSD cache directory. `preserve_mid_system_cache` keeps the shared system prompt cached across agent turns.
- **Scheduler:** 4 concurrent requests with chunked prefill, context-priority prefill, and decode fairness, so several agents (or several Orca worktrees) can share one server without one starving the others.
- **Decode:** aggressive burst decode, with the GPU kept warm every 0.5 s.
- **Context:** the global default is 64K, overridden per model to 256K (1M for GLM). The OpenCode `limit.context` values match, so OpenCode compacts at the right point.

## Setup

1. Install oMLX and download the models into your oMLX models directory.
2. Copy `omlx/settings.json` and `omlx/model_settings.json` into `~/.omlx/`. Replace `YOUR_USER`, `your-mac.local`, and both `REPLACE_ME` values:
   ```sh
   openssl rand -hex 32   # run twice: once for api_key, once for secret_key
   ```
3. Copy `opencode/opencode.jsonc` to `~/.config/opencode/opencode.jsonc`.
4. Copy `.env.example` to `.env`, fill it in, and export it before launching OpenCode:
   ```sh
   set -a; source .env; set +a
   opencode
   ```
   OpenCode resolves `{env:OMLX_BASE_URL}`, `{env:OMLX_API_KEY}`, and `{env:HOME}` from the environment.

## Notes

- The server binds `0.0.0.0` so other machines on the LAN can use it. If you only use it locally, set `host` to `127.0.0.1`.
- The permission list auto-allows read-only shell commands (`git log`, `rg`, `jq`, and similar) and asks before edits or any other shell command.
- `model_settings.json` also keeps entries for the unsuffixed base checkpoints (for example `GLM-5.3-Flash`). Only the `-oQ4-mtp` / `-oQ8-mtp` entries are used by this setup.

## License

MIT

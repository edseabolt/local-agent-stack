---
description: Install the oMLX and OpenCode config templates from this repo into their live locations (~/.omlx, ~/.config/opencode), replacing sentinels with real values from .env. Use when the user asks to install, apply, sync, or deploy the configs, or after editing any template in omlx/ or opencode/.
---

# Skill: omlx-install

## /omlx-install

Install this repo's config templates into their live locations, substituting
the sentinels with real values. This is the **only** sanctioned way to write to
`~/.omlx/*` or `~/.config/opencode/*` from a session (carve-out to the AGENTS.md
hard rule) — and only when the user asked for an install/sync.

## What it does

1. **Build/refresh the repo-root `.env`** (gitignored, chmod 600). Value
   resolution, highest wins:
   - existing `.env`
   - values harvested from the installed `~/.omlx/settings.json`
     (`auth.api_key`, `auth.secret_key`, first non-localhost `server_aliases` entry)
   - generated: hex-32 keys via `secrets.token_hex(32)`, hostname via
     `scutil --get LocalHostName` + `.local`
   - `OMLX_BASE_URL` is always derived: `http://$OMLX_HOST:8000/v1`
2. **Render and install** (backing up each overwritten file as `<name>.bak.<ts>`):
   | Repo file | Target |
   |---|---|
   | `omlx/settings.json` | `~/.omlx/settings.json` (chmod 600 — contains keys) |
   | `omlx/model_settings.json` | `~/.omlx/model_settings.json` |
   | `opencode/opencode.jsonc` | `~/.config/opencode/opencode.jsonc` |
   | `opencode/skills/` | `~/.config/opencode/skills/` (replaced wholesale) |

## Sentinel → source mapping

| Sentinel in templates | Replaced with |
|---|---|
| `/Users/YOUR_USER/...` | `/Users/$USER/...` |
| `your-mac.local` | `$OMLX_HOST` |
| `"REPLACE_ME"` (auth.api_key) | `$OMLX_API_KEY` |
| `REPLACE_ME_WITH_openssl_rand_-hex_32` (secret_key) | `$OMLX_SECRET_KEY` |

## Execution Order

1. [ ] Run from the repo root (the script locates the repo automatically; use
      `--repo` otherwise). ALWAYS start with a dry run:
      `python3 opencode/skills/omlx-install/scripts/install.py --dry-run`
      and show the user the plan (host, keys set/generated, files + backups).
2. [ ] On approval, rerun without `--dry-run`.
3. [ ] Report: which files changed vs unchanged, backup names, and the reminder
      that oMLX needs a restart and OpenCode a reload to pick up the changes.

## Hard Rules

- **Never run this skill unsolicited.** Installing overwrites the live
  production config — require an explicit user request.
- The installed `opencode.jsonc` gets **literal** `baseURL`/`apiKey` (the
  `{env:OMLX_BASE_URL}`/`{env:OMLX_API_KEY}` placeholders are resolved at
  install time) so OpenCode connects without sourcing `.env`. The repo template
  keeps the placeholders; after any key/hostname change, re-run this skill.
- Never print the `.env` values (key material) into the conversation; show only
  "set"/"generated".
- If a sentinel remains after substitution (grep `YOUR_USER|REPLACE_ME|your-mac.local`
  in the rendered output), STOP — report instead of installing.
- The script validates JSON before writing; if validation fails, fix the repo
  template, never the target.
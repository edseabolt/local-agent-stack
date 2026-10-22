#!/usr/bin/env python3
"""Install local-agent-stack configs into their live locations.

Renders the repo templates (omlx/settings.json, omlx/model_settings.json,
opencode/opencode.jsonc) by replacing sentinels, then installs them plus the
bundled skills. Backs up every file it overwrites.

Sentinels and their sources:
  YOUR_USER                     -> $USER (paths), never committed
  your-mac.local                -> OMLX_HOST from .env
  auth.api_key REPLACE_ME       -> OMLX_API_KEY from .env
  auth.secret_key REPLACE_ME    -> OMLX_SECRET_KEY from .env

.env resolution (repo root): existing .env > values harvested from the
installed ~/.omlx/settings.json > generate (hex keys) / scutil (hostname).
The .env is written/updated and is gitignored.

Usage: install.py [--dry-run] [--repo PATH]
Run from the repo root (or pass --repo).
"""

import argparse
import datetime
import getpass
import json
import os
import re
import secrets
import shutil
import subprocess
import sys
from pathlib import Path

ENV_KEYS = ("OMLX_HOST", "OMLX_API_KEY", "OMLX_SECRET_KEY", "OMLX_BASE_URL")


def die(msg):
    sys.exit(f"install.py: {msg}")


def find_repo(explicit):
    if explicit:
        return Path(explicit).resolve()
    cwd = Path.cwd().resolve()
    for p in (cwd, *cwd.parents):
        if (p / "omlx" / "settings.json").exists() and (p / "opencode").is_dir():
            return p
    die("repo root not found; run from the repo or pass --repo")


def parse_env(path):
    vals = {}
    if path.exists():
        for line in path.read_text().splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, _, v = line.partition("=")
                v = v.strip()
                if v.startswith("REPLACE_ME"):  # unfilled .env.example copy
                    continue
                vals[k.strip()] = v
    return vals


def harvest_installed():
    """Adopt api_key/secret_key/host from the live install, if any."""
    p = Path.home() / ".omlx" / "settings.json"
    if not p.exists():
        return {}
    try:
        s = json.loads(p.read_text())
    except Exception:
        return {}
    out = {}
    if s.get("auth", {}).get("api_key") and "REPLACE" not in s["auth"]["api_key"]:
        out["OMLX_API_KEY"] = s["auth"]["api_key"]
    if s.get("auth", {}).get("secret_key") and "REPLACE" not in s["auth"]["secret_key"]:
        out["OMLX_SECRET_KEY"] = s["auth"]["secret_key"]
    aliases = s.get("server", {}).get("server_aliases") or []
    host = next(
        (a for a in aliases if a not in ("localhost", "127.0.0.1", "your-mac.local")),
        None,
    )
    if host:
        out["OMLX_HOST"] = host
    return out


def detect_host():
    try:
        out = subprocess.run(
            ["scutil", "--get", "LocalHostName"], capture_output=True, text=True, timeout=5
        )
        if out.returncode == 0 and out.stdout.strip():
            return f"{out.stdout.strip()}.local"
    except Exception:
        pass
    return None


def build_env(repo, dry_run):
    env_path = repo / ".env"
    vals = parse_env(env_path)
    vals.update({k: v for k, v in harvest_installed().items() if not vals.get(k)})
    changed = False

    if not vals.get("OMLX_HOST"):
        vals["OMLX_HOST"] = detect_host() or ""
        changed = True
        if not vals["OMLX_HOST"]:
            die("could not detect OMLX_HOST; set it in .env or pass it via the environment")
    if not vals.get("OMLX_API_KEY"):
        vals["OMLX_API_KEY"] = secrets.token_hex(32)
        changed = True
    if not vals.get("OMLX_SECRET_KEY"):
        vals["OMLX_SECRET_KEY"] = secrets.token_hex(32)
        changed = True
    # Base URL derives from host unless the user pinned a custom one (port change)
    if not vals.get("OMLX_BASE_URL") or vals["OMLX_BASE_URL"].startswith("http://REPLACE"):
        vals["OMLX_BASE_URL"] = f"http://{vals['OMLX_HOST']}:8000/v1"
        changed = True

    content = (
        "# Generated/managed by omlx-install. Do not commit — this file is gitignored.\n"
        + "".join(f"{k}={vals[k]}\n" for k in ENV_KEYS)
    )
    if not env_path.exists() or env_path.read_text() != content:
        changed = True
    if changed and not dry_run:
        env_path.write_text(content)
        os.chmod(env_path, 0o600)
        print(f".env written: {env_path}")
    return vals, changed


def render(text, env, jsonc=False):
    user = getpass.getuser()
    text = text.replace("/Users/YOUR_USER", f"/Users/{user}")
    text = text.replace("your-mac.local", env["OMLX_HOST"])
    text = text.replace("REPLACE_ME_WITH_openssl_rand_-hex_32", env["OMLX_SECRET_KEY"])
    text = re.sub(r'"REPLACE_ME[^"]*"', f'"{env["OMLX_API_KEY"]}"', text)
    if jsonc:
        # The installed client config must work without sourcing .env: resolve
        # the connection placeholders to literals (HOME is always set, keep it).
        text = text.replace("{env:OMLX_BASE_URL}", env["OMLX_BASE_URL"])
        text = text.replace("{env:OMLX_API_KEY}", env["OMLX_API_KEY"])
    return text


def backup(target, dest_dir=None):
    if not target.exists():
        return None
    name = target.name + f".bak.{datetime.datetime.now():%Y%m%d-%H%M%S}"
    b = (Path(dest_dir) if dest_dir else target.parent) / name
    if target.is_dir():
        shutil.copytree(target, b, symlinks=True)
    else:
        shutil.copy2(target, b)
    return b


def install_file(src, dst, env, dry_run):
    jsonc = dst.name.endswith(".jsonc")
    data = render(src.read_text(), env, jsonc=jsonc)
    leftover = re.findall(r"YOUR_USER|REPLACE_ME|your-mac\.local", data)
    if leftover:
        die(f"unresolved sentinels in rendered {src.name}: {sorted(set(leftover))} — check .env")
    if dst.suffix == ".json" or jsonc:
        candidate = re.sub(r"(?m)^\s*//.*$", "", data) if jsonc else data
        json.loads(candidate)  # validate before touching the target
    if dst.exists() and dst.read_text() == data:
        return f"unchanged  {dst}"
    if not dry_run:
        dst.parent.mkdir(parents=True, exist_ok=True)
        b = backup(dst)
        dst.write_text(data)
        # both omlx settings and the client config carry the API key
        os.chmod(dst, 0o600 if dst.suffix == ".json" or jsonc else 0o644)
        if b:
            return f"installed  {dst}  (backup: {b.name})"
    return f"installed  {dst}"


def install_dir(src, dst, dry_run):
    """Merge skills into the live dir — never remove skills the repo doesn't own."""
    if dry_run:
        return f"merge      {dst}/ (skills: {', '.join(p.name for p in src.iterdir())})"
    dst.mkdir(parents=True, exist_ok=True)
    # skill backups live outside the skills dir — the skill scanner reads
    # every immediate child of dst, so a *.bak dir would load as a skill
    bak_dir = dst.parent / ".skill-backups"
    merged = []
    for skill in src.iterdir():
        target = dst / skill.name
        b = backup(target, bak_dir) if target.exists() else None
        if target.exists():
            shutil.rmtree(target)
        shutil.copytree(skill, target)
        merged.append(skill.name + (f" (backup: {b.name})" if b else ""))
    return f"merge      {dst}/ -> {', '.join(merged)}"


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--repo", default=None)
    args = ap.parse_args()

    repo = find_repo(args.repo)
    env, _ = build_env(repo, args.dry_run)
    print(f"host={env['OMLX_HOST']}  api_key={'set' if env['OMLX_API_KEY'] else 'MISSING'}"
          f"  secret_key={'set' if env['OMLX_SECRET_KEY'] else 'MISSING'}\n")

    home = Path.home()
    jobs = [
        (repo / "omlx" / "settings.json", home / ".omlx" / "settings.json"),
        (repo / "omlx" / "model_settings.json", home / ".omlx" / "model_settings.json"),
        (repo / "opencode" / "opencode.jsonc", home / ".config" / "opencode" / "opencode.jsonc"),
    ]
    results = [install_file(s, d, env, args.dry_run) for s, d in jobs]
    results.append(install_dir(repo / "opencode" / "skills", home / ".config" / "opencode" / "skills", args.dry_run))
    print("\n".join(results))

    if not args.dry_run:
        print("\nDone. Restart oMLX to reload server config; reload OpenCode to pick up client config.")


if __name__ == "__main__":
    main()
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

from __future__ import annotations

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
from typing import NoReturn

ENV_KEYS: tuple[str, ...] = ("OMLX_HOST", "OMLX_API_KEY", "OMLX_SECRET_KEY", "OMLX_BASE_URL")


def die(msg: str) -> NoReturn:
    """Print the installer-prefixed message and exit.

    Args:
        msg: The problem, stated so the user can fix it.
    """
    sys.exit(f"install.py: {msg}")


def find_repo(explicit: str | None) -> Path:
    """Locate the repo root.

    Args:
        explicit: The --repo value, or None to search upward.

    Returns:
        The resolved repo root: --repo when given, else the nearest
        ancestor of the cwd containing omlx/settings.json and opencode/.
    """
    if explicit:
        return Path(explicit).resolve()
    cwd = Path.cwd().resolve()
    for p in (cwd, *cwd.parents):
        if (p / "omlx" / "settings.json").exists() and (p / "opencode").is_dir():
            return p
    die("repo root not found; run from the repo or pass --repo")


def parse_env(path: Path) -> dict[str, str]:
    """Read KEY=VALUE pairs from a .env file.

    Args:
        path: The .env path; missing files yield an empty mapping.

    Returns:
        The key/value pairs, with comments skipped and unfilled
        .env.example copies (values starting with REPLACE_ME) dropped.
    """
    vals: dict[str, str] = {}
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


def harvest_installed() -> dict[str, str]:
    """Adopt connection values from the live install, if any.

    Reads ~/.omlx/settings.json so a re-install keeps working keys and the
    real hostname instead of regenerating them.

    Returns:
        The OMLX_API_KEY / OMLX_SECRET_KEY / OMLX_HOST values found
        (sentinel-containing keys and placeholder aliases are skipped);
        empty when there is no usable installed settings file.
    """
    p = Path.home() / ".omlx" / "settings.json"
    if not p.exists():
        return {}
    try:
        s = json.loads(p.read_text())
    except Exception:
        return {}
    out: dict[str, str] = {}
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


def detect_host() -> str | None:
    """Detect the machine's local hostname via scutil.

    Returns:
        "<LocalHostName>.local", or None when scutil fails or is
        unavailable.
    """
    try:
        out = subprocess.run(
            ["scutil", "--get", "LocalHostName"], capture_output=True, text=True, timeout=5
        )
        if out.returncode == 0 and out.stdout.strip():
            return f"{out.stdout.strip()}.local"
    except Exception:
        pass
    return None


def complete_env(vals: dict[str, str]) -> tuple[dict[str, str], bool]:
    """Fill missing .env values so rendering can never see a sentinel.

    Order: values already parsed from .env survive; the rest come from the
    live install (harvest_installed), detection, or generation.

    Args:
        vals: Values parsed from the existing .env (possibly empty).

    Returns:
        (completed mapping, whether anything was added).

    Raises:
        SystemExit: When OMLX_HOST is missing and cannot be detected.
    """
    completed = dict(vals)
    completed.update({k: v for k, v in harvest_installed().items() if not completed.get(k)})
    changed = False

    if not completed.get("OMLX_HOST"):
        completed["OMLX_HOST"] = detect_host() or ""
        changed = True
        if not completed["OMLX_HOST"]:
            die("could not detect OMLX_HOST; set it in .env or pass it via the environment")
    if not completed.get("OMLX_API_KEY"):
        completed["OMLX_API_KEY"] = secrets.token_hex(32)
        changed = True
    if not completed.get("OMLX_SECRET_KEY"):
        completed["OMLX_SECRET_KEY"] = secrets.token_hex(32)
        changed = True
    # Base URL derives from host unless the user pinned a custom one (port change)
    if not completed.get("OMLX_BASE_URL") or completed["OMLX_BASE_URL"].startswith("http://REPLACE"):
        completed["OMLX_BASE_URL"] = f"http://{completed['OMLX_HOST']}:8000/v1"
        changed = True
    return completed, changed


def build_env(repo: Path, dry_run: bool) -> tuple[dict[str, str], bool]:
    """Load or create the repo's .env.

    Args:
        repo: The repo root holding .env.
        dry_run: When True, never write the file.

    Returns:
        (env values, whether the .env content changed).
    """
    env_path = repo / ".env"
    vals, changed = complete_env(parse_env(env_path))

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


def render(text: str, env: dict[str, str], jsonc: bool = False) -> str:
    """Substitute a template's sentinels with real values.

    Args:
        text: The template content.
        env: The .env values used for host and auth keys.
        jsonc: When True (the client config), also resolve the
            {env:OMLX_*} connection placeholders to literals — the
            installed config must work without sourcing .env.

    Returns:
        The rendered text: user paths, host, and the scoped auth.api_key /
        auth.secret_key substitutions applied.
    """
    user = getpass.getuser()
    text = text.replace("/Users/YOUR_USER", f"/Users/{user}")
    text = text.replace("your-mac.local", env["OMLX_HOST"])
    text = re.sub(
        r'("secret_key":\s*")REPLACE_ME[^"]*(")',
        rf"\g<1>{env['OMLX_SECRET_KEY']}\g<2>", text,
    )
    text = re.sub(
        r'("api_key":\s*")REPLACE_ME[^"]*(")',
        rf"\g<1>{env['OMLX_API_KEY']}\g<2>", text,
    )
    if jsonc:
        # The installed client config must work without sourcing .env: resolve
        # the connection placeholders to literals (HOME is always set, keep it).
        text = text.replace("{env:OMLX_BASE_URL}", env["OMLX_BASE_URL"])
        text = text.replace("{env:OMLX_API_KEY}", env["OMLX_API_KEY"])
    return text


def backup(target: Path, dest_dir: Path | None = None) -> Path | None:
    """Copy target to a timestamped backup before it is overwritten.

    Args:
        target: The file or directory about to be replaced.
        dest_dir: Backup directory; defaults to target's parent. Callers
            pass a separate dir when the target's siblings are scanned
            (e.g. skills, where a *.bak dir would load as a skill).

    Returns:
        The backup path, or None when target does not exist.
    """
    if not target.exists():
        return None
    name = target.name + f".bak.{datetime.datetime.now():%Y%m%d-%H%M%S}"
    b = (Path(dest_dir) if dest_dir else target.parent) / name
    if target.is_dir():
        shutil.copytree(target, b, symlinks=True)
    else:
        shutil.copy2(target, b)
    return b


def install_file(src: Path, dst: Path, env: dict[str, str], dry_run: bool) -> str:
    """Render one template and install it.

    The rendered text is checked for leftover sentinels and, for JSON
    targets, parsed before anything is written; the previous file is backed
    up and secret-bearing files get 0600.

    Args:
        src: The repo template path.
        dst: The live installation path.
        env: The .env values used for rendering.
        dry_run: When True, report instead of writing.

    Returns:
        A status line: "installed" (with backup name when one was made),
        "unchanged", or "would install" on dry-run.
    """
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
    return f"would install  {dst}"


def install_dir(src: Path, dst: Path, dry_run: bool) -> str:
    """Merge skills into the live skills dir.

    Existing skills are backed up and replaced; skills the repo doesn't own
    are never removed.

    Args:
        src: The repo's opencode/skills directory.
        dst: The live skills directory.
        dry_run: When True, report instead of writing.

    Returns:
        A status line naming the merged (and backed-up) skills.
    """
    if dry_run:
        return f"would merge {dst}/ (skills: {', '.join(p.name for p in src.iterdir())})"
    dst.mkdir(parents=True, exist_ok=True)
    # skill backups live outside the skills dir — the skill scanner reads
    # every immediate child of dst, so a *.bak dir would load as a skill
    bak_dir = dst.parent / ".skill-backups"
    merged: list[str] = []
    for skill in src.iterdir():
        target = dst / skill.name
        b = backup(target, bak_dir) if target.exists() else None
        if target.exists():
            shutil.rmtree(target)
        shutil.copytree(skill, target)
        merged.append(skill.name + (f" (backup: {b.name})" if b else ""))
    return f"merge      {dst}/ -> {', '.join(merged)}"


def main() -> None:
    """Orchestrate the install: locate the repo, build .env, install the
    three config files, and merge the skills."""
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
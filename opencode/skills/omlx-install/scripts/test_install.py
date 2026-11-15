#!/usr/bin/env python3
"""Self-test for install.py: scoped sentinel substitution and dry-run labels.

Run: python3 test_install.py  (prints "test_install: OK" on success)
"""

import json
from pathlib import Path

from install import ENV_KEYS, render

env = dict.fromkeys(ENV_KEYS, "")
env.update({"OMLX_HOST": "test-host.local",
            "OMLX_API_KEY": "ak-test-123",
            "OMLX_SECRET_KEY": "sk-test-456",
            "OMLX_BASE_URL": "http://test-host.local:8000/v1"})


def _find_repo():
    # Walk up until a directory containing both omlx/settings.json and
    # opencode/ is found (mirrors find_repo() in install.py).
    p = Path(__file__).resolve()
    for cand in [p] + list(p.parents):
        if (cand / "omlx" / "settings.json").is_file() and (cand / "opencode").is_dir():
            return cand
    raise SystemExit("repo root not found")


repo = _find_repo()
tpl = repo / "omlx" / "settings.json"
out = render(tpl.read_text(), env)
data = json.loads(out)

# Scoped substitution on the real template: auth.api_key / auth.secret_key
assert data["auth"]["api_key"] == "ak-test-123"
assert data["auth"]["secret_key"] == "sk-test-456"
assert "REPLACE_ME" not in out

# Poison case: an unrelated REPLACE_ME value must NOT become the api key,
# and a key merely *ending* in api_key must not match either.
poison = (
    '{"auth": {"api_key": "REPLACE_ME_with_openssl", "secret_key": "REPLACE_ME_SECRET"}, '
    '"future_field": "REPLACE_ME_unrelated", "web_search_brave_api_key": ""}'
)
pd = json.loads(render(poison, env))
assert pd["auth"]["api_key"] == "ak-test-123"
assert pd["auth"]["secret_key"] == "sk-test-456"
assert pd["future_field"] == "REPLACE_ME_unrelated"
assert pd["web_search_brave_api_key"] == ""

# Dry-run labels (source-level contract checks)
src = Path(__file__).parent.joinpath("install.py").read_text()
assert 'f"would install  {dst}"' in src
assert src.count('return f"installed  {dst}"') == 1  # only inside the write path
assert 'f"would merge {dst}/' in src

print("test_install: OK")
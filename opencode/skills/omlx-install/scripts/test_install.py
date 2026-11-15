#!/usr/bin/env python3
"""Self-test for install.py: scoped sentinel substitution and dry-run labels.

Run: python3 test_install.py  (unittest; "OK" on success)
"""

from __future__ import annotations

import json
import unittest
from pathlib import Path

from install import render

TEST_ENV: dict[str, str] = {
    "OMLX_HOST": "test-host.local",
    "OMLX_API_KEY": "ak-test-123",
    "OMLX_SECRET_KEY": "sk-test-456",
    "OMLX_BASE_URL": "http://test-host.local:8000/v1",
}

POISON = (
    '{"auth": {"api_key": "REPLACE_ME_with_openssl", "secret_key": "REPLACE_ME_SECRET"}, '
    '"future_field": "REPLACE_ME_unrelated", "web_search_brave_api_key": ""}'
)


def _find_repo() -> Path:
    """Locate the repo root for the template read.

    Walks up from this file until a directory containing both
    omlx/settings.json and opencode/ is found (mirrors find_repo() in
    install.py).

    Returns:
        The repo root path.
    """
    p = Path(__file__).resolve()
    for cand in [p, *p.parents]:
        if (cand / "omlx" / "settings.json").is_file() and (cand / "opencode").is_dir():
            return cand
    raise SystemExit("repo root not found")


class RenderSentinelTest(unittest.TestCase):
    """render() must substitute only the scoped auth sentinels."""

    def setUp(self) -> None:
        """Load the real settings template and render it once for all cases."""
        tpl = _find_repo() / "omlx" / "settings.json"
        self.out = render(tpl.read_text(), TEST_ENV)
        self.data = json.loads(self.out)

    def test_api_key_substituted_in_auth(self) -> None:
        """The auth.api_key sentinel becomes the test .env api key."""
        self.assertEqual(self.data["auth"]["api_key"], TEST_ENV["OMLX_API_KEY"])

    def test_secret_key_substituted_in_auth(self) -> None:
        """The auth.secret_key sentinel becomes the test .env secret key."""
        self.assertEqual(self.data["auth"]["secret_key"], TEST_ENV["OMLX_SECRET_KEY"])

    def test_no_sentinels_left_in_rendered_template(self) -> None:
        """The rendered real template contains no leftover REPLACE_ME."""
        self.assertNotIn("REPLACE_ME", self.out)

    def test_unrelated_replace_me_value_survives(self) -> None:
        """A REPLACE_ME value outside auth.* must not be substituted."""
        pd = json.loads(render(POISON, TEST_ENV))
        self.assertEqual(pd["future_field"], "REPLACE_ME_unrelated")

    def test_key_ending_in_api_key_not_matched(self) -> None:
        """A field merely named '*api_key' outside auth must keep its value."""
        pd = json.loads(render(POISON, TEST_ENV))
        self.assertEqual(pd["web_search_brave_api_key"], "")

    def test_poison_auth_keys_still_substituted(self) -> None:
        """auth.* sentinels inside arbitrary JSON still get the real values."""
        pd = json.loads(render(POISON, TEST_ENV))
        self.assertEqual(pd["auth"]["api_key"], TEST_ENV["OMLX_API_KEY"])
        self.assertEqual(pd["auth"]["secret_key"], TEST_ENV["OMLX_SECRET_KEY"])


class SourceLabelContractTest(unittest.TestCase):
    """The dry-run/installed output labels are a contract for callers."""

    def test_dry_run_and_install_labels_in_source(self) -> None:
        """install.py prints 'would ...' on dry-run and 'installed' only in
        the write path (exactly one return site)."""
        src = Path(__file__).parent.joinpath("install.py").read_text()
        self.assertIn('f"would install  {dst}"', src)
        self.assertEqual(src.count('return f"installed  {dst}"'), 1)
        self.assertIn('f"would merge {dst}/', src)


if __name__ == "__main__":
    unittest.main()
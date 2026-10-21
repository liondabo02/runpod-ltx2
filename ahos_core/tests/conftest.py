"""Test-wide defaults.

The browser smoke step in ``project_qa`` is enabled in production, but it must
never launch a real browser from the unit suite: it is slow and depends on an
installed browser. Tests that exercise it inject a fake and switch the env var
back on explicitly.
"""

import os

os.environ["AHOS_BROWSER_QA"] = "0"

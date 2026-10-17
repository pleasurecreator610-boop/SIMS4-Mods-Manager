"""
End-to-End Live Simulation Test Suite.
Directly inspired by scripts/simulate_user_flow.py.
Executes live end-to-end workflows against LoversLab and Patreon with Playwright.
Marked with @pytest.mark.live; skipped by default in local/CI test runs unless explicitly requested.
"""

import os
import pytest

from scripts.simulate_user_flow import SimulationRunner


@pytest.mark.live
def test_live_simulation_pipeline(tmp_path):
    """
    Executes an end-to-end simulation against real endpoints:
    1. Tests API server lifecycle.
    2. Validates Playwright Chromium engine.
    3. Runs limited 1-page LoversLab sync.
    4. Performs online consistency audit.
    5. Verifies installation and clean up.
    Requires internet connectivity and is only executed when running pytest with '-m live'.
    """
    if os.environ.get("RUN_LIVE_TESTS") != "1" and not os.environ.get("CI_LIVE"):
        pytest.skip("Test live E2E ignoré par défaut. Exécuter avec 'uv run pytest tests/e2e/test_live_simulation_e2e.py -m live -s' pour lancer la simulation réelle.")

    runner = SimulationRunner(
        api_url="http://127.0.0.1:8000",
        max_pages=1,
        max_installs=1,
        skip_install=False,
        concurrency=2,
        limit_audit=5,
        fail_on_errors=False,
    )

    exit_code = runner.run()
    assert exit_code == 0, f"La simulation live a échoué avec le code de sortie {exit_code}"

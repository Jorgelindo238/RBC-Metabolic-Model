"""Test bootstrap for the ``qa/`` suite.

Two regular packages live under the dotted name ``services``:

- ``<repo>/services``           - RoBoCop runtime, calibration triage,
  agentic supervisor (PEP 420 namespace at the root, with regular
  subpackages: ``services.robocop``, ``services.robocop.messaging``,
  ``services.robocop.agentic``, ...).
- ``<repo>/apps/api/services``  - regular package shipped with the
  FastAPI app (``__init__.py`` present, contains
  ``mm_calibration_adapter``, ``pure_ode_runtime``,
  ``teacher_flux_generic``).

Several existing tests prepend ``<repo>/apps/api`` to ``sys.path``
inside their own module body. Once that happens, ``import services``
resolves to the regular ``apps/api/services`` package and shadows the
namespace ``services`` at the repo root - so ``services.robocop`` and
its subpackages become unreachable for any later test file.

``apps/api/services/mm_calibration_adapter.py`` works around this
shadow today by manually injecting a small allow-list of robocop
submodules (``services.robocop.curve_triage``,
``services.robocop.custom_dataset_planner``,
``services.robocop.pure_ode_triage``) into ``sys.modules``. Tests that
only need those three submodules pass; tests that need
``services.robocop.messaging`` or ``services.robocop.agentic`` (the
agentic supervisor prototype) fail with
``ModuleNotFoundError: No module named 'services.robocop'``.

This conftest forces every ``services.robocop.*`` submodule the qa
suite needs into ``sys.modules`` BEFORE any test file is collected, so
the later regular-package shadow can no longer hide them.
"""

from __future__ import annotations

import importlib
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

# Pre-load and pin the ``services.robocop`` package and the submodules
# the qa suite imports directly. Once a module is in ``sys.modules``,
# Python returns it without consulting the parent package's
# ``__path__``, so a later ``apps/api/services`` shadow cannot evict
# these entries.
_PRELOAD = (
    "services.robocop",
    "services.robocop.curve_triage",
    "services.robocop.pure_ode_triage",
    "services.robocop.custom_dataset_planner",
    "services.robocop.calibration_triage_env",
    "services.robocop.messaging",
    "services.robocop.messaging.robocop_alerts",
    "services.robocop.messaging.telegram_notifier",
    "services.robocop.agentic",
    "services.robocop.agentic.tools",
    "services.robocop.agentic.prompts",
    "services.robocop.agentic.subagents",
    "services.robocop.agentic.robocop_deep_agent",
    "services.robocop.agentic.offline_runner",
    "services.robocop.agentic.compare_with_langgraph",
)

for _modname in _PRELOAD:
    try:
        importlib.import_module(_modname)
    except ImportError:  # pragma: no cover - safety net only
        # Optional dependencies (e.g. deepagents itself) are tolerated;
        # only the core robocop submodules need to be importable here.
        pass

# Drop the parent ``services`` entry so the next ``import services``
# (typically from ``test_adapter_integration.py``, after it prepends
# ``<repo>/apps/api`` to ``sys.path``) re-resolves freshly to the
# regular package at ``apps/api/services``. The pre-loaded
# ``services.robocop.*`` entries above remain in ``sys.modules`` and
# satisfy direct ``import services.robocop.X`` lookups regardless of
# what the parent ``services`` resolves to.
sys.modules.pop("services", None)

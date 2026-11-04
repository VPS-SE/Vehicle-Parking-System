"""TC-43 / NFR-TST-01, NFR-MNT-01/02: the CI gates refuse low coverage, and the allocation
and billing rules can be called directly, without a web request."""

import ast
import importlib.util
import tomllib
from datetime import timedelta
from decimal import Decimal
from pathlib import Path
from types import SimpleNamespace

import pytest

from vps.allocation.services import choose_best_slot, eligible_slot_types
from vps.gate.services import _billable_hours

ROOT = Path(__file__).resolve().parent.parent
_spec = importlib.util.spec_from_file_location("check_coverage", ROOT / "scripts/check_coverage.py")
_module = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_module)
coverage_gate = _module.main


def report(tmp_path, line, branch):
    path = tmp_path / "coverage.xml"
    path.write_text(f'<coverage line-rate="{line}" branch-rate="{branch}"></coverage>')
    return str(path)


@pytest.mark.parametrize(
    "line,branch,result",
    [
        ("0.70", "0.60", 0),  # exactly at both thresholds passes
        ("0.6999", "0.90", 1),  # step 1: line coverage below 70%
        ("0.95", "0.5999", 1),  # step 1: branch coverage below 60%
    ],
)
def test_coverage_gate_thresholds(tmp_path, line, branch, result):
    assert coverage_gate([report(tmp_path, line, branch)]) == result


def test_coverage_gate_rejects_an_unreadable_report(tmp_path):
    bad = tmp_path / "coverage.xml"
    bad.write_text("<html></html>")
    assert coverage_gate([str(bad)]) == 2
    assert coverage_gate([str(tmp_path / "missing.xml")]) == 2


def test_ci_runs_ruff_and_the_coverage_gate():
    """Step 2's lint gate and step 1's coverage gate are both wired into CI."""
    workflow = (ROOT / ".github/workflows/ci.yml").read_text()
    assert "ruff check ." in workflow
    assert "python scripts/check_coverage.py coverage.xml" in workflow
    assert (
        tomllib.loads((ROOT / "pyproject.toml").read_text())["tool"]["ruff"]["line-length"] == 100
    )


def test_allocation_rules_run_without_the_web_layer():
    car = SimpleNamespace(vehicle_type="Car", owner=SimpleNamespace(accessible_permit=False))
    slots = [
        SimpleNamespace(pk=1, code="B", slot_type="Standard", distance_rank=2),
        SimpleNamespace(pk=2, code="A", slot_type="Standard", distance_rank=2),
        SimpleNamespace(pk=3, code="H", slot_type="Accessible", distance_rank=1),
    ]
    assert eligible_slot_types(car) == {"Standard"}
    assert choose_best_slot(slots, car).code == "A"


def test_billing_rules_run_without_the_web_layer():
    assert _billable_hours(timedelta(minutes=20), minimum_one_hour=True) == Decimal("1.0")
    assert _billable_hours(timedelta(minutes=61)) == Decimal("1.5")


@pytest.mark.parametrize(
    "module", ["vps/allocation/services.py", "vps/billing/services.py", "vps/gate/services.py"]
)
def test_rule_modules_do_not_depend_on_requests(module):
    tree = ast.parse((ROOT / module).read_text())
    imported = {
        node.module for node in ast.walk(tree) if isinstance(node, ast.ImportFrom) and node.module
    }
    assert not imported & {"django.http", "django.shortcuts", "django.views", "django.urls"}
    arguments = {
        a.arg
        for node in ast.walk(tree)
        if isinstance(node, ast.FunctionDef)
        for a in node.args.args
    }
    assert "request" not in arguments

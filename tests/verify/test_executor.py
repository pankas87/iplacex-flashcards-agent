"""Test-first (CLAUDE.md): estos tests se escriben antes que verify/executor.py.

Casos de mcm/mcd/operatoria verificados contra el material real (Mate S1 EJ_1.1/R_1.1,
IPL-26) — no fabricados.
"""

from fractions import Fraction

import pytest

from flashcards_agent.verify.executor import UnsupportedOperation, execute_plan
from flashcards_agent.verify.plan import ComputePlan, ComputeStep, StepRef


def test_mcm_of_two_numbers():
    # ej. 12: mcm(4, 3) = 12
    plan = ComputePlan(steps=(ComputeStep(operation="mcm", operands=(4, 3)),))
    assert execute_plan(plan) == Fraction(12)


def test_mcm_of_three_numbers():
    # ej. 15: mcm(6, 4, 12) = 12
    plan = ComputePlan(steps=(ComputeStep(operation="mcm", operands=(6, 4, 12)),))
    assert execute_plan(plan) == Fraction(12)


def test_mcm_of_15_and_10():
    # ej. 13: mcm(15, 10) = 30
    plan = ComputePlan(steps=(ComputeStep(operation="mcm", operands=(15, 10)),))
    assert execute_plan(plan) == Fraction(30)


def test_mcd_of_three_numbers():
    # ej. 17: mcd(25, 15, 90) = 5
    plan = ComputePlan(steps=(ComputeStep(operation="mcd", operands=(25, 15, 90)),))
    assert execute_plan(plan) == Fraction(5)


def test_mcd_of_two_numbers():
    # ej. 20: mcd(12, 8) = 4
    plan = ComputePlan(steps=(ComputeStep(operation="mcd", operands=(12, 8)),))
    assert execute_plan(plan) == Fraction(4)


def test_mcd_of_45_and_60():
    # ej. 19: mcd(45, 60) = 15
    plan = ComputePlan(steps=(ComputeStep(operation="mcd", operands=(45, 60)),))
    assert execute_plan(plan) == Fraction(15)


def test_multi_step_division_chain():
    # ej. 1: 1800 / 45 / 5 = 8
    plan = ComputePlan(
        steps=(
            ComputeStep(operation="divide", operands=(1800, 45)),
            ComputeStep(operation="divide", operands=(StepRef(step=0), 5)),
        )
    )
    assert execute_plan(plan) == Fraction(8)


def test_multi_step_with_step_ref_across_branches():
    # ej. 8: (16*15*24) + (16*2*20) = 6400
    plan = ComputePlan(
        steps=(
            ComputeStep(operation="multiply", operands=(16, 15, 24)),
            ComputeStep(operation="multiply", operands=(16, 2, 20)),
            ComputeStep(operation="add", operands=(StepRef(step=0), StepRef(step=1))),
        )
    )
    assert execute_plan(plan) == Fraction(6400)


def test_subtract_requires_exactly_two_operands():
    plan = ComputePlan(steps=(ComputeStep(operation="subtract", operands=(10, 3, 1)),))
    with pytest.raises(UnsupportedOperation):
        execute_plan(plan)


def test_mcm_on_non_integer_step_ref_raises():
    plan = ComputePlan(
        steps=(
            ComputeStep(operation="divide", operands=(5, 2)),  # 2.5, no entero
            ComputeStep(operation="mcm", operands=(StepRef(step=0), 4)),
        )
    )
    with pytest.raises(UnsupportedOperation):
        execute_plan(plan)


def test_division_by_zero_raises_unsupported_operation():
    plan = ComputePlan(steps=(ComputeStep(operation="divide", operands=(10, 0)),))
    with pytest.raises(UnsupportedOperation):
        execute_plan(plan)


def test_unknown_step_ref_raises():
    plan = ComputePlan(steps=(ComputeStep(operation="add", operands=(StepRef(step=5), 1)),))
    with pytest.raises(UnsupportedOperation):
        execute_plan(plan)


def test_empty_plan_raises():
    with pytest.raises(UnsupportedOperation):
        execute_plan(ComputePlan(steps=()))


def test_result_is_exact_fraction_not_float():
    plan = ComputePlan(steps=(ComputeStep(operation="divide", operands=(1, 3)),))
    result = execute_plan(plan)
    assert result == Fraction(1, 3)
    assert isinstance(result, Fraction)

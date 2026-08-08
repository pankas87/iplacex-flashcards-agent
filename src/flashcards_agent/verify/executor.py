"""Ejecuta un ComputePlan con aritmética exacta — Python puro, sin LLM (TDD §2.3, §4.6)."""

from __future__ import annotations

import math
from fractions import Fraction

from flashcards_agent.verify.plan import ComputePlan, ComputeStep, Operand, StepRef


class UnsupportedOperation(Exception):
    """El plan usa una operación/operando que esta tool no puede resolver con confianza.

    Nunca se devuelve un resultado inventado — se declara explícitamente no verificable.
    """


def _resolve(operand: Operand, results: list[Fraction]) -> Fraction:
    if isinstance(operand, StepRef):
        if not 0 <= operand.step < len(results):
            raise UnsupportedOperation(f"StepRef fuera de rango: {operand.step}")
        return results[operand.step]
    return Fraction(operand)


def _as_int(value: Fraction, operation: str) -> int:
    if value.denominator != 1:
        raise UnsupportedOperation(f"{operation} requiere operandos enteros, se recibió {value}")
    return value.numerator


def _execute_step(step: ComputeStep, results: list[Fraction]) -> Fraction:
    resolved = [_resolve(operand, results) for operand in step.operands]

    if step.operation == "mcm":
        ints = [_as_int(value, "mcm") for value in resolved]
        return Fraction(math.lcm(*ints))
    if step.operation == "mcd":
        ints = [_as_int(value, "mcd") for value in resolved]
        return Fraction(math.gcd(*ints))
    if step.operation == "add":
        return sum(resolved, start=Fraction(0))
    if step.operation == "multiply":
        result = Fraction(1)
        for value in resolved:
            result *= value
        return result
    if step.operation == "subtract":
        if len(resolved) != 2:
            raise UnsupportedOperation("subtract requiere exactamente 2 operandos")
        return resolved[0] - resolved[1]
    if step.operation == "divide":
        if len(resolved) != 2:
            raise UnsupportedOperation("divide requiere exactamente 2 operandos")
        if resolved[1] == 0:
            raise UnsupportedOperation("división por cero")
        return resolved[0] / resolved[1]

    raise UnsupportedOperation(f"operación no soportada: {step.operation}")


def execute_plan(plan: ComputePlan) -> Fraction:
    if not plan.steps:
        raise UnsupportedOperation("el plan no tiene steps")

    results: list[Fraction] = []
    for step in plan.steps:
        results.append(_execute_step(step, results))
    return results[-1]

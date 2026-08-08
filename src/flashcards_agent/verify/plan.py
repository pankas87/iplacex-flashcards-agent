"""El lenguaje de cómputo que el LLM emite y executor.py ejecuta (TDD §2.3, §4.6)."""

from __future__ import annotations

from dataclasses import dataclass
from fractions import Fraction
from typing import Literal


@dataclass(frozen=True)
class StepRef:
    """Referencia al resultado de un ComputeStep previo dentro del mismo plan."""

    step: int


Operand = int | Fraction | StepRef


@dataclass(frozen=True)
class ComputeStep:
    operation: Literal["mcm", "mcd", "add", "subtract", "multiply", "divide"]
    operands: tuple[Operand, ...]


@dataclass(frozen=True)
class ComputePlan:
    steps: tuple[ComputeStep, ...]

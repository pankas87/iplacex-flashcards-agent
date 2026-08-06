"""Punto único de salida al usuario del CLI — no usar print() directo en el resto del paquete."""


def ok(msg: str) -> None:
    print(f"[ok] {msg}")


def err(msg: str) -> None:
    print(f"[error] {msg}")


def warn(msg: str) -> None:
    print(f"[warn] {msg}")


def info(msg: str) -> None:
    print(f"[info] {msg}")

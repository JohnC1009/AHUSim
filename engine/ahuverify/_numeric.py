"""Small numeric helpers (no NumPy needed for scalar root finding)."""

from collections.abc import Callable


def bisect(
    f: Callable[[float], float], lo: float, hi: float, tol: float, max_iter: int = 100
) -> float:
    """Root of f in [lo, hi] by bisection. f(lo) and f(hi) must differ in sign."""
    f_lo = f(lo)
    if f_lo * f(hi) > 0:
        raise ValueError(f"No sign change between {lo} and {hi}.")
    for _ in range(max_iter):
        mid = 0.5 * (lo + hi)
        f_mid = f(mid)
        if abs(hi - lo) < tol or f_mid == 0:
            return mid
        if f_lo * f_mid < 0:
            hi = mid
        else:
            lo, f_lo = mid, f_mid
    return 0.5 * (lo + hi)

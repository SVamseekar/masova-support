"""Shared invariants/clamps for ops agent proposals.

Values sourced from operational policy (originally validated against
the frozen masova-enterprise-fleet reference core/ops_contract.py).
"""

from __future__ import annotations

PRICE_INCREASE_PCT_MAX = 12
PRICE_DISCOUNT_PCT_MAX = 15
PO_QTY_MAX_MULT = 2.0
OVERLOAD_ACTIVE_ORDERS = 15
UNDERLOAD_ORDERS_30MIN = 3
CHURN_MIN_ORDERS = 2
CHURN_INACTIVE_DAYS = 14
CHURN_LOOKBACK_DAYS = 60

SHIFT_WINDOWS = {
    "morning": ("09:00", "16:00"),
    "mid": ("11:00", "19:00"),
    "midday": ("11:00", "19:00"),
    "afternoon": ("16:00", "23:00"),
    "evening": ("16:00", "23:00"),
}


def clamp_po_quantity(requested: float, reorder_qty: float) -> float:
    cap = reorder_qty * PO_QTY_MAX_MULT
    return min(requested, cap)


def clamp_price_delta(current_price: float, suggested_price: float, direction: str) -> float:
    if direction == "increase":
        cap = current_price * (1 + PRICE_INCREASE_PCT_MAX / 100)
        return min(suggested_price, round(cap, 2))
    cap = current_price * (1 - PRICE_DISCOUNT_PCT_MAX / 100)
    return max(suggested_price, round(cap, 2))


def is_valid_shift_window(start: str, end: str, window_name: str) -> bool:
    bounds = SHIFT_WINDOWS.get(window_name)
    if not bounds:
        return False
    return bounds[0] <= start and end <= bounds[1]

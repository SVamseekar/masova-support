"""ops_contract clamps and shift-window invariants."""

from masova_agent.runtime.ops_contract import (
    SHIFT_WINDOWS,
    clamp_po_quantity,
    clamp_price_delta,
    is_valid_shift_window,
)


def test_po_qty_clamped_at_2x_reorder():
    assert clamp_po_quantity(requested=500, reorder_qty=100) == 200


def test_po_qty_below_cap_passes_through():
    assert clamp_po_quantity(requested=150, reorder_qty=100) == 150


def test_price_increase_capped_at_12_pct():
    result = clamp_price_delta(current_price=10.00, suggested_price=15.00, direction="increase")
    assert result == 11.20


def test_price_discount_capped_at_15_pct():
    result = clamp_price_delta(current_price=10.00, suggested_price=5.00, direction="decrease")
    assert result == 8.50


def test_shift_window_valid():
    assert is_valid_shift_window("09:30", "15:00", "morning") is True


def test_shift_window_outside_bounds_rejected():
    assert is_valid_shift_window("04:00", "07:00", "morning") is False


def test_shift_windows_contains_expected_names():
    assert set(SHIFT_WINDOWS.keys()) >= {"morning", "midday", "evening"}

"""LLM circuit breaker with cooldown-based half-open recovery."""

import time

from masova_agent.runtime import circuit


def setup_function():
    circuit._reset_for_tests()


def test_closed_by_default():
    assert circuit.allow_llm("agent1") is True


def test_opens_after_threshold_failures():
    for _ in range(3):
        circuit.record_failure("agent1")
    assert circuit.allow_llm("agent1") is False


def test_stays_open_during_cooldown():
    for _ in range(3):
        circuit.record_failure("agent1")
    assert circuit.allow_llm("agent1") is False
    assert circuit.allow_llm("agent1") is False


def test_half_open_trial_after_cooldown_then_closes_on_success(monkeypatch):
    monkeypatch.setattr(circuit, "_COOLDOWN_SECONDS", 0.1)
    for _ in range(3):
        circuit.record_failure("agent1")
    time.sleep(0.15)
    assert circuit.allow_llm("agent1") is True
    circuit.record_success("agent1")
    assert circuit.allow_llm("agent1") is True


def test_half_open_trial_failure_reopens_cooldown(monkeypatch):
    monkeypatch.setattr(circuit, "_COOLDOWN_SECONDS", 0.1)
    for _ in range(3):
        circuit.record_failure("agent1")
    time.sleep(0.15)
    assert circuit.allow_llm("agent1") is True
    circuit.record_failure("agent1")
    assert circuit.allow_llm("agent1") is False


def test_agents_independent():
    for _ in range(3):
        circuit.record_failure("agent1")
    assert circuit.allow_llm("agent2") is True

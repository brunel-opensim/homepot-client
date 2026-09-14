"""Tests for the real device agent's proactive alert rules."""

import asyncio

from homepot.agent.real_device_agent import alerts_loop
from homepot.agent.utils.alerts import AlertEvaluator


def _titles(cycle):
    """Return the alert payload titles in an ``AlertCycle``."""
    return [payload["title"] for _, payload in cycle.new_alerts]


class TestAlertEvaluator:
    """Unit tests for the alert rule catalogue and dedup semantics."""

    @staticmethod
    def base(**overrides):
        """Return a healthy telemetry snapshot with optional overrides."""
        metrics = {
            "cpu_usage": 40,
            "memory_usage": 50,
            "disk_usage": 60,
            "network_latency_ms": 20,
        }
        metrics.update(overrides)
        return metrics

    def test_thresholds_and_severity(self):
        """Each condition maps to the expected title/severity/category once."""
        evaluator = AlertEvaluator()
        metrics = self.base(
            cpu_usage=95.2, memory_usage=91, disk_usage=88, network_latency_ms=610
        )
        assert evaluator.alert_candidates(metrics).new_alerts == []
        cycle = evaluator.alert_candidates(metrics)
        by_title = {payload["title"]: payload for _, payload in cycle.new_alerts}
        assert set(by_title) == {
            "High CPU: 95.2%",
            "High Memory Usage: 91.0%",
            "High Network Latency: 610ms",
        }
        assert by_title["High CPU: 95.2%"]["severity"] == "warning"
        assert by_title["High CPU: 95.2%"]["category"] == "hardware"
        assert by_title["High Memory Usage: 91.0%"]["category"] == "hardware"
        # >500ms latency escalates to critical; disk at 88% stays quiet.
        assert by_title["High Network Latency: 610ms"]["severity"] == "critical"
        assert by_title["High Network Latency: 610ms"]["category"] == "network"
        # Payloads match AgentAlertRequest; device_id/timestamp are added by the loop.
        for _, payload in cycle.new_alerts:
            assert set(payload) == {"title", "description", "severity", "category"}
        assert evaluator.alert_candidates(metrics).new_alerts == []

    def test_latency_warning_below_critical(self):
        """Latency past the warning threshold but under critical stays warning."""
        evaluator = AlertEvaluator()
        metrics = self.base(network_latency_ms=310)
        assert evaluator.alert_candidates(metrics).new_alerts == []
        cycle = evaluator.alert_candidates(metrics)
        assert _titles(cycle) == ["High Network Latency: 310ms"]
        assert cycle.new_alerts[0][1]["severity"] == "warning"

    def test_transient_blip_is_never_reported(self):
        """A violation that clears before the second observation stays quiet."""
        evaluator = AlertEvaluator()
        assert evaluator.alert_candidates(self.base(cpu_usage=95)).new_alerts == []
        assert evaluator.alert_candidates(self.base(cpu_usage=70)).new_alerts == []
        assert evaluator.alert_candidates(self.base(cpu_usage=40)).new_alerts == []

    def test_hysteresis_holds_active_condition_in_band(self):
        """An active alert survives in-band jitter and only resolves below clear."""
        evaluator = AlertEvaluator()
        violated = self.base(cpu_usage=95)  # warning line is 90
        in_band = self.base(cpu_usage=85)  # between clear (80) and warning (90)
        cleared = self.base(cpu_usage=70)  # below the clear line
        assert evaluator.alert_candidates(violated).new_alerts == []
        cycle = evaluator.alert_candidates(violated)
        assert _titles(cycle) == ["High CPU: 95.0%"]
        assert cycle.cleared_conditions == []

        # In-band jitter: still above the clear threshold, so nothing changes.
        for _ in range(3):
            cycle = evaluator.alert_candidates(in_band)
            assert cycle.new_alerts == []
            assert cycle.cleared_conditions == []

        # Dropping below the clear threshold resolves the condition.
        cycle = evaluator.alert_candidates(cleared)
        assert cycle.new_alerts == []
        assert cycle.cleared_conditions == ["high_cpu"]
        assert evaluator.alert_candidates(cleared).cleared_conditions == []

    def test_clear_then_recur_reports_again(self):
        """An active alert is reported once and a later recurrence reports again."""
        evaluator = AlertEvaluator()
        violated = self.base(cpu_usage=95)
        cleared = self.base(cpu_usage=70)
        assert evaluator.alert_candidates(violated).new_alerts == []
        cycle = evaluator.alert_candidates(violated)
        assert len(cycle.new_alerts) == 1
        assert evaluator.alert_candidates(violated).new_alerts == []
        assert evaluator.alert_candidates(cleared).cleared_conditions == ["high_cpu"]
        assert evaluator.alert_candidates(violated).new_alerts == []
        cycle = evaluator.alert_candidates(violated)
        assert len(cycle.new_alerts) == 1

    def test_backend_unreachable_when_latency_missing(self):
        """Missing latency surfaces a backend-unreachable alert that clears on recovery."""
        evaluator = AlertEvaluator()
        metrics = self.base()
        metrics.pop("network_latency_ms")
        assert evaluator.alert_candidates(metrics).new_alerts == []
        cycle = evaluator.alert_candidates(metrics)
        assert len(cycle.new_alerts) == 1
        assert cycle.new_alerts[0][1]["title"] == "Backend Unreachable"
        assert cycle.new_alerts[0][1]["severity"] == "warning"
        assert cycle.new_alerts[0][1]["category"] == "network"

        # Any latency measurement means the backend is reachable again.
        cycle = evaluator.alert_candidates(self.base(network_latency_ms=20))
        assert cycle.new_alerts == []
        assert cycle.cleared_conditions == ["backend_unreachable"]

    def test_custom_thresholds_override_with_merge(self):
        """Configured thresholds replace defaults while unset ones stay default."""
        evaluator = AlertEvaluator({"cpu": 45})
        # A clear threshold left at its default is clamped so it stays at or
        # below the (lower) custom trigger; otherwise warnings would never fire.
        assert evaluator.thresholds["cpu_clear"] == 45
        assert evaluator.alert_candidates(self.base(cpu_usage=50)).new_alerts == []
        cycle = evaluator.alert_candidates(self.base(cpu_usage=50))
        assert _titles(cycle) == ["High CPU: 50.0%"]

        # Unspecified thresholds keep their defaults (memory still 90).
        evaluator2 = AlertEvaluator({"cpu": 45})
        assert evaluator2.alert_candidates(self.base(cpu_usage=40)).new_alerts == []
        assert (
            evaluator2.alert_candidates(
                self.base(cpu_usage=40, memory_usage=95)
            ).new_alerts
            == []
        )
        cycle2 = evaluator2.alert_candidates(self.base(cpu_usage=40, memory_usage=95))
        assert _titles(cycle2) == ["High Memory Usage: 95.0%"]

    def test_custom_clear_threshold(self):
        """A custom clear threshold narrows or widens the hysteresis band."""
        evaluator = AlertEvaluator({"cpu": 45, "cpu_clear": 20})
        assert evaluator.alert_candidates(self.base(cpu_usage=50)).new_alerts == []
        cycle = evaluator.alert_candidates(self.base(cpu_usage=50))
        assert _titles(cycle) == ["High CPU: 50.0%"]

        # 30 is still above the custom clear line: held, not resolved.
        cycle = evaluator.alert_candidates(self.base(cpu_usage=30))
        assert cycle.new_alerts == []
        assert cycle.cleared_conditions == []

        # Below the custom clear line (20) resolves.
        cycle = evaluator.alert_candidates(self.base(cpu_usage=10))
        assert cycle.cleared_conditions == ["high_cpu"]


class TestAlertsLoop:
    """Integration behaviour of ``alerts_loop`` against the shared agent_state."""

    async def test_posts_edge_triggered_and_autoresolves_on_clear(self, monkeypatch):
        """A persisting condition posts once; dropping below clear resolves it."""
        from homepot.agent import real_device_agent as reader

        calls: list = []
        next_id = {"value": 0}

        async def fake_post_parsed(
            client,
            url,
            payload,
            headers,
            submission_log=None,
            timeout=10.0,
            method="POST",
        ):
            calls.append((method.upper(), url, dict(payload)))
            next_id["value"] += 1
            return {"id": next_id["value"]}

        async def fake_post(
            client,
            url,
            payload,
            headers,
            *,
            submission_log=None,
            timeout=10.0,
            method="POST",
        ):
            calls.append((method.upper(), url, dict(payload)))
            return True

        monkeypatch.setattr(reader, "post_json_parsed", fake_post_parsed)
        monkeypatch.setattr(reader, "post_json", fake_post)
        config = {
            "backend_url": "http://localhost:8000",
            "device_id": "dev-1",
            "api_key": "secret",
            "alerts_enabled": True,
            "alerts_interval_seconds": 0.02,
            "alert_thresholds": {"memory": 5, "memory_clear": 2},
        }
        state = {
            "metrics": {
                "cpu_usage": 20,
                "memory_usage": 6,
                "disk_usage": 10,
                "network_latency_ms": 5,
            }
        }
        task = asyncio.ensure_future(alerts_loop(None, config, state, None))
        await asyncio.sleep(0.07)

        posts = [c for c in calls if c[0] == "POST"]
        assert len(posts) == 1
        assert posts[0][1].endswith("/api/v1/agent/alert")
        assert posts[0][2]["title"] == "High Memory Usage: 6.0%"
        assert posts[0][2]["device_id"] == "dev-1"
        assert isinstance(posts[0][2]["timestamp"], str)

        # Condition recovers below the clear threshold -> auto-resolve.
        state["metrics"]["memory_usage"] = 1
        await asyncio.sleep(0.05)
        task.cancel()
        await asyncio.gather(task, return_exceptions=True)

        resolves = [c for c in calls if c[0] == "PUT"]
        assert len(resolves) == 1
        assert resolves[0][1].endswith("/api/v1/agent/alerts/1/resolve")

    async def test_disabled_loop_does_not_post(self, monkeypatch):
        """alerts_enabled=false short-circuits the loop before posting anything."""
        from homepot.agent import real_device_agent as reader

        calls: list = []

        async def fake_post_parsed(*args, **kwargs):
            calls.append(args)
            return {"id": 1}

        async def fake_post(*args, **kwargs):
            calls.append(args)
            return True

        monkeypatch.setattr(reader, "post_json_parsed", fake_post_parsed)
        monkeypatch.setattr(reader, "post_json", fake_post)
        config = {
            "backend_url": "http://localhost:8000",
            "device_id": "dev-1",
            "api_key": "secret",
            "alerts_enabled": False,
            "alert_thresholds": {"cpu": 1},
        }
        task = asyncio.ensure_future(
            alerts_loop(None, config, {"metrics": {"cpu_usage": 99}}, None)
        )
        await asyncio.sleep(0.03)
        task.cancel()
        await asyncio.gather(task, return_exceptions=True)
        assert calls == []

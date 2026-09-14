"""Tests for the real device agent's proactive alert rules."""

import asyncio

from homepot.agent.real_device_agent import alerts_loop
from homepot.agent.utils.alerts import AlertEvaluator


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
        assert evaluator.alert_candidates(metrics) == []
        out = evaluator.alert_candidates(metrics)
        by_title = {p["title"]: p for p in out}
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
        for payload in out:
            assert set(payload) == {"title", "description", "severity", "category"}
        assert evaluator.alert_candidates(metrics) == []

    def test_latency_warning_below_critical(self):
        """Latency past the warning threshold but under critical stays warning."""
        evaluator = AlertEvaluator()
        metrics = self.base(network_latency_ms=310)
        assert evaluator.alert_candidates(metrics) == []
        out = evaluator.alert_candidates(metrics)
        assert len(out) == 1
        assert out[0]["title"] == "High Network Latency: 310ms"
        assert out[0]["severity"] == "warning"

    def test_transient_blip_is_never_reported(self):
        """A violation that clears before the second observation stays quiet."""
        evaluator = AlertEvaluator()
        assert evaluator.alert_candidates(self.base(cpu_usage=95)) == []
        assert evaluator.alert_candidates(self.base(cpu_usage=30)) == []
        assert evaluator.alert_candidates(self.base(cpu_usage=40)) == []
        assert evaluator.alert_candidates(self.base(cpu_usage=41)) == []

    def test_clear_then_recur_reports_again(self):
        """An active alert is reported once and a later recurrence reports again."""
        evaluator = AlertEvaluator()
        violated = self.base(cpu_usage=95)
        healthy = self.base(cpu_usage=30)
        assert evaluator.alert_candidates(violated) == []
        assert len(evaluator.alert_candidates(violated)) == 1
        assert evaluator.alert_candidates(violated) == []
        assert evaluator.alert_candidates(healthy) == []
        assert evaluator.alert_candidates(healthy) == []
        assert evaluator.alert_candidates(violated) == []
        assert len(evaluator.alert_candidates(violated)) == 1

    def test_backend_unreachable_when_latency_missing(self):
        """Missing latency from a snapshot surfaces a backend-unreachable alert."""
        evaluator = AlertEvaluator()
        metrics = {"cpu_usage": 20, "memory_usage": 30, "disk_usage": 40}
        assert evaluator.alert_candidates(metrics) == []
        out = evaluator.alert_candidates(metrics)
        assert len(out) == 1
        assert out[0]["title"] == "Backend Unreachable"
        assert out[0]["severity"] == "warning"
        assert out[0]["category"] == "network"

    def test_custom_thresholds_override_with_merge(self):
        """Configured thresholds replace defaults while unset ones stay default."""
        evaluator = AlertEvaluator({"cpu": 45})
        assert evaluator.alert_candidates(self.base(cpu_usage=50)) == []
        out = evaluator.alert_candidates(self.base(cpu_usage=50))
        assert [p["title"] for p in out] == ["High CPU: 50.0%"]
        assert evaluator.alert_candidates(self.base(cpu_usage=40)) == []

        # Unspecified thresholds keep their defaults (memory still 90).
        evaluator2 = AlertEvaluator({"cpu": 45})
        assert evaluator2.alert_candidates(self.base(cpu_usage=40)) == []
        assert (
            evaluator2.alert_candidates(self.base(cpu_usage=40, memory_usage=95)) == []
        )
        out2 = evaluator2.alert_candidates(self.base(cpu_usage=40, memory_usage=95))
        assert [p["title"] for p in out2] == ["High Memory Usage: 95.0%"]

    def test_job_failure_reports_once_per_job(self):
        """A failed maintenance job raises one alert keyed by its job id."""
        evaluator = AlertEvaluator()
        metrics = self.base()
        failed = {"job_id": "job-1", "status": "failed", "action": "Firmware Check"}
        out = evaluator.alert_candidates(metrics, last_job=failed)
        assert len(out) == 1
        assert out[0]["title"] == "Background Job Failed"
        assert out[0]["category"] == "software"
        assert "Firmware Check" in out[0]["description"]
        assert evaluator.alert_candidates(metrics, last_job=failed) == []
        out2 = evaluator.alert_candidates(
            metrics,
            last_job={"job_id": "job-2", "status": "failed", "action": "Security Scan"},
        )
        assert len(out2) == 1
        assert "Security Scan" in out2[0]["description"]


class TestAlertsLoop:
    """Integration behaviour of ``alerts_loop`` against the shared agent_state."""

    async def test_posts_edge_triggered_once(self, monkeypatch):
        """A persisting condition posts exactly one payload with identity fields."""
        from homepot.agent import real_device_agent as reader

        posted: list = []

        async def fake_post(
            client,
            url,
            payload,
            headers,
            submission_log=None,
            timeout=10.0,
            method="POST",
        ):
            posted.append(payload)
            return True

        monkeypatch.setattr(reader, "post_json", fake_post)
        config = {
            "backend_url": "http://localhost:8000",
            "device_id": "dev-1",
            "api_key": "secret",
            "alerts_enabled": True,
            "alerts_interval_seconds": 0.02,
            "alert_thresholds": {"memory": 5},
        }
        state = {
            "metrics": {
                "cpu_usage": 20,
                "memory_usage": 6,
                "disk_usage": 10,
                "network_latency_ms": 5,
            },
            "last_job": None,
        }
        task = asyncio.ensure_future(alerts_loop(None, config, state, None))
        await asyncio.sleep(0.07)
        task.cancel()
        await asyncio.gather(task, return_exceptions=True)
        assert len(posted) == 1
        assert posted[0]["title"] == "High Memory Usage: 6.0%"
        assert posted[0]["device_id"] == "dev-1"
        assert isinstance(posted[0]["timestamp"], str)

    async def test_disabled_loop_does_not_post(self, monkeypatch):
        """alerts_enabled=false short-circuits the loop before posting anything."""
        from homepot.agent import real_device_agent as reader

        posted: list = []

        async def fake_post(*args, **kwargs):
            posted.append(args)
            return True

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
        assert posted == []

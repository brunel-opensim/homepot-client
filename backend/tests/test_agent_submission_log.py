"""Tests for the agent submission-attempt log and submission recording."""

import asyncio
import json

import httpx

from homepot.agent.real_device_agent import post_json
from homepot.agent.utils.submission_log import SubmissionLog


class TestSubmissionLog:
    """Tests for the append-only JSONL submission log."""

    def test_append_and_read_round_trip(self, tmp_path):
        """Appended records are readable with all fields intact."""
        log = SubmissionLog(log_path=tmp_path / "subs.jsonl")
        log.append(
            endpoint="https://x/api/v1/agent/telemetry",
            status_code=201,
            payload_timestamp="2026-01-01T00:00:00+00:00",
        )

        records = log.read_all()
        assert len(records) == 1
        record = records[0]
        assert record["endpoint"].endswith("/api/v1/agent/telemetry")
        assert record["status_code"] == 201
        assert record["accepted"] is True
        assert record["payload_timestamp"] == "2026-01-01T00:00:00+00:00"
        assert record["retry_count"] == 0
        assert "timestamp" in record

    def test_accepted_derived_from_status_code(self, tmp_path):
        """Acceptance is derived from the HTTP status when not supplied."""
        log = SubmissionLog(log_path=tmp_path / "subs.jsonl")
        log.append(endpoint="https://x/telemetry", status_code=500)
        log.append(endpoint="https://x/telemetry", status_code=None)

        records = log.read_all()
        assert records[0]["accepted"] is False
        assert records[1]["accepted"] is False

    def test_explicit_accepted_wins(self, tmp_path):
        """An explicitly supplied acceptance is kept as-is."""
        log = SubmissionLog(log_path=tmp_path / "subs.jsonl")
        log.append(endpoint="https://x/telemetry", status_code=None, accepted=True)

        records = log.read_all()
        assert records[0]["accepted"] is True

    def test_read_all_empty_when_missing(self, tmp_path):
        """A missing log file yields no records."""
        log = SubmissionLog(log_path=tmp_path / "missing.jsonl")
        assert log.read_all() == []

    def test_clear_removes_records(self, tmp_path):
        """Clearing removes all recorded attempts."""
        log = SubmissionLog(log_path=tmp_path / "subs.jsonl")
        log.append(endpoint="https://x/telemetry", status_code=201)
        log.clear()
        assert log.read_all() == []

    def test_records_are_json_lines(self, tmp_path):
        """Each appended record is a single JSON line."""
        log = SubmissionLog(log_path=tmp_path / "subs.jsonl")
        log.append(endpoint="https://x/telemetry", status_code=201)
        log.append(endpoint="https://x/telemetry", status_code=500)

        lines = log.path.read_text(encoding="utf-8").splitlines()
        assert len(lines) == 2
        for line in lines:
            parsed = json.loads(line)
            assert "endpoint" in parsed


class TestPostJsonSubmissionLog:
    """Tests that ``post_json`` records attempts in the submission log."""

    def test_success_records_accepted(self, tmp_path):
        """A 2xx response records an accepted submission."""

        def _handler(request):
            return httpx.Response(201, json={})

        async def _run():
            log = SubmissionLog(log_path=tmp_path / "subs.jsonl")
            transport = httpx.MockTransport(_handler)
            async with httpx.AsyncClient(transport=transport) as client:
                ok = await post_json(
                    client,
                    "https://x/api/v1/agent/telemetry",
                    {"device_id": "dev-1", "timestamp": "2026-01-01T00:00:00+00:00"},
                    {"X-Device-ID": "dev-1"},
                    submission_log=log,
                )
            records = log.read_all()
            return ok, records

        ok, records = asyncio.run(_run())
        assert ok is True
        assert len(records) == 1
        assert records[0]["accepted"] is True
        assert records[0]["status_code"] == 201
        assert records[0]["payload_timestamp"] == "2026-01-01T00:00:00+00:00"

    def test_failure_records_rejected(self, tmp_path):
        """A failed request records a rejected submission."""
        import httpx as _httpx

        def _handler(request):
            raise _httpx.ConnectError("connection refused")

        async def _run():
            log = SubmissionLog(log_path=tmp_path / "subs.jsonl")
            transport = httpx.MockTransport(_handler)
            async with httpx.AsyncClient(transport=transport) as client:
                ok = await post_json(
                    client,
                    "https://x/api/v1/agent/telemetry",
                    {"device_id": "dev-1"},
                    {"X-Device-ID": "dev-1"},
                    submission_log=log,
                )
            records = log.read_all()
            return ok, records

        ok, records = asyncio.run(_run())
        assert ok is False
        assert len(records) == 1
        assert records[0]["accepted"] is False
        assert records[0]["status_code"] is None

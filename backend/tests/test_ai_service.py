"""Tests for AI Service components (Anomaly Detection & API).

These tests use MOCKING to avoid needing a real LLM or Vector DB running.
"""

import builtins
import importlib
import os
import sys
from unittest.mock import MagicMock, patch

import pytest

# Add the workspace root to sys.path so we can import 'ai' as a package
current_dir = os.path.dirname(os.path.abspath(__file__))
workspace_root = os.path.abspath(os.path.join(current_dir, "../../"))
if workspace_root not in sys.path:
    sys.path.insert(0, workspace_root)

# Now we can import from the ai package
from ai.anomaly_detection import AnomalyDetector  # noqa: E402

# ==========================================
# 1. Test Anomaly Detector (Pure Logic)
# ==========================================


def test_anomaly_detector_initialization():
    """Test that detector loads defaults if config is missing."""
    detector = AnomalyDetector(config_path="non_existent.yaml")
    assert detector.sensitivity == 0.8
    assert detector.thresholds["cpu_percent"] == 90.0


def test_anomaly_detector_normal_metrics():
    """Test that normal metrics return 0.0 score."""
    detector = AnomalyDetector()
    normal_metrics = {
        "cpu_percent": 50.0,
        "memory_percent": 60.0,
        "disk_percent": 40.0,
        "error_rate": 0.0,
        "network_latency_ms": 50.0,
    }
    score = detector.check_anomaly(normal_metrics)
    assert score == 0.0


def test_anomaly_detector_high_cpu():
    """Test that high CPU triggers an anomaly score."""
    detector = AnomalyDetector()
    metrics = {"cpu_percent": 95.0, "memory_percent": 50.0}  # Above 90.0 threshold
    score = detector.check_anomaly(metrics)
    assert score > 0.0
    assert score == 0.4  # Based on the logic we wrote (0.4 for CPU)


def test_anomaly_detector_multiple_issues():
    """Test that multiple issues accumulate score (capped at 1.0)."""
    detector = AnomalyDetector()
    metrics = {
        "cpu_percent": 99.0,  # +0.4
        "error_rate": 0.5,  # +0.5
        "network_latency_ms": 2000,  # +0.2
    }
    # Sum is 1.1, but should be capped at 1.0
    score = detector.check_anomaly(metrics)
    assert score == 1.0


# ==========================================
# 2. Test AI API (With Mocks)
# ==========================================


@pytest.mark.asyncio
async def test_analyze_endpoint_logic():
    """Test the /analyze endpoint logic without running real AI."""
    # Mock config loading to avoid FileNotFoundError
    mock_config = {
        "app": {
            "name": "Test App",
            "version": "1.0.0",
            "host": "localhost",
            "port": 8000,
        },
        "llm": {"model": "test-model"},
        "memory": {"chroma_path": "test-db", "collection_name": "test-col"},
    }

    # Capture original open
    original_open = builtins.open

    def open_side_effect(file, *args, **kwargs):
        if file == "config.yaml":
            # Return a file-like mock for config.yaml
            m = MagicMock()
            # Ensure it works as a context manager
            m.__enter__.return_value = m
            m.__exit__.return_value = None
            # Ensure read returns a string (empty is fine as we mock yaml.safe_load)
            m.read.return_value = ""
            return m
        return original_open(file, *args, **kwargs)

    # We must patch the dependencies BEFORE importing api, because api.py
    # instantiates classes at module level.
    with (
        patch("builtins.open", side_effect=open_side_effect),
        patch("yaml.safe_load", return_value=mock_config),
        patch("ai.device_memory.DeviceMemory"),
        patch("ai.llm.LLMService") as MockLLM,
        patch("ai.anomaly_detection.AnomalyDetector") as MockDetector,
    ):

        # Import api inside the patch context
        from ai import api

        # Force reload to ensure module-level code runs with patched dependencies
        importlib.reload(api)

        # Setup Mocks
        mock_llm_instance = MockLLM.return_value
        mock_llm_instance.generate_response.return_value = (
            "Mocked AI Analysis: CPU is high."
        )

        mock_detector_instance = MockDetector.return_value
        mock_detector_instance.check_anomaly.return_value = 0.8

        # Create a request object
        from ai.api import AnalysisRequest

        request = AnalysisRequest(
            device_id="device-123",
            metrics={
                "cpu_percent": 95.0,
                "memory_percent": 60.0,
                "disk_percent": 40.0,
                "error_rate": 0.0,
                "network_latency_ms": 50.0,
            },
            context="User reported slowness.",
        )

        # Call the endpoint function directly
        response = await api.analyze_device(request)

        # Assertions
        assert response["status"] == "anomaly_detected"
        assert response["anomaly_score"] == 0.8
        assert "Mocked AI Analysis" in response["analysis"]

        # Verify interactions
        mock_detector_instance.check_anomaly.assert_called_once()
        mock_llm_instance.generate_response.assert_called_once()
        # Memory should be added
        api.memory_service.add_memory.assert_called_once()

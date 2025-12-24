"""Tests for AI Service components (Anomaly Detection & API).

These tests use MOCKING to avoid needing a real LLM or Vector DB running.
"""

import sys
import os
from unittest.mock import MagicMock, patch
import pytest

# Add the 'ai' directory to sys.path so we can import from it
# (Assuming tests are run from the workspace root or backend/ directory)
current_dir = os.path.dirname(os.path.abspath(__file__))
workspace_root = os.path.abspath(os.path.join(current_dir, "../../"))
ai_dir = os.path.join(workspace_root, "ai")
if ai_dir not in sys.path:
    sys.path.insert(0, ai_dir)

# Now we can import from the ai/ directory
from anomaly_detection import AnomalyDetector

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
        "network_latency_ms": 50.0
    }
    score = detector.check_anomaly(normal_metrics)
    assert score == 0.0

def test_anomaly_detector_high_cpu():
    """Test that high CPU triggers an anomaly score."""
    detector = AnomalyDetector()
    metrics = {
        "cpu_percent": 95.0,  # Above 90.0 threshold
        "memory_percent": 50.0
    }
    score = detector.check_anomaly(metrics)
    assert score > 0.0
    assert score == 0.4  # Based on the logic we wrote (0.4 for CPU)

def test_anomaly_detector_multiple_issues():
    """Test that multiple issues accumulate score (capped at 1.0)."""
    detector = AnomalyDetector()
    metrics = {
        "cpu_percent": 99.0,      # +0.4
        "error_rate": 0.5,        # +0.5
        "network_latency_ms": 2000 # +0.2
    }
    # Sum is 1.1, but should be capped at 1.0
    score = detector.check_anomaly(metrics)
    assert score == 1.0

# ==========================================
# 2. Test AI API (With Mocks)
# ==========================================

@patch("api.LLMService")
@patch("api.DeviceMemory")
@patch("api.AnomalyDetector")
def test_analyze_endpoint_logic(MockDetector, MockMemory, MockLLM):
    """Test the /analyze endpoint logic without running real AI."""
    
    # Setup Mocks
    mock_llm_instance = MockLLM.return_value
    mock_llm_instance.generate_response.return_value = "Mocked AI Analysis: CPU is high."
    
    mock_detector_instance = MockDetector.return_value
    mock_detector_instance.check_anomaly.return_value = 0.8
    
    # Mock config loading to avoid FileNotFoundError
    mock_config = {
        "app": {"name": "Test App", "version": "1.0.0", "host": "localhost", "port": 8000},
        "llm": {"model": "test-model"},
        "memory": {"chroma_path": "test-db", "collection_name": "test-col"}
    }
    
    with patch("builtins.open", new_callable=MagicMock) as mock_open, \
         patch("yaml.safe_load", return_value=mock_config):
        
        # Import app INSIDE the patch context so it uses the mocked config
        # We need to reload it if it was already imported, but for this test run it's likely first import
        import api
        from api import analyze_device, AnalysisRequest
    
    # Create a request
    request = AnalysisRequest(
        device_id="device-123",
        metrics={"cpu_percent": 95.0}
    )
    
    # We need to patch the global instances in api.py since they are created at import time
    with patch("api.anomaly_detector", mock_detector_instance), \
         patch("api.llm_service", mock_llm_instance):
        
        # Run the function (async)
        import asyncio
        result = asyncio.run(analyze_device(request))
        
        # Verify Results
        assert result["device_id"] == "device-123"
        assert result["anomaly_score"] == 0.8
        assert result["is_anomaly"] is True
        assert result["analysis"] == "Mocked AI Analysis: CPU is high."
        
        # Verify Interactions
        mock_detector_instance.check_anomaly.assert_called_once_with({"cpu_percent": 95.0})
        mock_llm_instance.generate_response.assert_called_once()
        
        # Verify the prompt contained the score (checking args passed to LLM)
        call_args = mock_llm_instance.generate_response.call_args
        prompt_sent = call_args[0][0]
        assert "Automated Anomaly Score: 0.8" in prompt_sent

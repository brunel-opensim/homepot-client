"""Tests for the SmartDataFilter utility."""

import time

from homepot.app.utils.smart_filter import SmartDataFilter


def test_smart_filter_initial_store():
    """Test that the first data point for a device is always stored."""
    data_filter = SmartDataFilter()
    metrics = {"cpu_percent": 10.0}
    assert data_filter.should_store("device-1", metrics) is True


def test_smart_filter_no_change():
    """Test that identical metrics are filtered out if sent immediately."""
    data_filter = SmartDataFilter()
    metrics = {"cpu_percent": 10.0}
    data_filter.should_store("device-1", metrics)

    # Same metrics immediately after
    assert data_filter.should_store("device-1", metrics) is False


def test_smart_filter_significant_change():
    """Test that significant changes trigger storage."""
    data_filter = SmartDataFilter(change_threshold=0.1)  # 10% threshold
    metrics1 = {"cpu_percent": 10.0}
    data_filter.should_store("device-1", metrics1)

    # Small change (5%) -> Should not store
    metrics2 = {"cpu_percent": 10.5}
    assert data_filter.should_store("device-1", metrics2) is False

    # Large change (15% from original 10.0 is 11.5)
    # Note: The filter compares against the LAST STORED state.
    # Since metrics2 was NOT stored, we compare metrics3 against metrics1.
    metrics3 = {"cpu_percent": 11.5}
    assert data_filter.should_store("device-1", metrics3) is True


def test_smart_filter_snapshot_interval():
    """Test that data is stored after the snapshot interval expires."""
    data_filter = SmartDataFilter(snapshot_interval=1)  # 1 second
    metrics = {"cpu_percent": 10.0}
    data_filter.should_store("device-1", metrics)

    # Immediately -> False
    assert data_filter.should_store("device-1", metrics) is False

    # Wait > 1s
    time.sleep(1.1)
    assert data_filter.should_store("device-1", metrics) is True


def test_smart_filter_error_rate():
    """Test that error rate changes are handled correctly."""
    data_filter = SmartDataFilter()
    metrics1 = {"error_rate": 0.0}
    data_filter.should_store("device-1", metrics1)

    # Small absolute change in error rate (0.02) should be significant
    # The code uses > 0.01 absolute change for error_rate
    metrics2 = {"error_rate": 0.02}
    assert data_filter.should_store("device-1", metrics2) is True


def test_smart_filter_error_deduplication():
    """Test that identical errors are deduplicated."""
    data_filter = SmartDataFilter(snapshot_interval=1)  # 1 second timeout
    device_id = "device-1"
    code = "ERR_001"
    msg = "Connection failed"

    # First time -> Store
    assert data_filter.should_store_error(device_id, code, msg) is True

    # Immediately again -> Filter
    assert data_filter.should_store_error(device_id, code, msg) is False

    # Different error -> Store
    assert data_filter.should_store_error(device_id, "ERR_002", msg) is True

    # Wait > 1s -> Store again
    time.sleep(1.1)
    assert data_filter.should_store_error(device_id, code, msg) is True

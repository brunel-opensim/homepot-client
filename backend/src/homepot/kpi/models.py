"""Data models for the UK demonstrator KPI calculations and export."""

from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, ConfigDict, Field

PROVENANCE_CLASSES = ["real", "controlled", "simulated"]


class ExportFilters(BaseModel):
    """Filters that bound a KPI calculation window and population."""

    start: datetime = Field(description="Window start (inclusive), UTC")
    end: datetime = Field(description="Window end (inclusive), UTC")
    site_id: Optional[str] = Field(
        default=None, description="Restrict to devices at this site"
    )
    device_id: Optional[str] = Field(
        default=None, description="Restrict to this device"
    )
    device_type: Optional[str] = Field(
        default=None, description="Restrict to this device type"
    )
    provenance: Optional[str] = Field(
        default=None,
        description="Restrict to one provenance class: real, controlled, simulated",
    )

    model_config = ConfigDict(extra="forbid")


class KPIResult(BaseModel):
    """One computed KPI value with its evidence counts."""

    kpi_id: str = Field(description="KPI register ID, e.g. MW-02")
    name: str = Field(description="Human-readable KPI name")
    formula: str = Field(description="Plain-text calculation description")
    unit: str = Field(description="Reported unit, e.g. %, seconds, ms")
    value: Optional[float] = Field(
        default=None, description="Computed value, null when the denominator is 0"
    )
    numerator: int = Field(default=0, description="Numerator count")
    denominator: int = Field(default=0, description="Denominator count")
    exclusions: int = Field(default=0, description="Excluded rows")
    sample_count: int = Field(default=0, description="Rows used for the value")
    provenance: str = Field(
        default="all", description="Provenance scope: all, real, controlled, simulated"
    )
    group: Optional[Dict[str, Any]] = Field(
        default=None, description="Grouping keys, e.g. {'command_type': 'ping'}"
    )


class RawTable(BaseModel):
    """Raw evidence rows backing the KPI calculations."""

    table: str
    columns: List[str]
    rows: List[List[Any]]


class KPIExportBundle(BaseModel):
    """Versioned, filtered KPI calculation result with raw evidence."""

    manifest: Dict[str, Any] = Field(description="Calculation metadata")
    kpis: List[KPIResult] = Field(description="Machine-readable KPI summary")
    raw: List[RawTable] = Field(description="Raw evidence rows in window")

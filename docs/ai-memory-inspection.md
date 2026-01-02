# AI Memory Inspection Guide

This guide explains how to inspect and debug the AI's Long-Term Memory (ChromaDB) using the provided utility scripts.

## Overview

The AI uses **ChromaDB** as a vector store to remember past device anomalies, analysis results, and resolutions. Unlike PostgreSQL, which stores structured data (tables), ChromaDB stores **semantic embeddings** (vectors) that allow the AI to find "similar" events based on meaning.

To help developers visualize what the AI "remembers," we provide a command-line tool: `scripts/query-chroma.sh`.

## The Inspection Tool

The tool is located at `scripts/query-chroma.sh`. It wraps a Python script (`ai/inspect_chroma.py`) that connects to the local ChromaDB instance.

### Prerequisites

*   The AI service must have run at least once to initialize the database.
*   You must be in the project root directory.
*   Python 3 must be installed.

### Usage

```bash
./scripts/query-chroma.sh [command] [options]
```

### Available Commands

#### 1. Count Memories
Check how many "memories" (log entries) are stored in the database.

```bash
./scripts/query-chroma.sh count
```
**Output:**
```text
Collection: device_logs
Total items: 15
```

#### 2. Peek at Recent Memories
View the most recent entries added to the memory. This is useful to verify that a recent analysis was successfully saved.

```bash
./scripts/query-chroma.sh peek -n 3
```
*   `-n`: Number of items to view (default: 5).

**Output:**
```text
[1] ID: 1d28fa11-fadf-41a3-9200-c78b316f90c8
    Metadata: {'device_id': 'pos-01', 'is_anomaly': True, 'anomaly_score': 0.85}
    Document: Analysis for pos-01: High CPU usage detected...
```

#### 3. Semantic Search (Query)
This is the most powerful feature. It allows you to search the memory using natural language, exactly like the AI does. You can see what the AI would "recall" for a given topic.

```bash
./scripts/query-chroma.sh query "camera failure"
```

**Output:**
```text
Searching for: 'camera failure' in 'device_logs'...

[1] ID: ...
    Distance: 0.4512
    Document: Analysis for cam-03: Video feed latency is high due to network congestion...
```
*   **Distance**: Lower numbers mean a closer match (0 = exact match).

#### 4. Dump All Data
Exports all IDs and Metadata (but not the full vector data) for a complete overview.

```bash
./scripts/query-chroma.sh dump
```

## Troubleshooting

*   **"Collection not found"**: The AI hasn't created the memory yet. Run an analysis via the API first.
*   **"Database not found"**: Check that `ai/data/chroma_db` exists.

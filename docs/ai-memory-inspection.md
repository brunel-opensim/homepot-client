# AI Memory Inspection Guide

This guide explains how to inspect and debug the AI's Long-Term Memory (ChromaDB) using the provided utility scripts.

## Overview

The AI uses **ChromaDB** as a vector store to remember past device anomalies, analysis results, and resolutions. Unlike PostgreSQL, which stores structured data (tables), ChromaDB stores **semantic embeddings** (vectors) that allow the AI to find "similar" events based on meaning.

Every record now also carries scope and retention metadata: `user_id`, `site_id`, `device_id`, `created_at`, and `source`. Recall is filtered to the caller's scope (admins are unrestricted) and memories older than `retention_days` are pruned automatically. See [AI Memory](ai-memory.md) for the full design and configuration.

To help developers visualize what the AI "remembers," we provide a command-line tool: `scripts/query-chroma.sh`.

## The Inspection Tool

The tool is located at `scripts/query-chroma.sh`. It wraps a Python script (`ai/inspect_chroma.py`) that connects to the local ChromaDB instance.

### Prerequisites

*   The AI service must have run at least once to initialize the database.
*   You must be in the project root directory.
*   Python 3 must be installed.

### Usage

```bash
./scripts/query-chroma.sh [--store memory|docs] [command] [options]
```

### Stores

There are two ChromaDB stores, both visible to the AI at query time:

| `--store` | Path | Collection | What it holds |
|---|---|---|---|
| `memory` (default) | `ai/data/chroma_db` | `device_logs` | Long-term AI memory: past Q&As, anomaly analyses and resolutions. Recalled into the `[RELEVANT MEMORIES]` block of every query. |
| `docs` | `ai/data/docs_chroma` | `project_docs` | Tier C documentation index: chunked `docs/*.md` used for grounding knowledge answers. |

Use `--store docs` to see **exactly which documentation chunks** the AI is given for a
question — this is the fastest way to tell whether a bad answer is a retrieval miss (the
right chunk was never returned) or a generation miss (the chunk was returned but ignored).

```bash
./scripts/query-chroma.sh --store docs query "How can I enrol a device?"
```

### Inspecting a Live Server

ChromaDB opens its SQLite file in read-write mode, so a second process (e.g. `demouser`
over SSH) cannot open a store that the running API already holds, or one owned by another
user. Rather than failing, the tool copies the store to a temporary directory and inspects
the copy, printing a notice:

```text
Note: the live store could not be opened (...); inspecting a snapshot copy instead.
```

The copy is removed when the command exits. If no `-wal`/`-shm` files are present (Chroma
checkpoints on idle) the snapshot is a consistent point-in-time view.

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
*   **"Database not found"**: Check that `ai/data/chroma_db` exists. Use `--store docs` for the documentation index at `ai/data/docs_chroma`.
*   **"attempt to write a readonly database"** followed by a snapshot notice: this is expected when inspecting a store held by the running API or owned by another user — the tool falls back to a temporary copy automatically. If you instead see the error *without* the snapshot notice, the copy itself failed (check `/tmp` is writable and has space).

# Visual Examples for Documentation

This page demonstrates various visual elements available in HOMEPOT documentation.

## Mermaid Diagrams

### System Architecture (Flowchart)

```mermaid
graph TB
    subgraph "Client Layer"
        A[React Frontend]
        B[Dashboard UI]
    end
    
    subgraph "API Layer"
        C[FastAPI Server]
        D[WebSocket Handler]
    end
    
    subgraph "Data Layer"
        E[(SQLite Database)]
        F[Audit Logs]
    end
    
    subgraph "Device Layer"
        G[POS Terminals]
        H[Agent Simulators]
    end
    
    A --> C
    B --> D
    C --> E
    D --> E
    C --> G
    D --> H
    E --> F
```

### Push Notification Flow (Sequence Diagram)

```mermaid
sequenceDiagram
    participant Server as HOMEPOT Server
    participant FCM as Firebase Cloud Messaging
    participant WNS as Windows Notification Service
    participant APNS as Apple Push Notification
    participant Device as POS Device
    
    Server->>Server: Detect Update Available
    
    alt Android/Linux Device
        Server->>FCM: Send Notification
        FCM->>Device: Push to Android
    else Windows Device
        Server->>WNS: Send Notification
        WNS->>Device: Push to Windows
    else iOS/macOS Device
        Server->>APNS: Send Notification
        APNS->>Device: Push to Apple Device
    end
    
    Device-->>Server: Acknowledge Receipt
    Device->>Device: Apply Update
    Device-->>Server: Report Status
```

### Agent State Machine

```mermaid
stateDiagram-v2
    [*] --> Idle
    Idle --> Updating: Update Available
    Updating --> HealthCheck: Update Complete
    HealthCheck --> Idle: All Checks Pass
    HealthCheck --> Error: Check Failed
    Error --> Idle: Retry/Reset
    Error --> [*]: Critical Failure
    
    note right of Idle
        Agent waiting for tasks
        Polling for updates
    end note
    
    note right of Updating
        Downloading software
        Installing packages
    end note
    
    note right of HealthCheck
        System diagnostics
        Network connectivity
        Hardware status
    end note
```

### Database Entity Relationships

```mermaid
erDiagram
    SITE ||--o{ DEVICE : contains
    SITE ||--o{ JOB : has
    DEVICE ||--o{ JOB : assigned_to
    USER ||--o{ JOB : creates
    USER ||--o{ AUDIT_LOG : generates
    SITE ||--o{ AUDIT_LOG : related_to
    DEVICE ||--o{ AUDIT_LOG : related_to
    
    SITE {
        int id PK
        string name
        string location
        string description
        datetime created_at
    }
    
    DEVICE {
        int id PK
        int site_id FK
        string device_name
        string device_type
        string status
    }
    
    JOB {
        int id PK
        int site_id FK
        int device_id FK
        int user_id FK
        string job_type
        string status
    }
    
    USER {
        int id PK
        string username
        string email
        string role
    }
    
    AUDIT_LOG {
        int id PK
        int user_id FK
        int site_id FK
        int device_id FK
        string event_type
        datetime timestamp
    }
```

### Deployment Architecture

```mermaid
graph LR
    subgraph "Development"
        A[Local Dev]
        B[Git Repo]
    end
    
    subgraph "CI/CD"
        C[GitHub Actions]
        D[Tests & Quality]
    end
    
    subgraph "Documentation"
        E[Read the Docs]
        F[MkDocs Build]
    end
    
    subgraph "Production"
        G[Docker Container]
        H[Database]
        I[POS Devices]
    end
    
    A -->|Push| B
    B -->|Webhook| C
    C -->|Run| D
    B -->|Webhook| E
    E -->|Build| F
    D -->|Deploy| G
    G -->|Connect| H
    G -->|Manage| I
```

### CI/CD Pipeline

```mermaid
graph LR
    A[Code Push] --> B{Branch?}
    B -->|main| C[Full Pipeline]
    B -->|feature| D[Quick Checks]
    
    C --> E[Backend Tests]
    C --> F[Frontend Tests]
    C --> G[Security Audit]
    
    D --> H[ESLint]
    D --> I[Prettier]
    D --> J[Build]
    
    E --> K{All Pass?}
    F --> K
    G --> K
    H --> K
    I --> K
    J --> K
    
    K -->|Yes| L[Deploy to Docs]
    K -->|No| M[Notify Developer]
    
    L --> N[Read the Docs]
    M --> O[Fix & Retry]
    O --> A
```

### Agent Lifecycle (Timeline)

```mermaid
gantt
    title POS Agent Daily Lifecycle
    dateFormat HH:mm
    axisFormat %H:%M
    
    section Initialization
    System Boot           :done, boot, 00:00, 00:05
    Connect to Server     :done, connect, 00:05, 00:10
    
    section Operations
    Idle Monitoring       :active, idle1, 00:10, 08:00
    Morning Transactions  :crit, trans1, 08:00, 12:00
    Idle Period          :idle2, 12:00, 13:00
    Afternoon Transactions:crit, trans2, 13:00, 18:00
    
    section Maintenance
    Check for Updates     :update, 18:00, 18:30
    Health Check         :health, 18:30, 19:00
    Idle Monitoring      :idle3, 19:00, 23:59
```

## Image Placeholders

### Logo Example

<div align="center">
  <p><em>Logo placeholder - Add your logo to <code>docs/images/logos/homepot-logo.png</code></em></p>
  <!-- ![HOMEPOT Logo](images/logos/homepot-logo.png){ width="200" } -->
</div>

### Screenshot Example

<figure markdown>
  <p><em>Screenshot placeholder - Add screenshots to <code>docs/images/screenshots/</code></em></p>
  <!-- ![Dashboard Screenshot](images/screenshots/dashboard.png) -->
  <figcaption>Real-time Dashboard Interface (placeholder)</figcaption>
</figure>

### Diagram Example

<figure markdown>
  <p><em>Diagram placeholder - Add diagrams to <code>docs/images/diagrams/</code></em></p>
  <!-- ![System Architecture](images/diagrams/system-architecture.png) -->
  <figcaption>HOMEPOT System Architecture (placeholder)</figcaption>
</figure>

## Icons and Badges

### Platform Support

<div class="grid" markdown>

- :material-linux:{ .lg .middle } **Linux**
  
  Ubuntu, Debian, CentOS

- :material-microsoft-windows:{ .lg .middle } **Windows**
  
  Windows 10, 11, Server

- :material-apple:{ .lg .middle } **macOS**
  
  macOS 10.15+

</div>

### Feature Highlights

<div class="grid cards" markdown>

- :material-clock-fast:{ .lg .middle } **Real-time**

    WebSocket-powered live monitoring

- :material-shield-check:{ .lg .middle } **Secure**

    Enterprise-grade security

- :material-scale-balance:{ .lg .middle } **Compliant**

    Audit-ready logging

- :material-api:{ .lg .middle } **API First**

    RESTful API design

</div>

## Status Indicators

| Status | Icon | Description |
|--------|------|-------------|
| Online | :material-check-circle:{ style="color: green" } | Device is operational |
| Updating | :material-update:{ style="color: blue" } | Receiving updates |
| Warning | :material-alert:{ style="color: orange" } | Attention needed |
| Offline | :material-close-circle:{ style="color: red" } | Device unavailable |

## Code Examples with Annotations

```python title="database.py" linenums="1" hl_lines="3 8-10"
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from .models import Base  # (1)

DATABASE_URL = "sqlite:///data/homepot.db"

engine = create_engine(DATABASE_URL, echo=True)
SessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,  # (2)
    bind=engine
)

def get_db():
    db = SessionLocal()
    try:
        yield db  # (3)
    finally:
        db.close()
```

1. Import database models
2. Disable autoflush for better control
3. Yield session for dependency injection

## Admonitions (Callout Boxes)

!!! note "Getting Started"
    Visit the [Getting Started Guide](getting-started.md) for installation instructions.

!!! tip "Pro Tip"
    Use `mkdocs serve` to preview documentation locally before committing.

!!! warning "Important"
    Always backup your database before running migrations.

!!! danger "Security Alert"
    Never commit API keys or credentials to version control.

!!! success "Build Passed"
    All tests passed successfully!

!!! example "Example Usage"
    ```bash
    homepot-client run --host 0.0.0.0 --port 8000
    ```

## Tabs

=== "Python"

    ```python
    from homepot import Client
    
    client = Client()
    devices = client.get_devices()
    ```

=== "JavaScript"

    ```javascript
    import { HomepotClient } from 'homepot-client';
    
    const client = new HomepotClient();
    const devices = await client.getDevices();
    ```

=== "cURL"

    ```bash
    curl -X GET http://localhost:8000/api/devices
    ```

## Progressive Disclosure

??? question "How do I add a new site?"
    See the [Database Guide](database-guide.md#adding-sites) for detailed instructions.

??? question "How do I configure push notifications?"
    Check out the platform-specific guides:
    
    - [FCM for Linux/Android](fcm-linux-integration.md)
    - [WNS for Windows](wns-windows-integration.md)
    - [APNs for Apple devices](apns-apple-integration.md)

??? tip "Performance Optimization"
    For better performance:
    
    1. Enable database indexing
    2. Use connection pooling
    3. Implement caching
    4. Monitor with the real-time dashboard

## Quick Reference

For more visual examples and usage instructions, see:

- **[Images Directory README](images/README.md)** - Comprehensive guide to images
- **[Images Quick Reference](images/QUICKREF.md)** - Quick examples

---

*This page demonstrates the visual capabilities of HOMEPOT documentation. Add your own images, diagrams, and screenshots to enhance your documentation!*

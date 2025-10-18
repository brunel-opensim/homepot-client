# Image Quick Reference

Quick examples for adding images to HOMEPOT documentation.

## Basic Usage

### Simple Image
```markdown
![Alt text](images/category/filename.png)
```

### Image with Size
```markdown
![Alt text](images/category/filename.png){ width="600" }
```

### Image with Caption
```markdown
<figure markdown>
  ![Alt text](images/screenshots/dashboard.png)
  <figcaption>Dashboard Overview</figcaption>
</figure>
```

## Mermaid Diagrams (Recommended)

### Flowchart
````markdown
```mermaid
graph TB
    A[Start] --> B{Decision}
    B -->|Yes| C[Action 1]
    B -->|No| D[Action 2]
    C --> E[End]
    D --> E
```
````

### Sequence Diagram
````markdown
```mermaid
sequenceDiagram
    participant Client
    participant Server
    participant Database
    
    Client->>Server: Request
    Server->>Database: Query
    Database-->>Server: Data
    Server-->>Client: Response
```
````

### Architecture Diagram
````markdown
```mermaid
graph LR
    subgraph "Frontend"
        A[React App]
    end
    subgraph "Backend"
        B[FastAPI]
        C[Database]
    end
    subgraph "Devices"
        D[POS Terminals]
    end
    
    A -->|API| B
    B -->|SQL| C
    B -->|WebSocket| D
```
````

### State Diagram
````markdown
```mermaid
stateDiagram-v2
    [*] --> Idle
    Idle --> Updating: Update Available
    Updating --> HealthCheck: Update Complete
    HealthCheck --> Idle: All OK
    HealthCheck --> Error: Check Failed
    Error --> Idle: Retry
```
````

## Common Patterns

### Dashboard Screenshot
```markdown
## Dashboard Interface

<figure markdown>
  ![Dashboard](images/screenshots/dashboard.png)
  <figcaption>Real-time monitoring dashboard with live device status</figcaption>
</figure>
```

### Architecture Diagram
```markdown
## System Architecture

<figure markdown>
  ![Architecture](images/diagrams/system-architecture.png)
  <figcaption>HOMEPOT Client System Architecture</figcaption>
</figure>
```

### Logo Header
```markdown
<div align="center">
  <img src="images/logos/homepot-logo.png" alt="HOMEPOT Logo" width="200">
</div>
```

### Feature Grid with Icons
```markdown
<div class="grid cards" markdown>

- :material-monitor:{ .lg .middle } **Real-time**

    ![Realtime](images/icons/realtime.svg){ width="48" }
    
    Live monitoring

- :material-shield:{ .lg .middle } **Secure**

    ![Security](images/icons/secure.svg){ width="48" }
    
    Enterprise security

</div>
```

## Image Locations

- **Logos**: `docs/images/logos/`
- **Screenshots**: `docs/images/screenshots/`
- **Diagrams**: `docs/images/diagrams/`
- **Icons**: `docs/images/icons/`

## Tips

1. **Use Mermaid** for simple diagrams (version controlled, themed)
2. **Add captions** to explain complex images
3. **Optimize images** before committing (< 500 KB)
4. **Use descriptive filenames**: `pos-device-management.png`
5. **Test locally** with `mkdocs serve`

---

For full documentation, see [images/README.md](README.md)

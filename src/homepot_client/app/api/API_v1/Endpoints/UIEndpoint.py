from fastapi import APIRouter, HTTPException, Depends
import logging
from fastapi.responses import HTMLResponse, JSONResponse

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

router = APIRouter()

@router.get("/", response_class=HTMLResponse, tags=["UI"])
async def get_dashboard() -> HTMLResponse:
    """Get simple dashboard HTML for testing WebSocket and API endpoints."""
    html_content = """
    <!DOCTYPE html>
    <html>
    <head>
        <title>HOMEPOT Client Dashboard - Phase 3</title>
        <style>
            body {
                font-family: Arial, sans-serif;
                margin: 20px;
                background-color: #f5f5f5;
            }
            .container {
                max-width: 1200px;
                margin: 0 auto;
            }
            .header {
                text-align: center;
                margin-bottom: 30px;
                background: white;
                padding: 20px;
                border-radius: 10px;
                box-shadow: 0 2px 4px rgba(0,0,0,0.1);
            }
            .dashboard-grid {
                display: grid;
                grid-template-columns: 1fr 1fr;
                gap: 20px;
                margin-bottom: 30px;
            }
            .panel {
                background: white;
                padding: 20px;
                border-radius: 10px;
                box-shadow: 0 2px 4px rgba(0,0,0,0.1);
            }
            .status-card {
                border: 1px solid #ddd;
                padding: 15px;
                margin: 10px 0;
                border-radius: 5px;
            }
            .healthy {
                background-color: #d4edda;
                border-color: #c3e6cb;
            }
            .warning {
                background-color: #fff3cd;
                border-color: #ffeaa7;
            }
            .error {
                background-color: #f8d7da;
                border-color: #f5c6cb;
            }
            .job-status {
                padding: 5px 10px;
                border-radius: 3px;
                color: white;
                margin-left: 10px;
            }
            .status-queued {
                background-color: #6c757d;
            }
            .status-running {
                background-color: #007bff;
            }
            .status-sent {
                background-color: #17a2b8;
            }
            .status-acknowledged {
                background-color: #28a745;
            }
            .status-completed {
                background-color: #28a745;
            }
            .status-failed {
                background-color: #dc3545;
            }
            .agent-state {
                padding: 3px 8px;
                border-radius: 3px;
                font-size: 0.8em;
                color: white;
            }
            .state-idle {
                background-color: #28a745;
            }
            .state-downloading {
                background-color: #17a2b8;
            }
            .state-updating {
                background-color: #ffc107;
                color: black;
            }
            .state-restarting {
                background-color: #fd7e14;
            }
            .state-health_check {
                background-color: #6f42c1;
            }
            .state-error {
                background-color: #dc3545;
            }
            .metrics {
                display: grid;
                grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
                gap: 10px;
                margin-top: 15px;
            }
            .metric {
                background: #f8f9fa;
                padding: 10px;
                border-radius: 5px;
                text-align: center;
            }
            .metric-value {
                font-size: 1.5em;
                font-weight: bold;
                color: #007bff;
            }
            .api-section {
                background: white;
                padding: 20px;
                border-radius: 10px;
                box-shadow: 0 2px 4px rgba(0,0,0,0.1);
            }
            .endpoint {
                background: #f8f9fa;
                padding: 10px;
                margin: 5px 0;
                border-radius: 5px;
                font-family: monospace;
            }
            .badge {
                background: #007bff;
                color: white;
                padding: 2px 6px;
                border-radius: 3px;
                font-size: 0.8em;
            }
            .phase-badge {
                background: #28a745;
                color: white;
                padding: 4px 8px;
                border-radius: 5px;
                font-size: 0.9em;
                margin-left: 10px;
            }
            .no-data {
                color: #666;
                font-style: italic;
                padding: 20px;
                text-align: center;
                background: #f8f9fa;
                border-radius: 5px;
                margin-top: 10px;
            }
        </style>
    </head>
    <body>
        <div class="container">
            <div class="header">
                <h1>
                    HOMEPOT Client Dashboard
                    <span class="phase-badge">Phase 4: Complete System</span>
                </h1>
                <p>
                    <strong>Consortium Project:</strong>
                    Homogenous Cyber Management of End-Points and OT
                </p>
                <p>
                    <strong>Enterprise Features:</strong>
                    Real-time monitoring • Agent simulation • Comprehensive audit
                </p>
            </div>
            <div class="dashboard-grid">
                <div class="panel">
                    <h2>Real-time Status</h2>
                    <div id="sites-health"></div>
                    <div id="recent-jobs"></div>
                </div>
                <div class="panel">
                    <h2>Agent Simulation</h2>
                    <div id="agents-status"></div>
                    <div class="metrics" id="simulation-metrics">
                        <div class="metric">
                            <div class="metric-value" id="total-agents">0</div>
                            <div>Active Agents</div>
                        </div>
                        <div class="metric">
                            <div class="metric-value" id="health-checks">0</div>
                            <div>Health Checks/min</div>
                        </div>
                    </div>
                </div>
            </div>
            <div class="dashboard-grid">
                <div class="panel">
                    <h2>Audit Trail (Phase 4)</h2>
                    <div id="audit-events"></div>
                    <div class="metrics" id="audit-metrics">
                        <div class="metric">
                            <div class="metric-value" id="total-events">0</div>
                            <div>Events (24h)</div>
                        </div>
                        <div class="metric">
                            <div class="metric-value" id="api-calls">0</div>
                            <div>API Calls</div>
                        </div>
                    </div>
                </div>
                <div class="panel">
                    <h2>System Metrics</h2>
                    <div id="system-status"></div>
                    <div class="metrics" id="system-metrics">
                        <div class="metric">
                            <div class="metric-value" id="uptime">0h</div>
                            <div>Uptime</div>
                        </div>
                        <div class="metric">
                            <div class="metric-value" id="total-sites">0</div>
                            <div>Total Sites</div>
                        </div>
                    </div>
                </div>
            </div>
            <div class="api-section">
                <h2>Phase 3 API Endpoints</h2>
                <p>Test the enhanced POS scenario with realistic agent simulation:</p>
                <h3>Core Workflow (Phases 1-2)</h3>
                <div class="endpoint">
                    <span class="badge">POST</span> /sites - Create restaurant site
                </div>
                <div class="endpoint">
                    <span class="badge">POST</span>
                    /sites/{site_id}/devices - Add POS terminals
                </div>
                <div class="endpoint">
                    <span class="badge">POST</span>
                    /sites/{site_id}/jobs - Trigger payment config update
                </div>
                <div class="endpoint">
                    <span class="badge">GET</span>
                    /jobs/{job_id} - Monitor job progress
                </div>
                <div class="endpoint">
                    <span class="badge">GET</span>
                    /sites/{site_id}/health - Check site health status
                </div>
                <h3>Agent Management (Phase 3)</h3>
                <div class="endpoint">
                    <span class="badge">GET</span>
                    /agents - List all POS agents
                </div>
                <div class="endpoint">
                    <span class="badge">GET</span>
                    /agents/{device_id} - Get agent status
                </div>
                <div class="endpoint">
                    <span class="badge">POST</span>
                    /agents/{device_id}/push - Send test notification
                </div>
                <h3>Device Health & Actions (Phase 3)</h3>
                <div class="endpoint">
                    <span class="badge">GET</span>
                    /devices/{device_id}/health - Device health details
                </div>
                <div class="endpoint">
                    <span class="badge">POST</span>
                    /devices/{device_id}/health - Trigger health check
                </div>
                <div class="endpoint">
                    <span class="badge">POST</span>
                    /devices/{device_id}/restart - Restart POS app
                </div>
            </div>
        </div>
    </body>
    </html>
    """
    return HTMLResponse(content=html_content)

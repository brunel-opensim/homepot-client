# Examples

This section provides practical examples of using the HOMEPOT client library.

## Basic Examples

### Simple Connection

```python
import asyncio
from homepot_client import HomepotClient

async def simple_connection():
    """Basic connection example."""
    client = HomepotClient()
    
    try:
        await client.connect()
        print(f"Connected: {client.is_connected}")
    finally:
        await client.disconnect()

# Run the example
asyncio.run(simple_connection())
```

### Using Configuration

```python
import asyncio
from homepot_client import HomepotClient, ClientConfig

async def configured_client():
    """Example with custom configuration."""
    config = ClientConfig(
        api_url="https://api.homepot.example.com",
        api_key="your-api-key-here",
        timeout=60,
        retries=5
    )
    
    client = HomepotClient(config=config)
    
    try:
        await client.connect()
        # Your code here
    finally:
        await client.disconnect()

asyncio.run(configured_client())
```

## Error Handling

### Robust Error Handling

```python
import asyncio
import logging
from homepot_client import HomepotClient, HomepotError

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def robust_client():
    """Example with comprehensive error handling."""
    client = HomepotClient()
    
    try:
        logger.info("Attempting to connect...")
        await client.connect()
        logger.info("Successfully connected!")
        
        # Simulate some work
        await asyncio.sleep(1)
        
    except HomepotError as e:
        logger.error(f"HOMEPOT-specific error: {e}")
        return False
    except ConnectionError as e:
        logger.error(f"Connection failed: {e}")
        return False
    except Exception as e:
        logger.error(f"Unexpected error: {e}")
        return False
    finally:
        if client.is_connected:
            await client.disconnect()
            logger.info("Disconnected successfully")
    
    return True

# Run with error handling
success = asyncio.run(robust_client())
print(f"Operation successful: {success}")
```

### Retry Logic

```python
import asyncio
from homepot_client import HomepotClient, HomepotError

async def connect_with_retry(max_retries=3):
    """Example with custom retry logic."""
    client = HomepotClient()
    
    for attempt in range(1, max_retries + 1):
        try:
            print(f"Connection attempt {attempt}/{max_retries}")
            await client.connect()
            print("Connected successfully!")
            return client
        except HomepotError as e:
            print(f"Attempt {attempt} failed: {e}")
            if attempt == max_retries:
                print("All retry attempts exhausted")
                raise
            await asyncio.sleep(2 ** attempt)  # Exponential backoff
    
    return None

# Usage
async def main():
    try:
        client = await connect_with_retry()
        # Use client here
    finally:
        if client and client.is_connected:
            await client.disconnect()

asyncio.run(main())
```

## Environment-Based Configuration

### Using Environment Variables

```python
import os
import asyncio
from homepot_client import HomepotClient, ClientConfig

async def env_based_client():
    """Configure client using environment variables."""
    config = ClientConfig(
        api_url=os.getenv("HOMEPOT_API_URL", "https://api.homepot.example.com"),
        api_key=os.getenv("HOMEPOT_API_KEY"),
        timeout=int(os.getenv("HOMEPOT_TIMEOUT", "30")),
        retries=int(os.getenv("HOMEPOT_RETRIES", "3"))
    )
    
    client = HomepotClient(config=config)
    
    try:
        await client.connect()
        print("Environment-configured client connected!")
    finally:
        await client.disconnect()

asyncio.run(env_based_client())
```

### Using .env File

```python
import asyncio
from pathlib import Path
from homepot_client import HomepotClient

async def dotenv_client():
    """Load configuration from .env file."""
    # Ensure .env file exists
    env_file = Path(".env")
    if not env_file.exists():
        print("Creating .env file...")
        env_file.write_text("""
HOMEPOT_API_URL=https://api.homepot.example.com
HOMEPOT_API_KEY=your_api_key_here
HOMEPOT_TIMEOUT=30
HOMEPOT_RETRIES=3
""".strip())
    
    # Load environment and create client
    try:
        from dotenv import load_dotenv
        load_dotenv()
    except ImportError:
        print("python-dotenv not installed. Install with: pip install python-dotenv")
        return
    
    client = HomepotClient()
    
    try:
        await client.connect()
        print("Client connected using .env configuration!")
    finally:
        await client.disconnect()

asyncio.run(dotenv_client())
```

## CLI Integration

### Running CLI Commands from Python

```python
import subprocess
import json

def run_cli_command(command):
    """Run HOMEPOT CLI command from Python."""
    try:
        result = subprocess.run(
            ["homepot-client"] + command,
            capture_output=True,
            text=True,
            check=True
        )
        return result.stdout.strip()
    except subprocess.CalledProcessError as e:
        print(f"CLI command failed: {e}")
        return None

# Examples
version = run_cli_command(["version"])
print(f"CLI Version: {version}")

# Get info as JSON
info_json = run_cli_command(["info", "--json"])
if info_json:
    info = json.loads(info_json)
    print(f"Python version: {info['system']['python']}")
```

## Testing Examples

### Unit Test Example

```python
import pytest
import asyncio
from unittest.mock import Mock, patch
from homepot_client import HomepotClient

class TestHomepotClient:
    """Test suite for HOMEPOT client."""
    
    @pytest.fixture
    def client(self):
        """Create a test client."""
        return HomepotClient()
    
    @pytest.mark.asyncio
    async def test_connection(self, client):
        """Test basic connection functionality."""
        # Mock the actual connection
        with patch.object(client, '_actual_connect', return_value=True):
            await client.connect()
            assert client.is_connected is True
            
            await client.disconnect()
            assert client.is_connected is False
    
    @pytest.mark.asyncio
    async def test_connection_error(self, client):
        """Test connection error handling."""
        with patch.object(client, '_actual_connect', side_effect=ConnectionError("Failed")):
            with pytest.raises(ConnectionError):
                await client.connect()
```

### Integration Test Example

```python
import pytest
import asyncio
from homepot_client import HomepotClient

@pytest.mark.integration
class TestIntegration:
    """Integration tests for HOMEPOT client."""
    
    @pytest.mark.asyncio
    async def test_real_connection(self):
        """Test actual connection to service."""
        client = HomepotClient()
        
        try:
            # This would connect to a real test service
            await client.connect()
            
            # Verify connection works
            assert client.is_connected
            
        except Exception as e:
            pytest.skip(f"Service unavailable: {e}")
        finally:
            if client.is_connected:
                await client.disconnect()
```

## Performance Examples

### Concurrent Connections

```python
import asyncio
from homepot_client import HomepotClient

async def create_client(client_id):
    """Create and test a client connection."""
    client = HomepotClient()
    
    try:
        start_time = asyncio.get_event_loop().time()
        await client.connect()
        end_time = asyncio.get_event_loop().time()
        
        connection_time = end_time - start_time
        print(f"Client {client_id}: Connected in {connection_time:.3f}s")
        
        # Simulate some work
        await asyncio.sleep(0.1)
        
        return True
    except Exception as e:
        print(f"Client {client_id}: Failed - {e}")
        return False
    finally:
        if client.is_connected:
            await client.disconnect()

async def concurrent_test(num_clients=5):
    """Test multiple concurrent client connections."""
    print(f"Testing {num_clients} concurrent connections...")
    
    start_time = asyncio.get_event_loop().time()
    
    # Create tasks for concurrent execution
    tasks = [create_client(i) for i in range(num_clients)]
    results = await asyncio.gather(*tasks, return_exceptions=True)
    
    end_time = asyncio.get_event_loop().time()
    total_time = end_time - start_time
    
    successful = sum(1 for r in results if r is True)
    print(f"Results: {successful}/{num_clients} successful in {total_time:.3f}s")

# Run concurrent test
asyncio.run(concurrent_test())
```

### Performance Monitoring

```python
import time
import asyncio
from homepot_client import HomepotClient

class PerformanceMonitor:
    """Monitor client performance metrics."""
    
    def __init__(self):
        self.metrics = {
            'connection_times': [],
            'operation_times': [],
            'errors': 0
        }
    
    async def timed_operation(self, operation_name, coro):
        """Time an async operation."""
        start = time.perf_counter()
        try:
            result = await coro
            end = time.perf_counter()
            duration = end - start
            
            self.metrics[f'{operation_name}_times'].append(duration)
            return result
        except Exception as e:
            self.metrics['errors'] += 1
            raise
    
    def report(self):
        """Generate performance report."""
        for metric, values in self.metrics.items():
            if isinstance(values, list) and values:
                avg = sum(values) / len(values)
                min_val = min(values)
                max_val = max(values)
                print(f"{metric}: avg={avg:.3f}s, min={min_val:.3f}s, max={max_val:.3f}s")
            else:
                print(f"{metric}: {values}")

async def performance_test():
    """Run performance tests."""
    monitor = PerformanceMonitor()
    client = HomepotClient()
    
    try:
        # Test connection performance
        await monitor.timed_operation('connection', client.connect())
        
        # Test multiple operations
        for i in range(10):
            await monitor.timed_operation('operation', asyncio.sleep(0.01))
        
    finally:
        if client.is_connected:
            await client.disconnect()
    
    monitor.report()

# Run performance test
asyncio.run(performance_test())
```

## Production Examples

### Application Integration

```python
from fastapi import FastAPI, HTTPException
import asyncio
from contextlib import asynccontextmanager
from homepot_client import HomepotClient

# Global client instance
homepot_client = None

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Manage HOMEPOT client lifecycle."""
    global homepot_client
    
    # Startup
    homepot_client = HomepotClient()
    try:
        await homepot_client.connect()
        print("HOMEPOT client connected")
        yield
    finally:
        # Shutdown
        if homepot_client and homepot_client.is_connected:
            await homepot_client.disconnect()
            print("HOMEPOT client disconnected")

# Create FastAPI app with lifespan
app = FastAPI(lifespan=lifespan)

@app.get("/health")
async def health_check():
    """Health check endpoint."""
    if homepot_client and homepot_client.is_connected:
        return {"status": "healthy", "homepot": "connected"}
    else:
        raise HTTPException(status_code=503, detail="HOMEPOT client not connected")

@app.get("/client/info")
async def client_info():
    """Get client information."""
    if not homepot_client or not homepot_client.is_connected:
        raise HTTPException(status_code=503, detail="Client not connected")
    
    return {
        "connected": homepot_client.is_connected,
        "version": "0.1.0"
    }
```

### Background Task Example

```python
import asyncio
import logging
from homepot_client import HomepotClient

class HomepotService:
    """Background service using HOMEPOT client."""
    
    def __init__(self):
        self.client = HomepotClient()
        self.running = False
        self.logger = logging.getLogger(__name__)
    
    async def start(self):
        """Start the background service."""
        self.logger.info("Starting HOMEPOT service...")
        
        try:
            await self.client.connect()
            self.running = True
            self.logger.info("Service started successfully")
            
            # Start background tasks
            await asyncio.gather(
                self._monitor_connection(),
                self._periodic_task()
            )
        except Exception as e:
            self.logger.error(f"Failed to start service: {e}")
            raise
    
    async def stop(self):
        """Stop the background service."""
        self.logger.info("Stopping HOMEPOT service...")
        self.running = False
        
        if self.client.is_connected:
            await self.client.disconnect()
        
        self.logger.info("Service stopped")
    
    async def _monitor_connection(self):
        """Monitor connection health."""
        while self.running:
            if not self.client.is_connected:
                self.logger.warning("Connection lost, attempting reconnect...")
                try:
                    await self.client.connect()
                    self.logger.info("Reconnected successfully")
                except Exception as e:
                    self.logger.error(f"Reconnection failed: {e}")
            
            await asyncio.sleep(30)  # Check every 30 seconds
    
    async def _periodic_task(self):
        """Perform periodic tasks."""
        while self.running:
            try:
                # Perform periodic work here
                self.logger.debug("Performing periodic task...")
                await asyncio.sleep(60)  # Run every minute
            except Exception as e:
                self.logger.error(f"Periodic task failed: {e}")

# Usage
async def main():
    service = HomepotService()
    
    try:
        await service.start()
    except KeyboardInterrupt:
        print("\nShutting down...")
    finally:
        await service.stop()

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    asyncio.run(main())
```

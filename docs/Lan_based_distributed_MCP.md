# MCP Distributed System over Tailscale

Arsitektur distributed MCP untuk 10+ komputer menggunakan Tailscale sebagai backbone network.

## 🌟 Keuntungan Menggunakan Tailscale

### Kenapa Tailscale Perfect untuk Anda:

✅ **Zero Configuration Networking**
- Semua komputer dalam satu network virtual (100.x.x.x)
- No port forwarding, no firewall config
- Works across different physical networks

✅ **Built-in Security**
- End-to-end encryption (WireGuard)
- Automatic key rotation
- ACL (Access Control Lists)

✅ **Global Reach**
- Komputer bisa di rumah, kantor, cloud - semua connect
- Better than LAN (tidak terbatas subnet fisik)

✅ **Service Discovery Built-in**
- MagicDNS: setiap device punya hostname
- Contoh: `mcp-server-1.tail1b96f3.ts.net`

## 🏗️ Arsitektur Recommended

```
┌──────────────────────────────────────────────────────────────┐
│                    Tailscale Network                         │
│                  (100.88.x.x/16 subnet)                      │
│                                                              │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐         │
│  │ Master Node │  │ Message Queue│  │Storage Cluster│        │
│  │ 100.88.72.19│  │ 100.88.1.10 │  │ 100.88.2.x  │         │
│  │             │  │  (RabbitMQ) │  │  (3 nodes)  │         │
│  │ - API       │  │             │  │             │         │
│  │ - Scheduler │  │ - Task Queue│  │ - PostgreSQL│         │
│  │ - Monitor   │  │ - Events    │  │ - MinIO     │         │
│  └─────────────┘  └─────────────┘  └─────────────┘         │
│         │                │                 │                │
│         └────────────────┼─────────────────┘                │
│                          │                                  │
│         ┌────────────────┴────────────────┐                │
│         │                                 │                │
│  ┌──────▼──────┐  ┌──────────────┐  ┌────▼──────┐         │
│  │ Worker 1    │  │ Worker 2     │  │ Worker N  │         │
│  │ 100.88.10.1 │  │ 100.88.10.2  │  │100.88.10.N│         │
│  │             │  │              │  │           │         │
│  │ - gRPC      │  │ - gRPC       │  │ - gRPC    │         │
│  │ - Executor  │  │ - Executor   │  │ - Executor│         │
│  │ - Cache     │  │ - Cache      │  │ - Cache   │         │
│  └─────────────┘  └──────────────┘  └───────────┘         │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

## 📋 Implementation Plan (4 Weeks)

### Week 1: Foundation Layer

#### Day 1-2: Setup Tailscale Infrastructure

```bash
# Install Tailscale di semua komputer
# Windows (sudah installed)
# Linux
curl -fsSL https://tailscale.com/install.sh | sh
sudo tailscale up

# Verify network
tailscale status

# Expected output:
# 100.88.72.19   mcp-main-server      aseps@       windows -
# 100.88.10.1    mcp-worker-1         aseps@       linux   -
# 100.88.10.2    mcp-worker-2         aseps@       linux   -
```

#### Day 3-4: Setup Message Queue (RabbitMQ)

Pilih 1 komputer sebagai message broker (bisa di main server).

```bash
# Install RabbitMQ via Docker
docker run -d \
  --name rabbitmq \
  -p 5672:5672 \
  -p 15672:15672 \
  -e RABBITMQ_DEFAULT_USER=mcp \
  -e RABBITMQ_DEFAULT_PASS=secure_password_here \
  rabbitmq:3-management

# Verify
curl http://100.88.72.19:15672
# Login: mcp / secure_password_here
```

#### Day 5-7: Implement Message Queue Client

```python
# mcp-unified/messaging/queue_client.py

import aio_pika
import json
import asyncio
from typing import Callable, Dict, Any

class MCPMessageQueue:
    """Message queue client untuk distributed MCP"""
    
    def __init__(self, rabbitmq_url: str):
        self.url = rabbitmq_url
        self.connection = None
        self.channel = None
        self.exchange = None
        
    async def connect(self):
        """Connect to RabbitMQ"""
        self.connection = await aio_pika.connect_robust(self.url)
        self.channel = await self.connection.channel()
        
        # Declare exchange untuk task distribution
        self.exchange = await self.channel.declare_exchange(
            'mcp_tasks',
            aio_pika.ExchangeType.TOPIC,
            durable=True
        )
        
    async def publish_task(
        self,
        task_type: str,
        task_data: Dict[str, Any],
        priority: int = 5
    ):
        """Publish task ke queue"""
        
        message = aio_pika.Message(
            body=json.dumps(task_data).encode(),
            priority=priority,
            delivery_mode=aio_pika.DeliveryMode.PERSISTENT
        )
        
        routing_key = f"task.{task_type}"
        
        await self.exchange.publish(
            message,
            routing_key=routing_key
        )
        
        print(f"📤 Published task: {task_type}")
        
    async def consume_tasks(
        self,
        task_types: list,
        handler: Callable
    ):
        """Consume tasks dari queue"""
        
        # Create queue untuk worker ini
        queue = await self.channel.declare_queue(
            '',  # Auto-generated name
            durable=True,
            arguments={'x-max-priority': 10}
        )
        
        # Bind to task types
        for task_type in task_types:
            routing_key = f"task.{task_type}"
            await queue.bind(self.exchange, routing_key=routing_key)
        
        # Start consuming
        async with queue.iterator() as queue_iter:
            async for message in queue_iter:
                async with message.process():
                    task_data = json.loads(message.body.decode())
                    
                    try:
                        result = await handler(task_data)
                        print(f"✅ Task completed: {task_data.get('id')}")
                    except Exception as e:
                        print(f"❌ Task failed: {e}")
                        # Re-queue or send to DLQ
    
    async def close(self):
        """Close connection"""
        if self.connection:
            await self.connection.close()


# Usage Example
async def main():
    # Master node: publish tasks
    mq = MCPMessageQueue("amqp://mcp:secure_password_here@100.88.72.19/")
    await mq.connect()
    
    await mq.publish_task(
        task_type="code_analysis",
        task_data={
            "id": "task_001",
            "file_path": "/path/to/code.py",
            "analysis_type": "complexity"
        },
        priority=7
    )
    
    # Worker node: consume tasks
    async def task_handler(task_data):
        # Process task
        print(f"Processing: {task_data}")
        # ... actual task execution
        return {"status": "completed"}
    
    await mq.consume_tasks(
        task_types=["code_analysis", "refactoring"],
        handler=task_handler
    )
```

### Week 2: gRPC Layer for Fast Communication

```python
# mcp-unified/grpc/mcp_service.proto

syntax = "proto3";

package mcp;

service MCPService {
  // Execute task
  rpc ExecuteTask(TaskRequest) returns (TaskResponse);
  
  // Stream task progress
  rpc StreamTaskProgress(TaskRequest) returns (stream ProgressUpdate);
  
  // Health check
  rpc HealthCheck(Empty) returns (HealthStatus);
  
  // File operations
  rpc ReadFile(FileRequest) returns (FileContent);
  rpc WriteFile(FileWriteRequest) returns (FileResponse);
}

message TaskRequest {
  string task_id = 1;
  string task_type = 2;
  string payload = 3;  // JSON encoded
  int32 priority = 4;
}

message TaskResponse {
  string task_id = 1;
  bool success = 2;
  string result = 3;
  string error = 4;
  int64 duration_ms = 5;
}

message ProgressUpdate {
  string task_id = 1;
  float progress = 2;  // 0.0 to 1.0
  string message = 3;
}

message Empty {}

message HealthStatus {
  bool healthy = 1;
  int32 active_tasks = 2;
  float cpu_usage = 3;
  float memory_usage = 4;
}
```

```python
# mcp-unified/grpc/server.py

import grpc
from concurrent import futures
import mcp_pb2
import mcp_pb2_grpc

class MCPServicer(mcp_pb2_grpc.MCPServiceServicer):
    """gRPC server implementation"""
    
    async def ExecuteTask(self, request, context):
        """Execute task via gRPC"""
        task_id = request.task_id
        
        try:
            # Execute task using existing MCP logic
            result = await execute_mcp_task(
                task_type=request.task_type,
                payload=json.loads(request.payload)
            )
            
            return mcp_pb2.TaskResponse(
                task_id=task_id,
                success=True,
                result=json.dumps(result)
            )
        except Exception as e:
            return mcp_pb2.TaskResponse(
                task_id=task_id,
                success=False,
                error=str(e)
            )
    
    async def StreamTaskProgress(self, request, context):
        """Stream progress updates"""
        task_id = request.task_id
        
        # Execute task with progress tracking
        async for progress in execute_with_progress(request):
            yield mcp_pb2.ProgressUpdate(
                task_id=task_id,
                progress=progress['percent'],
                message=progress['message']
            )

# Start gRPC server
async def serve():
    server = grpc.aio.server(futures.ThreadPoolExecutor(max_workers=10))
    mcp_pb2_grpc.add_MCPServiceServicer_to_server(
        MCPServicer(), server
    )
    
    # Listen on Tailscale IP
    listen_addr = '100.88.72.19:50051'
    server.add_insecure_port(listen_addr)
    
    await server.start()
    print(f"🚀 gRPC server listening on {listen_addr}")
    await server.wait_for_termination()
```

### Week 3: Distributed File Storage

```python
# mcp-unified/storage/distributed_fs.py

import asyncio
import hashlib
from pathlib import Path
import aiofiles
import httpx

class DistributedFileSystem:
    """Distributed file storage menggunakan MinIO"""
    
    def __init__(self, minio_endpoints: list):
        """
        minio_endpoints: List of MinIO servers
        Example: ['http://100.88.2.1:9000', 'http://100.88.2.2:9000']
        """
        self.endpoints = minio_endpoints
        self.current_endpoint = 0
        
    async def store_file(
        self,
        file_path: str,
        content: bytes,
        replicas: int = 3
    ) -> dict:
        """Store file with replication"""
        
        # Calculate hash for deduplication
        file_hash = hashlib.sha256(content).hexdigest()
        
        # Store in bucket based on hash prefix
        bucket = f"mcp-storage-{file_hash[:2]}"
        object_name = file_hash
        
        stored_locations = []
        
        # Store on multiple endpoints
        for i in range(min(replicas, len(self.endpoints))):
            endpoint = self.endpoints[i]
            
            try:
                async with httpx.AsyncClient() as client:
                    # Upload to MinIO
                    response = await client.put(
                        f"{endpoint}/{bucket}/{object_name}",
                        content=content,
                        headers={"Content-Type": "application/octet-stream"}
                    )
                    
                    if response.status_code == 200:
                        stored_locations.append({
                            'endpoint': endpoint,
                            'bucket': bucket,
                            'object': object_name
                        })
            except Exception as e:
                print(f"Failed to store on {endpoint}: {e}")
        
        return {
            'file_hash': file_hash,
            'original_path': file_path,
            'locations': stored_locations,
            'size': len(content)
        }
    
    async def retrieve_file(self, file_hash: str) -> bytes:
        """Retrieve file from any available replica"""
        
        bucket = f"mcp-storage-{file_hash[:2]}"
        
        # Try each endpoint
        for endpoint in self.endpoints:
            try:
                async with httpx.AsyncClient() as client:
                    response = await client.get(
                        f"{endpoint}/{bucket}/{file_hash}"
                    )
                    
                    if response.status_code == 200:
                        return response.content
            except Exception:
                continue
        
        raise FileNotFoundError(f"File not found: {file_hash}")
```

### Week 4: Orchestration & Monitoring

```python
# mcp-unified/orchestration/coordinator.py

class MCPCoordinator:
    """Central coordinator untuk distributed system"""
    
    def __init__(
        self,
        message_queue: MCPMessageQueue,
        grpc_clients: dict,
        storage: DistributedFileSystem
    ):
        self.mq = message_queue
        self.grpc_clients = grpc_clients
        self.storage = storage
        self.worker_status = {}
        
    async def execute_distributed_task(
        self,
        task: dict,
        strategy: str = "auto"
    ) -> dict:
        """Execute task using best available method"""
        
        if strategy == "auto":
            # Decide based on task characteristics
            if task.get('size', 0) > 1_000_000:
                # Large task -> async via message queue
                return await self._execute_via_queue(task)
            else:
                # Small task -> sync via gRPC
                return await self._execute_via_grpc(task)
        
        elif strategy == "queue":
            return await self._execute_via_queue(task)
        
        elif strategy == "grpc":
            return await self._execute_via_grpc(task)
    
    async def _execute_via_queue(self, task: dict):
        """Async execution via RabbitMQ"""
        await self.mq.publish_task(
            task_type=task['type'],
            task_data=task,
            priority=task.get('priority', 5)
        )
        
        # Return task ID for tracking
        return {'task_id': task['id'], 'status': 'queued'}
    
    async def _execute_via_grpc(self, task: dict):
        """Sync execution via gRPC"""
        
        # Select best worker
        worker = await self._select_worker(task)
        
        # Execute on worker
        client = self.grpc_clients[worker]
        response = await client.ExecuteTask(
            task_id=task['id'],
            task_type=task['type'],
            payload=json.dumps(task['data'])
        )
        
        return {
            'task_id': task['id'],
            'success': response.success,
            'result': json.loads(response.result) if response.success else None,
            'error': response.error if not response.success else None
        }
    
    async def _select_worker(self, task: dict) -> str:
        """Select best worker for task"""
        
        # Health check all workers
        healthy_workers = []
        
        for worker_id, client in self.grpc_clients.items():
            try:
                health = await client.HealthCheck()
                if health.healthy and health.active_tasks < 10:
                    healthy_workers.append({
                        'id': worker_id,
                        'load': health.active_tasks,
                        'cpu': health.cpu_usage
                    })
            except Exception:
                continue
        
        if not healthy_workers:
            raise RuntimeError("No healthy workers available")
        
        # Select worker dengan load terendah
        best_worker = min(healthy_workers, key=lambda w: w['load'] + w['cpu']/100)
        return best_worker['id']
```

## 🚀 Quick Start (Today!)

### Step 1: Setup Configuration

```yaml
# mcp-unified/config/tailscale_network.yaml

tailscale:
  network: "tail1b96f3.ts.net"
  
master_node:
  hostname: "mcp-main"
  tailscale_ip: "100.88.72.19"
  services:
    - api_gateway: 8000
    - grpc_server: 50051
    - rabbitmq: 5672
    - monitoring: 3000

worker_nodes:
  - hostname: "mcp-worker-1"
    tailscale_ip: "100.88.10.1"
    capabilities: ["code_analysis", "refactoring"]
    grpc_port: 50051
    
  - hostname: "mcp-worker-2"
    tailscale_ip: "100.88.10.2"
    capabilities: ["testing", "documentation"]
    grpc_port: 50051

storage_nodes:
  - hostname: "mcp-storage-1"
    tailscale_ip: "100.88.2.1"
    minio_port: 9000
    
  - hostname: "mcp-storage-2"
    tailscale_ip: "100.88.2.2"
    minio_port: 9000
```

### Step 2: Install Dependencies

```bash
# Master node
pip install aio-pika grpcio grpcio-tools minio httpx

# Worker nodes
pip install grpcio grpcio-tools

# Storage nodes
docker run -d \
  -p 9000:9000 \
  -p 9001:9001 \
  -e MINIO_ROOT_USER=mcp \
  -e MINIO_ROOT_PASSWORD=secure_password \
  -v /data/minio:/data \
  minio/minio server /data --console-address ":9001"
```

### Step 3: Deploy Master Node

```bash
# Start RabbitMQ
docker run -d \
  --name rabbitmq \
  -p 5672:5672 \
  -p 15672:15672 \
  -e RABBITMQ_DEFAULT_USER=mcp \
  -e RABBITMQ_DEFAULT_PASS=secure_password \
  rabbitmq:3-management

# Start MCP Master
cd ~/MCP/mcp-unified
python -m orchestration.master_server
```

### Step 4: Deploy Worker Nodes

```bash
# Di setiap worker node
cd ~/MCP/mcp-unified
python -m grpc.worker_server --config config/tailscale_network.yaml
```

### Step 5: Test Distribution

```python
# test_distributed.py

import asyncio
from orchestration.coordinator import MCPCoordinator
from messaging.queue_client import MCPMessageQueue

async def test():
    # Setup coordinator
    mq = MCPMessageQueue("amqp://mcp:secure_password@100.88.72.19/")
    await mq.connect()
    
    coordinator = MCPCoordinator(mq, {}, None)
    
    # Test distributed task
    result = await coordinator.execute_distributed_task({
        'id': 'test_001',
        'type': 'code_analysis',
        'data': {'file': '/path/to/code.py'},
        'priority': 7
    })
    
    print(f"Result: {result}")

asyncio.run(test())
```

## 📊 Monitoring Dashboard

```python
# mcp-unified/monitoring/dashboard.py

from fastapi import FastAPI
from fastapi.responses import HTMLResponse

app = FastAPI()

@app.get("/dashboard", response_class=HTMLResponse)
async def dashboard():
    # Collect metrics dari semua nodes
    metrics = await collect_cluster_metrics()
    
    return f"""
    <html>
        <head><title>MCP Cluster Dashboard</title></head>
        <body>
            <h1>MCP Distributed System</h1>
            <div>
                <h2>Master Node: 100.88.72.19</h2>
                <p>Status: {metrics['master']['status']}</p>
            </div>
            <div>
                <h2>Workers ({len(metrics['workers'])})</h2>
                <ul>
                    {''.join([f"<li>{w['id']}: {w['status']}</li>" for w in metrics['workers']])}
                </ul>
            </div>
            <div>
                <h2>Tasks Today</h2>
                <p>Completed: {metrics['tasks']['completed']}</p>
                <p>Failed: {metrics['tasks']['failed']}</p>
                <p>Queued: {metrics['tasks']['queued']}</p>
            </div>
        </body>
    </html>
    """
```

## 🎯 Deployment Checklist

- [ ] Tailscale running di semua nodes
- [ ] RabbitMQ deployed & accessible
- [ ] MinIO deployed (min 2 instances)
- [ ] Master node running
- [ ] Worker nodes (min 3) registered
- [ ] Storage nodes configured
- [ ] Monitoring dashboard active
- [ ] Test tasks berhasil execute
- [ ] Failover tested
- [ ] Backup system configured

## 💡 Pro Tips untuk Tailscale

1. **Enable MagicDNS** di Tailscale admin console
   - Setiap node dapat access via hostname: `mcp-worker-1.tail1b96f3.ts.net`

2. **Setup ACLs** untuk security:
```json
{
  "acls": [
    {
      "action": "accept",
      "src": ["tag:mcp-master"],
      "dst": ["tag:mcp-worker:*", "tag:mcp-storage:*"]
    }
  ]
}
```

3. **Use Tailscale SSH** untuk zero-config remote access:
```bash
tailscale ssh mcp-worker-1
```

Siap untuk implementasi? Mulai dari week 1 atau ada pertanyaan? 🚀
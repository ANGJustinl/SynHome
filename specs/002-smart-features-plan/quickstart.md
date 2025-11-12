# Smart Features Quick Start Guide

**Feature**: Smart Home Intelligence Implementation
**Version**: 1.0.0
**Last Updated**: 2025-11-12

## Overview

This guide helps developers get started with implementing smart home intelligence features including user habit learning, data analytics, and remote control capabilities.

## Prerequisites

### System Requirements
- Python 3.11+
- 8GB RAM minimum (16GB recommended)
- 100GB storage space
- Redis server (for caching)
- SQLite or PostgreSQL database

### Dependencies
```bash
# Core dependencies
pip install zhipuai yaml asyncio websockets
pip install fastapi uvicorn python-jose[cryptography]

# Memory and analytics
pip install chromadb sentence-transformers pandas
pip install matplotlib redis

# Testing
pip install pytest pytest-asyncio pytest-cov
```

### Existing SynHome Setup
Ensure you have the current SynHome system running:
- Device management system
- ZhipuAI LLM integration
- YAML device configurations
- Basic web interface

## Project Structure

```
libs/
├── memory/                 # Memory system components
│   ├── __init__.py
│   ├── storage.py         # Memory storage and retrieval
│   ├── embedding.py       # Text embeddings and vector search
│   ├── compression.py     # Memory compression algorithms
│   └── retrieval.py       # Memory retrieval strategies
├── patterns/               # Pattern recognition
│   ├── __init__.py
│   ├── detector.py        # Pattern detection algorithms
│   ├── learner.py         # Pattern learning from memories
│   └── executor.py        # Pattern execution engine
├── analytics/              # Analytics and insights
│   ├── __init__.py
│   ├── processor.py       # Data processing pipelines
│   ├── insights.py        # Insight generation
│   └── reports.py         # Report generation
└── remote/                 # Remote control and sharing
    ├── __init__.py
    ├── websocket.py       # WebSocket server
    ├── auth.py           # Authentication and sessions
    └── sharing.py        # Device sharing logic

apps/
├── analytics_api/          # Analytics API service
├── remote_gateway/         # Remote control gateway
└── memory_service/         # Memory management service

tests/
├── test_memory/
├── test_patterns/
├── test_analytics/
└── test_remote/

config/
├── memory_config.yaml      # Memory system configuration
├── analytics_config.yaml   # Analytics configuration
└── remote_config.yaml      # Remote control configuration
```

## Getting Started

### 1. Initialize Memory System

```python
# libs/memory/storage.py
from chromadb import Client
from sentence_transformers import SentenceTransformer
import redis

class MemoryStore:
    def __init__(self, config):
        self.chroma_client = Client()
        self.embedder = SentenceTransformer('all-MiniLM-L6-v2')
        self.redis_client = redis.Redis(host='localhost', port=6379)
        self.collection = self.chroma_client.get_or_create_collection("memories")

    async def store_memory(self, user_id: str, memory_type: str, content: dict):
        # Store memory in vector database
        embedding = self.embedder.encode(str(content))

        memory_entry = {
            'user_id': user_id,
            'type': memory_type,
            'content': content,
            'timestamp': datetime.now(),
            'embedding': embedding.tolist()
        }

        # Store in ChromaDB
        self.collection.add(
            embeddings=[embedding.tolist()],
            documents=[str(content)],
            metadatas=[memory_entry],
            ids=[str(uuid.uuid4())]
        )

        # Cache in Redis for fast access
        cache_key = f"memory:{user_id}:recent"
        self.redis_client.lpush(cache_key, json.dumps(memory_entry))
        self.redis_client.expire(cache_key, 86400)  # 24 hours
```

### 2. Set Up Pattern Detection

```python
# libs/patterns/detector.py
from typing import List, Dict
from datetime import datetime, timedelta

class PatternDetector:
    def __init__(self, memory_store):
        self.memory_store = memory_store

    async def detect_temporal_patterns(self, user_id: str) -> List[Dict]:
        """Detect time-based usage patterns"""
        # Get recent memories
        memories = await self.memory_store.get_recent_memories(user_id, days=30)

        # Analyze time patterns
        patterns = []
        device_usage_by_hour = self._analyze_hourly_usage(memories)

        # Find recurring patterns
        for hour, usage in device_usage_by_hour.items():
            if len(usage) > 5:  # Threshold for pattern detection
                pattern = {
                    'type': 'temporal',
                    'time': hour,
                    'devices': usage,
                    'confidence': len(usage) / 30.0,  # Frequency over 30 days
                    'description': f"Common usage pattern at {hour}:00"
                }
                patterns.append(pattern)

        return patterns

    async def detect_device_combination_patterns(self, user_id: str) -> List[Dict]:
        """Detect device combinations used together"""
        memories = await self.memory_store.get_recent_memories(user_id, days=30)

        # Find device combinations
        combinations = self._find_device_combinations(memories)
        patterns = []

        for combo, frequency in combinations.items():
            if frequency > 3:  # Threshold
                pattern = {
                    'type': 'device_combination',
                    'devices': combo,
                    'frequency': frequency,
                    'confidence': frequency / 30.0,
                    'description': f"Devices often used together: {', '.join(combo)}"
                }
                patterns.append(pattern)

        return patterns
```

### 3. Implement Analytics Processing

```python
# libs/analytics/processor.py
import pandas as pd
from datetime import datetime, timedelta

class AnalyticsProcessor:
    def __init__(self, memory_store):
        self.memory_store = memory_store

    async def generate_energy_report(self, household_id: str, period: str) -> Dict:
        """Generate energy usage report"""
        # Get device interactions for period
        end_date = datetime.now()
        if period == 'week':
            start_date = end_date - timedelta(days=7)
        elif period == 'month':
            start_date = end_date - timedelta(days=30)
        else:  # day
            start_date = end_date - timedelta(days=1)

        interactions = await self.memory_store.get_device_interactions(
            household_id, start_date, end_date
        )

        # Process data
        df = pd.DataFrame(interactions)

        # Calculate energy consumption
        energy_data = self._calculate_energy_consumption(df)

        # Generate insights
        insights = self._generate_energy_insights(energy_data)

        return {
            'period': period,
            'total_consumption': energy_data['total_kwh'],
            'device_breakdown': energy_data['by_device'],
            'cost_estimate': energy_data['estimated_cost'],
            'insights': insights,
            'comparison': await self._get_period_comparison(household_id, period)
        }
```

### 4. Set Up Remote Control Gateway

```python
# apps/remote_gateway/main.py
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI(title="SynHome Remote Gateway")

# CORS middleware for web clients
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class ConnectionManager:
    def __init__(self):
        self.active_connections: Dict[str, WebSocket] = {}

    async def connect(self, websocket: WebSocket, user_id: str):
        await websocket.accept()
        self.active_connections[user_id] = websocket

    def disconnect(self, user_id: str):
        if user_id in self.active_connections:
            del self.active_connections[user_id]

    async def send_personal_message(self, message: str, user_id: str):
        if user_id in self.active_connections:
            await self.active_connections[user_id].send_text(message)

manager = ConnectionManager()

@app.websocket("/ws/{user_id}")
async def websocket_endpoint(websocket: WebSocket, user_id: str):
    await manager.connect(websocket, user_id)
    try:
        while True:
            data = await websocket.receive_text()
            # Process device commands
            response = await process_device_command(user_id, data)
            await websocket.send_text(response)
    except WebSocketDisconnect:
        manager.disconnect(user_id)

async def process_device_command(user_id: str, command_data: str) -> str:
    """Process device control command"""
    try:
        command = json.loads(command_data)

        # Validate permissions
        if not await validate_device_access(user_id, command['device_id']):
            return json.dumps({"error": "Permission denied"})

        # Execute command through device manager
        result = await device_manager.execute_command(
            command['device_id'],
            command['action'],
            command.get('parameters', {})
        )

        # Store in memory for learning
        await memory_store.store_interaction(user_id, command, result)

        return json.dumps({
            "success": True,
            "result": result,
            "timestamp": datetime.now().isoformat()
        })

    except Exception as e:
        return json.dumps({
            "success": False,
            "error": str(e),
            "timestamp": datetime.now().isoformat()
        })
```

### 5. Configure Services

```yaml
# config/memory_config.yaml
memory:
  storage:
    type: "chromadb"
    path: "./data/memory"

  compression:
    working_memory_hours: 24
    episodic_retention_days: 30
    semantic_retention_days: 365

  embedding:
    model: "all-MiniLM-L6-v2"
    dimension: 384

  redis:
    host: "localhost"
    port: 6379
    db: 0

learning:
  pattern_detection:
    min_frequency: 3
    confidence_threshold: 0.6

  batch_processing:
    interval_hours: 6
    batch_size: 1000
```

```yaml
# config/remote_config.yaml
remote_control:
  websocket:
    host: "0.0.0.0"
    port: 8001
    max_connections: 1000

  authentication:
    jwt_secret: "${JWT_SECRET}"
    token_expiry_hours: 24
    refresh_token_days: 30

  sessions:
    max_sessions_per_user: 5
    session_timeout_minutes: 30

  sharing:
    max_devices_per_share: 10
    default_expiry_hours: 24
    max_expiry_hours: 8760  # 1 year
```

## Development Workflow

### 1. Set Up Development Environment
```bash
# Clone repository
git clone <repository-url>
cd synhome

# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Set up Redis
docker run -d -p 6379:6379 redis:alpine

# Initialize databases
python scripts/init_memory_db.py
python scripts/init_analytics_db.py
```

### 2. Run Services
```bash
# Start memory service
python -m apps.memory_service.main

# Start analytics API
python -m apps.analytics_api.main

# Start remote gateway
python -m apps.remote_gateway.main

# Start main SynHome application with new features
python -m apps.main.main --with-smart-features
```

### 3. Run Tests
```bash
# Run all tests
pytest tests/ -v

# Run specific feature tests
pytest tests/test_memory/ -v
pytest tests/test_patterns/ -v
pytest tests/test_analytics/ -v
pytest tests/test_remote/ -v

# Run with coverage
pytest --cov=libs --cov-report=html tests/
```

## API Usage Examples

### Store Memory Entry
```python
import requests

# Store device interaction memory
memory_data = {
    "type": "episodic",
    "content": {
        "device_id": "thermostat_living_room",
        "action": "set_temperature",
        "parameters": {"temperature": 23},
        "result": {"success": True, "new_temperature": 23}
    },
    "context": {
        "time_of_day": "evening",
        "outdoor_temperature": 18,
        "user_activity": "watching_tv"
    },
    "importance_score": 0.7
}

response = requests.post(
    "http://localhost:8000/api/v1/memory",
    json=memory_data,
    headers={"Authorization": "Bearer <token>"}
)
```

### Get User Patterns
```python
# Get learned patterns
response = requests.get(
    "http://localhost:8000/api/v1/patterns",
    params={"active_only": True, "min_confidence": 0.6},
    headers={"Authorization": "Bearer <token>"}
)

patterns = response.json()["patterns"]
for pattern in patterns:
    print(f"Pattern: {pattern['name']}")
    print(f"Confidence: {pattern['confidence']}")
    print(f"Description: {pattern['description']}")
```

### Remote Device Control
```javascript
// WebSocket connection for real-time control
const ws = new WebSocket('ws://localhost:8001/ws/user123');

ws.onopen = function(event) {
    console.log('Connected to remote control');
};

ws.onmessage = function(event) {
    const response = JSON.parse(event.data);
    console.log('Device response:', response);
};

// Send device command
const command = {
    device_id: 'light_kitchen',
    action: 'set_brightness',
    parameters: { brightness: 80 }
};

ws.send(JSON.stringify(command));
```

## Monitoring and Debugging

### Memory System Monitoring
```python
# Monitor memory usage
from libs.memory.storage import MemoryStore

memory_store = MemoryStore(config)

# Get memory statistics
stats = await memory_store.get_statistics()
print(f"Total memories: {stats['total_count']}")
print(f"Memory usage: {stats['storage_mb']} MB")
print(f"Compression ratio: {stats['compression_ratio']}")

# Monitor pattern detection
from libs.patterns.detector import PatternDetector

detector = PatternDetector(memory_store)
patterns = await detector.detect_all_patterns(user_id)
print(f"Active patterns: {len(patterns)}")
```

### Performance Monitoring
```python
# Monitor response times
import time
from functools import wraps

def monitor_performance(func):
    @wraps(func)
    async def wrapper(*args, **kwargs):
        start_time = time.time()
        result = await func(*args, **kwargs)
        end_time = time.time()

        # Log performance metrics
        logger.info(f"{func.__name__} took {end_time - start_time:.3f}s")
        return result
    return wrapper
```

## Troubleshooting

### Common Issues

1. **Memory Storage Errors**
   - Check Redis connection
   - Verify ChromaDB permissions
   - Monitor storage space

2. **Pattern Detection Not Working**
   - Ensure sufficient memory data (minimum 30 days)
   - Check confidence thresholds
   - Verify time zone settings

3. **Remote Connection Issues**
   - Check WebSocket port accessibility
   - Verify JWT token validity
   - Monitor session timeouts

4. **Analytics Performance**
   - Optimize database queries
   - Implement data pagination
   - Use caching for frequent queries

### Debug Tools
```bash
# Check Redis connection
redis-cli ping

# Monitor memory storage
python -m libs.memory.debug --check-storage

# Test WebSocket connection
wscat -c ws://localhost:8001/ws/test_user

# Analyze memory data
python -m libs.analytics.debug --analyze-data
```

## Next Steps

1. **Complete Phase 1 Implementation**
   - Implement all memory components
   - Set up pattern detection
   - Create analytics processing

2. **Integration Testing**
   - Test with existing SynHome devices
   - Validate memory retention policies
   - Test remote control functionality

3. **Performance Optimization**
   - Optimize memory compression
   - Implement advanced caching
   - Scale for multiple households

4. **Security Review**
   - Validate authentication flows
   - Test permission systems
   - Review data encryption

For detailed implementation guidance, refer to the [research.md](research.md) and [data-model.md](data-model.md) files.
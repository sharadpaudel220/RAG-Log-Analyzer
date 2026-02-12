# API Integration Guide - Agentic RAG Log Analyzer

## 🔌 Multi-Source Log Integration

The Agentic RAG Log Analyzer supports multiple methods for ingesting logs from different sources. This guide covers all integration options.

---

## 📋 Table of Contents

1. [Supported Log Types](#supported-log-types)
2. [Ingestion Methods](#ingestion-methods)
3. [API Authentication](#api-authentication)
4. [Integration Examples](#integration-examples)
5. [Log Format Specifications](#log-format-specifications)
6. [Best Practices](#best-practices)

---

## 🗂️ Supported Log Types

### 1. **System Logs**
- Operating system logs (syslog, Windows Event Log)
- Kernel messages
- System service logs

### 2. **Network Logs**
- Router logs
- Switch logs
- Firewall logs
- Load balancer logs
- VPN logs

### 3. **Application Logs**
- Application server logs
- Microservice logs
- API logs
- Custom application logs

### 4. **Security/Audit Logs**
- Authentication logs
- Authorization logs
- Security event logs
- Compliance audit trails

### 5. **Database Logs**
- Query logs
- Error logs
- Slow query logs
- Transaction logs

### 6. **Web Server Logs**
- Apache logs
- Nginx logs
- IIS logs
- Access logs

### 7. **Container Logs**
- Docker container logs
- Kubernetes pod logs
- Container orchestration logs

### 8. **Cloud Service Logs**
- AWS CloudWatch
- Azure Monitor
- Google Cloud Logging

---

## 🔄 Ingestion Methods

### Method 1: REST API (Push)

**Best for**: Real-time log streaming, custom integrations

```bash
POST http://localhost:5001/api/ingest
Headers:
  X-API-Key: your-api-key-here
  Content-Type: application/json
```

**Single Log:**
```json
{
  "message": "ERROR: Connection timeout to database",
  "timestamp": "2024-01-15T10:23:45Z",
  "severity": "ERROR",
  "hostname": "web-server-01",
  "application": "api-service"
}
```

**Batch Logs:**
```json
[
  {
    "message": "ERROR: Connection timeout",
    "timestamp": "2024-01-15T10:23:45Z",
    "severity": "ERROR"
  },
  {
    "message": "INFO: Request processed",
    "timestamp": "2024-01-15T10:23:46Z",
    "severity": "INFO"
  }
]
```

**Response:**
```json
{
  "success": true,
  "processed": 2,
  "anomalies_detected": 1,
  "anomalies": [
    {
      "log": {...},
      "confidence": 0.85,
      "alert": {...}
    }
  ]
}
```

---

### Method 2: Webhook Receiver

**Best for**: Integration with monitoring tools, alerting systems

```bash
POST http://localhost:5001/api/ingest/webhook/{source_id}
Content-Type: application/json
```

**No authentication required for webhooks** (source-specific endpoint)

**Example:**
```bash
curl -X POST http://localhost:5001/api/ingest/webhook/prod-alerts \
  -H "Content-Type: application/json" \
  -d '{
    "message": "CRITICAL: Disk space at 95%",
    "timestamp": "2024-01-15T10:23:45Z",
    "severity": "CRITICAL"
  }'
```

---

### Method 3: File Upload

**Best for**: Batch processing, historical analysis

```bash
POST http://localhost:5001/api/ingest/upload
Content-Type: multipart/form-data
```

**Form Data:**
- `file`: Log file (txt, log, json, csv)
- `source_id`: Source identifier
- `source_type`: Log type (system, network, application, etc.)

**Example:**
```bash
curl -X POST http://localhost:5001/api/ingest/upload \
  -F "file=@/path/to/logs.log" \
  -F "source_id=prod-servers" \
  -F "source_type=application"
```

---

## 🔐 API Authentication

### Creating a Log Source

1. **Via Web UI:**
   - Navigate to http://localhost:5001/sources
   - Click "Add Source"
   - Fill in source details
   - Copy the generated API key

2. **Via API:**
```bash
curl -X POST http://localhost:5001/api/sources \
  -H "Content-Type: application/json" \
  -d '{
    "id": "prod-web-servers",
    "name": "Production Web Servers",
    "source_type": "application",
    "ingestion_method": "api",
    "metadata": {
      "description": "Production web server logs"
    }
  }'
```

**Response includes API key:**
```json
{
  "success": true,
  "source": {...},
  "api_key": "a1b2c3d4e5f6g7h8i9j0k1l2m3n4o5p6"
}
```

⚠️ **Important**: Save the API key securely. It cannot be retrieved later.

---

## 💻 Integration Examples

### Python Client

```python
import requests
import json
from datetime import datetime

class LogAnalyzerClient:
    def __init__(self, base_url, api_key):
        self.base_url = base_url
        self.api_key = api_key
        self.headers = {
            'X-API-Key': api_key,
            'Content-Type': 'application/json'
        }
    
    def send_log(self, message, severity='INFO', **kwargs):
        """Send a single log entry"""
        log_data = {
            'message': message,
            'timestamp': datetime.utcnow().isoformat() + 'Z',
            'severity': severity,
            **kwargs
        }
        
        response = requests.post(
            f'{self.base_url}/api/ingest',
            headers=self.headers,
            json=log_data
        )
        return response.json()
    
    def send_batch(self, logs):
        """Send multiple log entries"""
        response = requests.post(
            f'{self.base_url}/api/ingest',
            headers=self.headers,
            json=logs
        )
        return response.json()

# Usage
client = LogAnalyzerClient(
    base_url='http://localhost:5001',
    api_key='your-api-key-here'
)

# Send single log
result = client.send_log(
    message='ERROR: Database connection failed',
    severity='ERROR',
    hostname='db-server-01',
    application='user-service'
)

print(f"Anomaly detected: {result['anomalies_detected']}")
```

---

### Node.js Client

```javascript
const axios = require('axios');

class LogAnalyzerClient {
    constructor(baseUrl, apiKey) {
        this.baseUrl = baseUrl;
        this.apiKey = apiKey;
    }
    
    async sendLog(message, severity = 'INFO', metadata = {}) {
        const logData = {
            message,
            timestamp: new Date().toISOString(),
            severity,
            ...metadata
        };
        
        try {
            const response = await axios.post(
                `${this.baseUrl}/api/ingest`,
                logData,
                {
                    headers: {
                        'X-API-Key': this.apiKey,
                        'Content-Type': 'application/json'
                    }
                }
            );
            return response.data;
        } catch (error) {
            console.error('Error sending log:', error.message);
            throw error;
        }
    }
    
    async sendBatch(logs) {
        try {
            const response = await axios.post(
                `${this.baseUrl}/api/ingest`,
                logs,
                {
                    headers: {
                        'X-API-Key': this.apiKey,
                        'Content-Type': 'application/json'
                    }
                }
            );
            return response.data;
        } catch (error) {
            console.error('Error sending batch:', error.message);
            throw error;
        }
    }
}

// Usage
const client = new LogAnalyzerClient(
    'http://localhost:5001',
    'your-api-key-here'
);

client.sendLog(
    'ERROR: Payment processing failed',
    'ERROR',
    { hostname: 'payment-server', user_id: '12345' }
).then(result => {
    console.log('Anomalies detected:', result.anomalies_detected);
});
```

---

### Bash/cURL Script

```bash
#!/bin/bash

# Configuration
API_URL="http://localhost:5001/api/ingest"
API_KEY="your-api-key-here"

# Function to send log
send_log() {
    local message="$1"
    local severity="${2:-INFO}"
    
    curl -X POST "$API_URL" \
        -H "X-API-Key: $API_KEY" \
        -H "Content-Type: application/json" \
        -d "{
            \"message\": \"$message\",
            \"timestamp\": \"$(date -u +%Y-%m-%dT%H:%M:%SZ)\",
            \"severity\": \"$severity\",
            \"hostname\": \"$(hostname)\"
        }"
}

# Usage
send_log "ERROR: Service unavailable" "ERROR"
send_log "INFO: Backup completed successfully" "INFO"
```

---

### Fluentd Integration

```ruby
# fluent.conf
<source>
  @type tail
  path /var/log/application/*.log
  pos_file /var/log/td-agent/application.pos
  tag application.logs
  <parse>
    @type json
  </parse>
</source>

<match application.logs>
  @type http
  endpoint http://localhost:5001/api/ingest
  headers {"X-API-Key":"your-api-key-here"}
  json_array true
  <buffer>
    flush_interval 10s
  </buffer>
</match>
```

---

### Logstash Integration

```ruby
# logstash.conf
input {
  file {
    path => "/var/log/application/*.log"
    start_position => "beginning"
    codec => json
  }
}

filter {
  mutate {
    add_field => {
      "timestamp" => "%{@timestamp}"
    }
  }
}

output {
  http {
    url => "http://localhost:5001/api/ingest"
    http_method => "post"
    headers => {
      "X-API-Key" => "your-api-key-here"
      "Content-Type" => "application/json"
    }
    format => "json"
  }
}
```

---

## 📝 Log Format Specifications

### System Logs
```json
{
  "message": "systemd[1]: Started Session 123 of user root",
  "timestamp": "2024-01-15T10:23:45Z",
  "severity": "INFO",
  "hostname": "server-01",
  "process": "systemd",
  "pid": 1
}
```

### Network Logs
```json
{
  "message": "DENY TCP 192.168.1.100:45678 -> 10.0.0.5:22",
  "timestamp": "2024-01-15T10:23:45Z",
  "level": "WARNING",
  "device": "firewall-01",
  "interface": "eth0",
  "src_ip": "192.168.1.100",
  "dst_ip": "10.0.0.5",
  "protocol": "TCP"
}
```

### Application Logs
```json
{
  "message": "Failed to connect to database",
  "timestamp": "2024-01-15T10:23:45Z",
  "level": "ERROR",
  "app_name": "user-service",
  "module": "database",
  "function": "connect",
  "line": 45
}
```

### Security Logs
```json
{
  "message": "Failed login attempt",
  "timestamp": "2024-01-15T10:23:45Z",
  "severity": "WARNING",
  "event_type": "authentication",
  "user": "admin",
  "src_ip": "192.168.1.100",
  "action": "login",
  "result": "failed"
}
```

### Web Server Logs
```json
{
  "message": "GET /api/users 200 45ms",
  "timestamp": "2024-01-15T10:23:45Z",
  "client_ip": "192.168.1.100",
  "method": "GET",
  "path": "/api/users",
  "status_code": 200,
  "response_time": 45,
  "user_agent": "Mozilla/5.0..."
}
```

---

## ✅ Best Practices

### 1. **Batch Processing**
- Send logs in batches of 10-100 for better performance
- Use batch API for high-volume scenarios

### 2. **Error Handling**
- Implement retry logic with exponential backoff
- Log failed submissions for later retry
- Monitor API response codes

### 3. **Rate Limiting**
- Respect rate limits (if implemented)
- Implement client-side throttling
- Use queuing for burst traffic

### 4. **Security**
- Store API keys securely (environment variables, secrets manager)
- Use HTTPS in production
- Rotate API keys periodically
- Implement IP whitelisting if needed

### 5. **Monitoring**
- Monitor ingestion success rates
- Track API latency
- Set up alerts for failed submissions
- Monitor anomaly detection rates

### 6. **Data Quality**
- Include timestamps in ISO 8601 format
- Provide severity levels consistently
- Include relevant metadata (hostname, application, etc.)
- Validate log format before sending

---

## 🔍 Troubleshooting

### Common Issues

**401 Unauthorized**
- Check API key is correct
- Verify API key header: `X-API-Key`

**403 Forbidden**
- Source may be disabled
- API key may be invalid or expired

**400 Bad Request**
- Check JSON format
- Verify required fields are present
- Validate timestamp format

**500 Internal Server Error**
- Check server logs
- Verify system is healthy: `GET /api/health`

---

## 📞 Support

For issues or questions:
- Check system health: http://localhost:5001/api/health
- Review logs: `logs/web_app.log`
- Test with sample data first

---

**Happy Logging! 🚀**

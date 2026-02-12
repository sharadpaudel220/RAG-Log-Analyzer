# System Architecture Documentation

## Overview

The Agentic RAG Framework implements a multi-layered architecture for intelligent log analysis with the following key characteristics:

- **Modular Design**: Each layer is independently testable and replaceable
- **Agentic Reasoning**: ReAct-style multi-step reasoning for complex analysis
- **Knowledge Grounding**: RAG-based approach with FAISS vector store
- **Comparative Evaluation**: Built-in baselines for rigorous comparison

## Architecture Layers

### 1. Input Layer

**Purpose**: Ingest raw log data from various sources

**Components**:
- `LogIngestion`: Handles file-based and stream-based log ingestion
- `RawLogEntry`: Data structure for unprocessed logs

**Supported Formats**:
- Plain text (.log, .txt)
- JSON logs
- Syslog format

**Key Features**:
- Timestamp extraction
- Format detection
- Batch and streaming modes
- Validation

### 2. Preprocessing Layer

**Purpose**: Parse and normalize raw logs into structured format

**Components**:
- `LogPreprocessor`: Main preprocessing orchestrator
- `ParsedLogEntry`: Structured log representation

**Technologies**:
- **Drain3**: Template-based log parsing
- **Regex**: Pattern matching for severity/component extraction

**Processing Steps**:
1. Template extraction using Drain3
2. Parameter extraction
3. Severity classification
4. Component identification
5. Timestamp normalization
6. Sequence generation

**Output**: Structured logs with:
- Template ID
- Parameters
- Severity level
- Component name
- Metadata

### 3. Knowledge Base Layer

**Purpose**: Store and retrieve domain knowledge for log analysis

**Components**:
- `KnowledgeBaseManager`: Manages document storage and indexing
- `KnowledgeDocument`: Document data structure

**Technologies**:
- **FAISS**: Vector similarity search (IndexFlatL2)
- **Sentence-Transformers**: Text embeddings (all-MiniLM-L6-v2)

**Knowledge Types**:
- Historical incidents
- Error documentation
- Troubleshooting guides
- Runbooks

**Operations**:
- Document ingestion and chunking
- Embedding generation
- Vector indexing
- Similarity search
- Persistence (pickle + FAISS index)

### 4. Retrieval Layer

**Purpose**: Retrieve relevant knowledge for log analysis

**Components**:
- `RetrievalSystem`: Orchestrates retrieval strategies
- `RetrievalResult`: Retrieved document with scores

**Retrieval Strategies**:
1. **Semantic**: Vector similarity search
2. **Keyword**: Term overlap matching
3. **Hybrid**: Weighted combination (0.7 semantic + 0.3 keyword)

**Features**:
- Top-k retrieval (default: 5)
- Similarity threshold filtering
- Context-aware re-ranking
- Result formatting

### 5. LLM Engine Layer

**Purpose**: Interface with Large Language Models for generation

**Components**:
- `LLMEngine`: LLM interface abstraction
- `LLMResponse`: Structured LLM output

**Technologies**:
- **Ollama**: Local LLM inference
- **Mistral 7B Instruct**: Generation model

**Capabilities**:
- Log anomaly analysis
- Alert explanation generation
- Structured information extraction
- Health checking

**Configuration**:
- Temperature: 0.1 (deterministic)
- Max tokens: 2048
- Timeout: 120s

### 6. Agentic Controller Layer

**Purpose**: Implement multi-step reasoning for complex analysis

**Components**:
- `AgenticController`: ReAct-style agent orchestrator
- `ReasoningStep`: Individual reasoning step
- `AgenticAnalysisResult`: Complete analysis with reasoning chain

**Reasoning Loop** (ReAct Pattern):
```
for step in 1..max_steps:
    1. THOUGHT: Analyze current state
    2. ACTION: Decide next action (retrieve/analyze/reflect/finish)
    3. OBSERVATION: Execute action and observe result
    4. UPDATE: Update context with new information
```

**Actions**:
- **RETRIEVE**: Get relevant knowledge from KB
- **ANALYZE**: Perform LLM-based analysis
- **REFLECT**: Self-assess analysis quality
- **FINISH**: Complete reasoning

**Configuration**:
- Max reasoning steps: 5
- Confidence threshold: 0.75
- Self-reflection: Enabled

### 7. Output Layer

**Purpose**: Generate structured, actionable alerts

**Components**:
- `AlertGenerator`: Alert creation and formatting
- `Alert`: Structured alert with metadata

**Alert Structure**:
```
- Alert ID
- Timestamp
- Severity (CRITICAL/HIGH/MEDIUM/LOW/INFO)
- Title
- Description
- Affected Component
- Reasoning Chain (optional)
- Source Attribution (optional)
- Recommendations
- Confidence Score
```

**Output Formats**:
- JSON (machine-readable)
- Human-readable text
- Structured dictionary

### 8. Baseline Systems

**Purpose**: Provide comparison baselines for evaluation

#### 8.1 Rule-Based System
- Pattern matching with regex
- Keyword-based detection
- Threshold-based triggering
- No learning capability

#### 8.2 Isolation Forest
- Classical ML anomaly detection
- TF-IDF vectorization
- Unsupervised learning
- Contamination-based threshold

#### 8.3 Non-Agentic RAG
- Single retrieve-then-generate pass
- No iterative reasoning
- Same LLM and retrieval as Agentic RAG
- Baseline for measuring agentic benefit

### 9. Evaluation Framework

**Purpose**: Measure and compare system performance

**Components**:
- `MetricsCalculator`: Compute performance metrics
- `SystemEvaluator`: Orchestrate evaluation
- `ResultVisualizer`: Generate plots
- `PerformanceMonitor`: Track efficiency

**Detection Metrics**:
- Precision, Recall, F1-Score
- False Positive Rate (FPR)
- False Negative Rate (FNR)
- Accuracy

**Efficiency Metrics**:
- Average latency (seconds/log)
- Throughput (logs/second)
- Memory usage (MB)
- Total processing time

**Statistical Tests**:
- Paired t-tests for significance
- Confidence intervals
- Effect size calculation

## Data Flow

```
Raw Logs
    ↓
[Input Layer] → RawLogEntry
    ↓
[Preprocessing] → ParsedLogEntry
    ↓
[Agentic Controller] ←→ [Retrieval System] ←→ [Knowledge Base]
    ↓                           ↓
[LLM Engine] ←------------------┘
    ↓
[Alert Generator] → Alert
    ↓
Output (JSON/Text)
```

## Agentic Reasoning Flow

```
Step 1: Initial Assessment
    Thought: "Need to analyze log with severity ERROR"
    Action: RETRIEVE
    Observation: "Retrieved 5 relevant documents about errors"

Step 2: Contextual Analysis
    Thought: "Have relevant knowledge, now analyze"
    Action: ANALYZE
    Observation: "LLM analysis indicates connection timeout"

Step 3: Confidence Check
    Thought: "Analysis confidence is 0.85, sufficient"
    Action: FINISH
    Observation: "Analysis complete"

→ Generate Alert with reasoning chain
```

## Configuration Management

**File**: `config/config.yaml`

**Sections**:
- System settings
- Input/output configuration
- Preprocessing parameters
- Knowledge base settings
- Retrieval configuration
- LLM parameters
- Agentic controller settings
- Baseline configurations
- Evaluation metrics

## Technology Stack

| Layer | Technology | Purpose |
|-------|-----------|---------|
| Language | Python 3.12 | Core implementation |
| Log Parsing | Drain3 | Template extraction |
| Vector Store | FAISS | Similarity search |
| Embeddings | Sentence-Transformers | Text vectorization |
| LLM | Ollama + Mistral 7B | Generation |
| ML Baseline | Scikit-learn | Isolation Forest |
| Evaluation | Matplotlib/Seaborn | Visualization |
| Framework | LangChain (concepts) | Agentic patterns |

## Design Patterns

### 1. Strategy Pattern
- Multiple retrieval strategies (semantic, keyword, hybrid)
- Pluggable baseline systems

### 2. Observer Pattern
- Performance monitoring during evaluation
- Latency tracking

### 3. Factory Pattern
- Log entry creation
- Alert generation

### 4. Template Method
- Evaluation pipeline
- Analysis workflow

## Scalability Considerations

### Current Limitations
- Single-threaded processing
- In-memory knowledge base
- Local LLM inference

### Future Enhancements
- Distributed processing with Ray/Dask
- Database-backed knowledge store (PostgreSQL + pgvector)
- Cloud LLM APIs (OpenAI, Anthropic)
- Real-time streaming with Kafka
- Horizontal scaling with Kubernetes

## Security Considerations

- No sensitive data in logs (anonymized datasets)
- Local LLM inference (no data sent to cloud)
- Configuration via environment variables
- No hardcoded credentials

## Performance Characteristics

**Expected Performance** (on sample dataset):
- **Agentic RAG**: 2-5s per log, F1 ~0.90
- **Non-Agentic RAG**: 1-2s per log, F1 ~0.85
- **Isolation Forest**: 0.1-0.5s per log, F1 ~0.75
- **Rule-Based**: 0.01-0.05s per log, F1 ~0.70

**Trade-offs**:
- Agentic RAG: Highest accuracy, highest latency
- Rule-Based: Lowest latency, lowest accuracy
- Isolation Forest: Balanced, no interpretability
- Non-Agentic RAG: Good accuracy, moderate latency

## Testing Strategy

### Unit Tests
- Component-level testing
- Mock external dependencies
- Test data fixtures

### Integration Tests
- End-to-end pipeline
- System health checks
- Dataset validation

### Evaluation Tests
- Comparative benchmarks
- Statistical significance
- Performance profiling

## Deployment Options

### Local Development
```bash
python main.py analyze --log-file logs.log
```

### Docker Container
```dockerfile
FROM python:3.12
COPY . /app
RUN pip install -r requirements.txt
CMD ["python", "main.py", "evaluate"]
```

### Production Deployment
- Containerized with Docker
- Orchestrated with Kubernetes
- Monitored with Prometheus/Grafana
- Logged to ELK stack

## Maintenance and Updates

### Knowledge Base Updates
- Add new incident documents
- Retrain embeddings
- Rebuild FAISS index

### Model Updates
- Pull new Ollama models
- Update configuration
- Re-run evaluations

### Code Updates
- Modular architecture allows independent updates
- Backward compatibility maintained
- Version control with Git

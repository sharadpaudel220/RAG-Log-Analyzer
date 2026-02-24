# Dissertation Progress Presentation

**Sharad Chandra Paudel** (23057169) | **Supervisor**: Aadesh Tandukar | **Feb 24, 2026**

---

## 1. TOPIC

**Title**: Design and Evaluation of an Agentic RAG Framework for Real-Time System Log Analysis

**Research Questions**:
- **RQ1**: How accurately can an agentic RAG framework detect anomalies in distributed system logs?
- **RQ2**: Can an agentic RAG framework process system logs with latency suitable for real-time monitoring?

---

## 2. PROBLEM

**Challenge**: Modern systems generate terabytes of logs daily (HDFS: 11M entries, BGL: 4.7M entries) - manual analysis impossible

**Limitations of Current Approaches**:
- Rule-Based: Inflexible, high false positives
- ML Methods: Black-box, no explanations
- Deep Learning: No interpretability

**Impact**: $5,600/min downtime cost | **Gap**: No systematic study of agentic RAG for log analysis

---

## 3. SOLUTION - SYSTEM ARCHITECTURE

### 3.1 High-Level Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                         INPUT LAYER                             │
│  Raw System Logs (HDFS, BGL) - Unstructured text with metadata │
└────────────────────────────┬────────────────────────────────────┘
                             │
┌────────────────────────────▼────────────────────────────────────┐
│                    PREPROCESSING LAYER                          │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │ Drain3 Log Parser                                        │  │
│  │ • Template extraction (depth=4, similarity=0.4)          │  │
│  │ • Severity extraction (ERROR, WARN, INFO)                │  │
│  │ • Component identification                               │  │
│  │ • Timestamp normalization                                │  │
│  └──────────────────────────────────────────────────────────┘  │
└────────────────────────────┬────────────────────────────────────┘
                             │
┌────────────────────────────▼────────────────────────────────────┐
│                   CORE PROCESSING LAYER                         │
│  ┌──────────────────┐  ┌─────────────────┐  ┌───────────────┐ │
│  │ Knowledge Base   │  │ Retrieval System│  │  LLM Engine   │ │
│  │ (FAISS)          │  │ (Hybrid)        │  │  (Mistral 7B) │ │
│  │                  │  │                 │  │               │ │
│  │ • Incident docs  │◄─┤ • Semantic      │◄─┤ • Ollama API │ │
│  │ • Best practices │  │   search        │  │ • Temp: 0.1   │ │
│  │ • Embeddings     │  │ • Top-k (k=5)   │  │ • Max: 2048   │ │
│  │ • 384-dim vectors│  │ • Reranking     │  │               │ │
│  └──────────────────┘  └─────────────────┘  └───────────────┘ │
│                             ▲                        │          │
│  ┌──────────────────────────┴────────────────────────▼───────┐ │
│  │           AGENTIC CONTROLLER (ReAct Strategy)            │ │
│  │                                                           │ │
│  │  Step 1: THOUGHT  → Analyze log entry context           │ │
│  │  Step 2: ACTION   → Retrieve relevant knowledge         │ │
│  │  Step 3: OBSERVE  → Review retrieved information        │ │
│  │  Step 4: REFLECT  → Assess confidence & need more info  │ │
│  │  Step 5: DECIDE   → Generate final analysis or iterate  │ │
│  │                                                           │ │
│  │  • Max reasoning steps: 5                                │ │
│  │  • Confidence threshold: 0.75                            │ │
│  │  • Self-reflection enabled                               │ │
│  └───────────────────────────────────────────────────────────┘ │
└────────────────────────────┬────────────────────────────────────┘
                             │
┌────────────────────────────▼────────────────────────────────────┐
│                       OUTPUT LAYER                              │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │ Alert Generator                                          │  │
│  │ • Severity: CRITICAL/HIGH/MEDIUM/LOW                     │  │
│  │ • Anomaly classification (True/False)                    │  │
│  │ • Reasoning chain (interpretability)                     │  │
│  │ • Root cause analysis                                    │  │
│  │ • Actionable recommendations                             │  │
│  │ • Source attribution (knowledge base references)         │  │
│  └──────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────┘
```

### 3.2 Component Details

#### **Input Layer**
- Ingests raw logs from HDFS, BGL datasets
- Supports .log, .txt, .json formats
- Batch processing (1000 logs/batch)

#### **Preprocessing Layer - Drain3**
- **Purpose**: Convert unstructured logs to structured templates
- **Algorithm**: Tree-based log parsing
- **Parameters**: depth=4, similarity_threshold=0.4, max_children=100
- **Output**: ParsedLogEntry(timestamp, severity, component, template, raw_content)

#### **Knowledge Base - FAISS Vector Store**
- **Storage**: Historical incidents, troubleshooting docs, best practices
- **Embeddings**: sentence-transformers/all-MiniLM-L6-v2 (384-dim)
- **Index**: FAISS IndexFlatL2 for similarity search
- **Size**: ~500 documents, chunked at 512 tokens

#### **Retrieval System - Hybrid Approach**
- **Semantic Search**: Cosine similarity on embeddings
- **Keyword Matching**: BM25 for exact term matching
- **Top-k Retrieval**: k=5 most relevant documents
- **Reranking**: Cross-encoder for final ordering

#### **LLM Engine - Mistral 7B Instruct**
- **Deployment**: Local via Ollama (http://localhost:11434)
- **Model**: mistral:7b-instruct
- **Configuration**: temperature=0.1 (deterministic), max_tokens=2048
- **Prompting**: Structured prompts for anomaly detection

#### **Agentic Controller - ReAct (Reasoning + Acting)**
- **Strategy**: Multi-step iterative reasoning
- **Max Steps**: 5 reasoning iterations
- **Process**:
  1. **Thought**: Analyze current log context
  2. **Action**: Decide to retrieve, analyze, or reflect
  3. **Observation**: Process action results
  4. **Reflection**: Assess confidence (threshold: 0.75)
  5. **Decision**: Continue or finalize analysis
- **Output**: Reasoning chain + final analysis

#### **Alert Generator**
- **Classification**: Binary (anomaly/normal) + severity level
- **Reasoning Chain**: Full thought process for interpretability
- **Recommendations**: Actionable next steps
- **Attribution**: Links to knowledge base sources

### 3.3 Data Flow Example

```
1. Raw Log: "2024-01-15 ERROR [DataNode] Block blk_123 corrupt"
   ↓
2. Drain3: Template="Block <*> corrupt", Severity=ERROR
   ↓
3. Retrieval: Top-5 docs about block corruption
   ↓
4. Agentic Reasoning:
   - Step 1: "This is a block corruption error"
   - Step 2: Retrieve corruption handling docs
   - Step 3: "Similar to incident #45 - disk failure"
   - Step 4: Confidence=0.85 (high)
   - Step 5: Generate alert
   ↓
5. Alert: CRITICAL | Anomaly=True | Cause="Disk failure" | 
          Action="Check disk health on DataNode"
```

### 3.4 Technology Stack

**Core**: Python 3.9+, LangChain, FAISS, Drain3  
**LLM**: Mistral 7B via Ollama  
**ML**: Scikit-learn (baselines)  
**Viz**: Matplotlib, Seaborn  
**Datasets**: HDFS (2k), BGL (2k) with ground truth labels

---

## 4. EVALUATION & ROADMAP

### Evaluation Approach
**Metrics**: F1-Score, Precision, Recall, Latency, Throughput, Memory  
**Method**: 70/30 train-test split on HDFS & BGL datasets  
**Output**: Performance metrics + visualization plots

### Timeline (11 weeks: Feb 16 - May 5, 2026)

| Phase | Status | Deliverables |
|-------|--------|--------------|
| Requirements (Feb 16-25) | ✅ Done | Literature, datasets |
| Design (Feb 26-Mar 7) | ✅ Done | Architecture |
| Implementation (Mar 8-31) | ✅ Done | All systems operational |
| Testing (Apr 1-10) | 🔄 Current | Validation |
| Evaluation (Apr 11-20) | ⏳ Next | Run experiments |
| Writing (Apr 21-May 5) | ⏳ Pending | Dissertation |

### Current Status: 75% Complete ✅
- ✅ All systems implemented & tested
- ✅ Datasets ready with labels
- ⏳ Next: Run evaluations this week

---

## SUMMARY

**System**: 4-layer agentic RAG with multi-step reasoning  
**Progress**: Implementation complete, ready for evaluation  
**Timeline**: On track for May 5 submission

**Sharad Chandra Paudel** | London Metropolitan University

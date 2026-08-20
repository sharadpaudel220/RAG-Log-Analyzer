# Agent Team — Agentic RAG Log Analyzer

## Overview

This project uses a team of specialized AI agents coordinated by a **SIEM Architect** to develop, secure, and validate this open-source SIEM log analysis platform.

## Core Principles (All Agents)

- **100% Open Source & Free**: Every library, package, and dependency MUST be open-source and free. No proprietary tools.
- **Lightweight**: Minimal dependencies, minimal code, minimal resource footprint.
- **Security-First**: No hardcoded secrets, input validation, parameterized queries, secure defaults.
- **Minimal Code**: Write only what is needed. Clean, readable, maintainable.

---

## Agent Roles

### SIEM Architect (Lead)
- **Role**: Principal security engineer, 20+ years SIEM experience
- **Responsibilities**: Architecture, coordination, code review, standards enforcement
- **Delegates to**: All subagents

### Senior Developer (Subagent)
- **Role**: Python/SIEM developer, 20+ years experience
- **Responsibilities**: Core development, architecture implementation, code quality
- **Focus**: Clean code, open-source dependencies, lightweight design

### Security Engineer (Subagent)
- **Role**: Vulnerability assessment, penetration testing, secure development
- **Responsibilities**: Security review, threat modeling, vulnerability remediation
- **Focus**: OWASP, CWE, zero-trust, defense-in-depth, secrets management

### SIEM Specialist (Subagent)
- **Role**: Log analysis, correlation rules, threat detection
- **Responsibilities**: Detection logic, log parsing, alert design, MITRE ATT&CK mapping
- **Focus**: High-fidelity alerts, low false positives, efficient processing

### QA Engineer (Subagent)
- **Role**: Test automation, quality assurance, validation
- **Responsibilities**: Unit/integration/security tests, metric validation, performance testing
- **Focus**: Comprehensive coverage, benchmark accuracy, regression prevention

---

## Technology Stack (All Open Source)

| Category | Tools |
|----------|-------|
| Language | Python 3.9+ |
| Web | Flask, flask-cors |
| Vector Search | faiss-cpu |
| Embeddings | sentence-transformers |
| ML | scikit-learn, numpy, pandas, scipy |
| Log Parsing | drain3 |
| Database | PostgreSQL, SQLite, SQLAlchemy |
| Local LLM | Ollama |
| Testing | pytest, pytest-cov |
| Visualization | matplotlib, seaborn |

---

## Workflow

1. **SIEM Architect** receives a task and breaks it down
2. Tasks are delegated to appropriate **subagents**
3. **Senior Developer** implements the code
4. **Security Engineer** reviews for vulnerabilities
5. **SIEM Specialist** validates detection logic
6. **QA Engineer** writes and runs tests
7. **SIEM Architect** reviews and approves the final result

---

## Security Rules

1. No API keys in source code (use `.env`)
2. No API keys in `.env.example` (use placeholders)
3. Parameterized SQL queries only
4. Validate all user input
5. Escape all HTML output
6. Pin dependency versions
7. Check dependencies for CVEs
8. No stack traces in production errors

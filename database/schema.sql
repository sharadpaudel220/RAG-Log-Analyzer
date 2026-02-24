-- PostgreSQL Schema for Log Analyzer System
-- Run this to manually create the database schema

-- Enable UUID extension
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- Enable pgvector extension for embeddings (optional, for future use)
-- CREATE EXTENSION IF NOT EXISTS vector;

-- Analysis Sessions Table
CREATE TABLE IF NOT EXISTS analysis_sessions (
    session_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    filename VARCHAR(255) NOT NULL,
    file_hash VARCHAR(64),
    system_type VARCHAR(50) NOT NULL,
    total_logs INTEGER NOT NULL,
    anomalies_detected INTEGER NOT NULL,
    analysis_time_seconds DECIMAL(10, 3),
    status VARCHAR(20) DEFAULT 'completed',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    meta JSONB
);

CREATE INDEX idx_sessions_created_at ON analysis_sessions(created_at DESC);
CREATE INDEX idx_sessions_system_type ON analysis_sessions(system_type);
CREATE INDEX idx_sessions_file_hash ON analysis_sessions(file_hash);

-- Uploaded Files Table
CREATE TABLE IF NOT EXISTS uploaded_files (
    file_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    session_id UUID REFERENCES analysis_sessions(session_id) ON DELETE CASCADE,
    filename VARCHAR(255) NOT NULL,
    file_size BIGINT,
    file_content TEXT,
    file_path VARCHAR(500),
    mime_type VARCHAR(100),
    uploaded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_files_session_id ON uploaded_files(session_id);

-- Log Entries Table
CREATE TABLE IF NOT EXISTS log_entries (
    log_id BIGSERIAL PRIMARY KEY,
    session_id UUID REFERENCES analysis_sessions(session_id) ON DELETE CASCADE,
    raw_content TEXT NOT NULL,
    template TEXT,
    template_id INTEGER,
    parameters TEXT[],
    timestamp TIMESTAMP,
    severity VARCHAR(20),
    component VARCHAR(100),
    source_file VARCHAR(255),
    line_number INTEGER,
    meta JSONB,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_logs_session_id ON log_entries(session_id);
CREATE INDEX idx_logs_severity ON log_entries(severity);
CREATE INDEX idx_logs_timestamp ON log_entries(timestamp);
CREATE INDEX idx_logs_template_id ON log_entries(template_id);

-- Anomalies Table
CREATE TABLE IF NOT EXISTS anomalies (
    anomaly_id BIGSERIAL PRIMARY KEY,
    session_id UUID REFERENCES analysis_sessions(session_id) ON DELETE CASCADE,
    log_id BIGINT REFERENCES log_entries(log_id) ON DELETE CASCADE,
    is_anomaly BOOLEAN NOT NULL,
    severity VARCHAR(20) NOT NULL,
    confidence_score DECIMAL(5, 4),
    anomaly_score DECIMAL(5, 4),
    final_analysis TEXT,
    matched_rules TEXT[],
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_anomalies_session_id ON anomalies(session_id);
CREATE INDEX idx_anomalies_log_id ON anomalies(log_id);
CREATE INDEX idx_anomalies_severity ON anomalies(severity);
CREATE INDEX idx_anomalies_is_anomaly ON anomalies(is_anomaly);

-- Reasoning Steps Table
CREATE TABLE IF NOT EXISTS reasoning_steps (
    step_id BIGSERIAL PRIMARY KEY,
    anomaly_id BIGINT REFERENCES anomalies(anomaly_id) ON DELETE CASCADE,
    step_number INTEGER NOT NULL,
    thought TEXT,
    action VARCHAR(50),
    action_input JSONB,
    observation TEXT,
    confidence DECIMAL(5, 4),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_reasoning_anomaly_id ON reasoning_steps(anomaly_id);
CREATE INDEX idx_reasoning_step_number ON reasoning_steps(step_number);

-- Retrieved Documents Table
CREATE TABLE IF NOT EXISTS retrieved_documents (
    retrieval_id BIGSERIAL PRIMARY KEY,
    anomaly_id BIGINT REFERENCES anomalies(anomaly_id) ON DELETE CASCADE,
    document_id VARCHAR(100),
    document_title VARCHAR(255),
    document_content TEXT,
    document_type VARCHAR(50),
    similarity_score DECIMAL(5, 4),
    relevance_score DECIMAL(5, 4),
    rank INTEGER,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_retrieved_anomaly_id ON retrieved_documents(anomaly_id);

-- Alerts Table
CREATE TABLE IF NOT EXISTS alerts (
    alert_id VARCHAR(50) PRIMARY KEY,
    anomaly_id BIGINT REFERENCES anomalies(anomaly_id) ON DELETE CASCADE,
    session_id UUID REFERENCES analysis_sessions(session_id) ON DELETE CASCADE,
    severity VARCHAR(20) NOT NULL,
    title VARCHAR(255) NOT NULL,
    description TEXT,
    affected_component VARCHAR(100),
    recommendations TEXT[],
    confidence_score DECIMAL(5, 4),
    meta JSONB,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_alerts_session_id ON alerts(session_id);
CREATE INDEX idx_alerts_severity ON alerts(severity);
CREATE INDEX idx_alerts_created_at ON alerts(created_at DESC);

-- Chat Messages Table
CREATE TABLE IF NOT EXISTS chat_messages (
    message_id BIGSERIAL PRIMARY KEY,
    session_id UUID REFERENCES analysis_sessions(session_id) ON DELETE CASCADE,
    role VARCHAR(20) NOT NULL,
    content TEXT NOT NULL,
    context JSONB,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_chat_session_id ON chat_messages(session_id);
CREATE INDEX idx_chat_created_at ON chat_messages(created_at);

-- Knowledge Documents Table
CREATE TABLE IF NOT EXISTS knowledge_documents (
    document_id VARCHAR(100) PRIMARY KEY,
    title VARCHAR(255) NOT NULL,
    content TEXT NOT NULL,
    doc_type VARCHAR(50),
    embedding DECIMAL[],
    meta JSONB,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_knowledge_doc_type ON knowledge_documents(doc_type);

-- System Stats Table
CREATE TABLE IF NOT EXISTS system_stats (
    stat_id INTEGER PRIMARY KEY DEFAULT 1,
    total_logs_analyzed BIGINT DEFAULT 0,
    total_anomalies_detected BIGINT DEFAULT 0,
    total_alerts_generated BIGINT DEFAULT 0,
    total_sessions INTEGER DEFAULT 0,
    last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Insert initial stats row
INSERT INTO system_stats (stat_id) VALUES (1) ON CONFLICT (stat_id) DO NOTHING;

-- Create update timestamp trigger function
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ language 'plpgsql';

-- Apply trigger to tables with updated_at
CREATE TRIGGER update_analysis_sessions_updated_at BEFORE UPDATE ON analysis_sessions
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_knowledge_documents_updated_at BEFORE UPDATE ON knowledge_documents
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

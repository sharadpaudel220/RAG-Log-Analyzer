# PostgreSQL Database Setup Guide

## Overview

The Log Analyzer system now uses PostgreSQL for persistent storage of all analysis sessions, logs, anomalies, alerts, and chat conversations. This replaces the previous JSON file-based storage.

## Prerequisites

- PostgreSQL 12 or higher
- Python 3.8+
- All dependencies from `requirements.txt`

## Quick Setup

### 1. Install PostgreSQL

**macOS (using Homebrew):**
```bash
brew install postgresql@15
brew services start postgresql@15
```

**Ubuntu/Debian:**
```bash
sudo apt-get update
sudo apt-get install postgresql postgresql-contrib
sudo service postgresql start
```

**Windows:**
Download and install from https://www.postgresql.org/download/windows/

### 2. Run Setup Script

```bash
cd log-analyzer
chmod +x setup_database.sh
./setup_database.sh
```

This will:
- Create the `log_analyzer` database
- Run the SQL schema to create all tables
- Set up indexes and triggers

### 3. Configure Environment Variables

Copy the example environment file:
```bash
cp .env.example .env
```

Edit `.env` with your database credentials:
```env
DB_HOST=localhost
DB_PORT=5432
DB_NAME=log_analyzer
DB_USER=postgres
DB_PASSWORD=your_password_here
```

### 4. Install Python Dependencies

```bash
pip install -r requirements.txt
```

### 5. Initialize Database

```bash
python src/database/init_db.py
```

This creates the tables and inserts default data.

### 6. Start the Application

```bash
python web_app_enhanced.py
```

## Manual Setup

If the automated script doesn't work, follow these steps:

### 1. Create Database

```bash
psql -U postgres
```

```sql
CREATE DATABASE log_analyzer;
\c log_analyzer
```

### 2. Run Schema

```bash
psql -U postgres -d log_analyzer -f database/schema.sql
```

### 3. Verify Tables

```sql
\dt
```

You should see all 10 tables:
- analysis_sessions
- uploaded_files
- log_entries
- anomalies
- reasoning_steps
- retrieved_documents
- alerts
- chat_messages
- knowledge_documents
- system_stats

## Database Schema

### Core Tables

**analysis_sessions** - Main table for each log analysis
- Stores session metadata, filename, system type
- Links to all related data via foreign keys

**log_entries** - Individual parsed log entries
- Raw content, template, severity, timestamp
- Linked to analysis session

**anomalies** - Detected anomalies from analysis
- Severity, confidence score, analysis results
- Linked to log entries and sessions

**reasoning_steps** - Agentic RAG reasoning chain
- Step-by-step thought process
- Linked to anomalies

**retrieved_documents** - RAG retrieved knowledge
- Documents used during analysis
- Similarity and relevance scores

**alerts** - Generated alerts for anomalies
- Title, description, recommendations
- Linked to anomalies and sessions

**chat_messages** - Chat conversation history
- User and assistant messages
- Linked to analysis sessions

**knowledge_documents** - Knowledge base for RAG
- Troubleshooting guides, best practices
- Embeddings for semantic search

**system_stats** - Overall system statistics
- Total logs analyzed, anomalies, alerts
- Updated in real-time

## Features

### 1. Persistent Storage
- All analysis sessions survive server restarts
- No data loss between sessions

### 2. Relational Integrity
- Foreign keys ensure data consistency
- Cascade deletes clean up related data

### 3. Efficient Queries
- Indexes on frequently queried columns
- Fast retrieval of sessions and logs

### 4. Chat History
- Full conversation tracking per session
- Context preserved across page refreshes

### 5. Analytics Ready
- Easy to generate reports and statistics
- Query historical data for insights

## API Endpoints Using Database

All these endpoints now use PostgreSQL:

- `POST /api/analyze-file` - Creates session, saves logs, anomalies, alerts
- `GET /api/analysis-sessions` - Lists all sessions from database
- `GET /api/analysis-sessions/<id>` - Retrieves session with full details
- `DELETE /api/analysis-sessions` - Clears all sessions
- `POST /api/chat` - Saves chat messages to database
- `GET /api/stats` - Gets statistics from database

## Troubleshooting

### Connection Error

If you see "Failed to initialize database connection":

1. Check PostgreSQL is running:
   ```bash
   pg_isready
   ```

2. Verify credentials in `.env` file

3. Test connection manually:
   ```bash
   psql -U postgres -d log_analyzer
   ```

### Permission Denied

If you get permission errors:

```bash
sudo -u postgres psql
ALTER USER postgres WITH PASSWORD 'your_password';
```

### Tables Not Created

Run the initialization script:
```bash
python src/database/init_db.py
```

Or manually:
```bash
psql -U postgres -d log_analyzer -f database/schema.sql
```

### Reset Database

**WARNING: This deletes ALL data!**

```bash
python src/database/init_db.py --reset
```

Or manually:
```sql
DROP DATABASE log_analyzer;
CREATE DATABASE log_analyzer;
\c log_analyzer
\i database/schema.sql
```

## Migration from JSON Files

If you have existing analysis sessions in `data/analysis_sessions/`:

1. The old JSON files are no longer used
2. New analyses will be stored in PostgreSQL
3. Old sessions can be manually imported if needed

## BYOK (Bring Your Own Key) Support

The database supports storing API keys for external LLM providers:

Set in `.env`:
```env
OPENAI_API_KEY=sk-...
ANTHROPIC_API_KEY=sk-ant-...
GEMINI_API_KEY=...
```

These are loaded securely and not stored in the database.

## Performance Tips

1. **Connection Pooling**: Already configured (pool_size=10)
2. **Indexes**: Created on all foreign keys and frequently queried columns
3. **Batch Operations**: Use transactions for multiple inserts
4. **Cleanup**: Regularly delete old sessions to maintain performance

## Backup and Restore

### Backup
```bash
pg_dump -U postgres log_analyzer > backup.sql
```

### Restore
```bash
psql -U postgres -d log_analyzer < backup.sql
```

## Security

1. **Never commit `.env` file** - Contains database credentials
2. **Use strong passwords** for PostgreSQL user
3. **Restrict database access** to localhost in production
4. **Regular backups** of important data

## Support

For issues:
1. Check logs in `logs/web_app.log`
2. Verify database connection with `psql`
3. Review error messages in terminal
4. Check PostgreSQL logs: `/var/log/postgresql/`

## Next Steps

After setup:
1. Upload a log file via the web interface
2. Analyze it with Agentic RAG
3. Check database to see stored data:
   ```sql
   SELECT * FROM analysis_sessions;
   SELECT * FROM log_entries LIMIT 10;
   SELECT * FROM anomalies;
   ```
4. Use the chat feature - messages are saved to database
5. Refresh the page - your session persists!

#!/bin/bash
# Database setup script for Log Analyzer

echo "=== Log Analyzer Database Setup ==="
echo ""

# Check if PostgreSQL is installed
if ! command -v psql &> /dev/null; then
    echo "PostgreSQL is not installed. Please install PostgreSQL first."
    echo "On macOS: brew install postgresql"
    echo "On Ubuntu: sudo apt-get install postgresql"
    exit 1
fi

# Check if PostgreSQL is running
if ! pg_isready &> /dev/null; then
    echo "PostgreSQL is not running. Starting PostgreSQL..."
    if command -v brew &> /dev/null; then
        brew services start postgresql
    else
        sudo service postgresql start
    fi
    sleep 2
fi

# Database configuration
DB_NAME="log_analyzer"
DB_USER="postgres"

echo "Creating database: $DB_NAME"

# Create database
psql -U $DB_USER -c "CREATE DATABASE $DB_NAME;" 2>/dev/null || echo "Database already exists"

# Run schema
echo "Creating database schema..."
psql -U $DB_USER -d $DB_NAME -f database/schema.sql

echo ""
echo "=== Database setup complete! ==="
echo ""
echo "Database: $DB_NAME"
echo "User: $DB_USER"
echo ""
echo "Next steps:"
echo "1. Copy .env.example to .env and update database credentials"
echo "2. Install Python dependencies: pip install -r requirements.txt"
echo "3. Initialize database: python src/database/init_db.py"
echo "4. Start the application: python web_app_enhanced.py"

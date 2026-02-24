"""
Database initialization script
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from src.database.config import db_config
from src.database.models import SystemStats
from src.utils.logger import get_logger

logger = get_logger(__name__)

def init_database():
    """Initialize database with tables and default data"""
    try:
        logger.info("Initializing database...")
        
        if not db_config.initialize():
            logger.error("Failed to connect to database")
            return False
        
        logger.info("Creating tables...")
        db_config.create_tables()
        
        logger.info("Inserting default data...")
        with db_config.get_session() as session:
            stats = session.query(SystemStats).filter_by(stat_id=1).first()
            if not stats:
                stats = SystemStats(stat_id=1)
                session.add(stats)
                logger.info("Created default system stats")
        
        logger.info("Database initialization completed successfully!")
        return True
        
    except Exception as e:
        logger.error(f"Database initialization failed: {e}")
        return False

def reset_database():
    """Drop and recreate all tables (WARNING: destroys all data!)"""
    try:
        logger.warning("RESETTING DATABASE - ALL DATA WILL BE LOST!")
        
        if not db_config.initialize():
            logger.error("Failed to connect to database")
            return False
        
        logger.info("Dropping all tables...")
        db_config.drop_tables()
        
        logger.info("Creating tables...")
        db_config.create_tables()
        
        logger.info("Inserting default data...")
        with db_config.get_session() as session:
            stats = SystemStats(stat_id=1)
            session.add(stats)
        
        logger.info("Database reset completed!")
        return True
        
    except Exception as e:
        logger.error(f"Database reset failed: {e}")
        return False

if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description='Database initialization')
    parser.add_argument('--reset', action='store_true', help='Reset database (WARNING: destroys all data)')
    args = parser.parse_args()
    
    if args.reset:
        confirm = input("Are you sure you want to RESET the database? This will DELETE ALL DATA! (yes/no): ")
        if confirm.lower() == 'yes':
            reset_database()
        else:
            print("Reset cancelled")
    else:
        init_database()

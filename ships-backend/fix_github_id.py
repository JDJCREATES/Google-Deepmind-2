"""
Fix database schema drift: Add missing github_id column to users table.
Run with: python fix_github_id.py
"""
import asyncio
import os
import sys

# Add parent directory to path so we can import app modules
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from sqlalchemy import text
from app.database.connection import DatabaseConnection

async def add_github_id_column():
    """Add github_id column to users table if it doesn't exist."""
    from app.database.connection import DATABASE_URL
    print(f"🔗 Database URL: {DATABASE_URL.split('@')[1] if '@' in DATABASE_URL else DATABASE_URL}")
    
    engine = DatabaseConnection.get_engine()
    async with engine.begin() as conn:
        # Check if column exists
        result = await conn.execute(text("""
            SELECT column_name FROM information_schema.columns 
            WHERE table_name = 'users' AND column_name = 'github_id'
        """))
        exists = result.fetchone() is not None
        
        if exists:
            print("✅ github_id column already exists!")
            return
        
        # Add the column
        print("Adding github_id column...")
        await conn.execute(text("""
            ALTER TABLE users ADD COLUMN github_id VARCHAR(255)
        """))
        
        # Create unique index
        print("Creating unique index...")
        await conn.execute(text("""
            CREATE UNIQUE INDEX ix_users_github_id ON users (github_id)
        """))
        
        print("✅ Successfully added github_id column and index!")

if __name__ == "__main__":
    asyncio.run(add_github_id_column())

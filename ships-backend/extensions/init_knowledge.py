import asyncio
import os
import sys

# Ensure backend root is in path
current_dir = os.path.dirname(os.path.abspath(__file__))
backend_root = os.path.dirname(current_dir)
sys.path.append(backend_root)

from app.database.connection import DatabaseConnection
from app.models.knowledge import KnowledgeEntry
from app.database.base import Base

async def init_db():
    print("Connecting to database...")
    engine = DatabaseConnection.get_engine()
    
    print("Creating tables for Knowledge Base...")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    
    print("Success! Tables created.")
    await DatabaseConnection.close()

if __name__ == "__main__":
    asyncio.run(init_db())

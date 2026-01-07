"""
Knowledge Testing Utilities

Provides utilities for testing and debugging the Collective Intelligence system:
- View saved knowledge entries
- Test capture flow
- Query knowledge base
- Clear test data
"""

import asyncio
import logging
from typing import Optional, List
from datetime import datetime, timedelta

logger = logging.getLogger("ships.knowledge.testing")

# Set logging to show INFO level for knowledge modules
logging.getLogger("ships.knowledge").setLevel(logging.INFO)


async def list_knowledge_entries(
    limit: int = 20,
    entry_type: Optional[str] = None,
    user_id: Optional[str] = None,
) -> List[dict]:
    """
    List all knowledge entries in the database.
    
    Usage:
        import asyncio
        from app.services.knowledge.testing import list_knowledge_entries
        
        entries = asyncio.run(list_knowledge_entries())
        for e in entries:
            print(f"{e['type']} | {e['signature'][:50]} | conf={e['confidence']}")
    """
    from app.database import get_session
    from app.models import KnowledgeEntry
    from sqlalchemy import select, desc
    
    query = select(KnowledgeEntry).order_by(desc(KnowledgeEntry.created_at)).limit(limit)
    
    if entry_type:
        query = query.where(KnowledgeEntry.entry_type == entry_type)
    if user_id:
        query = query.where(KnowledgeEntry.user_id == user_id)
    
    entries = []
    async for db in get_session():
        result = await db.execute(query)
        for row in result.scalars():
            entries.append({
                "id": row.id,
                "type": row.entry_type,
                "signature": row.error_signature,
                "tech_stack": row.tech_stack,
                "confidence": round(row.confidence, 2),
                "success_count": row.success_count,
                "failure_count": row.failure_count,
                "visibility": row.visibility,
                "created_at": str(row.created_at),
                "solution_preview": row.get_solution()[:100] + "..." if row.get_solution() else None,
            })
        break
    
    return entries


async def get_entry_details(entry_id: str) -> Optional[dict]:
    """
    Get full details of a specific knowledge entry.
    
    Usage:
        details = asyncio.run(get_entry_details("ke_abc123"))
        print(details['solution'])
    """
    from app.database import get_session
    from app.models import KnowledgeEntry
    from sqlalchemy import select
    
    async for db in get_session():
        result = await db.execute(
            select(KnowledgeEntry).where(KnowledgeEntry.id == entry_id)
        )
        entry = result.scalar_one_or_none()
        
        if entry:
            return {
                "id": entry.id,
                "type": entry.entry_type,
                "signature": entry.error_signature,
                "tech_stack": entry.tech_stack,
                "solution": entry.get_solution(),
                "confidence": entry.confidence,
                "success_count": entry.success_count,
                "failure_count": entry.failure_count,
                "visibility": entry.visibility,
                "user_id": entry.user_id,
                "created_at": str(entry.created_at),
                "updated_at": str(entry.updated_at),
                "has_embedding": entry.context_embedding is not None,
            }
        break
    
    return None


async def search_knowledge(
    query: str,
    tech_stack: str = "unknown",
    entry_type: Optional[str] = None,
    limit: int = 5,
) -> List[dict]:
    """
    Search knowledge base for relevant entries.
    
    Usage:
        results = asyncio.run(search_knowledge("TypeError cannot read property"))
        for r in results:
            print(f"Score: {r['score']:.2f} | {r['suggestion']}")
    """
    from app.database import get_session
    from app.services.knowledge import retrieve_relevant_knowledge
    
    async for db in get_session():
        entry_types = [entry_type] if entry_type else None
        
        suggestions = await retrieve_relevant_knowledge(
            db=db,
            query=query,
            tech_stack=tech_stack,
            entry_types=entry_types,
            limit=limit,
        )
        
        return [
            {
                "entry_id": s.entry_id,
                "type": s.entry_type,
                "score": round(s.score, 2),
                "confidence": round(s.confidence, 2),
                "suggestion": s.suggestion[:200] + "..." if len(s.suggestion) > 200 else s.suggestion,
            }
            for s in suggestions
        ]
    
    return []


async def count_entries() -> dict:
    """Count entries by type."""
    from app.database import get_session
    from app.models import KnowledgeEntry
    from sqlalchemy import select, func
    
    async for db in get_session():
        result = await db.execute(
            select(
                KnowledgeEntry.entry_type,
                func.count(KnowledgeEntry.id)
            ).group_by(KnowledgeEntry.entry_type)
        )
        
        counts = {"total": 0}
        for row in result:
            counts[row[0]] = row[1]
            counts["total"] += row[1]
        
        return counts
    
    return {}


async def delete_test_entries(before_hours: int = 24) -> int:
    """
    Delete entries created in the last N hours (for testing cleanup).
    
    Usage:
        deleted = asyncio.run(delete_test_entries(before_hours=1))
        print(f"Deleted {deleted} test entries")
    """
    from app.database import get_session
    from app.models import KnowledgeEntry
    from sqlalchemy import delete
    
    cutoff = datetime.utcnow() - timedelta(hours=before_hours)
    
    async for db in get_session():
        result = await db.execute(
            delete(KnowledgeEntry).where(KnowledgeEntry.created_at >= cutoff)
        )
        await db.commit()
        return result.rowcount
    
    return 0


def print_entries(entries: List[dict]) -> None:
    """Pretty print knowledge entries."""
    if not entries:
        print("📭 No entries found")
        return
    
    print(f"\n📚 Found {len(entries)} knowledge entries:\n")
    print("-" * 80)
    
    for e in entries:
        print(f"🔹 [{e['type']}] {e['signature'][:60]}...")
        print(f"   Tech: {e['tech_stack']} | Conf: {e['confidence']} | Success: {e['success_count']}")
        print(f"   Created: {e['created_at']}")
        if e.get('solution_preview'):
            print(f"   Solution: {e['solution_preview'][:80]}...")
        print()


# CLI helper for quick testing
if __name__ == "__main__":
    import sys
    
    async def main():
        cmd = sys.argv[1] if len(sys.argv) > 1 else "list"
        
        if cmd == "list":
            entries = await list_knowledge_entries()
            print_entries(entries)
            
        elif cmd == "count":
            counts = await count_entries()
            print("\n📊 Knowledge Entry Counts:")
            for k, v in counts.items():
                print(f"   {k}: {v}")
                
        elif cmd == "search":
            query = sys.argv[2] if len(sys.argv) > 2 else "error"
            results = await search_knowledge(query)
            print(f"\n🔍 Search results for '{query}':")
            for r in results:
                print(f"   [{r['type']}] Score: {r['score']} - {r['suggestion'][:60]}...")
                
        elif cmd == "clean":
            deleted = await delete_test_entries(before_hours=1)
            print(f"🗑️ Deleted {deleted} test entries from last hour")
            
        else:
            print("Usage: python -m app.services.knowledge.testing [list|count|search|clean]")
    
    asyncio.run(main())

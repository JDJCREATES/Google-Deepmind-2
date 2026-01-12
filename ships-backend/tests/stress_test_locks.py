import asyncio
import sys
import os
import random
import logging

# Add app to path (assuming script is in ships-backend/tests/)
sys.path.append(os.path.join(os.path.dirname(__file__), ".."))

# Attempt to import LockManager
try:
    from app.services.lock_manager import LockManager
except ImportError:
    # Handle running from different CWD
    sys.path.append(os.getcwd())
    from app.services.lock_manager import LockManager

# Setup Logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(message)s', datefmt='%H:%M:%S')
logger = logging.getLogger("test")

async def simulated_agent(agent_id, target_file, lock_manager):
    """Simulates an agent trying to work on a file."""
    # Stagger start slightly to make it realistic
    await asyncio.sleep(random.uniform(0.01, 0.05))
    logger.info(f"[{agent_id}] 🏁 Started. Wants {target_file}")
    
    attempts = 0
    max_attempts = 20
    
    while attempts < max_attempts:
        # Try to acquire
        # Note: project_path is "TEST_PROJECT"
        if lock_manager.acquire("TEST_PROJECT", target_file, agent_id):
            logger.info(f"[{agent_id}] 🔒 ACQUIRED LOCK! Working on {target_file}...")
            
            # CRITICAL CHECK: Verify we actually own it
            owner = lock_manager.is_locked("TEST_PROJECT", target_file)
            if owner != agent_id:
                logger.error(f"[{agent_id}] 🚨 RACE CONDITION DETECTED! Thought I had lock, but owner is {owner}")
                return False
            
            # Simulate work (variable duration)
            work_time = random.uniform(0.2, 0.5)
            await asyncio.sleep(work_time)
            
            logger.info(f"[{agent_id}] 🔓 Done. Releasing {target_file}")
            lock_manager.release("TEST_PROJECT", target_file, agent_id)
            return True
        else:
            owner = lock_manager.is_locked("TEST_PROJECT", target_file)
            logger.info(f"[{agent_id}] ⏳ Blocked by {owner}. Retrying...")
            # Random backoff to prevent thundering herd
            await asyncio.sleep(random.uniform(0.1, 0.3))
            attempts += 1
            
    logger.error(f"[{agent_id}] ❌ STARVED after {attempts} attempts")
    return False

async def run_stress_test():
    # Use the Singleton instance
    lock_manager = LockManager.get_instance()
    # Clear any previous state
    lock_manager.clear_all_for_project("TEST_PROJECT")
    
    target_file = "src/concurrent_component.tsx"
    
    logger.info("==============================================")
    logger.info("⚔️  STARTING LOCK MANAGER STRESS TEST ⚔️")
    logger.info("   - 4 Agents")
    file_count = 1
    logger.info(f"   - {file_count} Shared Resource ({target_file})")
    logger.info("==============================================")
    
    # Spawn 4 agents concurrently
    agents = ["Agent_Alpha", "Agent_Beta", "Agent_Gamma", "Agent_Delta"]
    tasks = [simulated_agent(a, target_file, lock_manager) for a in agents]
    
    # Run them all
    results = await asyncio.gather(*tasks)
    
    logger.info("==============================================")
    logger.info("📊 TEST RESULTS")
    success_count = sum(results)
    
    for i, res in enumerate(results):
        status = "✅ Success" if res else "❌ Failed"
        logger.info(f"   - {agents[i]}: {status}")
        
    logger.info(f"Total Success: {success_count}/{len(agents)}")
    
    if success_count == len(agents):
        logger.info("✅ PASSED: Mutex logic holds. No race conditions.")
    else:
        logger.error("❌ FAILED: Some agents starved or crashed.")
    logger.info("==============================================")

if __name__ == "__main__":
    asyncio.run(run_stress_test())

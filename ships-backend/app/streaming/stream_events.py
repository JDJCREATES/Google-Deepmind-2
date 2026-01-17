from enum import Enum
from typing import Optional, Dict, Any, List
import uuid
import json
import time

class BlockType(str, Enum):
    TEXT = "text"           # Standard text response
    CODE = "code"           # Code block (file content)
    COMMAND = "command"     # Terminal command
    PLAN = "plan"           # Implementation Step/Plan
    THINKING = "thinking"   # Internal chain-of-thought
    TOOL_USE = "tool_use"   # Tool execution status
    ERROR = "error"         # Error messages

class StreamBlock:
    """
    Represents a single UI block (card) in the stream.
    """
    def __init__(self, block_type: BlockType, title: Optional[str] = None, metadata: Dict[str, Any] = None):
        self.id = str(uuid.uuid4())
        self.type = block_type
        self.title = title
        self.metadata = metadata or {}
        self.content = ""
        self.is_complete = False
        self.start_time = time.time()

    def to_event(self, event_type: str, delta: str = None) -> str:
        """Convert to JSON event string."""
        payload = {
            "type": event_type,
            "id": self.id,
            "block_type": self.type.value,
            "timestamp": int(time.time() * 1000)
        }
        
        if event_type == "block_start":
            if self.title: payload["title"] = self.title
            if self.metadata: payload["metadata"] = self.metadata
            
        if event_type == "block_delta":
            payload["content"] = delta
            
        if event_type == "block_end":
            payload["final_content"] = self.content
            payload["duration_ms"] = int((time.time() - self.start_time) * 1000)
            
        return json.dumps(payload)

class StreamBlockManager:
    """
    Manages the lifecycle of streaming blocks.
    Ensures valid state transitions (Start -> Delta -> End).
    """
    def __init__(self):
        self.active_block: Optional[StreamBlock] = None
        self.blocks: List[StreamBlock] = []
        
    def start_block(self, block_type: BlockType, title: Optional[str] = None, **metadata) -> str:
        """
        Start a new block. accessible via .active_block
        Auto-closes the previous block if open.
        """
        events = []
        
        # Close existing if open
        if self.active_block and not self.active_block.is_complete:
            events.append(self.end_current_block())
            
        # Create new
        self.active_block = StreamBlock(block_type, title, metadata)
        self.blocks.append(self.active_block)
        
        # Emit start
        events.append(self.active_block.to_event("block_start"))
        
        return "\n".join(filter(None, events))

    def append_delta(self, text: str) -> Optional[str]:
        """Append content to active block."""
        if not self.active_block or self.active_block.is_complete:
            # Fallback: Create default text block if none active
             # (Or should we simplify and ignore? Better to catch it)
             return self.start_block(BlockType.TEXT, title=None) + "\n" + self.append_delta(text)
             
        self.active_block.content += text
        return self.active_block.to_event("block_delta", delta=text)

    def end_current_block(self) -> Optional[str]:
        """Close the active block."""
        if not self.active_block or self.active_block.is_complete:
            return None
            
        self.active_block.is_complete = True
        return self.active_block.to_event("block_end")

    def ensure_block_type(self, block_type: BlockType, title: Optional[str] = None) -> Optional[str]:
        """Ensure the active block is of specific type. If not, start new one."""
        if self.active_block and self.active_block.type == block_type:
            return None
        return self.start_block(block_type, title)

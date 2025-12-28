import { VscNewFile, VscNewFolder, VscRefresh, VscCollapseAll } from 'react-icons/vsc';
import { useFileSystem } from '../../store/fileSystem';
import { useState } from 'react';

export default function ExplorerToolbar() {
  const { createNode, refreshFileTree, rootHandle } = useFileSystem();
  const [isCreating, setIsCreating] = useState(false);

  const handleCreate = async (type: 'file' | 'folder') => {
    if (!rootHandle) return;
    
    // Simple prompt for now - could be enhanced to an inline input in the tree later
    const name = window.prompt(`Enter ${type} name:`);
    if (!name) return;

    try {
      setIsCreating(true);
      await createNode(name, type);
    } catch (error) {
      alert(`Failed to create ${type}: ${error}`);
    } finally {
      setIsCreating(false);
    }
  };

  const handleRefresh = async () => {
      // Use the new refreshFileTree action (doesn't open picker)
      await refreshFileTree();
  };

  return (
    <div className="explorer-toolbar">
      <button 
        className="explorer-toolbar-btn" 
        onClick={() => handleCreate('file')}
        title="New File"
      >
        <VscNewFile size={14} />
      </button>
      <button 
        className="explorer-toolbar-btn" 
        onClick={() => handleCreate('folder')}
        title="New Folder"
      >
        <VscNewFolder size={14} />
      </button>
      <button 
        className="explorer-toolbar-btn" 
        onClick={handleRefresh}
        title="Refresh"
      >
        <VscRefresh size={14} />
      </button>
      <button 
        className="explorer-toolbar-btn" 
        title="Collapse All"
      >
        <VscCollapseAll size={14} />
      </button>
    </div>
  );
}

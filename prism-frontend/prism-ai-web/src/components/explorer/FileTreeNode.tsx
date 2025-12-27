import { useState, type MouseEvent as ReactMouseEvent } from 'react';
import { useFileSystem, type FileNode } from '../../store/fileSystem';
import { VscChevronRight, VscChevronDown, VscFile, VscFolder, VscFolderOpened } from 'react-icons/vsc';
import {
  SiTypescript,
  SiJavascript,
  SiHtml5,
  SiCss3,
  SiJson,
  SiPython
} from 'react-icons/si';

const getFileIcon = (filename: string) => {
  const ext = filename.split('.').pop()?.toLowerCase();
  switch (ext) {
    case 'ts':
    case 'tsx': return <SiTypescript color="#3178C6" size={14} />;
    case 'js':
    case 'jsx': return <SiJavascript color="#F7DF1E" size={14} />;
    case 'html': return <SiHtml5 color="#E34F26" size={14} />;
    case 'css': return <SiCss3 color="#1572B6" size={14} />;
    case 'json': return <SiJson color="#CBCB41" size={14} />; 
    case 'py': return <SiPython color="#3776AB" size={14} />;
    default: return <VscFile size={14} />;
  }
};

interface FileTreeNodeProps {
  node: FileNode;
  level: number;
}

export default function FileTreeNode({ node, level }: FileTreeNodeProps) {
  const [isOpen, setIsOpen] = useState(false);
  const { openFile, activeFile, selectedNodeId, setSelectedNode } = useFileSystem();

  const handleClick = (e: ReactMouseEvent<HTMLDivElement>) => {
    e.stopPropagation();
    setSelectedNode(node.id);
    
    if (node.type === 'folder') {
      setIsOpen(!isOpen);
    } else {
      openFile(node.id);
    }
  };

  const isActive = activeFile === node.id;
  const isSelected = selectedNodeId === node.id;

  return (
    <div>
      <div
        className={`file-tree-node ${isActive ? 'active' : ''} ${isSelected ? 'selected' : ''}`}
        style={{ 
            paddingLeft: `${level * 12 + 8}px`,
            backgroundColor: isSelected ? 'var(--selection-bg)' : undefined, 
        }}
        onClick={handleClick}
      >
        <span className="file-icon" style={{ marginRight: 4, display: 'flex', alignItems: 'center' }}>
          {node.type === 'folder' ? (
            isOpen ? <VscChevronDown size={14} /> : <VscChevronRight size={14} />
          ) : (
            <span style={{ width: 14 }}></span>
          )}
        </span>
        
        <span className="file-type-icon" style={{ marginRight: 6, display: 'flex', alignItems: 'center' }}>
          {node.type === 'folder' ? (
             isOpen ? <VscFolderOpened color="#dcb67a" size={16} /> : <VscFolder color="#dcb67a" size={16} />
          ) : (
            getFileIcon(node.name)
          )}
        </span>

        <span className="file-name" style={{ fontSize: '13px' }}>{node.name}</span>
      </div>
      
      {isOpen && node.children && (
        <div className="file-tree-children">
          {node.children.map((child: FileNode) => (
            <FileTreeNode key={child.id} node={child} level={level + 1} />
          ))}
        </div>
      )}
    </div>
  );
}

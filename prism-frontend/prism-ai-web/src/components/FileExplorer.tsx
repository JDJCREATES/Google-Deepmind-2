import { useState } from 'react';
import { useFileSystem, type FileNode } from '../store/fileSystem';
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
    case 'tsx': return <SiTypescript color="#3178C6" />;
    case 'js':
    case 'jsx': return <SiJavascript color="#F7DF1E" />;
    case 'html': return <SiHtml5 color="#E34F26" />;
    case 'css': return <SiCss3 color="#1572B6" />;
    case 'json': return <SiJson color="#CBCB41" />; 
    case 'py': return <SiPython color="#3776AB" />;
    default: return <VscFile />;
  }
};

interface FileTreeNodeProps {
  node: FileNode;
  level: number;
}

const FileTreeNode = ({ node, level }: FileTreeNodeProps) => {
  const [isOpen, setIsOpen] = useState(false);
  const { openFile, activeFile } = useFileSystem();



  const handleClick = () => {
    if (node.type === 'folder') {
      setIsOpen(!isOpen);
    } else {
      openFile(node.id); // This now triggers content loading
    }
  };

  const isActive = activeFile === node.id;

  return (
    <div>
      <div
        className={`file-tree-node ${isActive ? 'active' : ''}`}
        style={{ paddingLeft: `${level * 12 + 8}px` }}
        onClick={handleClick}
      >
        <span className="file-icon">
          {node.type === 'folder' ? (
            isOpen ? <VscChevronDown /> : <VscChevronRight />
          ) : (
            <span style={{ width: 16 }}></span>
          )}
        </span>
        
        <span className="file-type-icon">
          {node.type === 'folder' ? (
             isOpen ? <VscFolderOpened color="#dcb67a" /> : <VscFolder color="#dcb67a" />
          ) : (
            getFileIcon(node.name)
          )}
        </span>

        <span className="file-name">{node.name}</span>
      </div>
      
      {isOpen && node.children && (
        <div className="file-tree-children">
          {node.children.map(child => (
            <FileTreeNode key={child.id} node={child} level={level + 1} />
          ))}
        </div>
      )}
    </div>
  );
};

export default function FileExplorer() {
  const { files, openProjectFolder, rootHandle } = useFileSystem();

  if (!rootHandle || files.length === 0) {
    return (
      <div className="file-explorer empty">
        <div className="explorer-header">
          <span>EXPLORER</span>
        </div>
        <div className="empty-explorer-content">
          <p>No Folder Opened</p>
          <button className="open-folder-btn" onClick={openProjectFolder}>
            Open Folder
          </button>
        </div>
      </div>
    );
  }

  return (
    <div className="file-explorer">
      <div className="explorer-header">
        <span>EXPLORER</span>
      </div>
      <div className="explorer-content">
        {files.map(node => (
          <FileTreeNode key={node.id} node={node} level={0} />
        ))}
      </div>
    </div>
  );
}

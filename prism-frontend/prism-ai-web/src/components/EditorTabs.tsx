import { useFileSystem } from '../store/fileSystem';
import { VscClose } from 'react-icons/vsc';

// Helper to get file icon (simplified for tabs)
import { SiTypescript, SiJavascript, SiHtml5, SiCss3, SiJson, SiPython } from 'react-icons/si';
import { VscFile } from 'react-icons/vsc';

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

export default function EditorTabs() {
  const { openFiles, activeFile, setActiveFile, closeFile, getFile } = useFileSystem();

  if (openFiles.length === 0) return null;

  return (
    <div className="editor-tabs">
      {openFiles.map(fileId => {
        const file = getFile(fileId);
        if (!file) return null;

        const isActive = activeFile === fileId;
        
        return (
          <div
            key={fileId}
            className={`editor-tab ${isActive ? 'active' : ''}`}
            onClick={() => setActiveFile(fileId)}
            title={file.path}
          >
            <span className="tab-icon">{getFileIcon(file.name)}</span>
            <span className="tab-name">{file.name}</span>
            <span
              className="tab-close"
              onClick={(e) => {
                e.stopPropagation();
                closeFile(fileId);
              }}
            >
              <VscClose />
            </span>
          </div>
        );
      })}
    </div>
  );
}

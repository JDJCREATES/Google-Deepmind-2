import { useFileSystem } from '../store/fileSystem';
import ExplorerToolbar from './explorer/ExplorerToolbar';
import FileTree from './explorer/FileTree';

export default function FileExplorer() {
  const { files, openProjectFolder, rootHandle } = useFileSystem();

  if (!rootHandle || files.length === 0) {
    return (
      <div className="file-explorer empty">
        <div className="explorer-header" style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
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
    <div className="file-explorer" style={{ display: 'flex', flexDirection: 'column', height: '100%' }}>
      <div className="explorer-header">
        <span>EXPLORER</span>
        <ExplorerToolbar />
      </div>
      <div className="explorer-content" style={{ flex: 1, overflowY: 'auto' }}>
        <FileTree />
      </div>
    </div>
  );
}

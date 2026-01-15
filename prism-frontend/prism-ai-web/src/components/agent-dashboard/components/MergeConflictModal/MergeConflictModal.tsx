import React from 'react';
import { DiffEditor } from '@monaco-editor/react';
import './MergeConflictModal.css';

interface MergeConflictModalProps {
  isOpen: boolean;
  onClose: () => void;
  onResolve: (strategy: 'accept_agent' | 'accept_current') => void;
  files: Array<{
    path: string;
    original: string;
    modified: string;
  }>;
}

export const MergeConflictModal: React.FC<MergeConflictModalProps> = ({ 
  isOpen, 
  onClose, 
  onResolve,
  files 
}) => {
  const [selectedFile, setSelectedFile] = React.useState(0);
  
  if (!isOpen) return null;

  const currentFile = files[selectedFile];

  return (
    <div className="merge-modal-overlay">
      <div className="merge-modal">
        <header className="merge-modal__header">
          <h3>Merge Conflicts</h3>
          <div className="merge-modal__actions">
            <button onClick={() => onResolve('accept_current')} className="btn btn--secondary">
              Keep My Changes
            </button>
            <button onClick={() => onResolve('accept_agent')} className="btn btn--primary">
              Accept Agent Changes
            </button>
          </div>
        </header>

        <div className="merge-modal__content">
          <div className="merge-modal__file-list">
            {files.map((file, idx) => (
              <div 
                key={file.path}
                className={`file-item ${idx === selectedFile ? 'active' : ''}`}
                onClick={() => setSelectedFile(idx)}
              >
                {file.path}
              </div>
            ))}
          </div>
          
          <div className="merge-modal__editor">
             <DiffEditor
               height="100%"
               original={currentFile?.original}
               modified={currentFile?.modified}
               options={{
                 readOnly: true,
                 renderSideBySide: true
               }}
             />
          </div>
        </div>
      </div>
    </div>
  );
};

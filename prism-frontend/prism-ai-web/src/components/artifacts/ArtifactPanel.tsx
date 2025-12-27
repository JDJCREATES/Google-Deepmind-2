/**
 * Artifact Panel Component
 * 
 * Left panel for navigating project artifacts grouped by type.
 * Replaces file explorer when "Artifacts" tab is selected.
 * 
 * @module components/artifacts/ArtifactPanel
 */

import { useRef, useEffect } from 'react';
import { useArtifactStore } from '../../store/artifactStore';
import ErrorBoundary from '../common/ErrorBoundary';
import { 
  VscJson, 
  VscListOrdered, 
  VscTypeHierarchy, 
  VscChecklist, 
  VscWarning, 
  VscReport, 
  VscTools, 
  VscFileMedia, 
  VscFile, 
  VscNewFile,
  VscCloudUpload,
  VscRefresh,
  VscPass,
  VscCircleFilled,
  VscArchive,
  VscArrowRight,
  VscEdit,
  VscFileCode
} from 'react-icons/vsc';
import { BiCube } from 'react-icons/bi';
import type { ArtifactType } from '../../types/artifacts';
import './ArtifactPanel.css';

/**
 * Artifact Panel Component
 * 
 * Displays artifacts in a grouped tree view with loading/error states.
 * 
 * @example
 * ```tsx
 * <ArtifactPanel projectId="my-project" />
 * ```
 */
export default function ArtifactPanel({ projectId }: { projectId: string }) {
  const {
    groups,
    selectedArtifactId,
    isLoading,
    error,
    setProject,
    selectArtifact,
    clearError,
    uploadArtifact,
  } = useArtifactStore();
  
  const fileInputRef = useRef<HTMLInputElement>(null);

  // Load artifacts when component mounts or project changes
  useEffect(() => {
    if (projectId) {
      setProject(projectId);
    }
  }, [projectId, setProject]);

  /**
   * Handle artifact selection
   */
  const handleSelectArtifact = (artifactId: string) => {
    selectArtifact(artifactId);
  };

  /**
   * Handle file upload
   */
  const handleUploadClick = () => {
    fileInputRef.current?.click();
  };

  const handleFileChange = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (file) {
      await uploadArtifact(file);
      // Reset input
      if (fileInputRef.current) {
        fileInputRef.current.value = '';
      }
    }
  };

  // Loading state
  if (isLoading && groups.length === 0) {
    return (
      <div className="artifact-panel loading">
        <div className="loading-spinner">
          <div className="spinner" />
          <p>Loading artifacts...</p>
        </div>
      </div>
    );
  }

  // Error state
  if (error) {
    return (
      <div className="artifact-panel error">
        <div className="error-message">
          <div className="error-icon">
            <VscWarning size={32} />
          </div>
          <h4>Error Loading Artifacts</h4>
          <p>{error}</p>
          <button className="retry-btn" onClick={() => {
            clearError();
            setProject(projectId);
          }}>
            <VscRefresh /> Retry
          </button>
        </div>
      </div>
    );
  }

  // Empty state
  if (groups.length === 0) {
    return (
      <div className="artifact-panel empty">
        <div className="empty-state">
          <span className="empty-icon">
            <BiCube size={48} />
          </span>
          <p>No artifacts yet</p>
          <small>Artifacts will appear here as they are created</small>
        </div>
      </div>
    );
  }

  return (
    <ErrorBoundary>
      <div className="artifact-panel">
        <div className="panel-header">
           <h3 className="panel-title">Artifacts</h3>
           <button 
             className="upload-btn"
             onClick={handleUploadClick}
             title="Upload Artifact"
           >
             <span className="icon"><VscCloudUpload size={16} /></span>
           </button>
           <input
             type="file"
             ref={fileInputRef}
             style={{ display: 'none' }}
             onChange={handleFileChange}
           />
        </div>
        <div className="artifact-groups">
          {groups.map((group) => (
            <div key={group.type} className="artifact-group">
              <div className="group-header">
                <span className="group-icon">{getGroupIcon(group.type as ArtifactType)}</span>
                <span className="group-label">{group.label}</span>
                <span className="group-count">{group.count}</span>
              </div>

              <div className="group-items">
                {group.artifacts.map((artifact) => (
                  <button
                    key={artifact.id}
                    className={`artifact-item ${
                      selectedArtifactId === artifact.id ? 'selected' : ''
                    }`}
                    onClick={() => handleSelectArtifact(artifact.id)}
                    title={artifact.title}
                  >
                    <span className="artifact-icon">
                      {getStatusIcon(artifact.status)}
                    </span>
                    <span className="artifact-title">{artifact.title}</span>
                    <span className="artifact-date">
                      {formatDate(artifact.updatedAt)}
                    </span>
                  </button>
                ))}
              </div>
            </div>
          ))}
        </div>
      </div>
    </ErrorBoundary>
  );
}

/**
 * Get icon for artifact type
 */
function getGroupIcon(type: ArtifactType) {
  switch (type) {
    case 'plan_manifest': return <VscListOrdered />;
    case 'task_list': return <VscChecklist />;
    case 'folder_map': return <VscTypeHierarchy />;
    case 'api_contracts': return <VscJson />;
    case 'dependency_plan': return <VscFileCode />;
    case 'validation_checklist': return <VscPass />;
    case 'risk_report': return <VscWarning />;
    case 'validation_report': return <VscReport />;
    case 'fix_plan': return <VscTools />;
    case 'fix_patch': return <VscEdit />;
    case 'fix_report': return <VscReport />;
    case 'image': return <VscFileMedia />;
    case 'text_document': return <VscFile />;
    case 'generic_file': return <VscNewFile />;
    default: return <VscFile />;
  }
}

/**
 * Get status icon for artifact
 */
function getStatusIcon(status: string) {
  switch (status) {
    case 'draft':
      return <VscEdit className="status-draft" />;
    case 'active':
      return <VscPass className="status-active" />;
    case 'archived':
      return <VscArchive className="status-archived" />;
    case 'superseded':
      return <VscArrowRight className="status-superseded" />;
    default:
      return <VscCircleFilled className="status-default" />;
  }
}

/**
 * Format date for display
 */
function formatDate(dateString: string): string {
  const date = new Date(dateString);
  const now = new Date();
  const diff = now.getTime() - date.getTime();

  const minutes = Math.floor(diff / 60000);
  const hours = Math.floor(diff / 3600000);
  const days = Math.floor(diff / 86400000);

  if (minutes < 1) return 'Just now';
  if (minutes < 60) return `${minutes}m ago`;
  if (hours < 24) return `${hours}h ago`;
  if (days < 7) return `${days}d ago`;

  return date.toLocaleDateString(undefined, {
    month: 'short',
    day: 'numeric',
  });
}

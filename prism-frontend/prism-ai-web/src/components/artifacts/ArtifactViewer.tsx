/**
 * Artifact Viewer Container
 * 
 * Main container that routes the selected artifact to the appropriate viewer.
 * 
 * @module components/artifacts/ArtifactViewer
 */

import { useArtifactStore } from '../../store/artifactStore';
import ErrorBoundary from '../common/ErrorBoundary';
import ImageViewer from './viewers/ImageViewer';
import TextViewer from './viewers/TextViewer';
import MermaidViewer from './viewers/MermaidViewer';
import JsonViewer from './viewers/JsonViewer';
import './ArtifactViewer.css';

export default function ArtifactViewer() {
  const { selectedArtifactId, updateArtifact } = useArtifactStore();

  // We need to fetch the full artifact content if not in cache
  // This logic should ideally use a hook that handles suspense or loading
  // For now, we'll assume the store handles fetching immediately on selection
  // or we might need a local state to track loading specific artifact details.
  
  // Actually, useArtifactStore's getArtifact is async. 
  // But we can peek at the cache synchronously for now or wrap in simple logic.
  // A better pattern: The main App or valid parent triggers load, or we do it here.
  
  // Let's grab it from cache directly if possible or use a hook wrapper.
  // Since `useArtifactStore` exposes `artifactCache`, we can read from it.
  
  const artifact = selectedArtifactId 
    ? useArtifactStore.getState().artifactCache.get(selectedArtifactId) 
    : null;

  if (!selectedArtifactId) {
    return (
      <div className="artifact-viewer-empty">
        <div className="empty-content">
          <span className="empty-icon">👈</span>
          <h3>Select an artifact</h3>
          <p>Choose an artifact from the panel to view details</p>
        </div>
      </div>
    );
  }

  if (!artifact) {
    return (
      <div className="artifact-viewer-loading">
        <div className="spinner" />
        <p>Loading artifact...</p>
      </div>
    );
  }

  const renderViewer = () => {
    switch (artifact.type) {
      case 'image':
        return <ImageViewer artifact={artifact} />;
      
      case 'text_document':
        return <TextViewer artifact={artifact} />;
        
      case 'folder_map':
        // Assuming folder map data has a mermaid definition or we generate it
        // If data is just structure, we might need a transformer.
        // For now, let's assume 'data.mermaid' exists or fallback to JSON
        if ('mermaid' in artifact.data) {
             // @ts-ignore
             return <MermaidViewer definition={artifact.data.mermaid} />;
        }
        return <JsonViewer data={artifact.data} />;

      // TODO: Add specific viewers for Plan, TaskList, Reports
      
      default:
        // Fallback to JSON viewer with edit capability
        return (
          <JsonViewer 
            data={artifact.data} 
            isEditable={true}
            onSave={async (newData) => {
              await updateArtifact(artifact.id, newData, 'user');
            }}
          />
        );
    }
  };

  return (
    <div className="artifact-viewer">
      <ErrorBoundary>
        <div className="artifact-header">
           <h2>{
             // @ts-ignore
             artifact.title || artifact.data.title || artifact.id
           }</h2>
           <div className="artifact-actions">
             {/* Edit/Download/Delete buttons could go here */}
             <span className="artifact-type-badge">{artifact.type}</span>
           </div>
        </div>
        <div className="viewer-content">
          {renderViewer()}
        </div>
      </ErrorBoundary>
    </div>
  );
}

/**
 * Image Viewer Component
 * 
 * Displays an image artifact with zoom/pan capabilities (future enhancement)
 * and metadata.
 * 
 * @module components/artifacts/viewers/ImageViewer
 */

import type { ImageArtifact } from '../../../types/artifacts';
import './ImageViewer.css';

interface ImageViewerProps {
  artifact: ImageArtifact;
}

export default function ImageViewer({ artifact }: ImageViewerProps) {
  const { url, filename, altText, dimensions } = artifact.data;

  return (
    <div className="image-viewer">
      <div className="image-container">
        <img 
          src={url} 
          alt={altText || filename} 
          className="artifact-image"
        />
      </div>
      <div className="image-metadata">
        <span>{filename}</span>
        {dimensions && (
          <span>
            {dimensions.width} x {dimensions.height}
          </span>
        )}
      </div>
    </div>
  );
}

/**
 * Artifact Store
 * 
 * Zustand store for managing artifact state with optimistic updates,
 * caching, and real-time synchronization support.
 * 
 * @module store/artifactStore
 */

import { create } from 'zustand';
import { devtools } from 'zustand/middleware';
import type {
  Artifact,
  ArtifactType,
  ArtifactMetadata,
  ArtifactGroup,
} from '../types/artifacts';
import artifactService, { ApiError } from '../services/artifactService';

/**
 * Artifact store state
 */
interface ArtifactState {
  /** Current project ID */
  currentProjectId: string | null;

  /** All artifacts metadata (for lists) */
  artifactMetadata: ArtifactMetadata[];

  /** Full artifact data cache */
  artifactCache: Map<string, Artifact>;

  /** Currently selected artifact */
  selectedArtifactId: string | null;

  /** Loading states */
  isLoading: boolean;
  isSaving: boolean;

  /** Error state */
  error: string | null;

  /** Grouped artifacts by type */
  groups: ArtifactGroup[];

  // ============================================================================
  // ACTIONS
  // ============================================================================

  /**
   * Set current project and load its artifacts
   * 
   * @param projectId - Project identifier
   */
  setProject: (projectId: string) => Promise<void>;

  /**
   * Load all artifacts for current project
   */
  loadArtifacts: () => Promise<void>;

  /**
   * Get a specific artifact (from cache or API)
   * 
   * @param artifactId - Artifact identifier
   * @returns Artifact data or null if not found
   */
  getArtifact: (artifactId: string) => Promise<Artifact | null>;

  /**
   * Select an artifact for viewing
   * 
   * @param artifactId - Artifact identifier
   */
  selectArtifact: (artifactId: string) => void;

  /**
   * Create a new artifact with optimistic update
   * 
   * @param type - Artifact type
   * @param data - Artifact data
   * @returns Created artifact or null on error
   */
  createArtifact: (type: ArtifactType, data: any) => Promise<Artifact | null>;

  /**
   * Update an artifact with optimistic update
   * 
   * @param artifactId - Artifact identifier
   * @param data - Updated data
   * @param updatedBy - User identifier
   * @returns Updated artifact or null on error
   */
  updateArtifact: (
    artifactId: string,
    data: any,
    updatedBy: string
  ) => Promise<Artifact | null>;

  /**
   * Delete an artifact
   * 
   * @param artifactId - Artifact identifier
   */
  deleteArtifact: (artifactId: string) => Promise<boolean>;

  /**
   * Upload a file as an artifact
   * 
   * @param file - File object to upload
   */
  uploadArtifact: (file: File) => Promise<Artifact | null>;

  /**
   * Clear error state
   */
  clearError: () => void;

  /**
   * Reset store to initial state
   */
  reset: () => void;
}

/**
 * Group artifacts by type with counts
 * 
 * @param artifacts - Array of artifact metadata
 * @returns Grouped artifacts
 */
function groupArtifacts(artifacts: ArtifactMetadata[]): ArtifactGroup[] {
  const typeLabels: Record<ArtifactType, { label: string }> = {
    plan_manifest: { label: 'Plans' },
    task_list: { label: 'Tasks' },
    folder_map: { label: 'Structure' },
    api_contracts: { label: 'API Contracts' },
    dependency_plan: { label: 'Dependencies' },
    validation_checklist: { label: 'Validation' },
    risk_report: { label: 'Risks' },
    validation_report: { label: 'Reports' },
    fix_plan: { label: 'Fix Plans' },
    fix_patch: { label: 'Patches' },
    fix_report: { label: 'Fix Reports' },
    image: { label: 'Images' },
    text_document: { label: 'Documents' },
    generic_file: { label: 'Files' },
  };

  const groups: Map<ArtifactType, ArtifactMetadata[]> = new Map();

  artifacts.forEach(artifact => {
    if (!groups.has(artifact.type)) {
      groups.set(artifact.type, []);
    }
    groups.get(artifact.type)!.push(artifact);
  });

  return Array.from(groups.entries()).map(([type, items]) => ({
    type,
    label: typeLabels[type].label,
    icon: '', // Icons handled in UI
    artifacts: items,
    count: items.length,
  }));
}

/**
 * Artifact store implementation
 */
export const useArtifactStore = create<ArtifactState>()(
  devtools(
    (set, get) => ({
      // Initial state
      currentProjectId: null,
      artifactMetadata: [],
      artifactCache: new Map(),
      selectedArtifactId: null,
      isLoading: false,
      isSaving: false,
      error: null,
      groups: [],

      // Set project
      setProject: async (projectId: string) => {
        set({ currentProjectId: projectId, error: null });
        await get().loadArtifacts();
      },

      // Load all artifacts
      loadArtifacts: async () => {
        const { currentProjectId } = get();
        if (!currentProjectId) {
          set({ error: 'No project selected' });
          return;
        }

        set({ isLoading: true, error: null });

        try {
          const response = await artifactService.listArtifacts(currentProjectId);

          set({
            artifactMetadata: response.artifacts,
            groups: groupArtifacts(response.artifacts),
            isLoading: false,
          });
        } catch (error) {
          const message =
            error instanceof ApiError
              ? error.message
              : 'Failed to load artifacts';

          set({
            error: message,
            isLoading: false,
          });

          console.error('Failed to load artifacts:', error);
        }
      },

      // Get artifact
      getArtifact: async (artifactId: string) => {
        const { artifactCache } = get();

        // Check cache first
        if (artifactCache.has(artifactId)) {
          return artifactCache.get(artifactId)!;
        }

        // Fetch from API
        set({ isLoading: true, error: null });

        try {
          const { artifact } = await artifactService.getArtifact(artifactId);

          // Update cache
          const newCache = new Map(artifactCache);
          newCache.set(artifactId, artifact);

          set({
            artifactCache: newCache,
            isLoading: false,
          });

          return artifact;
        } catch (error) {
          const message =
            error instanceof ApiError
              ? error.message
              : 'Failed to load artifact';

          set({
            error: message,
            isLoading: false,
          });

          console.error('Failed to load artifact:', error);
          return null;
        }
      },

      // Select artifact
      selectArtifact: (artifactId: string) => {
        set({ selectedArtifactId: artifactId });
      },

      // Create artifact
      createArtifact: async (type: ArtifactType, data: any) => {
        const { currentProjectId, artifactMetadata } = get();
        if (!currentProjectId) {
          set({ error: 'No project selected' });
          return null;
        }

        set({ isSaving: true, error: null });

        try {
          const artifact = await artifactService.createArtifact({
            type,
            projectId: currentProjectId,
            data,
          });

          // Update metadata list
          const newMetadata: ArtifactMetadata = {
            id: artifact.id,
            type: artifact.type,
            title:
              (artifact.data as any).title ||
              (artifact.data as any).summary ||
              'Untitled',
            createdAt: artifact.createdAt,
            updatedAt: artifact.updatedAt,
            status: artifact.status,
          };

          const updatedMetadata = [...artifactMetadata, newMetadata];

          // Update cache
          const newCache = new Map(get().artifactCache);
          newCache.set(artifact.id, artifact);

          set({
            artifactMetadata: updatedMetadata,
            groups: groupArtifacts(updatedMetadata),
            artifactCache: newCache,
            selectedArtifactId: artifact.id,
            isSaving: false,
          });

          return artifact;
        } catch (error) {
          const message =
            error instanceof ApiError
              ? error.message
              : 'Failed to create artifact';

          set({
            error: message,
            isSaving: false,
          });

          console.error('Failed to create artifact:', error);
          return null;
        }
      },

      // Update artifact
      updateArtifact: async (
        artifactId: string,
        data: any,
        updatedBy: string
      ) => {
        set({ isSaving: true, error: null });

        // Optimistic update
        const { artifactCache } = get();
        const oldArtifact = artifactCache.get(artifactId);

        if (oldArtifact) {
          const optimisticArtifact = {
            ...oldArtifact,
            data: { ...oldArtifact.data, ...data },
            updatedAt: new Date().toISOString(),
          };

          const newCache = new Map(artifactCache);
          newCache.set(artifactId, optimisticArtifact);
          set({ artifactCache: newCache });
        }

        try {
          const updated = await artifactService.updateArtifact(artifactId, {
            data,
            updatedBy,
          });

          // Update cache with real data
          const newCache = new Map(artifactCache);
          newCache.set(artifactId, updated);

          set({
            artifactCache: newCache,
            isSaving: false,
          });

          return updated;
        } catch (error) {
          // Revert optimistic update on error
          if (oldArtifact) {
            const revertedCache = new Map(artifactCache);
            revertedCache.set(artifactId, oldArtifact);
            set({ artifactCache: revertedCache });
          }

          const message =
            error instanceof ApiError
              ? error.message
              : 'Failed to update artifact';

          set({
            error: message,
            isSaving: false,
          });

          console.error('Failed to update artifact:', error);
          return null;
        }
      },

      // Delete artifact
      deleteArtifact: async (artifactId: string) => {
        set({ isSaving: true, error: null });

        try {
          await artifactService.deleteArtifact(artifactId);

          // Remove from metadata and cache
          const { artifactMetadata, artifactCache, selectedArtifactId } = get();

          const updatedMetadata = artifactMetadata.filter(
            a => a.id !== artifactId
          );

          const newCache = new Map(artifactCache);
          newCache.delete(artifactId);

          set({
            artifactMetadata: updatedMetadata,
            groups: groupArtifacts(updatedMetadata),
            artifactCache: newCache,
            selectedArtifactId:
              selectedArtifactId === artifactId ? null : selectedArtifactId,
            isSaving: false,
          });

          return true;
        } catch (error) {
          const message =
            error instanceof ApiError
              ? error.message
              : 'Failed to delete artifact';

          set({
            error: message,
            isSaving: false,
          });

          console.error('Failed to delete artifact:', error);
          return false;
        }
      },

      // Upload artifact
      uploadArtifact: async (file: File) => {
        const { currentProjectId, artifactMetadata } = get();
        if (!currentProjectId) {
          set({ error: 'No project selected' });
          return null;
        }

        set({ isSaving: true, error: null });

        try {
          const artifact = await artifactService.uploadArtifact(
            currentProjectId,
            file
          );

          // Update metadata list
          const newMetadata: ArtifactMetadata = {
            id: artifact.id,
            type: artifact.type,
            title: file.name,
            createdAt: artifact.createdAt,
            updatedAt: artifact.updatedAt,
            status: artifact.status,
          };

          const updatedMetadata = [...artifactMetadata, newMetadata];

          // Update cache
          const newCache = new Map(get().artifactCache);
          newCache.set(artifact.id, artifact);

          set({
            artifactMetadata: updatedMetadata,
            groups: groupArtifacts(updatedMetadata),
            artifactCache: newCache,
            selectedArtifactId: artifact.id,
            isSaving: false,
          });

          return artifact;
        } catch (error) {
          const message =
            error instanceof ApiError
              ? error.message
              : 'Failed to upload artifact';

          set({
            error: message,
            isSaving: false,
          });

          console.error('Failed to upload artifact:', error);
          return null;
        }
      },

      // Clear error
      clearError: () => {
        set({ error: null });
      },

      // Reset
      reset: () => {
        set({
          currentProjectId: null,
          artifactMetadata: [],
          artifactCache: new Map(),
          selectedArtifactId: null,
          isLoading: false,
          isSaving: false,
          error: null,
          groups: [],
        });
      },
    }),
    { name: 'ArtifactStore' }
  )
);

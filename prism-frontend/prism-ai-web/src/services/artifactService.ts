/**
 * Artifact Service
 * 
 * Production-ready service for interacting with the ShipS* backend API.
 * Handles all artifact CRUD operations with comprehensive error handling,
 * retry logic, and optimistic updates support.
 * 
 * @module services/artifactService
 */

import type {
  Artifact,
  ArtifactType,
  ArtifactListResponse,
  ArtifactResponse,
  CreateArtifactRequest,
  UpdateArtifactRequest,
} from '../types/artifacts';

/**
 * Base API URL - configurable via environment
 */
const API_BASE_URL = import.meta.env.VITE_API_URL || 'http://localhost:8001';

/**
 * Custom error class for API errors
 */
export class ApiError extends Error {
  public statusCode: number;
  public response?: any;

  constructor(
    message: string,
    statusCode: number,
    response?: any
  ) {
    super(message);
    this.name = 'ApiError';
    this.statusCode = statusCode;
    this.response = response;
  }
}

/**
 * Fetch with timeout and error handling
 * 
 * @param url - URL to fetch
 * @param options - Fetch options
 * @param timeout - Timeout in milliseconds
 * @returns Response data
 * @throws {ApiError} If request fails
 */
async function fetchWithTimeout(
  url: string,
  options: RequestInit = {},
  timeout: number = 10000
): Promise<any> {
  const controller = new AbortController();
  const timeoutId = setTimeout(() => controller.abort(), timeout);

  try {
    const response = await fetch(url, {
      ...options,
      signal: controller.signal,
      headers: {
        'Content-Type': 'application/json',
        ...options.headers,
      },
    });

    clearTimeout(timeoutId);

    if (!response.ok) {
      const errorData = await response.json().catch(() => ({}));
      throw new ApiError(
        errorData.message || `Request failed with status ${response.status}`,
        response.status,
        errorData
      );
    }

    return await response.json();
  } catch (error) {
    clearTimeout(timeoutId);

    if (error instanceof ApiError) {
      throw error;
    }

    if (error instanceof Error) {
      if (error.name === 'AbortError') {
        throw new ApiError('Request timeout', 408);
      }
      throw new ApiError(error.message, 0);
    }

    throw new ApiError('Unknown error occurred', 0);
  }
}

/**
 * Retry a function with exponential backoff
 * 
 * @param fn - Function to retry
 * @param maxRetries - Maximum number of retries
 * @param baseDelay - Base delay in milliseconds
 * @returns Result of function
 */
async function retryWithBackoff<T>(
  fn: () => Promise<T>,
  maxRetries: number = 3,
  baseDelay: number = 1000
): Promise<T> {
  let lastError: Error | null = null;

  for (let i = 0; i <= maxRetries; i++) {
    try {
      return await fn();
    } catch (error) {
      lastError = error as Error;

      // Don't retry on client errors (4xx)
      if (error instanceof ApiError && error.statusCode >= 400 && error.statusCode < 500) {
        throw error;
      }

      if (i < maxRetries) {
        const delay = baseDelay * Math.pow(2, i);
        await new Promise(resolve => setTimeout(resolve, delay));
      }
    }
  }

  throw lastError;
}

/**
 * Artifact Service
 * 
 * Provides methods for all artifact-related API operations
 */
export const artifactService = {
  /**
   * List all artifacts for a project
   * 
   * @param projectId - Project identifier
   * @param type - Optional filter by artifact type
   * @returns Artifact list with metadata
   * @throws {ApiError} If request fails
   * 
   * @example
   * ```ts
   * const artifacts = await artifactService.listArtifacts('my-project');
   * const plans = await artifactService.listArtifacts('my-project', 'plan_manifest');
   * ```
   */
  async listArtifacts(
    projectId: string,
    type?: ArtifactType
  ): Promise<ArtifactListResponse> {
    const url = type
      ? `${API_BASE_URL}/api/artifacts/${projectId}?type=${type}`
      : `${API_BASE_URL}/api/artifacts/${projectId}`;

    return retryWithBackoff(() => fetchWithTimeout(url));
  },

  /**
   * Get a single artifact by ID
   * 
   * @param artifactId - Artifact identifier
   * @returns Artifact data with related artifacts
   * @throws {ApiError} If artifact not found or request fails
   * 
   * @example
   * ```ts
   * const { artifact, relatedArtifacts } = await artifactService.getArtifact('plan_123');
   * ```
   */
  async getArtifact<T extends Artifact = Artifact>(
    artifactId: string
  ): Promise<ArtifactResponse<T>> {
    const url = `${API_BASE_URL}/api/artifact/${artifactId}`;
    return retryWithBackoff(() => fetchWithTimeout(url));
  },

  /**
   * Create a new artifact
   * 
   * @param request - Artifact creation data
   * @returns Created artifact
   * @throws {ApiError} If creation fails
   * 
   * @example
   * ```ts
   * const artifact = await artifactService.createArtifact({
   *   type: 'plan_manifest',
   *   projectId: 'my-project',
   *   data: { title: 'New Plan', ... }
   * });
   * ```
   */
  async createArtifact<T extends Artifact = Artifact>(
    request: CreateArtifactRequest
  ): Promise<T> {
    const url = `${API_BASE_URL}/api/artifact`;

    return retryWithBackoff(() =>
      fetchWithTimeout(url, {
        method: 'POST',
        body: JSON.stringify(request),
      })
    );
  },

  /**
   * Update an existing artifact
   * 
   * @param artifactId - Artifact identifier
   * @param request - Update data
   * @returns Updated artifact
   * @throws {ApiError} If update fails
   * 
   * @example
   * ```ts
   * const updated = await artifactService.updateArtifact('plan_123', {
   *   data: { title: 'Updated Title' },
   *   updatedBy: 'user@example.com'
   * });
   * ```
   */
  async updateArtifact<T extends Artifact = Artifact>(
    artifactId: string,
    request: UpdateArtifactRequest
  ): Promise<T> {
    const url = `${API_BASE_URL}/api/artifact/${artifactId}`;

    return retryWithBackoff(() =>
      fetchWithTimeout(url, {
        method: 'PUT',
        body: JSON.stringify(request),
      })
    );
  },

  /**
   * Delete an artifact (archives it, doesn't hard delete)
   * 
   * @param artifactId - Artifact identifier
   * @returns Success status
   * @throws {ApiError} If deletion fails
   * 
   * @example
   * ```ts
   * await artifactService.deleteArtifact('plan_123');
   * ```
   */
  async deleteArtifact(artifactId: string): Promise<{ success: boolean }> {
    const url = `${API_BASE_URL}/api/artifact/${artifactId}`;

    return retryWithBackoff(() =>
      fetchWithTimeout(url, {
        method: 'DELETE',
      })
    );
  },

  /**
   * Get artifacts by type for a project
   * 
   * @param projectId - Project identifier
   * @param type - Artifact type
   * @returns Array of artifacts
   * @throws {ApiError} If request fails
   * 
   * @example
   * ```ts
   * const tasks = await artifactService.getArtifactsByType('my-project', 'task_list');
   * ```
   */
  async getArtifactsByType<T extends Artifact = Artifact>(
    projectId: string,
    type: ArtifactType
  ): Promise<T[]> {
    const response = await this.listArtifacts(projectId, type);
    const artifacts: T[] = [];

    // Fetch full data for each artifact
    for (const metadata of response.artifacts) {
      try {
        const { artifact } = await this.getArtifact<T>(metadata.id);
        artifacts.push(artifact);
      } catch (error) {
        console.error(`Failed to fetch artifact ${metadata.id}:`, error);
        // Continue with other artifacts
      }
    }

    return artifacts;
  },

  /**
   * Upload a file artifact
   * 
   * @param projectId - Project to upload to
   * @param file - File to upload
   * @returns Created artifact
   */
  async uploadArtifact<T extends Artifact = Artifact>(
    projectId: string,
    file: File
  ): Promise<T> {
    const url = `${API_BASE_URL}/api/artifacts/upload?projectId=${projectId}`;
    const formData = new FormData();
    formData.append('file', file);

    return retryWithBackoff(() =>
      fetchWithTimeout(url, {
        method: 'POST',
        // Content-Type header is set automatically by browser for FormData
        body: formData,
        headers: {}, // Do not set Content-Type manually
      })
    );
  },
};

/**
 * Export for direct import
 */
export default artifactService;

import axios from 'axios';

// Don't set a BASE_URL - let Vite proxy handle API calls
const BASE_URL = '';

const api = axios.create({
  baseURL: BASE_URL,
  withCredentials: true,
  headers: {
    'Content-Type': 'application/json',
  },
});

export interface SearchResult {
  id?: number;  // Made optional since backend might not provide it
  title: string;
  page_url: string;
  poster_url?: string;  // Also made optional
  data?: {  // Made optional to handle different backend structures
    title: string;
    release_year: string;
    imdb_score: string;
    duration: string;
    release_country: string;
    genre: string;
    description_preview: string;
    quality_tag: string;
    user_rating: string;
  };
  // Add fields that might actually be coming from backend
  filename?: string;
  filename_old?: string;  // Added for original filename
  release_year?: string;
  description?: string;
  catagory?: string;
  duration?: number | string;
  score?: string;  // Added for IMDB score
  quality_tag?: string;  // Added for quality
  tmdb_id?: string;  // Added for TMDB ID
  genre?: string;  // Added for genre
}

export interface VideoData {
  video_url: string;
  video_data: {
    title: string;
    release_year: string;
    imdb_score: string;
    duration: string;
    release_country: string;
    genre: string;
    description_preview: string;
    quality_tag: string;
    user_rating: string;
  };
}

export interface DownloadResponse {
  message: string;
  video_data?: VideoData['video_data'];
  video_url?: string;
  id?: number;
}

export interface DownloadStatusResponse {
  message?: string;
  filename?: string;
  status?: string;
}

export interface ApiResponse<T> {
  message: string;
  data: T;
}

export const apiService = {
  // Search API with streaming support
  search: async (query: string, onBatch: (results: SearchResult[], isComplete: boolean) => void): Promise<void> => {
    try {
      const response = await fetch(`/api/v2/search?q=${encodeURIComponent(query)}`, {
        credentials: 'include'
      });

      // Check if it's a streaming response
      if (response.headers.get('content-type')?.includes('text/event-stream')) {
        console.log(`🌊 Received streaming response for query: ${query}`);
        const reader = response.body?.getReader();
        const decoder = new TextDecoder();

        if (reader) {
          let buffer = '';
          
          while (true) {
            const { done, value } = await reader.read();
            if (done) break;
            
            buffer += decoder.decode(value, { stream: true });
            const lines = buffer.split('\n');
            buffer = lines.pop() || '';
            
            for (const line of lines) {
              if (line.startsWith('data: ')) {
                try {
                  const data = JSON.parse(line.slice(6));
                  if (data.results) {
                    console.log(`📦 Received batch with ${data.results.length} results`);
                    onBatch(data.results, false);
                  }
                  if (data.complete) {
                    console.log('✅ Streaming complete');
                    onBatch([], true);
                    return;
                  }
                  if (data.error) {
                    throw new Error(data.error);
                  }
                } catch (e) {
                  console.warn('Failed to parse SSE data:', line, e);
                }
              }
            }
          }
        }
      } else {
        console.log(`📄 Received regular JSON response for query: ${query}`);
        // Handle regular JSON response
        const data = await response.json();
        onBatch(data.data, true);
      }
    } catch (error) {
      console.warn('Request failed, falling back to regular API:', error);
      // Fallback to regular API call
      const response = await api.get<ApiResponse<SearchResult[]>>(`/api/v2/search?q=${encodeURIComponent(query)}`);
      onBatch(response.data.data, true);
    }
  },

  // Get popular content with progressive streaming (calls callback for each batch)
  getPopular: async (onBatch: (results: SearchResult[], isComplete: boolean) => void): Promise<void> => {
    try {
      const response = await fetch('/api/v2/popular', {
        credentials: 'include'
      });

      // Check if it's a streaming response
      if (response.headers.get('content-type')?.includes('text/event-stream')) {
        console.log('🌊 Received streaming response');
        const reader = response.body?.getReader();
        const decoder = new TextDecoder();

        if (reader) {
          let buffer = '';
          
          while (true) {
            const { done, value } = await reader.read();
            if (done) break;
            
            buffer += decoder.decode(value, { stream: true });
            const lines = buffer.split('\n');
            buffer = lines.pop() || '';
            
            for (const line of lines) {
              if (line.startsWith('data: ')) {
                try {
                  const data = JSON.parse(line.slice(6));
                  if (data.results) {
                    console.log(`📦 Received batch with ${data.results.length} results`);
                    onBatch(data.results, false);
                  }
                  if (data.complete) {
                    console.log('✅ Streaming complete');
                    onBatch([], true);
                    return;
                  }
                  if (data.error) {
                    throw new Error(data.error);
                  }
                } catch (e) {
                  console.warn('Failed to parse SSE data:', line, e);
                }
              }
            }
          }
        }
      } else {
        console.log('📄 Received regular JSON response');
        // Handle regular JSON response
        const data = await response.json();
        onBatch(data.data, true);
      }
    } catch (error) {
      console.warn('Request failed, falling back to regular API:', error);
      // Fallback to regular API call
      const response = await api.get<ApiResponse<SearchResult[]>>('/api/v2/popular');
      onBatch(response.data.data, true);
    }
  },

  // Get popular content with progressive streaming (calls callback for each batch)
  getPopularStreaming: async (onBatch: (results: SearchResult[], isComplete: boolean) => void): Promise<void> => {
    try {
      const response = await fetch('/api/v2/popular', {
        credentials: 'include'
      });

      // Check if it's a streaming response
      if (response.headers.get('content-type')?.includes('text/event-stream')) {
        console.log('🌊 Received streaming response');
        const reader = response.body?.getReader();
        const decoder = new TextDecoder();

        if (reader) {
          let buffer = '';
          
          while (true) {
            const { done, value } = await reader.read();
            if (done) break;
            
            buffer += decoder.decode(value, { stream: true });
            const lines = buffer.split('\n');
            buffer = lines.pop() || '';
            
            for (const line of lines) {
              if (line.startsWith('data: ')) {
                try {
                  const data = JSON.parse(line.slice(6));
                  if (data.results) {
                    console.log(`📦 Received batch with ${data.results.length} results`);
                    onBatch(data.results, false);
                  }
                  if (data.complete) {
                    console.log('✅ Streaming complete');
                    onBatch([], true);
                    return;
                  }
                  if (data.error) {
                    throw new Error(data.error);
                  }
                } catch (e) {
                  console.warn('Failed to parse SSE data:', line, e);
                }
              }
            }
          }
        }
      } else {
        console.log('📄 Received regular JSON response');
        // Handle regular JSON response
        const data = await response.json();
        onBatch(data.data, true);
      }
    } catch (error) {
      console.warn('Request failed, falling back to regular API:', error);
      // Fallback to regular API call
      const response = await api.get<ApiResponse<SearchResult[]>>('/api/v2/popular');
      onBatch(response.data.data, true);
    }
  },

  // Get video details
  getVideo: async (pageUrl: string): Promise<VideoData> => {
    const response = await api.get<VideoData>(`/api/v2/getvideo?page_url=${encodeURIComponent(pageUrl)}`);
    return response.data;
  },

  // Download video
  downloadVideo: async (pageUrl: string, id: number): Promise<DownloadResponse> => {
    const response = await api.post('/api/v2/download', null, {
      params: { page_url: pageUrl, id }
    });
    return response.data;
  },

  // Get download status
  getDownloadStatus: async (filename?: string): Promise<DownloadStatusResponse> => {
    const url = filename ? `/test/${filename}` : '/test';
    const response = await api.get(url);
    return response.data;
  },
};

export default api;

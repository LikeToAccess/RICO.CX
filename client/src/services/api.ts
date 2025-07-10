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
  // Search API
  search: async (query: string): Promise<SearchResult[]> => {
    const response = await api.get<ApiResponse<SearchResult[]>>(`/api/v2/search?q=${encodeURIComponent(query)}`);
    return response.data.data;
  },

  // Get popular content
  getPopular: async (): Promise<SearchResult[]> => {
    const response = await api.get<ApiResponse<SearchResult[]>>('/api/v2/popular');
    return response.data.data;
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

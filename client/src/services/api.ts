import axios from 'axios';

const BASE_URL = import.meta.env.DEV ? 'http://localhost:9000' : '';

const api = axios.create({
  baseURL: BASE_URL,
  withCredentials: true,
  headers: {
    'Content-Type': 'application/json',
  },
});

export interface SearchResult {
  id: number;
  title: string;
  page_url: string;
  poster_url: string;
  data: {
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
  downloadVideo: async (pageUrl: string, id: number): Promise<any> => {
    const response = await api.post('/api/v2/download', null, {
      params: { page_url: pageUrl, id }
    });
    return response.data;
  },

  // Get download status
  getDownloadStatus: async (filename?: string): Promise<any> => {
    const url = filename ? `/test/${filename}` : '/test';
    const response = await api.get(url);
    return response.data;
  },
};

export default api;

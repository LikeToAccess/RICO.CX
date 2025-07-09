import React, { useEffect, useState } from 'react';
import { Paper, Title, Loader, Center, Alert } from '@mantine/core';
import { motion } from 'framer-motion';
import { apiService } from '../services/api';
import type { VideoData } from '../services/api';

interface VideoPlayerProps {
  videoUrl: string;
}

export const VideoPlayer: React.FC<VideoPlayerProps> = ({ videoUrl }) => {
  const [videoData, setVideoData] = useState<VideoData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const fetchVideoData = async () => {
      try {
        setLoading(true);
        const data = await apiService.getVideo(videoUrl);
        setVideoData(data);
      } catch (err) {
        setError('Failed to load video data');
        console.error('Video fetch error:', err);
      } finally {
        setLoading(false);
      }
    };

    if (videoUrl) {
      fetchVideoData();
    }
  }, [videoUrl]);

  if (loading) {
    return (
      <Center h={300}>
        <Loader size="lg" />
      </Center>
    );
  }

  if (error) {
    return (
      <Alert color="red" title="Error">
        {error}
      </Alert>
    );
  }

  if (!videoData) {
    return null;
  }

  return (
    <motion.div
      initial={{ opacity: 0, scale: 0.9 }}
      animate={{ opacity: 1, scale: 1 }}
      transition={{ duration: 0.5 }}
    >
      <Paper p="md" radius="md" mb="xl">
        <Title order={2} mb="md">
          {videoData.video_data.title}
        </Title>
        
        <video
          controls
          style={{
            width: '100%',
            maxHeight: '500px',
            borderRadius: '8px',
          }}
          src={videoData.video_url}
        >
          Your browser does not support the video tag.
        </video>

        <div style={{ marginTop: '1rem' }}>
          <p><strong>Release Year:</strong> {videoData.video_data.release_year}</p>
          <p><strong>Duration:</strong> {videoData.video_data.duration}</p>
          <p><strong>Genre:</strong> {videoData.video_data.genre}</p>
          <p><strong>IMDB Score:</strong> {videoData.video_data.imdb_score}</p>
          <p><strong>Description:</strong> {videoData.video_data.description_preview}</p>
        </div>
      </Paper>
    </motion.div>
  );
};

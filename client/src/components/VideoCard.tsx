import React, { useState } from 'react';
import { Card, Image, Text, Badge, Button, Group, Stack, Loader } from '@mantine/core';
import { IconDownload, IconCheck, IconX } from '@tabler/icons-react';
import { motion } from 'framer-motion';
import { apiService } from '../services/api';
import { notifications } from '@mantine/notifications';
import type { SearchResult } from '../services/api';

interface VideoCardProps {
  result: SearchResult;
}

export const VideoCard: React.FC<VideoCardProps> = ({ result }) => {
  const [isDownloading, setIsDownloading] = useState(false);
  const [downloadStatus, setDownloadStatus] = useState<'idle' | 'downloading' | 'success' | 'error'>('idle');

  // Handle both flat and nested data structures
  // Prioritize FileBot-processed title over raw filename
  const title = result.title || result.filename || 'Unknown Title';
  const poster = result.poster_url || 'https://via.placeholder.com/300x450/333/fff?text=No+Poster';
  const quality = result.quality_tag || '';
  const description = result.description || '';
  const year = result.release_year || '';
  const duration = result.duration || '';
  const imdbScore = result.score || '';
  const genre = result.genre || '';

  const handleDownload = async () => {
    try {
      setIsDownloading(true);
      setDownloadStatus('downloading');
      
      await apiService.downloadVideo(result.page_url, result.id || 0);
      
      setDownloadStatus('success');
      notifications.show({
        title: 'Download Started',
        message: `${result.title} has been added to the download queue`,
        color: 'green',
        icon: <IconCheck size={16} />,
      });
    } catch (error: unknown) {
      setDownloadStatus('error');
      const errorMessage = error instanceof Error ? error.message : 'Failed to start download';
      notifications.show({
        title: 'Download Failed',
        message: errorMessage,
        color: 'red',
        icon: <IconX size={16} />,
      });
    } finally {
      setIsDownloading(false);
    }
  };

  const getDownloadButton = () => {
    switch (downloadStatus) {
      case 'downloading':
        return (
          <Button 
            leftSection={<Loader size={16} />} 
            disabled 
            size="sm"
          >
            Downloading...
          </Button>
        );
      case 'success':
        return (
          <Button 
            leftSection={<IconCheck size={16} />} 
            color="green" 
            disabled 
            size="sm"
          >
            Downloaded
          </Button>
        );
      case 'error':
        return (
          <Button 
            leftSection={<IconDownload size={16} />} 
            color="red" 
            onClick={handleDownload}
            size="sm"
          >
            Retry
          </Button>
        );
      default:
        return (
          <Button 
            leftSection={<IconDownload size={16} />} 
            onClick={handleDownload} 
            disabled={isDownloading}
            size="sm"
          >
            Download
          </Button>
        );
    }
  };

  return (
    <motion.div
      whileHover={{ scale: 1.02 }}
      whileTap={{ scale: 0.98 }}
      transition={{ type: "spring", stiffness: 300, damping: 20 }}
      style={{ height: '100%' }}
    >
      <Card shadow="sm" padding="lg" radius="md" withBorder style={{ height: '630px', display: 'flex', flexDirection: 'column' }}>
        <Card.Section style={{ flex: '0 0 450px' }}>
          <Image
            src={poster}
            height={450}
            alt={title}
            fallbackSrc="https://via.placeholder.com/300x450/333/fff?text=No+Poster"
            fit="cover"
          />
        </Card.Section>

        <Stack gap="xs" mt="sm" style={{ flex: 1 }}>
          <div style={{ flex: 1 }}>
            <Group justify="space-between" align="flex-start" mb="xs">
              <Text fw={500} size="sm" lineClamp={2} style={{ flex: 1, lineHeight: 1.2 }}>
                {title}
              </Text>
              {quality && (
                <Badge color="blue" variant="light" size="xs" style={{ flexShrink: 0 }}>
                  {quality}
                </Badge>
              )}
            </Group>

            {description && (
              <Text size="xs" c="dimmed" lineClamp={2} mb="xs">
                {description}
              </Text>
            )}

            <Group justify="space-between" gap="xs" mb="xs">
              <Text size="xs" c="dimmed">
                {year && duration ? `${year} • ${duration}min` : year || (duration ? `${duration}min` : '')}
              </Text>
              {imdbScore && (
                <Text size="xs" c="dimmed">
                  ⭐ {imdbScore}
                </Text>
              )}
            </Group>

            {genre && (
              <Text size="xs" c="dimmed" lineClamp={1} mb="xs">
                {genre}
              </Text>
            )}
          </div>

          <div style={{ marginTop: 'auto', paddingTop: '8px' }}>
            {getDownloadButton()}
          </div>
        </Stack>
      </Card>
    </motion.div>
  );
};

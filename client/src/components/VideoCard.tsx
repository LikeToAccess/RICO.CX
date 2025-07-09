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

  const handleDownload = async () => {
    try {
      setIsDownloading(true);
      setDownloadStatus('downloading');
      
      await apiService.downloadVideo(result.page_url, result.id);
      
      setDownloadStatus('success');
      notifications.show({
        title: 'Download Started',
        message: `${result.title} has been added to the download queue`,
        color: 'green',
        icon: <IconCheck size={16} />,
      });
    } catch (error: any) {
      setDownloadStatus('error');
      notifications.show({
        title: 'Download Failed',
        message: error.response?.data?.message || 'Failed to start download',
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
    >
      <Card shadow="sm" padding="lg" radius="md" withBorder h="100%">
        <Card.Section>
          <Image
            src={result.poster_url}
            height={300}
            alt={result.title}
            fallbackSrc="/placeholder-poster.png"
          />
        </Card.Section>

        <Stack gap="sm" mt="md">
          <Group justify="space-between" align="flex-start">
            <Text fw={500} size="lg" lineClamp={2}>
              {result.data.title}
            </Text>
            <Badge color="blue" variant="light">
              {result.data.quality_tag}
            </Badge>
          </Group>

          <Text size="sm" c="dimmed" lineClamp={3}>
            {result.data.description_preview}
          </Text>

          <Group justify="space-between" gap="xs">
            <Text size="xs" c="dimmed">
              {result.data.release_year} • {result.data.duration}
            </Text>
            <Text size="xs" c="dimmed">
              {result.data.imdb_score}
            </Text>
          </Group>

          <Group justify="space-between" gap="xs">
            <Text size="xs" c="dimmed" lineClamp={1}>
              {result.data.genre}
            </Text>
          </Group>

          {getDownloadButton()}
        </Stack>
      </Card>
    </motion.div>
  );
};

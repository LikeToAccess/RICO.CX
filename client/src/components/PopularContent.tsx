import React, { useEffect, useState } from 'react';
import { Title, Grid, Loader, Center, Alert } from '@mantine/core';
import { motion } from 'framer-motion';
import { apiService } from '../services/api';
import { VideoCard } from './VideoCard';
import type { SearchResult } from '../services/api';

export const PopularContent: React.FC = () => {
  const [popularContent, setPopularContent] = useState<SearchResult[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const fetchPopular = async () => {
      try {
        setLoading(true);
        const data = await apiService.getPopular();
        setPopularContent(data);
      } catch (err) {
        setError('Failed to load popular content');
        console.error('Popular content fetch error:', err);
      } finally {
        setLoading(false);
      }
    };

    fetchPopular();
  }, []);

  if (loading) {
    return (
      <Center h={200}>
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

  return (
    <motion.div
      initial={{ opacity: 0, y: 30 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.6 }}
    >
      <Title order={2} mb="lg" ta="center">
        Popular Content
      </Title>
      
      <Grid>
        {popularContent.map((item, index) => (
          <Grid.Col key={item.id} span={{ base: 12, sm: 6, md: 4, lg: 3 }}>
            <motion.div
              initial={{ opacity: 0, y: 20 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: index * 0.1, duration: 0.5 }}
            >
              <VideoCard result={item} />
            </motion.div>
          </Grid.Col>
        ))}
      </Grid>
    </motion.div>
  );
};

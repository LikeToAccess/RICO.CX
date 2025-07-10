import React, { useState } from 'react';
import { Title, Grid, Loader, Center, Alert, Button } from '@mantine/core';
import { motion } from 'framer-motion';
import { apiService } from '../services/api';
import { VideoCard } from './VideoCard';
import type { SearchResult } from '../services/api';

export const PopularContent: React.FC = () => {
  const [popularContent, setPopularContent] = useState<SearchResult[]>([]);
  const [loading, setLoading] = useState(false); // Changed to false - don't load immediately
  const [error, setError] = useState<string | null>(null);
  const [hasLoaded, setHasLoaded] = useState(false);

  const fetchPopular = async () => {
    if (hasLoaded) return; // Don't fetch if already loaded
    
    try {
      setLoading(true);
      const data = await apiService.getPopular();
      setPopularContent(data);
      setHasLoaded(true);
    } catch (err) {
      setError('Failed to load popular content');
      console.error('Popular content fetch error:', err);
    } finally {
      setLoading(false);
    }
  };

  // Remove the useEffect - no automatic loading
  // useEffect(() => {
  //   fetchPopular();
  // }, []);

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

  // Show load button if content hasn't been loaded yet
  if (!hasLoaded && popularContent.length === 0) {
    return (
      <motion.div
        initial={{ opacity: 0, y: 30 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.6 }}
      >
        <Title order={2} mb="lg" ta="center">
          Popular Content
        </Title>
        <Center>
          <Button onClick={fetchPopular} size="lg">
            Load Popular Content
          </Button>
        </Center>
      </motion.div>
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

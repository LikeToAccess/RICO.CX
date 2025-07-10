import React, { useEffect, useState } from 'react';
import { useParams } from 'react-router-dom';
import { Container, Title, Grid, Loader, Center, Alert, Text } from '@mantine/core';
import { motion } from 'framer-motion';
import { apiService } from '../services/api';
import { SearchForm } from '../components/SearchForm';
import { VideoCard } from '../components/VideoCard';
import type { SearchResult } from '../services/api';

export const SearchPage: React.FC = () => {
  const { query } = useParams<{ query: string }>();
  const [results, setResults] = useState<SearchResult[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const performSearch = async () => {
      if (!query) return;

      try {
        setLoading(true);
        setError(null);
        
        let data: SearchResult[];
        if (query === 'popular') {
          data = await apiService.getPopular();
        } else {
          data = await apiService.search(decodeURIComponent(query));
        }
        
        setResults(data);
      } catch (err: unknown) {
        const errorMsg = err instanceof Error ? err.message : 'Search failed';
        setError(errorMsg);
        console.error('Search error:', err);
        console.error('Error details:', {
          err,
          query,
          decodedQuery: decodeURIComponent(query)
        });
      } finally {
        setLoading(false);
      }
    };

    performSearch();
  }, [query]);

  return (
    <Container size="xl" py="xl">
      <motion.div
        initial={{ opacity: 0, y: 30 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.6 }}
      >
        <Title order={1} mb="xl" ta="center">
          {query === 'popular' ? 'Popular Content' : `Search Results for "${decodeURIComponent(query || '')}"`}
        </Title>

        <SearchForm />

        {loading && (
          <Center h={300}>
            <Loader size="lg" />
          </Center>
        )}

        {error && (
          <Alert color="red" title="Error" mb="xl">
            {error}
          </Alert>
        )}

        {!loading && !error && results.length === 0 && query && (
          <Center h={200}>
            <Text size="lg" c="dimmed">
              No results found for "{decodeURIComponent(query)}"
            </Text>
          </Center>
        )}

        {results.length > 0 && (
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.2, duration: 0.6 }}
          >
            <Grid>
              {results.map((result, index) => (
                <Grid.Col key={result.id || result.page_url || index} span={{ base: 12, sm: 6, md: 4, lg: 3 }}>
                  <motion.div
                    initial={{ opacity: 0, y: 20 }}
                    animate={{ opacity: 1, y: 0 }}
                    transition={{ delay: index * 0.1, duration: 0.5 }}
                  >
                    <VideoCard result={{ ...result, id: result.id || index }} />
                  </motion.div>
                </Grid.Col>
              ))}
            </Grid>
          </motion.div>
        )}
      </motion.div>
    </Container>
  );
};

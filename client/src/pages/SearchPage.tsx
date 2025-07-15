import React, { useEffect, useState } from 'react';
import { useParams } from 'react-router-dom';
import { Loader, Center, Alert, Text } from '@mantine/core';
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
        setResults([]); // Clear previous results immediately
        
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
    <div style={{ 
      minHeight: '100vh', 
      background: 'transparent',
      paddingTop: '6rem'
    }}>
      <motion.div
        initial={{ opacity: 0, y: 30 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.6 }}
      >
        <div style={{ 
          maxWidth: '800px', 
          margin: '0 auto 2rem auto', 
          padding: '0 1rem'
        }}>
          <SearchForm initialQuery={query !== 'popular' ? decodeURIComponent(query || '') : ''} />
        </div>

        {loading && (
          <Center h={300}>
            <div className="preloader">
              <Loader size="lg" color="var(--secondary-color)" />
            </div>
          </Center>
        )}

        {error && (
          <div style={{ 
            maxWidth: '800px', 
            margin: '0 auto', 
            padding: '0 1rem' 
          }}>
            <Alert 
              color="red" 
              title="Error" 
              style={{
                backgroundColor: 'var(--result-card-background-color)',
                borderColor: '#FF0000',
                color: 'var(--body-text-color)',
                backdropFilter: 'blur(10px)'
              }}
            >
              {error}
            </Alert>
          </div>
        )}

        {!loading && !error && results.length === 0 && query && (
          <Center h={200}>
            <Text 
              size="lg" 
              style={{ 
                color: 'var(--body-text-color)', 
                opacity: 0.8 
              }}
            >
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
            <section 
              id="results-section"
              style={{
                display: 'flex',
                flexWrap: 'wrap',
                justifyContent: 'center',
                gap: '1rem',
                padding: '0 1rem',
                marginTop: '2rem'
              }}
            >
              {results.map((result, index) => (
                <motion.div
                  key={result.id || result.page_url || index}
                  initial={{ opacity: 0, y: 20 }}
                  animate={{ opacity: 1, y: 0 }}
                  transition={{ delay: index * 0.1, duration: 0.5 }}
                >
                  <VideoCard result={{ ...result, id: result.id || index }} />
                </motion.div>
              ))}
            </section>
          </motion.div>
        )}
      </motion.div>
    </div>
  );
};

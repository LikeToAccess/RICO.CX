import React, { useState, useEffect } from 'react';
import { TextInput, Button } from '@mantine/core';
import { IconSearch } from '@tabler/icons-react';
import { useNavigate } from 'react-router-dom';
import { motion } from 'framer-motion';

interface SearchFormProps {
  initialQuery?: string;
}

export const SearchForm: React.FC<SearchFormProps> = ({ initialQuery = '' }) => {
  const [query, setQuery] = useState(initialQuery);
  const navigate = useNavigate();

  useEffect(() => {
    setQuery(initialQuery);
  }, [initialQuery]);

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (query.trim()) {
      navigate(`/search/${encodeURIComponent(query.trim())}`);
    }
  };

  const handlePopular = () => {
    navigate('/search/popular');
  };

  return (
    <motion.div
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.5 }}
    >
      <div 
        className="admin-card"
        style={{ 
          padding: '2rem', 
          marginBottom: '2rem',
          backgroundColor: 'var(--result-card-background-color)',
          border: '1px solid #808080',
          borderRadius: '12px',
          backdropFilter: 'blur(10px)'
        }}
      >
        <form onSubmit={handleSubmit}>
          <div style={{ 
            display: 'flex', 
            flexDirection: 'column',
            gap: '1rem'
          }}>
            <TextInput
              placeholder="Search for movies, TV shows..."
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              leftSection={<IconSearch size={16} />}
              size="lg"
              styles={{
                input: {
                  backgroundColor: 'var(--background-color)',
                  borderColor: 'var(--secondary-color)',
                  color: 'var(--body-text-color)',
                  '&::placeholder': {
                    color: 'var(--body-text-color)',
                    opacity: 0.6
                  },
                  '&:focus': {
                    borderColor: 'var(--secondary-color)',
                    boxShadow: `0 0 0 1px var(--secondary-color)`
                  }
                },
                label: {
                  color: 'var(--body-text-color)'
                }
              }}
            />
            
            <div 
              className="search-buttons"
              style={{
                display: 'flex',
                gap: '0.75rem',
                flexDirection: 'row'
              }}
            >
              <Button 
                type="submit" 
                size="lg" 
                disabled={!query.trim()}
                style={{
                  backgroundColor: 'var(--secondary-color)',
                  borderColor: 'var(--secondary-color)',
                  color: 'white',
                  transition: 'all 0.2s',
                  flex: 1
                }}
              >
                Search
              </Button>
              <Button 
                variant="outline" 
                size="lg" 
                onClick={handlePopular}
                style={{
                  borderColor: 'var(--secondary-color)',
                  color: 'var(--secondary-color)',
                  backgroundColor: 'transparent',
                  transition: 'all 0.2s',
                  flex: 1
                }}
              >
                Popular
              </Button>
            </div>
          </div>
        </form>
      </div>
    </motion.div>
  );
};

import React, { useState } from 'react';
import { TextInput, Button, Group } from '@mantine/core';
import { IconSearch } from '@tabler/icons-react';
import { useNavigate } from 'react-router-dom';
import { motion } from 'framer-motion';

export const SearchForm: React.FC = () => {
  const [query, setQuery] = useState('');
  const navigate = useNavigate();

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
          <Group gap="md" style={{ alignItems: 'flex-end' }}>
            <TextInput
              placeholder="Search for movies, TV shows..."
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              leftSection={<IconSearch size={16} />}
              style={{ flex: 1 }}
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
            <Button 
              type="submit" 
              size="lg" 
              disabled={!query.trim()}
              style={{
                backgroundColor: 'var(--secondary-color)',
                borderColor: 'var(--secondary-color)',
                color: 'white',
                transition: 'all 0.2s'
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
                transition: 'all 0.2s'
              }}
            >
              Popular
            </Button>
          </Group>
        </form>
      </div>
    </motion.div>
  );
};

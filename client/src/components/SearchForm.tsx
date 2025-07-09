import React, { useState } from 'react';
import { TextInput, Button, Group, Paper } from '@mantine/core';
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
      <Paper p="lg" radius="md" mb="xl" style={{ background: 'rgba(255, 255, 255, 0.05)' }}>
        <form onSubmit={handleSubmit}>
          <Group gap="md">
            <TextInput
              placeholder="Search for movies, TV shows..."
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              leftSection={<IconSearch size={16} />}
              style={{ flex: 1 }}
              size="lg"
            />
            <Button type="submit" size="lg" disabled={!query.trim()}>
              Search
            </Button>
            <Button variant="outline" size="lg" onClick={handlePopular}>
              Popular
            </Button>
          </Group>
        </form>
      </Paper>
    </motion.div>
  );
};

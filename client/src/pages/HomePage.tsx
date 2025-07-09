import React from 'react';
import { useParams } from 'react-router-dom';
import { Container, Title } from '@mantine/core';
import { motion } from 'framer-motion';
import { SearchForm } from '../components/SearchForm';
import { VideoPlayer } from '../components/VideoPlayer';
import { PopularContent } from '../components/PopularContent';

export const HomePage: React.FC = () => {
  const { videoUrl } = useParams<{ videoUrl: string }>();

  return (
    <Container size="xl" py="xl">
      <motion.div
        initial={{ opacity: 0, y: 30 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.6 }}
      >
        <Title
          order={1}
          size="h1"
          mb="xl"
          ta="center"
          style={{
            fontFamily: 'YouTubeSansDarkSemibold, Poppins, sans-serif',
            background: 'linear-gradient(45deg, #3b82f6, #8b5cf6)',
            backgroundClip: 'text',
            WebkitBackgroundClip: 'text',
            WebkitTextFillColor: 'transparent',
          }}
        >
          Welcome to RICO.CX
        </Title>

        <SearchForm />

        {videoUrl && (
          <motion.div
            initial={{ opacity: 0, scale: 0.9 }}
            animate={{ opacity: 1, scale: 1 }}
            transition={{ delay: 0.3, duration: 0.5 }}
          >
            <VideoPlayer videoUrl={videoUrl} />
          </motion.div>
        )}

        <motion.div
          initial={{ opacity: 0, y: 30 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.4, duration: 0.6 }}
        >
          <PopularContent />
        </motion.div>
      </motion.div>
    </Container>
  );
};

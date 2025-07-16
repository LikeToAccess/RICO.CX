import React from 'react';
import { useParams } from 'react-router-dom';
import { motion } from 'framer-motion';
import { SearchForm } from '../components/SearchForm';
import { VideoPlayer } from '../components/VideoPlayer';

export const HomePage: React.FC = () => {
  const { videoUrl } = useParams<{ videoUrl: string }>();

  return (
    <div style={{ 
      minHeight: '100vh', 
      background: 'transparent',
      paddingTop: '8rem',
      display: 'flex',
      flexDirection: 'column',
      alignItems: 'center'
    }}>
      <motion.div
        initial={{ opacity: 0, y: 30 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.6 }}
        style={{ width: '100%', maxWidth: '800px', padding: '0 2rem' }}
      >
        <SearchForm />
      </motion.div>

      {videoUrl && (
        <motion.div
          initial={{ opacity: 0, scale: 0.9 }}
          animate={{ opacity: 1, scale: 1 }}
          transition={{ delay: 0.3, duration: 0.5 }}
          style={{ 
            margin: '2rem auto', 
            maxWidth: '1200px', 
            padding: '0 2rem',
            width: '100%'
          }}
        >
          <VideoPlayer videoUrl={videoUrl} />
        </motion.div>
      )}
    </div>
  );
};

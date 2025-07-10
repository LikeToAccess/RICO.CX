import React from 'react';
import { useParams } from 'react-router-dom';
import { motion } from 'framer-motion';
import { SearchForm } from '../components/SearchForm';
import { VideoPlayer } from '../components/VideoPlayer';
import { PopularContent } from '../components/PopularContent';

export const HomePage: React.FC = () => {
  const { videoUrl } = useParams<{ videoUrl: string }>();

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
        <h1
          className="title"
          style={{
            fontFamily: 'Poppins, sans-serif',
            color: '#ffffff',
            textAlign: 'center',
            fontSize: '3rem',
            fontWeight: 'bold',
            margin: '2rem 0'
          }}
        >
          Welcome to RICO.CX
        </h1>

        <div style={{ 
          maxWidth: '800px', 
          margin: '0 auto', 
          padding: '0 2rem' 
        }}>
          <SearchForm />
        </div>

        {videoUrl && (
          <motion.div
            initial={{ opacity: 0, scale: 0.9 }}
            animate={{ opacity: 1, scale: 1 }}
            transition={{ delay: 0.3, duration: 0.5 }}
            style={{ 
              margin: '2rem auto', 
              maxWidth: '1200px', 
              padding: '0 2rem' 
            }}
          >
            <VideoPlayer videoUrl={videoUrl} />
          </motion.div>
        )}

        <motion.div
          initial={{ opacity: 0, y: 30 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.4, duration: 0.6 }}
          style={{ 
            margin: '2rem auto', 
            maxWidth: '1200px', 
            padding: '0 2rem' 
          }}
        >
          <PopularContent />
        </motion.div>
      </motion.div>
    </div>
  );
};

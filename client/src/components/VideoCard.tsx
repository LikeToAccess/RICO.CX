import React, { useState, useRef, useEffect } from 'react';
import { Button, Loader } from '@mantine/core';
import { IconDownload, IconCheck, IconX } from '@tabler/icons-react';
import { motion } from 'framer-motion';
import { apiService } from '../services/api';
import { notifications } from '@mantine/notifications';
import type { SearchResult } from '../services/api';

interface VideoCardProps {
  result: SearchResult;
}

export const VideoCard: React.FC<VideoCardProps> = ({ result }) => {
  const [isDownloading, setIsDownloading] = useState(false);
  const [downloadStatus, setDownloadStatus] = useState<'idle' | 'downloading' | 'success' | 'error'>('idle');
  const [titleHeight, setTitleHeight] = useState(0);
  const titleRef = useRef<HTMLDivElement>(null);

  // Handle both flat and nested data structures
  // Prioritize FileBot-processed title over raw filename
  const title = result.title || result.filename || 'Unknown Title';

  useEffect(() => {
    if (titleRef.current) {
      setTitleHeight(titleRef.current.offsetHeight);
    }
  }, [title]); // Now title is defined

  // Calculate dynamic position based on title height
  // Single line is about 24px (20px font * 1.2 line-height), wrapped is about 48px
  const isWrapped = titleHeight > 35; 
  const filenameTopPosition = isWrapped ? '500px' : '485px';

  const poster = result.poster_url || 'http://localhost:5000/static/img/missing_poster.svg';
  const quality = result.quality_tag || '';
  const description = result.description || '';
  const year = result.release_year || '';
  const duration = result.duration || '';
  const imdbScore = result.score || '';
  const genre = result.genre || '';

  // Debug logging to understand the comparison
  if (result.filename_old) {
    console.log('Debug comparison:', {
      title: title.trim(),
      filename_old: result.filename_old.trim(),
      areEqual: result.filename_old.trim() === title.trim(),
      result_title: result.title,
      result_filename: result.filename
    });
  }

  const handleDownload = async () => {
    try {
      setIsDownloading(true);
      setDownloadStatus('downloading');
      
      await apiService.downloadVideo(result.page_url, result.id || 0);
      
      setDownloadStatus('success');
      notifications.show({
        title: 'Download Started',
        message: `${result.title} has been added to the download queue`,
        color: 'green',
        icon: <IconCheck size={16} />,
      });
    } catch (error: unknown) {
      setDownloadStatus('error');
      const errorMessage = error instanceof Error ? error.message : 'Failed to start download';
      notifications.show({
        title: 'Download Failed',
        message: errorMessage,
        color: 'red',
        icon: <IconX size={16} />,
      });
    } finally {
      setIsDownloading(false);
    }
  };

  const getDownloadButton = () => {
    const buttonStyle = {
      width: '100%',
      fontSize: '14px',
      padding: '8px 16px',
      borderRadius: '4px',
      border: 'none',
      cursor: 'pointer',
      transition: 'all 0.2s',
      fontFamily: 'Poppins, sans-serif',
      fontWeight: 'bold'
    };

    switch (downloadStatus) {
      case 'downloading':
        return (
          <Button 
            leftSection={<Loader size={16} />} 
            disabled 
            size="sm"
            style={{
              ...buttonStyle,
              backgroundColor: '#999',
              color: 'white'
            }}
          >
            Downloading...
          </Button>
        );
      case 'success':
        return (
          <Button 
            leftSection={<IconCheck size={16} />} 
            color="green" 
            disabled 
            size="sm"
            style={{
              ...buttonStyle,
              backgroundColor: '#4CAF50',
              color: 'white'
            }}
          >
            Downloaded
          </Button>
        );
      case 'error':
        return (
          <Button 
            leftSection={<IconDownload size={16} />} 
            color="red" 
            onClick={handleDownload}
            size="sm"
            style={{
              ...buttonStyle,
              backgroundColor: '#FF0000',
              color: 'white'
            }}
          >
            Retry
          </Button>
        );
      default:
        return (
          <Button 
            leftSection={<IconDownload size={16} />} 
            onClick={handleDownload} 
            disabled={isDownloading}
            size="sm"
            style={{
              ...buttonStyle,
              backgroundColor: 'var(--secondary-color)',
              color: 'white'
            }}
          >
            Download
          </Button>
        );
    }
  };

  return (
    <motion.div
      whileHover={{ scale: 1.05 }}
      whileTap={{ scale: 0.98 }}
      transition={{ type: "spring", stiffness: 300, damping: 20 }}
      style={{ height: '100%' }}
      className="search-result"
    >
      <div style={{ 
        position: 'relative',
        width: '280px',
        minWidth: '280px',
        height: '620px',
        backgroundColor: 'var(--result-card-background-color)',
        border: '1px solid #808080',
        borderRadius: '12px',
        margin: '3px',
        marginBottom: '12px',
        transition: '0.2s',
        display: 'flex',
        flexDirection: 'column'
      }}>
        {/* Poster Image */}
        <img
          src={poster}
          alt={title}
          className="result-thumbnail"
          style={{
            width: '100%',
            height: '420px',
            borderRadius: 'inherit',
            borderBottomRightRadius: 0,
            borderBottomLeftRadius: 0,
            borderBottom: 'inherit',
            cursor: 'pointer',
            objectFit: 'cover',
            display: 'block'
          }}
          onError={(e) => {
            const target = e.currentTarget;
            // First fallback: try the server's missing poster
            if (target.src !== "http://localhost:5000/static/img/missing_poster.svg") {
              target.src = "http://localhost:5000/static/img/missing_poster.svg";
            } else {
              // Second fallback: use a data URL with a simple gray placeholder
              target.src = "data:image/svg+xml;base64,PHN2ZyB3aWR0aD0iMzAwIiBoZWlnaHQ9IjQ1MCIgdmlld0JveD0iMCAwIDMwMCA0NTAiIGZpbGw9Im5vbmUiIHhtbG5zPSJodHRwOi8vd3d3LnczLm9yZy8yMDAwL3N2ZyI+PHJlY3Qgd2lkdGg9IjMwMCIgaGVpZ2h0PSI0NTAiIGZpbGw9IiM0YTRhNGEiLz48dGV4dCB4PSIxNTAiIHk9IjIyNSIgZm9udC1mYW1pbHk9IkFyaWFsLCBzYW5zLXNlcmlmIiBmb250LXNpemU9IjE4IiBmaWxsPSIjZmZmIiB0ZXh0LWFuY2hvcj0ibWlkZGxlIiBkeT0iLjNlbSI+Tm8gUG9zdGVyPC90ZXh0Pjwvc3ZnPg==";
            }
          }}
        />

        {/* Quality Badge */}
        {quality && (
          <div className="label result-quality" style={{
            position: 'absolute',
            top: '5px',
            right: '12px',
            backgroundColor: 'rgba(49, 130, 206, 0.8)',
            color: 'var(--body-text-color)',
            fontSize: '14px',
            padding: '4px 10px',
            borderRadius: '80vw',
            fontFamily: 'LexendBold, Poppins, sans-serif',
            fontWeight: 'bold'
          }}>
            {quality}
          </div>
        )}

        {/* Info Pills Grid */}
        <div style={{
          position: 'absolute',
          bottom: '52px',
          left: '12px',
          right: '12px',
          display: 'grid',
          gridTemplateColumns: 'repeat(auto-fit, minmax(60px, 1fr))',
          gap: '6px',
          alignItems: 'center'
        }}>
          {/* Year Badge */}
          {year && (
            <div className="label result-year" style={{
              backgroundColor: 'rgba(49, 130, 206, 0.6)',
              color: 'var(--body-text-color)',
              fontSize: '14px',
              padding: '4px 10px',
              borderRadius: '80vw',
              fontFamily: 'LexendBold, Poppins, sans-serif',
              fontWeight: 'bold',
              textAlign: 'center',
              whiteSpace: 'nowrap',
              overflow: 'hidden',
              textOverflow: 'ellipsis'
            }}>
              {year}
            </div>
          )}

          {/* Score Badge */}
          {imdbScore && (
            <div className="label result-score" style={{
              backgroundColor: 'rgba(229, 62, 62, 0.8)',
              color: 'var(--body-text-color)',
              fontSize: '14px',
              padding: '4px 10px',
              borderRadius: '80vw',
              fontFamily: 'LexendBold, Poppins, sans-serif',
              fontWeight: 'bold',
              textAlign: 'center',
              whiteSpace: 'nowrap',
              overflow: 'hidden',
              textOverflow: 'ellipsis'
            }}>
              {imdbScore}
            </div>
          )}

          {/* Duration Badge */}
          {duration && (
            <div className="label result-duration" style={{
              backgroundColor: 'rgba(0, 181, 216, 0.6)',
              color: 'var(--body-text-color)',
              fontSize: '14px',
              padding: '4px 10px',
              borderRadius: '80vw',
              fontFamily: 'LexendBold, Poppins, sans-serif',
              fontWeight: 'bold',
              textAlign: 'center',
              whiteSpace: 'nowrap',
              overflow: 'hidden',
              textOverflow: 'ellipsis'
            }}>
              {duration}min
            </div>
          )}
        </div>

        {/* Title */}
        <div 
          ref={titleRef}
          className="result-title" 
          style={{
            position: 'absolute',
            textAlign: 'left',
            top: '450px',
            left: '16px',
            right: '16px',
            fontFamily: '"Open Sans", sans-serif',
            color: 'var(--body-text-color)',
            fontSize: '20px',
            fontWeight: '600',
            lineHeight: '1.2',
            overflow: 'hidden',
            textOverflow: 'ellipsis',
            display: '-webkit-box',
            WebkitLineClamp: 2,
            WebkitBoxOrient: 'vertical' as const
          }}
        >
          {title}
        </div>

        {/* Original Filename */}
        {result.filename_old && result.filename_old.trim() !== title.trim() && (
          <div className="result-filename" style={{
            position: 'absolute',
            textAlign: 'left',
            top: filenameTopPosition,
            left: '16px',
            right: '16px',
            fontFamily: '"Open Sans", sans-serif',
            fontSize: '12px',
            color: 'var(--body-text-color)',
            opacity: 0.6,
            fontStyle: 'italic',
            overflow: 'hidden',
            textOverflow: 'ellipsis',
            display: '-webkit-box',
            WebkitLineClamp: 1,
            WebkitBoxOrient: 'vertical' as const
          }}>
            {result.filename_old}
          </div>
        )}

        {/* Description/Genre */}
        {(description || genre) && (
          <div className="result-subtitle" style={{
            position: 'absolute',
            textAlign: 'left',
            top: '505px',
            left: '16px',
            right: '16px',
            fontFamily: '"Open Sans", sans-serif',
            fontSize: '14px',
            color: 'var(--body-text-color)',
            opacity: 0.8,
            overflow: 'hidden',
            textOverflow: 'ellipsis',
            display: '-webkit-box',
            WebkitLineClamp: 1,
            WebkitBoxOrient: 'vertical' as const
          }}>
            {description || genre}
          </div>
        )}

        {/* Download Button */}
        <div style={{
          position: 'absolute',
          bottom: '12px',
          left: '50%',
          transform: 'translateX(-50%)',
          width: 'calc(100% - 24px)'
        }}>
          {getDownloadButton()}
        </div>
      </div>
    </motion.div>
  );
};

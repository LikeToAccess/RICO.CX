import React from 'react';
import { Text, Button, Avatar, Menu } from '@mantine/core';
import { useAuth } from '../hooks/useAuth';
import { useNavigate } from 'react-router-dom';
import { motion } from 'framer-motion';
import type { ReactNode } from 'react';

interface LayoutProps {
  children: ReactNode;
}

export const Layout: React.FC<LayoutProps> = ({ children }) => {
  const { user, isAuthenticated, login, logout } = useAuth();
  const navigate = useNavigate();

  const handleHomeClick = () => {
    navigate('/');
  };

  return (
    <div style={{ 
      minHeight: '100vh',
      backgroundColor: 'transparent',
      backgroundImage: 'var(--body-background-image)',
      backgroundSize: 'cover',
      backgroundRepeat: 'no-repeat',
      backgroundAttachment: 'fixed',
      position: 'relative'
    }}>
      {/* Top Left - Rico's Island */}
      <motion.div
        initial={{ x: -50, opacity: 0 }}
        animate={{ x: 0, opacity: 1 }}
        transition={{ duration: 0.5 }}
        style={{
          position: 'fixed',
          top: '2rem',
          left: '2rem',
          zIndex: 1000
        }}
      >
        <Text
          size="2xl"
          fw={700}
          className="title"
          onClick={handleHomeClick}
          style={{
            fontFamily: 'Poppins, sans-serif',
            color: '#ffffff',
            fontSize: '1.8rem',
            fontWeight: 'bold',
            cursor: 'pointer',
            transition: 'color 0.2s ease'
          }}
          onMouseEnter={(e) => {
            (e.target as HTMLElement).style.color = 'var(--secondary-color)';
          }}
          onMouseLeave={(e) => {
            (e.target as HTMLElement).style.color = '#ffffff';
          }}
        >
          Rico's Island
        </Text>
      </motion.div>

      {/* Top Right - Login */}
      <motion.div
        initial={{ x: 50, opacity: 0 }}
        animate={{ x: 0, opacity: 1 }}
        transition={{ duration: 0.5 }}
        style={{
          position: 'fixed',
          top: '2rem',
          right: '2rem',
          zIndex: 1000
        }}
      >
        {isAuthenticated ? (
          <div style={{ position: 'relative' }}>
            <Menu 
              shadow="md" 
              width={248}
              styles={{
                dropdown: {
                  backgroundColor: 'var(--primary-color)',
                  borderRadius: '4px',
                  boxShadow: '0 3px 10px rgb(0 0 0 / 0.8)',
                  border: '1px solid var(--background-color)'
                }
              }}
            >
              <Menu.Target>
                <div style={{ 
                  display: 'flex', 
                  alignItems: 'center', 
                  cursor: 'pointer',
                  padding: '8px',
                  borderRadius: '4px',
                  transition: 'background-color 0.2s'
                }}>
                  <Avatar
                    src={user?.profile_pic}
                    size={50}
                    radius="50%"
                    style={{ marginRight: '10px' }}
                  />
                  <Text style={{ 
                    color: '#ffffff'
                  }}>
                    {user?.first_name}
                  </Text>
                </div>
              </Menu.Target>

              <Menu.Dropdown>
                <Menu.Item 
                  onClick={logout}
                  style={{ 
                    padding: '10px',
                    color: '#ffffff',
                    transition: 'background-color 0.2s'
                  }}
                >
                  Logout
                </Menu.Item>
              </Menu.Dropdown>
            </Menu>
          </div>
        ) : (
          <Button 
            onClick={login} 
            variant="filled"
            style={{
              backgroundColor: 'var(--secondary-color)',
              borderColor: 'var(--secondary-color)',
              color: 'white',
              transition: 'all 0.2s'
            }}
          >
            Login with Google
          </Button>
        )}
      </motion.div>

      {/* Main Content */}
      <motion.div
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.5 }}
        style={{ minHeight: '100vh', padding: 0 }}
      >
        {children}
      </motion.div>
    </div>
  );
};

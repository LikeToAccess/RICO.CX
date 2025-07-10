import React from 'react';
import { AppShell, Text, Group, Button, Avatar, Menu } from '@mantine/core';
import { useAuth } from '../hooks/useAuth';
import { motion } from 'framer-motion';
import type { ReactNode } from 'react';

interface LayoutProps {
  children: ReactNode;
}

export const Layout: React.FC<LayoutProps> = ({ children }) => {
  const { user, isAuthenticated, login, logout } = useAuth();

  return (
    <AppShell
      header={{ height: 80 }}
      styles={{
        main: {
          backgroundColor: 'transparent',
          minHeight: '100vh',
          padding: 0,
          backgroundImage: 'var(--body-background-image)',
          backgroundSize: 'cover',
          backgroundRepeat: 'no-repeat',
          backgroundAttachment: 'fixed',
        },
        header: {
          backgroundColor: 'transparent',
          borderBottom: 'none',
          backdropFilter: 'none',
        }
      }}
    >
      <AppShell.Header>
        <Group h="100%" px="md" justify="space-between" style={{ padding: '0 2rem' }}>
          <motion.div
            initial={{ x: -50, opacity: 0 }}
            animate={{ x: 0, opacity: 1 }}
            transition={{ duration: 0.5 }}
          >
            <Text
              size="2xl"
              fw={700}
              className="title"
              style={{
                fontFamily: 'Poppins, sans-serif',
                color: '#ffffff',
                fontSize: '1.8rem',
                fontWeight: 'bold'
              }}
            >
              RICO.CX
            </Text>
          </motion.div>

          <Group>
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
          </Group>
        </Group>
      </AppShell.Header>

      <AppShell.Main style={{ padding: 0 }}>
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.5 }}
          style={{ minHeight: 'calc(100vh - 80px)' }}
        >
          {children}
        </motion.div>
      </AppShell.Main>
    </AppShell>
  );
};

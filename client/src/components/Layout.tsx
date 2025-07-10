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
      header={{ height: 70 }}
      styles={{
        main: {
          backgroundColor: 'var(--mantine-color-dark-8)',
          minHeight: '100vh',
        },
      }}
    >
      <AppShell.Header>
        <Group h="100%" px="md" justify="space-between">
          <motion.div
            initial={{ x: -50, opacity: 0 }}
            animate={{ x: 0, opacity: 1 }}
            transition={{ duration: 0.5 }}
          >
            <Text
              size="xl"
              fw={700}
              style={{
                fontFamily: 'YouTubeSansDarkSemibold, Poppins, sans-serif',
                color: 'var(--mantine-color-blue-4)',
              }}
            >
              RICO.CX
            </Text>
          </motion.div>

          <Group>
            {isAuthenticated ? (
              <Menu shadow="md" width={200}>
                <Menu.Target>
                  <Button
                    variant="subtle"
                    leftSection={
                      <Avatar
                        src={user?.profile_pic}
                        size="sm"
                        radius="xl"
                      />
                    }
                  >
                    {user?.first_name}
                  </Button>
                </Menu.Target>

                <Menu.Dropdown>
                  <Menu.Label>User Actions</Menu.Label>
                  <Menu.Item onClick={logout}>
                    Logout
                  </Menu.Item>
                </Menu.Dropdown>
              </Menu>
            ) : (
              <Button onClick={login} variant="filled">
                Login with Google
              </Button>
            )}
          </Group>
        </Group>
      </AppShell.Header>

      <AppShell.Main>
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.5 }}
        >
          {children}
        </motion.div>
      </AppShell.Main>
    </AppShell>
  );
};

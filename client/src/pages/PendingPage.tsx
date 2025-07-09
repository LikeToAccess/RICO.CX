import React from 'react';
import { Container, Title, Text, Paper, Center, Stack } from '@mantine/core';
import { motion } from 'framer-motion';
import { useAuth } from '../contexts/AuthContext';

export const PendingPage: React.FC = () => {
  const { user } = useAuth();

  return (
    <Container size="sm" py="xl">
      <motion.div
        initial={{ opacity: 0, y: 30 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.6 }}
      >
        <Center>
          <Paper p="xl" radius="md" withBorder>
            <Stack align="center" gap="lg">
              <Title order={1} ta="center">
                Account Pending Approval
              </Title>
              
              <Text size="lg" ta="center" c="dimmed">
                Welcome, {user?.first_name}!
              </Text>
              
              <Text ta="center">
                Your account has been created successfully, but you're currently waiting for approval from an administrator.
              </Text>
              
              <Text ta="center" size="sm" c="dimmed">
                You'll receive access to the platform once an admin approves your account. 
                Please check back later or contact support if you have any questions.
              </Text>
            </Stack>
          </Paper>
        </Center>
      </motion.div>
    </Container>
  );
};

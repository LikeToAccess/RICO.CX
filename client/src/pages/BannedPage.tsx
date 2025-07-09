import React from 'react';
import { Container, Title, Text, Paper, Center, Stack, Alert } from '@mantine/core';
import { IconExclamationMark } from '@tabler/icons-react';
import { motion } from 'framer-motion';

export const BannedPage: React.FC = () => {
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
              <Alert 
                icon={<IconExclamationMark size={16} />} 
                title="Account Suspended" 
                color="red"
                radius="md"
              >
                <Text>
                  Your account has been suspended by an administrator.
                </Text>
              </Alert>
              
              <Title order={1} ta="center" c="red">
                Access Denied
              </Title>
              
              <Text ta="center">
                Your account has been banned from accessing this platform. 
                This action was taken due to a violation of our terms of service.
              </Text>
              
              <Text ta="center" size="sm" c="dimmed">
                If you believe this is an error, please contact support for assistance.
              </Text>
            </Stack>
          </Paper>
        </Center>
      </motion.div>
    </Container>
  );
};

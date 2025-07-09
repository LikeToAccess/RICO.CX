import React, { useEffect, useState } from 'react';
import { Container, Title, Table, Button, Modal, Select, Alert, Badge, Group, ActionIcon } from '@mantine/core';
import { IconTrash, IconBan, IconShield } from '@tabler/icons-react';
import { motion } from 'framer-motion';
import { notifications } from '@mantine/notifications';
import { useAuth } from '../contexts/AuthContext';

interface User {
  id: string;
  first_name: string;
  last_name: string;
  email: string;
  banned: boolean;
}

interface GroupMembership {
  user_id: string;
  role: string;
}

export const AdminPage: React.FC = () => {
  const { group } = useAuth();
  const [users, setUsers] = useState<User[]>([]);
  const [groups, setGroups] = useState<GroupMembership[]>([]);
  const [selectedUser, setSelectedUser] = useState<string | null>(null);
  const [modalOpened, setModalOpened] = useState(false);
  const [actionType, setActionType] = useState<'delete' | 'ban' | 'unban' | 'change_role'>('delete');
  const [newRole, setNewRole] = useState<string>('');

  useEffect(() => {
    // In a real implementation, you would fetch users and groups from the API
    // For now, we'll show the admin interface structure
  }, []);

  const handleAction = async () => {
    if (!selectedUser) return;

    try {
      const formData = new FormData();
      formData.append('user_id', selectedUser);
      formData.append('action', actionType);
      if (actionType === 'change_role' && newRole) {
        formData.append('role', newRole);
      }

      const response = await fetch('/admin', {
        method: 'POST',
        body: formData,
        credentials: 'include',
      });

      if (response.ok) {
        notifications.show({
          title: 'Success',
          message: 'Action completed successfully',
          color: 'green',
        });
        setModalOpened(false);
        // Refresh data
      } else {
        throw new Error('Action failed');
      }
    } catch (error) {
      notifications.show({
        title: 'Error',
        message: 'Failed to perform action',
        color: 'red',
      });
    }
  };

  if (!group || !['Administrators', 'Root'].includes(group.role)) {
    return (
      <Container size="xl" py="xl">
        <Alert color="red" title="Access Denied">
          You don't have permission to access this page.
        </Alert>
      </Container>
    );
  }

  return (
    <Container size="xl" py="xl">
      <motion.div
        initial={{ opacity: 0, y: 30 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.6 }}
      >
        <Title order={1} mb="xl" ta="center">
          Admin Panel
        </Title>

        <Table striped highlightOnHover>
          <Table.Thead>
            <Table.Tr>
              <Table.Th>Name</Table.Th>
              <Table.Th>Email</Table.Th>
              <Table.Th>Role</Table.Th>
              <Table.Th>Status</Table.Th>
              <Table.Th>Actions</Table.Th>
            </Table.Tr>
          </Table.Thead>
          <Table.Tbody>
            {users.map((user) => {
              const userGroup = groups.find(g => g.user_id === user.id);
              return (
                <Table.Tr key={user.id}>
                  <Table.Td>{`${user.first_name} ${user.last_name}`}</Table.Td>
                  <Table.Td>{user.email}</Table.Td>
                  <Table.Td>
                    <Badge color={userGroup?.role === 'Root' ? 'red' : userGroup?.role === 'Administrators' ? 'orange' : 'blue'}>
                      {userGroup?.role || 'No Role'}
                    </Badge>
                  </Table.Td>
                  <Table.Td>
                    <Badge color={user.banned ? 'red' : 'green'}>
                      {user.banned ? 'Banned' : 'Active'}
                    </Badge>
                  </Table.Td>
                  <Table.Td>
                    <Group gap="xs">
                      <ActionIcon
                        color="red"
                        onClick={() => {
                          setSelectedUser(user.id);
                          setActionType('delete');
                          setModalOpened(true);
                        }}
                      >
                        <IconTrash size={16} />
                      </ActionIcon>
                      <ActionIcon
                        color="orange"
                        onClick={() => {
                          setSelectedUser(user.id);
                          setActionType(user.banned ? 'unban' : 'ban');
                          setModalOpened(true);
                        }}
                      >
                        <IconBan size={16} />
                      </ActionIcon>
                      <ActionIcon
                        color="blue"
                        onClick={() => {
                          setSelectedUser(user.id);
                          setActionType('change_role');
                          setModalOpened(true);
                        }}
                      >
                        <IconShield size={16} />
                      </ActionIcon>
                    </Group>
                  </Table.Td>
                </Table.Tr>
              );
            })}
          </Table.Tbody>
        </Table>

        <Modal
          opened={modalOpened}
          onClose={() => setModalOpened(false)}
          title="Confirm Action"
        >
          <div>
            <p>Are you sure you want to {actionType} this user?</p>
            
            {actionType === 'change_role' && (
              <Select
                label="New Role"
                placeholder="Select role"
                data={['Members', 'Administrators', 'Root']}
                value={newRole}
                onChange={(value) => setNewRole(value || '')}
                mt="md"
              />
            )}

            <Group justify="flex-end" mt="md">
              <Button variant="outline" onClick={() => setModalOpened(false)}>
                Cancel
              </Button>
              <Button color="red" onClick={handleAction}>
                Confirm
              </Button>
            </Group>
          </div>
        </Modal>
      </motion.div>
    </Container>
  );
};

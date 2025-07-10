import React, { useEffect, useState } from 'react';
import { Table, Button, Modal, Select, Alert, Badge, Group, ActionIcon } from '@mantine/core';
import { IconTrash, IconBan, IconShield } from '@tabler/icons-react';
import { motion } from 'framer-motion';
import { notifications } from '@mantine/notifications';
import { useAuth } from '../hooks/useAuth';

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
    // Fetch users and groups from the API
    const fetchUsersAndGroups = async () => {
      try {
        // This would normally fetch from your API
        // For now we'll set empty arrays, but you could populate with demo data
        setUsers([]);
        setGroups([]);
      } catch (error) {
        console.error('Failed to fetch data:', error);
      }
    };

    fetchUsersAndGroups();
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
      // eslint-disable-next-line @typescript-eslint/no-unused-vars
    } catch (_error) {
      notifications.show({
        title: 'Error',
        message: 'Failed to perform action',
        color: 'red',
      });
    }
  };

  if (!group || !['Administrators', 'Root'].includes(group.role)) {
    return (
      <div style={{ 
        minHeight: '100vh', 
        background: 'transparent',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        padding: '2rem'
      }}>
        <div className="admin-card" style={{ 
          padding: '2rem',
          maxWidth: '500px',
          textAlign: 'center'
        }}>
          <Alert 
            color="red" 
            title="Access Denied"
            styles={{
              root: {
                backgroundColor: 'transparent',
                borderColor: '#FF0000',
                color: '#ffffff'
              },
              title: {
                color: '#FF0000'
              }
            }}
          >
            You don't have permission to access this page.
          </Alert>
        </div>
      </div>
    );
  }

  return (
    <div style={{ minHeight: '100vh', background: 'transparent' }}>
      <motion.div
        initial={{ opacity: 0, y: 30 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.6 }}
        style={{ padding: '2rem' }}
      >
        <h1 className="title page-title" style={{ 
          fontSize: '2.5rem', 
          marginBottom: '2rem',
          color: '#ffffff',
          fontFamily: 'Poppins, sans-serif'
        }}>
          Admin Panel
        </h1>

        <div className="admin-card" style={{ 
          padding: '2rem', 
          margin: '0 auto', 
          maxWidth: '1200px',
          marginBottom: '2rem'
        }}>
          <Table 
            striped 
            highlightOnHover
            style={{ 
              backgroundColor: 'transparent',
              borderCollapse: 'collapse',
              width: '100%'
            }}
          >
            <Table.Thead>
              <Table.Tr>
                <Table.Th style={{ 
                  backgroundColor: '#4a4a4a',
                  color: '#ffffff',
                  padding: '12px 8px',
                  border: '1px solid #4a4a4a'
                }}>Name</Table.Th>
                <Table.Th style={{ 
                  backgroundColor: '#4a4a4a',
                  color: '#ffffff',
                  padding: '12px 8px',
                  border: '1px solid #4a4a4a'
                }}>Email</Table.Th>
                <Table.Th style={{ 
                  backgroundColor: '#4a4a4a',
                  color: '#ffffff',
                  padding: '12px 8px',
                  border: '1px solid #4a4a4a'
                }}>Role</Table.Th>
                <Table.Th style={{ 
                  backgroundColor: '#4a4a4a',
                  color: '#ffffff',
                  padding: '12px 8px',
                  border: '1px solid #4a4a4a'
                }}>Status</Table.Th>
                <Table.Th style={{ 
                  backgroundColor: '#4a4a4a',
                  color: '#ffffff',
                  padding: '12px 8px',
                  border: '1px solid #4a4a4a'
                }}>Actions</Table.Th>
              </Table.Tr>
            </Table.Thead>
            <Table.Tbody>
              {users.length === 0 ? (
                <Table.Tr>
                  <Table.Td colSpan={5} style={{ 
                    textAlign: 'center', 
                    padding: '2rem',
                    color: '#ffffff',
                    backgroundColor: 'rgba(58, 58, 58, 0.5)'
                  }}>
                    No users found. Users will appear here when loaded from the API.
                  </Table.Td>
                </Table.Tr>
              ) : (
                users.map((user) => {
                  const userGroup = groups.find(g => g.user_id === user.id);
                  return (
                    <Table.Tr 
                      key={user.id}
                      style={{ 
                        backgroundColor: 'transparent',
                        transition: 'background-color 0.2s'
                      }}
                      className={user.banned ? 'banned' : ''}
                    >
                      <Table.Td style={{ 
                        padding: '8px',
                        border: '1px solid #4a4a4a',
                        color: '#ffffff'
                      }}>{`${user.first_name} ${user.last_name}`}</Table.Td>
                      <Table.Td style={{ 
                        padding: '8px',
                        border: '1px solid #4a4a4a',
                        color: '#ffffff'
                      }}>{user.email}</Table.Td>
                      <Table.Td style={{ 
                        padding: '8px',
                        border: '1px solid #4a4a4a'
                      }}>
                        <Badge color={userGroup?.role === 'Root' ? 'red' : userGroup?.role === 'Administrators' ? 'orange' : 'blue'}>
                          {userGroup?.role || 'No Role'}
                        </Badge>
                      </Table.Td>
                      <Table.Td style={{ 
                        padding: '8px',
                        border: '1px solid #4a4a4a'
                      }}>
                        <Badge color={user.banned ? 'red' : 'green'}>
                          {user.banned ? 'Banned' : 'Active'}
                        </Badge>
                      </Table.Td>
                      <Table.Td style={{ 
                        padding: '8px',
                        border: '1px solid #4a4a4a'
                      }}>
                        <Group gap="xs">
                          <ActionIcon
                            color="red"
                            onClick={() => {
                              setSelectedUser(user.id);
                              setActionType('delete');
                              setModalOpened(true);
                            }}
                            style={{ transition: 'transform 0.2s' }}
                            className="action-icon"
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
                            style={{ transition: 'transform 0.2s' }}
                            className="action-icon"
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
                            style={{ transition: 'transform 0.2s' }}
                            className="action-icon"
                          >
                            <IconShield size={16} />
                          </ActionIcon>
                        </Group>
                      </Table.Td>
                    </Table.Tr>
                  );
                })
              )}
            </Table.Tbody>
          </Table>
        </div>

        <Modal
          opened={modalOpened}
          onClose={() => setModalOpened(false)}
          title="Confirm Action"
          styles={{
            content: {
              backgroundColor: '#3a3a3a',
              backdropFilter: 'blur(10px)',
              border: '1px solid #4a4a4a',
              borderRadius: '12px'
            },
            header: {
              backgroundColor: 'transparent',
              color: '#ffffff',
              borderBottom: '1px solid #4a4a4a'
            },
            body: {
              backgroundColor: 'transparent',
              color: '#ffffff'
            }
          }}
        >
          <div>
            <p style={{ color: '#ffffff', marginBottom: '1rem' }}>
              Are you sure you want to {actionType} this user?
            </p>
            
            {actionType === 'change_role' && (
              <Select
                label="New Role"
                placeholder="Select role"
                data={['Members', 'Administrators', 'Root']}
                value={newRole}
                onChange={(value) => setNewRole(value || '')}
                styles={{
                  input: {
                    backgroundColor: '#3a3a3a',
                    borderColor: '#4a90e2',
                    color: '#ffffff'
                  },
                  label: {
                    color: '#ffffff'
                  }
                }}
                mt="md"
              />
            )}

            <Group justify="flex-end" mt="md">
              <Button 
                variant="outline" 
                onClick={() => setModalOpened(false)}
                styles={{
                  root: {
                    borderColor: '#4a90e2',
                    color: '#4a90e2',
                    backgroundColor: 'transparent'
                  }
                }}
              >
                Cancel
              </Button>
              <Button 
                color="red" 
                onClick={handleAction}
                styles={{
                  root: {
                    backgroundColor: '#FF0000',
                    borderColor: '#FF0000'
                  }
                }}
              >
                Confirm
              </Button>
            </Group>
          </div>
        </Modal>
      </motion.div>
    </div>
  );
};

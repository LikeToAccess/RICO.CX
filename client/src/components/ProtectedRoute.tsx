import React from 'react';
import { Navigate } from 'react-router-dom';
import { useAuth } from '../contexts/AuthContext';
import { Loader, Center } from '@mantine/core';
import type { ReactNode } from 'react';

interface ProtectedRouteProps {
  children: ReactNode;
  requiredRole?: string[];
}

export const ProtectedRoute: React.FC<ProtectedRouteProps> = ({ 
  children, 
  requiredRole 
}) => {
  const { isAuthenticated, isLoading, user, group } = useAuth();

  if (isLoading) {
    return (
      <Center h={200}>
        <Loader size="lg" />
      </Center>
    );
  }

  if (!isAuthenticated) {
    return <Navigate to="/" replace />;
  }

  if (user?.banned) {
    return <Navigate to="/banned" replace />;
  }

  if (!group && window.location.pathname !== '/pending') {
    return <Navigate to="/pending" replace />;
  }

  if (requiredRole && group && !requiredRole.includes(group.role)) {
    return <Navigate to="/" replace />;
  }

  return <>{children}</>;
};

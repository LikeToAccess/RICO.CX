import React from 'react';
import { Routes, Route } from 'react-router-dom';
import { AppShell } from '@mantine/core';
import { Layout } from './Layout';
import { HomePage } from '../pages/HomePage';
import { SearchPage } from '../pages/SearchPage';
import { AdminPage } from '../pages/AdminPage';
import { PendingPage } from '../pages/PendingPage';
import { BannedPage } from '../pages/BannedPage';
import { ProtectedRoute } from './ProtectedRoute';

export const AppRouter: React.FC = () => {
  return (
    <Layout>
      <Routes>
        <Route path="/" element={<HomePage />} />
        <Route path="/:videoUrl" element={<HomePage />} />
        <Route path="/search" element={<SearchPage />} />
        <Route path="/search/:query" element={<SearchPage />} />
        <Route 
          path="/admin" 
          element={
            <ProtectedRoute requiredRole={['Administrators', 'Root']}>
              <AdminPage />
            </ProtectedRoute>
          } 
        />
        <Route 
          path="/pending" 
          element={
            <ProtectedRoute>
              <PendingPage />
            </ProtectedRoute>
          } 
        />
        <Route 
          path="/banned" 
          element={
            <ProtectedRoute>
              <BannedPage />
            </ProtectedRoute>
          } 
        />
      </Routes>
    </Layout>
  );
};

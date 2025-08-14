import React, { createContext, useState, useEffect } from 'react';
import type { ReactNode } from 'react';

interface User {
  id: string;
  first_name: string;
  last_name: string;
  email: string;
  profile_pic: string;
  banned: boolean;
}

interface Group {
  role: string;
}

interface AuthContextType {
  user: User | null;
  group: Group | null;
  isAuthenticated: boolean;
  isLoading: boolean;
  login: () => void;
  logout: () => void;
}

const AuthContext = createContext<AuthContextType | undefined>(undefined);

export { AuthContext };

interface AuthProviderProps {
  children: ReactNode;
}

export const AuthProvider: React.FC<AuthProviderProps> = ({ children }) => {
  const [user, setUser] = useState<User | null>(null);
  const [group, setGroup] = useState<Group | null>(null);
  const [isLoading, setIsLoading] = useState(true);

  const fetchUser = async () => {
    try {
      const response = await fetch('/api/v2/user', {
        credentials: 'include'
      });
      if (response.ok) {
        const data = await response.json();
        setUser(data.data);
        // You might want to fetch group data as well
        // setGroup(data.group);
      } else if (response.status !== 403) { // Any status other than 403 is an error
        throw new Error('Failed to fetch user');
      }
    } catch (error) {
      console.error('Failed to fetch user:', error);
    }
    setIsLoading(false);
  };

  useEffect(() => {
    fetchUser();
  }, []);

  const login = () => {
    window.location.href = '/login';
  };

  const logout = async () => {
    try {
      await fetch('/logout', {
        method: 'GET',
        credentials: 'include'
      });
      setUser(null);
      setGroup(null);
      window.location.href = '/';
    } catch (error) {
      console.error('Logout failed:', error);
    }
  };

  const value: AuthContextType = {
    user,
    group,
    isAuthenticated: !!user,
    isLoading,
    login,
    logout,
  };

  return (
    <AuthContext.Provider value={value}>
      {children}
    </AuthContext.Provider>
  );
};

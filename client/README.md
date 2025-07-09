# Client

This directory contains the modern React TypeScript frontend for RICO.CX, built with Vite, Mantine UI, and Framer Motion.

## Current Implementation

The frontend has been fully migrated from server-side templates to a modern React application that communicates with the Flask backend via REST API.

### Technology Stack

- **React 18** - Modern React with hooks and functional components
- **TypeScript** - Type-safe development
- **Vite** - Fast build tool and development server
- **Mantine UI** - Modern React components library
- **Framer Motion** - Smooth animations and transitions
- **React Router** - Client-side routing
- **Axios** - HTTP client for API communication

### Project Structure

```
Client/
├── src/
│   ├── components/           # Reusable UI components
│   │   ├── AppRouter.tsx    # Main application routing
│   │   ├── Layout.tsx       # App shell with header/navigation
│   │   ├── ProtectedRoute.tsx # Route protection wrapper
│   │   ├── SearchForm.tsx   # Video search form
│   │   ├── VideoCard.tsx    # Video result cards
│   │   ├── VideoPlayer.tsx  # Video player component
│   │   └── PopularContent.tsx # Popular content display
│   ├── contexts/            # React contexts for state management
│   │   └── AuthContext.tsx  # Authentication state management
│   ├── pages/               # Page-level components
│   │   ├── HomePage.tsx     # Main landing page
│   │   ├── SearchPage.tsx   # Search results page
│   │   ├── AdminPage.tsx    # Admin panel
│   │   ├── PendingPage.tsx  # Pending approval page
│   │   └── BannedPage.tsx   # Banned user page
│   ├── services/            # API and external services
│   │   └── api.ts          # REST API service layer
│   ├── App.tsx             # Main application component
│   ├── main.tsx            # Application entry point
│   └── index.css           # Global styles
├── public/                  # Static assets
├── package.json            # Dependencies and scripts
├── vite.config.ts          # Vite configuration
└── tsconfig.json           # TypeScript configuration
```

### Features Implemented

#### Core Functionality
- **Search & Discovery** - Video/movie search with real-time results
- **Popular Content** - Trending and popular video display
- **Video Playback** - Integrated video player with controls
- **Download Management** - Queue and download video content

#### User Interface
- **Responsive Design** - Mobile-first, works on all screen sizes
- **Dark Theme** - Elegant dark theme with gradient accents
- **Smooth Animations** - Framer Motion animations throughout
- **Modern Components** - Mantine UI components with custom styling

#### Authentication & Authorization
- **Google OAuth Integration** - Seamless login/logout
- **Role-based Access** - Different access levels (Root, Admin, Member)
- **Protected Routes** - Automatic redirection based on auth status
- **User Status Handling** - Pending approval and banned user states

#### Admin Features
- **User Management** - View, ban, unban, and role management
- **Admin Panel** - Complete administrative interface
- **Action Confirmations** - Modal confirmations for admin actions

### API Integration

The client communicates with the Flask backend through a comprehensive API service:

#### Authentication Endpoints
- **GET /login** - Initiate Google OAuth flow
- **GET /logout** - User logout
- **GET /login/callback** - OAuth callback handling

#### Search & Content Endpoints
- **GET /api/v2/search?q={query}** - Search for content
- **GET /api/v2/popular** - Get popular content
- **GET /api/v2/getvideo?page_url={url}** - Get video details

#### Download Endpoints
- **POST /api/v2/download** - Start video download
- **GET /test/{filename}** - Check download status

#### Admin Endpoints
- **GET /admin** - Access admin panel
- **POST /admin** - Perform admin actions

### Development Setup

1. **Install Dependencies**
   ```bash
   cd Client
   npm install
   ```

2. **Start Development Server**
   ```bash
   npm run dev
   ```
   The client will start on `http://localhost:3000`

3. **Start Backend Server**
   ```bash
   cd ../server
   python app.py
   ```
   The Flask backend should run on `http://localhost:9000`

### Configuration

The Vite configuration includes proxy settings that automatically forward API requests to the Flask backend during development:

- `/api/*` → `http://localhost:9000`
- `/login` → `http://localhost:9000`
- `/logout` → `http://localhost:9000`
- `/admin` → `http://localhost:9000`

### Build for Production

```bash
npm run build
```

This creates an optimized production build in the `dist/` directory that can be served by any static file server or integrated with the Flask application.

### Architecture Benefits

1. **Separation of Concerns** - Clean separation between frontend and backend
2. **Modern Development** - Type safety, hot reloading, and modern tooling
3. **Performance** - Optimized bundles and lazy loading
4. **Maintainability** - Component-based architecture with clear separation
5. **Scalability** - Easy to extend with new features and pages

The frontend now provides a modern, responsive, and feature-rich user experience while maintaining full compatibility with the existing Flask backend API.

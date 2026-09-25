import { io } from "/socket.io.esm.min.js";

const FALLBACK_AVATAR = "data:image/svg+xml;utf8,<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24' fill='%2364748b'><circle cx='12' cy='12' r='12' fill='%231e293b'/><path d='M12 12c2.21 0 4-1.79 4-4s-1.79-4-4-4-4 1.79-4 4 1.79 4 4 4zm0 2c-2.67 0-8 1.34-8 4v2h16v-2c0-2.66-5.33-4-8-4z' fill='%2394a3b8'/></svg>";

function escapeHtml(str) {
  if (str === null || str === undefined) return "";
  return String(str)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#039;");
}

// Safe localStorage wrapper
const safeStorage = {
  getItem(key) {
    try {
      return localStorage.getItem(key);
    } catch (e) {
      console.error("Failed to read from localStorage:", e);
      return null;
    }
  },
  setItem(key, value) {
    try {
      localStorage.setItem(key, value);
    } catch (e) {
      console.error("Failed to write to localStorage:", e);
    }
  },
  removeItem(key) {
    try {
      localStorage.removeItem(key);
    } catch (e) {
      console.error("Failed to remove from localStorage:", e);
    }
  }
};

// Parse saved recent search if any
let savedSearchData = null;
const saved = safeStorage.getItem("rico_recent_search");
if (saved) {
  try {
    savedSearchData = JSON.parse(saved);
  } catch (e) {
    console.error(e);
  }
}

// Global Application State
let state = {
  user: null,
  token: safeStorage.getItem("session_token"),
  currentView: "login", // 'login', 'dashboard', 'settings'
  searchResults: savedSearchData ? (savedSearchData.searchResults || []) : [],
  downloads: [],
  socket: null,
  sidebarOpen: false
};

// Main Entry Point
document.addEventListener("DOMContentLoaded", () => {
  initApp();
});

async function initApp() {
  const success = await fetchCurrentUser();
  
  // Set up popstate routing listener
  window.addEventListener("popstate", (event) => {
    if (event.state && event.state.view) {
      navigate(event.state.view, false);
    } else {
      routeByPath(false);
    }
  });

  if (success) {
    console.log("Sign in successful for email:", state.user.username);
    
    // Play initial page entry slide animation on main app shell wrapper
    const appEl = document.getElementById("app");
    appEl.classList.add("animate-slide");
    
    // Route dynamically based on current browser path on load
    routeByPath(false);
    initSocket();
  } else {
    logout();
  }
}

// Router Helper to parse browser pathname
function routeByPath(pushState = true) {
  const path = window.location.pathname;
  if (!state.user) {
    navigate("login", pushState);
    return;
  }
  
  const isApproved = state.user && state.user.group_name && state.user.group_name !== "None (Pending Approval)";
  if (!isApproved) {
    navigate("pending", pushState);
    return;
  }
  
  if (path === "/popular") {
    navigate("popular", pushState);
  } else if (path === "/settings") {
    const isAdmin = state.user.group_name === "Admin";
    if (isAdmin) {
      state.adminActiveTab = "settings";
      navigate("admin", pushState);
    } else {
      navigate("dashboard", pushState);
    }
  } else if (path === "/admin") {
    const isAdminOrMod = state.user.group_name === "Admin" || state.user.group_name === "Moderator";
    if (isAdminOrMod) {
      state.adminActiveTab = (state.user.group_name === "Admin") ? "users" : "downloads";
      navigate("admin", pushState);
    } else {
      navigate("dashboard", pushState);
    }
  } else {
    navigate("dashboard", pushState);
  }
}

function updateNavButtons(view) {
  const searchBtn = document.getElementById("nav-search");
  const popularBtn = document.getElementById("nav-popular");
  const adminBtn = document.getElementById("nav-admin");
  if (searchBtn) searchBtn.classList.toggle("btn-primary", view === "dashboard");
  if (popularBtn) popularBtn.classList.toggle("btn-primary", view === "popular");
  if (adminBtn) adminBtn.classList.toggle("btn-primary", view === "admin");
}

// Navigation & View Router
function navigate(view, pushState = true) {
  state.currentView = view;
  const appContainer = document.getElementById("app");
  
  if (view === "login") {
    state.sidebarOpen = false;
    appContainer.className = "";
    appContainer.innerHTML = renderLogin();
    setupLoginListeners();
    if (pushState && window.location.pathname !== "/login") {
      history.pushState({ view }, "", "/login");
    }
    return;
  }
  
  if (view === "pending") {
    state.sidebarOpen = false;
    appContainer.className = "";
    appContainer.innerHTML = renderPendingApproval();
    setupPendingListeners();
    if (pushState && window.location.pathname !== "/pending") {
      history.pushState({ view }, "", "/pending");
    }
    return;
  }
  
  // Render application shell wrapper if not already present
  ensureAppShell();
  updateNavButtons(view);
  
  const mainContentEl = document.getElementById("main-content");
  
  // Reset and trigger page fade transition
  mainContentEl.classList.remove("animate-fade");
  void mainContentEl.offsetWidth; // Force reflow
  mainContentEl.classList.add("animate-fade");
  
  if (view === "dashboard") {
    stopAdminSync();
    mainContentEl.innerHTML = renderDashboardContent();
    setupDashboardContentListeners();
    renderSearchResults(); // Draw any existing search results
    fetchDownloads();
    if (pushState && window.location.pathname !== "/") {
      history.pushState({ view }, "", "/");
    }
  } else if (view === "popular") {
    stopAdminSync();
    mainContentEl.innerHTML = renderPopularContent();
    setupPopularContentListeners();
    fetchPopularMedia();
    fetchDownloads();
    if (pushState && window.location.pathname !== "/popular") {
      history.pushState({ view }, "", "/popular");
    }
  } else if (view === "admin") {
    const isAdminOrMod = state.user && (state.user.group_name === "Admin" || state.user.group_name === "Moderator");
    if (!isAdminOrMod) {
      stopAdminSync();
      navigate("dashboard", pushState);
      return;
    }
    if (!state.adminActiveTab) {
      state.adminActiveTab = (state.user.group_name === "Admin") ? "users" : "downloads";
    }
    mainContentEl.innerHTML = renderAdminContent();
    setupAdminContentListeners();
    startAdminSync();
    if (pushState && window.location.pathname !== "/admin") {
      history.pushState({ view }, "", "/admin");
    }
  }
}

// Ensure the stable header & sidebar outer shell is in the DOM
function ensureAppShell() {
  const appEl = document.getElementById("app");
  if (document.getElementById("main-content")) {
    appEl.className = state.sidebarOpen ? "sidebar-open" : "";
    return;
  }
  
  appEl.className = state.sidebarOpen ? "sidebar-open" : "";
  appEl.innerHTML = renderAppShellTemplate();
  setupAppShellListeners();
}

// Socket.IO Connection Setup
function initSocket() {
  if (state.socket) return;

  const socketUrl = window.location.origin;
  state.socket = io(socketUrl, {
    transports: ["websocket", "polling"]
  });

  state.socket.on("connect", () => {
    console.log("Downloads WebSocket connected");
  });

  state.socket.on("download_progress", (data) => {
    updateDownloadProgressUI(data);
  });

  state.socket.on("download_added", (data) => {
    handleDownloadAddedSocket(data);
  });

  state.socket.on("download_deleted", (data) => {
    handleDownloadDeletedSocket(data);
  });

  state.socket.on("disconnect", () => {
    console.log("Downloads WebSocket disconnected");
  });
}

// API Fetch Operations
async function fetchCurrentUser() {
  try {
    const headers = {};
    if (state.token) {
      headers["Authorization"] = `Bearer ${state.token}`;
    }
    const resp = await fetch("/api/auth/me", { headers });
    if (resp.ok) {
      state.user = await resp.json();
      if (state.user.session_token) {
        state.token = state.user.session_token;
        safeStorage.setItem("session_token", state.token);
      }
      return true;
    }
    return false;
  } catch (err) {
    console.error("Failed to fetch user state:", err);
    return false;
  }
}

async function fetchDownloads() {
  try {
    const headers = {};
    if (state.token) {
      headers["Authorization"] = `Bearer ${state.token}`;
    }
    const resp = await fetch("/api/downloads", { headers });
    if (resp.ok) {
      state.downloads = await resp.json();
      renderActiveDownloads();
      updateSidebarBadge();
      updateSearchResultButtons();
      if (state.currentView === "popular") {
        renderPopularGrid();
      }
    }
  } catch (err) {
    console.error("Failed to fetch downloads:", err);
  }
}

async function searchTrackers(query, category) {
  // Dismiss mobile virtual keyboard immediately
  if (document.activeElement && typeof document.activeElement.blur === "function") {
    document.activeElement.blur();
  }

  const container = document.getElementById("results-list");
  const loaderEl = document.getElementById("search-loading");

  const trimmed = (query || "").trim();
  const isMagnet = trimmed.toLowerCase().startsWith("magnet:") ||
                   /^[0-9a-fA-F]{40}$/.test(trimmed) ||
                   /^[2-7a-zA-Z]{32}$/.test(trimmed);

  if (loaderEl) {
    const textSpan = loaderEl.querySelector("span:last-child");
    if (textSpan) {
      textSpan.textContent = isMagnet ? "ADDING MAGNET & STARTING DOWNLOAD..." : "SCRAPING INDEXERS...";
    }
    loaderEl.style.display = "flex";
  }
  container.innerHTML = "";

  try {
    const headers = {};
    if (state.token) {
      headers["Authorization"] = `Bearer ${state.token}`;
    }
    const resp = await fetch(`/api/search?q=${encodeURIComponent(query)}&category=${category || ""}`, { headers });
    const resData = await resp.json();
    if (resp.ok) {
      state.searchResults = resData.data;

      // If auto-downloaded, ensure downloads state is immediately synced
      if (resData.auto_downloaded && resData.data && resData.data.length > 0) {
        const firstDl = resData.data[0].downloads?.[0];
        if (firstDl && firstDl.torbox_id) {
          const already = state.downloads.some(d => String(d.torbox_id) === String(firstDl.torbox_id));
          if (!already) {
            state.downloads.unshift({
              torbox_id: firstDl.torbox_id,
              title: resData.data[0].clean_title || firstDl.title,
              filename: firstDl.title,
              magnet: firstDl.download_url,
              status: firstDl.db_status || "queued",
              progress: 0,
              speed: 0,
              size: firstDl.size || 0,
              category: resData.data[0].is_tv ? "tv" : "movie",
              user_id: state.user?.id
            });
            renderActiveDownloads();
            updateSidebarBadge();
          }
        }
        fetchDownloads();
      }

      saveRecentSearch();
      renderSearchResults();
      updateClearButtonVisibility();
    } else {
      container.innerHTML = `<div class="alert-box alert-error">Error: ${resData.error}</div>`;
    }
  } catch (err) {
    console.error("Search API failure:", err);
    container.innerHTML = `<div class="alert-box alert-error">Failed to query search indexers.</div>`;
  } finally {
    if (loaderEl) {
      loaderEl.style.display = "none";
      const textSpan = loaderEl.querySelector("span:last-child");
      if (textSpan) textSpan.textContent = "SCRAPING INDEXERS...";
    }
  }
}

async function triggerDownload(magnet, title, filename, category, year, season, episode, size, btn, overwrite = false) {
  btn.disabled = true;
  btn.innerHTML = `<span class="spinner"></span> REQUESTING...`;

  try {
    const headers = {
      "Content-Type": "application/json"
    };
    if (state.token) {
      headers["Authorization"] = `Bearer ${state.token}`;
    }
    const resp = await fetch("/api/download", {
      method: "POST",
      headers: headers,
      body: JSON.stringify({ magnet, title, filename, category, year, season, episode, size, overwrite })
    });
    
    const data = await resp.json();
    if (resp.ok) {
      const exists = state.downloads.some(d => String(d.torbox_id) === String(data.torbox_id));
      if (!exists) {
        state.downloads.unshift({
          torbox_id: data.torbox_id,
          magnet: magnet,
          title: title,
          filename: filename,
          status: data.status || "queued",
          progress: 0,
          speed: 0,
          size: size,
          user_id: state.user ? state.user.id : null
        });
      }
      
      updateSearchResultButtons();
      
      if (!state.sidebarOpen) {
        toggleSidebar();
      }
      fetchDownloads();
    } else {
      btn.disabled = false;
      btn.innerHTML = overwrite ? "RE-DOWNLOAD" : "DOWNLOAD";
      alert(`Download start failed: ${data.error}`);
    }
  } catch (err) {
    console.error("Trigger download failure:", err);
    btn.disabled = false;
    btn.innerHTML = overwrite ? "RE-DOWNLOAD" : "DOWNLOAD";
    alert("Could not connect to download service.");
  }
}

function logout() {
  fetch("/api/auth/logout", {
    method: "POST"
  }).catch(() => {});
  
  state.token = null;
  state.user = null;
  safeStorage.removeItem("session_token");
  if (state.socket) {
    state.socket.disconnect();
    state.socket = null;
  }
  navigate("login");
}

// UI Outer App Shell Template
function renderAppShellTemplate() {
  const name = state.user.full_name || state.user.username;
  const avatar = state.user.profile_picture || FALLBACK_AVATAR;
  
  const isAdmin = state.user && state.user.group_name === "Admin";
  const isMod = state.user && state.user.group_name === "Moderator";
  
  const adminBtnHtml = (isAdmin || isMod) 
    ? `<button id="nav-admin" class="btn">Admin</button>`
    : "";
  
  return `
    <header class="container">
      <a href="#" class="brand" id="brand-link">RICO.CX</a>
      <div class="nav-actions">
        <div class="profile-badge">
          <img src="${avatar}" alt="${name}">
          <span>${name}</span>
        </div>
        <button id="nav-search" class="btn ${state.currentView === 'dashboard' ? 'btn-primary' : ''}">Search</button>
        <button id="nav-popular" class="btn ${state.currentView === 'popular' ? 'btn-primary' : ''}">Popular</button>
        <button id="nav-downloads-toggle" class="btn sidebar-toggle-btn">
          Downloads <span id="downloads-badge" class="badge-count" style="display:none;">0</span>
        </button>
        ${adminBtnHtml}
        <button id="nav-logout" class="btn btn-danger">Logout</button>
      </div>
    </header>

    <main class="container animate-fade" id="main-content"></main>

    <!-- Downloads Sidebar (Collapsible) -->
    <aside id="downloads-sidebar" class="downloads-sidebar">
      <div class="sidebar-header">
        <h2>Active Downloads</h2>
        <button id="downloads-sidebar-close" class="btn" style="padding:0.25rem 0.5rem;">Close</button>
      </div>
      <div id="sidebar-downloads-list" class="sidebar-content">
        <div class="empty-state">NO ACTIVE TRANSFERS</div>
      </div>
    </aside>
  `;
}

// UI Inner View Contents
function renderDashboardContent() {
  return `
    <form id="search-form" class="search-block">
      <div class="search-row">
        <div class="search-input-wrapper">
          <input type="text" id="search-input" class="form-input" required placeholder="Search movies, TV shows, or paste a magnet link/torrent hash..." enterkeyhint="search" autocapitalize="off" autocomplete="off" autocorrect="off" spellcheck="false">
          <button type="button" id="btn-clear-search" class="clear-search-btn" title="Clear all search & filters">&times;</button>
        </div>
        <button type="submit" class="btn btn-primary">Search</button>
        <button type="button" id="btn-toggle-filters" class="btn">Filters ▾</button>
      </div>

      <div id="advanced-filters" class="filters-panel" style="display: none;">
        <div class="filters-grid">
          <div class="form-group">
            <label class="form-label" for="filter-category">Category</label>
            <select id="filter-category" class="form-input">
              <option value="">All Categories</option>
              <option value="movie">Movies</option>
              <option value="tv">TV Shows</option>
            </select>
          </div>
          <div class="form-group">
            <label class="form-label" for="filter-resolution">Resolution</label>
            <select id="filter-resolution" class="form-input">
              <option value="">All Resolutions</option>
              <option value="2160p">2160p / 4K</option>
              <option value="1080p">1080p</option>
              <option value="720p">720p</option>
              <option value="480p">480p</option>
            </select>
          </div>
          <div class="form-group">
            <label class="form-label" for="filter-min-seeds">Min Seeds</label>
            <input type="number" id="filter-min-seeds" class="form-input" min="0" value="0">
          </div>
          <div class="form-group">
            <label class="form-label" for="filter-max-size">Max Size (GB)</label>
            <input type="number" id="filter-max-size" class="form-input" min="0" step="0.5" value="0">
          </div>
          <div class="form-group">
            <label class="form-label" for="filter-sort-by">Sort By</label>
            <select id="filter-sort-by" class="form-input">
              <option value="relevancy-desc">Relevancy (Recommended)</option>
              <option value="seeds-desc">Seeds (High to Low)</option>
              <option value="size-desc">Size (Large to Small)</option>
              <option value="size-asc">Size (Small to Large)</option>
              <option value="title-asc">Title (A to Z)</option>
            </select>
          </div>
        </div>
      </div>
    </form>

    <section>
      <div class="results-header-row">
        <h2>Search Results</h2>
        <div id="search-loading" class="loader-inline" style="display: none;">
          <span class="spinner"></span>
          <span>SCRAPING INDEXERS...</span>
        </div>
      </div>
      <div id="results-list">
        <div class="empty-state">EXECUTE SEARCH QUERY TO LOAD RESULTS</div>
      </div>
    </section>
  `;
}

// Popular / Trending State & Helpers
let popularState = {
  type: "movie",
  window: "day",
  hideOnServer: false,
  items: [],
  loading: false,
  error: null
};

function renderPopularContent() {
  const isMovie = popularState.type === "movie";
  const isDay = popularState.window === "day";

  return `
    <section class="popular-section">
      <div class="popular-header-row">
        <div>
          <h2>Popular & Trending</h2>
          <div class="popular-subtitle">Browse today's or this week's top trending movies and shows</div>
        </div>
        <div class="popular-controls">
          <div class="btn-group" role="group">
            <button type="button" id="popular-toggle-movie" class="btn ${isMovie ? 'btn-primary' : ''}">Movies</button>
            <button type="button" id="popular-toggle-tv" class="btn ${!isMovie ? 'btn-primary' : ''}">TV Shows</button>
          </div>
          <div class="btn-group" role="group">
            <button type="button" id="popular-toggle-day" class="btn ${isDay ? 'btn-primary' : ''}">Today</button>
            <button type="button" id="popular-toggle-week" class="btn ${!isDay ? 'btn-primary' : ''}">This Week</button>
          </div>
          <label class="popular-checkbox-label">
            <input type="checkbox" id="popular-hide-server" ${popularState.hideOnServer ? 'checked' : ''}>
            <span>Hide items on server</span>
          </label>
        </div>
      </div>

      <div id="popular-loading" class="loader-inline" style="display: none; margin: 2rem 0;">
        <span class="spinner"></span>
        <span>FETCHING TRENDING TITLES...</span>
      </div>

      <div id="popular-grid" class="popular-grid">
        <div class="empty-state" style="grid-column: 1 / -1;">LOADING TRENDING TITLES...</div>
      </div>
    </section>
  `;
}

function setupPopularContentListeners() {
  const typeMovieBtn = document.getElementById("popular-toggle-movie");
  const typeTvBtn = document.getElementById("popular-toggle-tv");
  const windowDayBtn = document.getElementById("popular-toggle-day");
  const windowWeekBtn = document.getElementById("popular-toggle-week");
  const hideServerChk = document.getElementById("popular-hide-server");

  if (typeMovieBtn && typeTvBtn) {
    typeMovieBtn.addEventListener("click", () => {
      if (popularState.type !== "movie") {
        popularState.type = "movie";
        typeMovieBtn.classList.add("btn-primary");
        typeTvBtn.classList.remove("btn-primary");
        fetchPopularMedia();
      }
    });
    typeTvBtn.addEventListener("click", () => {
      if (popularState.type !== "tv") {
        popularState.type = "tv";
        typeTvBtn.classList.add("btn-primary");
        typeMovieBtn.classList.remove("btn-primary");
        fetchPopularMedia();
      }
    });
  }

  if (windowDayBtn && windowWeekBtn) {
    windowDayBtn.addEventListener("click", () => {
      if (popularState.window !== "day") {
        popularState.window = "day";
        windowDayBtn.classList.add("btn-primary");
        windowWeekBtn.classList.remove("btn-primary");
        fetchPopularMedia();
      }
    });
    windowWeekBtn.addEventListener("click", () => {
      if (popularState.window !== "week") {
        popularState.window = "week";
        windowWeekBtn.classList.add("btn-primary");
        windowDayBtn.classList.remove("btn-primary");
        fetchPopularMedia();
      }
    });
  }

  if (hideServerChk) {
    hideServerChk.addEventListener("change", (e) => {
      popularState.hideOnServer = e.target.checked;
      renderPopularGrid();
    });
  }

  const gridEl = document.getElementById("popular-grid");
  if (gridEl) {
    gridEl.addEventListener("click", (e) => {
      const trackerBtn = e.target.closest(".btn-popular-tv-tracker");
      if (trackerBtn) {
        const tvId = trackerBtn.getAttribute("data-tv-id");
        const title = trackerBtn.getAttribute("data-title");
        const year = trackerBtn.getAttribute("data-year");
        openTvTrackerModal({ tmdb_id: tvId, clean_title: title, year });
        return;
      }
      const actionBtn = e.target.closest(".btn-popular-action");
      const posterWrap = e.target.closest(".popular-poster-wrap");
      const targetEl = actionBtn || posterWrap;
      if (targetEl) {
        const title = targetEl.getAttribute("data-title");
        const year = targetEl.getAttribute("data-year");
        const isTv = targetEl.getAttribute("data-is-tv") === "1";
        if (title) {
          searchFromPopular(title, year, isTv);
        }
      }
    });
  }
}

async function fetchPopularMedia() {
  popularState.loading = true;
  popularState.error = null;
  const loaderEl = document.getElementById("popular-loading");
  const gridEl = document.getElementById("popular-grid");
  if (loaderEl) loaderEl.style.display = "flex";
  if (gridEl) gridEl.innerHTML = "";

  try {
    const headers = {};
    if (state.token) {
      headers["Authorization"] = `Bearer ${state.token}`;
    }
    const resp = await fetch(`/api/trending?type=${popularState.type}&window=${popularState.window}`, { headers });
    const resData = await resp.json();
    if (resp.ok) {
      popularState.items = resData.results || [];
      renderPopularGrid();
    } else {
      popularState.error = resData.error || "Failed to load trending items.";
      if (gridEl) {
        gridEl.innerHTML = `<div class="alert-box alert-error" style="grid-column: 1 / -1;">${escapeHtml(popularState.error)}</div>`;
      }
    }
  } catch (err) {
    console.error("Failed to fetch popular media:", err);
    popularState.error = "Network error loading trending media.";
    if (gridEl) {
      gridEl.innerHTML = `<div class="alert-box alert-error" style="grid-column: 1 / -1;">Network error loading trending media.</div>`;
    }
  } finally {
    popularState.loading = false;
    if (loaderEl) loaderEl.style.display = "none";
  }
}

function isItemCompletedInDownloads(cleanTitle) {
  if (!cleanTitle || !state.downloads) return false;
  const target = cleanTitle.trim().toLowerCase();
  const targetNorm = target.replace(/[^a-z0-9]/g, "");
  return state.downloads.some(d => {
    const s = (d.status || "").toLowerCase();
    const isDone = s.includes("completed") || s.includes("downloaded") || Number(d.progress) >= 100;
    if (!isDone) return false;
    const dTitle = (d.title || "").trim().toLowerCase();
    const dNorm = dTitle.replace(/[^a-z0-9]/g, "");
    return dTitle === target || (targetNorm && dNorm === targetNorm);
  });
}

function renderPopularGrid() {
  const gridEl = document.getElementById("popular-grid");
  if (!gridEl) return;

  let items = popularState.items || [];
  if (popularState.hideOnServer) {
    items = items.filter(item => !item.in_database && !isItemCompletedInDownloads(item.clean_title));
  }

  if (items.length === 0) {
    const msg = popularState.hideOnServer
      ? "ALL TRENDING TITLES ARE CURRENTLY SAVED ON YOUR SERVER!"
      : "NO TRENDING MEDIA FOUND";
    gridEl.innerHTML = `<div class="empty-state" style="grid-column: 1 / -1;">${msg}</div>`;
    return;
  }

  let html = "";
  items.forEach(item => {
    const isSaved = item.in_database || isItemCompletedInDownloads(item.clean_title);
    const posterHtml = item.poster_url
      ? `<img src="${escapeHtml(item.poster_url)}" alt="${escapeHtml(item.clean_title)}" loading="lazy">`
      : `<div class="popular-poster-stub"><span>${item.is_tv ? 'TV' : 'FILM'}</span></div>`;

    const yearStr = item.year ? `(${item.year})` : "";
    const genresStr = (item.genres && item.genres.length > 0)
      ? item.genres.slice(0, 2).join(" • ")
      : (item.is_tv ? "Series" : "Feature Film");
    const ratingStr = item.vote_average ? Number(item.vote_average).toFixed(1) : "—";

    html += `
      <div class="popular-card ${isSaved ? 'in-database' : ''} animate-slide">
        <div class="popular-poster-wrap" data-title="${escapeHtml(item.clean_title)}" data-year="${item.year || ''}" data-is-tv="${item.is_tv ? '1' : '0'}" title="Search releases for ${escapeHtml(item.clean_title)}">
          ${posterHtml}
          <div class="popular-rating-pill">★ ${ratingStr}</div>
          ${isSaved ? `
            <div class="popular-server-pill">
              <svg width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round" style="vertical-align: -1px; margin-right: 2px;"><ellipse cx="12" cy="5" rx="9" ry="3"/><path d="M21 12c0 1.66-4 3-9 3s-9-1.34-9-3"/><path d="M3 5v14c0 1.66 4 3 9 3s9-1.34 9-3V5"/></svg>
              ON SERVER
            </div>` : ''}
        </div>
        <div class="popular-card-body">
          <div class="popular-card-title" title="${escapeHtml(item.clean_title)}">
            ${escapeHtml(item.clean_title)} <span class="popular-year">${escapeHtml(yearStr)}</span>
          </div>
          <div class="popular-card-meta">
            <span class="media-type-badge">${item.is_tv ? 'TV' : 'MOVIE'}</span>
            <span class="popular-genres">${escapeHtml(genresStr)}</span>
          </div>
          <p class="popular-overview" title="${escapeHtml(item.overview || '')}">
            ${escapeHtml(item.overview || 'No overview available.')}
          </p>
          <div class="popular-card-footer">
            <button class="btn ${isSaved ? 'btn-server-saved' : 'btn-primary'} btn-popular-action" 
                    data-title="${escapeHtml(item.clean_title)}" 
                    data-year="${item.year || ''}" 
                    data-is-tv="${item.is_tv ? '1' : '0'}">
              ${isSaved ? '✓ Saved • Search More' : 'Search Releases'}
            </button>
            ${item.is_tv ? `
              <button class="btn btn-secondary btn-popular-tv-tracker" 
                      data-tv-id="${item.id}" 
                      data-title="${escapeHtml(item.clean_title)}" 
                      data-year="${item.year || ''}" 
                      title="Inspect seasons and missing episodes">
                Seasons
              </button>
            ` : ''}
          </div>
        </div>
      </div>
    `;
  });

  gridEl.innerHTML = html;
}

function executeMediaSearch(queryStr, category = "tv") {
  closeTvTrackerModal();
  if (state.currentTab !== "dashboard") {
    navigate("dashboard");
  }
  const searchInput = document.getElementById("search-input");
  if (searchInput) {
    searchInput.value = queryStr;
  }
  const categorySelect = document.getElementById("filter-category");
  if (categorySelect) {
    categorySelect.value = category;
  }
  saveRecentSearch();
  updateClearButtonVisibility();
  searchTrackers(queryStr, category);
}

function searchFromPopular(cleanTitle, year, isTv) {
  executeMediaSearch(cleanTitle, isTv ? "tv" : "movie");
}

// TV Show Tracker State & Cache
const tvDetailsCache = new Map();
const tvSeasonCache = new Map();

async function getTvDetails(tvId, title, year) {
  const cacheKey = tvId ? String(tvId) : `${title}:${year || ""}`.toLowerCase();
  if (tvDetailsCache.has(cacheKey)) {
    return tvDetailsCache.get(cacheKey);
  }
  const headers = {};
  if (state.token) headers["Authorization"] = `Bearer ${state.token}`;
  const params = new URLSearchParams();
  if (tvId) params.set("tv_id", String(tvId));
  if (title) params.set("title", title);
  if (year) params.set("year", String(year));

  try {
    const resp = await fetch(`/api/tv/details?${params.toString()}`, { headers });
    if (!resp.ok) return null;
    const data = await resp.json();
    tvDetailsCache.set(cacheKey, data);
    if (data.tv_id) tvDetailsCache.set(String(data.tv_id), data);
    return data;
  } catch (e) {
    console.error("Failed to fetch TV details:", e);
    return null;
  }
}

async function getTvSeasonDetails(tvId, season, title, year) {
  const cacheKey = `${tvId}:${season}`;
  if (tvSeasonCache.has(cacheKey)) {
    return tvSeasonCache.get(cacheKey);
  }
  const headers = {};
  if (state.token) headers["Authorization"] = `Bearer ${state.token}`;
  const params = new URLSearchParams({
    tv_id: String(tvId),
    season: String(season)
  });
  if (title) params.set("title", title);
  if (year) params.set("year", String(year));

  try {
    const resp = await fetch(`/api/tv/season?${params.toString()}`, { headers });
    if (!resp.ok) return null;
    const data = await resp.json();
    tvSeasonCache.set(cacheKey, data);
    return data;
  } catch (e) {
    console.error("Failed to fetch TV season details:", e);
    return null;
  }
}

async function toggleTvDrawer(index, item) {
  const drawerEl = document.getElementById(`tv-drawer-${index}`);
  const toggleBtn = document.getElementById(`btn-tv-tracker-${index}`);
  if (!drawerEl) return;

  if (drawerEl.style.display !== "none") {
    drawerEl.style.display = "none";
    if (toggleBtn) toggleBtn.classList.remove("active");
    return;
  }

  drawerEl.style.display = "flex";
  if (toggleBtn) toggleBtn.classList.add("active");

  drawerEl.innerHTML = `
    <div style="display: flex; align-items: center; justify-content: center; padding: 1.5rem; color: var(--text-secondary); gap: 0.5rem;">
      <span class="spinner"></span> Inspecting seasons and local library...
    </div>
  `;

  const showData = await getTvDetails(item.tmdb_id, item.clean_title, item.year);
  if (!showData || !showData.seasons || showData.seasons.length === 0) {
    drawerEl.innerHTML = '<div class="empty-state" style="padding: 1rem;">No season details available.</div>';
    return;
  }

  const defaultSeason = showData.seasons[0]?.season_number || 1;
  renderTvTrackerContent(drawerEl, showData, defaultSeason, `card-${index}`);
}

function openTvTrackerModal(item) {
  let modalEl = document.getElementById("tv-tracker-modal");
  if (!modalEl) {
    modalEl = document.createElement("div");
    modalEl.id = "tv-tracker-modal";
    modalEl.className = "tv-modal-overlay";
    document.body.appendChild(modalEl);
  }
  modalEl.style.display = "flex";
  const displayTitle = item.clean_title || item.title || "TV Show";
  modalEl.innerHTML = `
    <div class="tv-modal-content">
      <div class="tv-modal-header">
        <div>
          <div class="tv-modal-title">${escapeHtml(displayTitle)} ${item.year ? `(${escapeHtml(item.year)})` : ''}</div>
          <div style="font-size: 0.8rem; color: var(--text-secondary); margin-top: 2px;">Season & Episode Tracker</div>
        </div>
        <button class="tv-modal-close" id="btn-close-tv-modal" aria-label="Close">&times;</button>
      </div>
      <div class="tv-modal-body" id="tv-modal-body">
        <div style="display: flex; align-items: center; justify-content: center; padding: 2.5rem; color: var(--text-secondary); gap: 0.5rem;">
          <span class="spinner"></span> Inspecting seasons and local library...
        </div>
      </div>
    </div>
  `;

  document.getElementById("btn-close-tv-modal").onclick = closeTvTrackerModal;
  modalEl.onclick = (e) => {
    if (e.target === modalEl) closeTvTrackerModal();
  };

  const bodyEl = document.getElementById("tv-modal-body");
  getTvDetails(item.tmdb_id || item.id, displayTitle, item.year).then(showData => {
    if (!showData || !showData.seasons || showData.seasons.length === 0) {
      bodyEl.innerHTML = '<div class="empty-state" style="padding: 1.5rem;">No season details found for this TV show.</div>';
      return;
    }
    const defaultSeason = showData.seasons[0]?.season_number || 1;
    renderTvTrackerContent(bodyEl, showData, defaultSeason, "modal-tv");
  }).catch(err => {
    console.error("TV Tracker modal error:", err);
    bodyEl.innerHTML = '<div class="empty-state" style="padding: 1.5rem;">Failed to load TV details.</div>';
  });
}

function closeTvTrackerModal() {
  const modalEl = document.getElementById("tv-tracker-modal");
  if (modalEl) modalEl.style.display = "none";
}

function renderTvTrackerContent(containerEl, showData, defaultSeasonNum, trackerIdPrefix) {
  containerEl.innerHTML = "";

  const tabsContainer = document.createElement("div");
  tabsContainer.className = "tv-season-tabs";

  showData.seasons.forEach(s => {
    const tabBtn = document.createElement("button");
    const isActive = s.season_number === defaultSeasonNum;
    tabBtn.className = `tv-season-tab ${isActive ? 'active' : ''}`;
    tabBtn.id = `${trackerIdPrefix}-tab-${s.season_number}`;

    const dotClass = s.status === "complete" ? "complete" : (s.status === "partial" ? "partial" : "missing");
    const statLabel = s.status === "complete" ? "✓" : `${s.episodes_on_disk}/${s.episode_count}`;

    tabBtn.innerHTML = `
      <span class="tab-status-dot ${dotClass}"></span>
      Season ${s.season_number} (${statLabel})
    `;

    tabBtn.onclick = () => {
      containerEl.querySelectorAll(".tv-season-tab").forEach(t => t.classList.remove("active"));
      tabBtn.classList.add("active");
      loadSeasonView(s.season_number);
    };

    tabsContainer.appendChild(tabBtn);
  });

  const contentContainer = document.createElement("div");
  contentContainer.className = "tv-season-content";
  contentContainer.id = `${trackerIdPrefix}-content`;

  containerEl.appendChild(tabsContainer);
  containerEl.appendChild(contentContainer);

  const loadSeasonView = async (seasonNum) => {
    contentContainer.innerHTML = `
      <div style="display: flex; align-items: center; justify-content: center; padding: 1.5rem; color: var(--text-secondary); gap: 0.5rem;">
        <span class="spinner"></span> Loading Season ${seasonNum} episodes...
      </div>
    `;

    const seasonData = await getTvSeasonDetails(showData.tv_id, seasonNum, showData.title, showData.year);
    if (!seasonData) {
      contentContainer.innerHTML = '<div class="empty-state" style="padding: 1rem;">Failed to load season episodes.</div>';
      return;
    }

    const sStr = String(seasonNum).padStart(2, '0');
    let statusBadgeHtml = "";
    if (seasonData.is_complete) {
      statusBadgeHtml = `<span class="badge-status badge-status-complete">✓ Season Complete (${seasonData.on_server_count}/${seasonData.total_episodes})</span>`;
    } else if (seasonData.missing_count > 0) {
      statusBadgeHtml = `<span class="badge-status badge-status-missing">⚠️ ${seasonData.missing_count} Missing (${seasonData.on_server_count}/${seasonData.total_episodes} on server)</span>`;
    } else {
      statusBadgeHtml = `<span class="badge-status badge-status-not-downloaded">0/${seasonData.total_episodes} on Server</span>`;
    }

    let episodesHtml = "";
    (seasonData.episodes || []).forEach(ep => {
      const eStr = String(ep.episode_number).padStart(2, '0');
      const epCode = `S${sStr}E${eStr}`;
      const searchTarget = `${showData.title} ${epCode}`;

      let epStatusBadge = "";
      let epActionBtn = "";

      if (ep.on_server) {
        const sizeTooltip = ep.file_size ? formatBytes(ep.file_size) : "";
        const titleTooltip = ep.file_name ? `${escapeHtml(ep.file_name)} (${sizeTooltip})` : "";
        epStatusBadge = `<span class="badge-status badge-status-complete" title="${titleTooltip}">✓ On Server</span>`;
        epActionBtn = `<button class="btn btn-secondary btn-sm btn-ep-search" data-query="${escapeHtml(searchTarget)}">Search</button>`;
      } else if (ep.has_aired) {
        epStatusBadge = `<span class="badge-status badge-status-missing">⚠️ Missing</span>`;
        epActionBtn = `<button class="btn btn-primary btn-sm btn-ep-grab" data-query="${escapeHtml(searchTarget)}">Get E${eStr}</button>`;
      } else {
        const dateLabel = ep.air_date || "TBA";
        epStatusBadge = `<span class="badge-status badge-status-not-downloaded">Airs ${escapeHtml(dateLabel)}</span>`;
        epActionBtn = `<button class="btn btn-secondary btn-sm" disabled style="opacity: 0.4;">Upcoming</button>`;
      }

      episodesHtml += `
        <div class="tv-episode-row ${ep.on_server ? 'on-server' : (ep.has_aired ? 'missing' : '')}">
          <div class="tv-ep-info">
            <span class="tv-ep-code">${epCode}</span>
            <span class="tv-ep-title" title="${escapeHtml(ep.name)}">${escapeHtml(ep.name)}</span>
            <span class="tv-ep-date">${escapeHtml(ep.air_date || '')}</span>
          </div>
          <div class="tv-ep-actions">
            ${epStatusBadge}
            ${epActionBtn}
          </div>
        </div>
      `;
    });

    contentContainer.innerHTML = `
      <div class="tv-season-header">
        <div class="tv-season-header-info">
          <span class="tv-season-title">Season ${seasonNum} • ${seasonData.total_episodes} Episodes</span>
          ${statusBadgeHtml}
        </div>
        <button class="btn btn-primary btn-season-pack-grab" data-query="${escapeHtml(showData.title)} S${sStr}">
          ⚡ Grab Season ${seasonNum} Pack
        </button>
      </div>
      <div class="tv-episodes-list">
        ${episodesHtml || '<div class="empty-state" style="padding: 1rem;">No episodes listed.</div>'}
      </div>
    `;

    // Wire action triggers
    contentContainer.querySelectorAll(".btn-season-pack-grab, .btn-ep-grab, .btn-ep-search").forEach(btn => {
      btn.onclick = () => {
        const q = btn.getAttribute("data-query");
        if (q) executeMediaSearch(q, "tv");
      };
    });
  };

  loadSeasonView(defaultSeasonNum);
}

// Client Side Filter & Sort logic
function getFilteredResults() {
  const categoryFilter = document.getElementById("filter-category").value;
  const resolutionFilter = document.getElementById("filter-resolution").value;
  const minSeedsFilter = parseInt(document.getElementById("filter-min-seeds").value) || 0;
  const maxSizeFilter = parseFloat(document.getElementById("filter-max-size").value) || 0; // in GB
  const maxSizeBytes = maxSizeFilter * 1024 * 1024 * 1024;
  
  let filtered = state.searchResults.map(card => {
    // Clone search card and filter its releases option list
    const clonedCard = { ...card, downloads: [...card.downloads] };
    
    clonedCard.downloads = clonedCard.downloads.filter(dl => {
      // Direct Link entries (user-pasted magnet links) bypass UI filters
      if (dl.indexer === "Direct Link") return true;

      // Category check
      if (categoryFilter === "movie" && card.is_tv) return false;
      if (categoryFilter === "tv" && !card.is_tv) return false;
      
      // Resolution check
      if (resolutionFilter && dl.resolution !== resolutionFilter) return false;
      
      // Seeds check
      if (dl.seeders < minSeedsFilter) return false;
      
      // Size check
      if (maxSizeBytes > 0 && dl.size > maxSizeBytes) return false;
      
      return true;
    });
    
    return clonedCard;
  });
  
  // Remove result cards containing no matching downloads
  filtered = filtered.filter(card => card.downloads.length > 0);
  
  // Apply sorting
  const sortBy = document.getElementById("filter-sort-by").value;
  if (sortBy === "relevancy-desc") {
    filtered.sort((a, b) => (b.downloads[0]?.relevancy_score ?? 0) - (a.downloads[0]?.relevancy_score ?? 0));
    filtered.forEach(c => c.downloads.sort((a, b) => (b.relevancy_score ?? 0) - (a.relevancy_score ?? 0) || b.seeders - a.seeders));
  } else if (sortBy === "seeds-desc") {
    filtered.sort((a, b) => b.downloads[0].seeders - a.downloads[0].seeders);
    filtered.forEach(c => c.downloads.sort((a, b) => b.seeders - a.seeders));
  } else if (sortBy === "size-desc") {
    filtered.sort((a, b) => b.downloads[0].size - a.downloads[0].size);
    filtered.forEach(c => c.downloads.sort((a, b) => b.size - a.size));
  } else if (sortBy === "size-asc") {
    filtered.sort((a, b) => a.downloads[0].size - b.downloads[0].size);
    filtered.forEach(c => c.downloads.sort((a, b) => a.size - b.size));
  } else if (sortBy === "title-asc") {
    filtered.sort((a, b) => a.clean_title.localeCompare(b.clean_title));
  }
  
  return filtered;
}

// Local Storage Search State Helpers
function saveRecentSearch() {
  const searchInput = document.getElementById("search-input");
  if (!searchInput) return;
  
  const recent = {
    query: searchInput.value,
    searchResults: state.searchResults || [],
    category: document.getElementById("filter-category").value,
    resolution: document.getElementById("filter-resolution").value,
    minSeeds: document.getElementById("filter-min-seeds").value,
    maxSize: document.getElementById("filter-max-size").value,
    sortBy: document.getElementById("filter-sort-by").value,
    filtersOpen: document.getElementById("advanced-filters").style.display === "block"
  };
  safeStorage.setItem("rico_recent_search", JSON.stringify(recent));
}

function updateClearButtonVisibility() {
  const clearBtn = document.getElementById("btn-clear-search");
  const searchInput = document.getElementById("search-input");
  if (!clearBtn || !searchInput) return;
  
  const hasQuery = searchInput.value.trim() !== "";
  const hasResults = state.searchResults && state.searchResults.length > 0;
  
  if (hasQuery || hasResults) {
    clearBtn.style.display = "flex";
  } else {
    clearBtn.style.display = "none";
  }
}

function areMagnetsEqual(m1, m2) {
  if (!m1 || !m2) return false;
  if (m1 === m2) return true;
  const extractHash = (m) => {
    const match = String(m).match(/urn:btih:([a-zA-Z0-9]+)/i);
    return match ? match[1].toLowerCase() : String(m).trim().toLowerCase();
  };
  return extractHash(m1) === extractHash(m2);
}

function syncSearchResultsWithDownloads() {
  if (!state.searchResults || state.searchResults.length === 0) return;
  if (!state.downloads || state.downloads.length === 0) return;

  const completedDownloads = state.downloads.filter(d => {
    const s = (d.status || "").toLowerCase();
    return s.includes("completed") || s.includes("downloaded") || Number(d.progress) >= 100;
  });

  if (completedDownloads.length === 0) return;

  const extractHash = (m) => {
    if (!m) return "";
    const match = String(m).match(/urn:btih:([a-zA-Z0-9]+)/i);
    return match ? match[1].toLowerCase() : String(m).trim().toLowerCase();
  };

  let hasChanges = false;

  state.searchResults.forEach(item => {
    const cleanTitle = (item.clean_title || "").trim().toLowerCase();

    // Check if any completed download matches this card's clean title
    const titleMatch = completedDownloads.find(d => {
      const dTitle = (d.title || "").trim().toLowerCase();
      return dTitle === cleanTitle;
    });

    if (titleMatch && !item.in_database) {
      item.in_database = true;
      item.existing_download = {
        title: titleMatch.title,
        filename: titleMatch.filename,
        size: titleMatch.size,
        status: "completed"
      };
      hasChanges = true;
    }

    // Check each download release under this card
    (item.downloads || []).forEach(dl => {
      const dlHash = extractHash(dl.download_url);
      const match = completedDownloads.find(d => {
        if (d.magnet && dl.download_url && areMagnetsEqual(d.magnet, dl.download_url)) return true;
        if (dlHash && d.magnet && extractHash(d.magnet) === dlHash) return true;
        return false;
      });

      if (match) {
        if (!dl.in_database || !dl.downloaded || dl.db_status !== "completed") {
          dl.in_database = true;
          dl.downloaded = true;
          dl.db_status = "completed";
          item.in_database = true;
          item.existing_download = {
            title: match.title,
            filename: match.filename,
            size: match.size,
            status: "completed"
          };
          hasChanges = true;
        }
      }
    });
  });

  if (hasChanges) {
    saveRecentSearch();
  }
}

// Real-time button and card state sync for active search results
function updateSearchResultButtons() {
  syncSearchResultsWithDownloads();

  const cards = document.querySelectorAll(".media-card");
  if (cards.length === 0) return;
  
  const filteredData = getFilteredResults();
  
  cards.forEach((cardEl, index) => {
    const selectEl = cardEl.querySelector("select");
    const downloadBtn = cardEl.querySelector('button[id^="btn-dl-"]');
    if (!selectEl || !downloadBtn) return;
    
    const item = filteredData[index];
    if (!item) return;
    
    const downloads = item.downloads || [];
    const dlIdx = parseInt(selectEl.value) || 0;
    const dlOption = downloads[dlIdx];
    if (!dlOption) return;
    
    const isSavedInDb = item.in_database || downloads.some(d => d.in_database || d.downloaded);
    const activeDl = state.downloads.find(d => areMagnetsEqual(d.magnet, dlOption.download_url));
    const isActiveInProgress = activeDl && !activeDl.status.toLowerCase().includes("completed") && !activeDl.status.toLowerCase().includes("failed");

    // 1. Update Card border / container class
    cardEl.classList.toggle("in-database", isSavedInDb);

    // 2. Update Title "ON SERVER" Badge
    const titleLine = cardEl.querySelector(".media-title-line");
    if (titleLine) {
      let dbBadgeEl = titleLine.querySelector(".media-in-db-badge");
      if (isSavedInDb) {
        if (!dbBadgeEl) {
          dbBadgeEl = document.createElement("span");
          dbBadgeEl.className = "media-in-db-badge";
          dbBadgeEl.title = "This media is already saved on the server database";
          dbBadgeEl.innerHTML = `
            <svg width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round" style="vertical-align: -1px; margin-right: 2px;"><ellipse cx="12" cy="5" rx="9" ry="3"/><path d="M21 12c0 1.66-4 3-9 3s-9-1.34-9-3"/><path d="M3 5v14c0 1.66 4 3 9 3s9-1.34 9-3V5"/></svg>
            ON SERVER
          `;
          titleLine.appendChild(dbBadgeEl);
        }
      } else if (dbBadgeEl) {
        dbBadgeEl.remove();
      }
    }

    // 3. Update Select Dropdown Options Marker
    Array.from(selectEl.options).forEach((opt, idx) => {
      const dl = downloads[idx];
      if (!dl) return;
      const isSaved = dl.in_database || dl.downloaded;
      const hasMarker = opt.text.includes(" • [ON SERVER]");
      if (isSaved && !hasMarker) {
        const hyphenIdx = opt.text.indexOf(" - ");
        if (hyphenIdx !== -1) {
          opt.text = opt.text.slice(0, hyphenIdx) + " • [ON SERVER]" + opt.text.slice(hyphenIdx);
        } else {
          opt.text += " • [ON SERVER]";
        }
      } else if (!isSaved && hasMarker) {
        opt.text = opt.text.replace(" • [ON SERVER]", "");
      }
    });

    // 4. Update Tags Container for currently selected option
    const tagsContainer = cardEl.querySelector(`#card-tags-${index}`);
    if (tagsContainer) {
      let dbTag = tagsContainer.querySelector(".tag-badge-in-db");
      let altTag = tagsContainer.querySelector(".tag-badge-alt-version");
      if (dlOption.in_database || dlOption.downloaded) {
        if (altTag) altTag.remove();
        if (!dbTag) {
          dbTag = document.createElement("span");
          dbTag.className = "tag-badge tag-badge-in-db";
          dbTag.textContent = "✓ Saved on Server";
          tagsContainer.appendChild(dbTag);
        }
      } else if (isSavedInDb) {
        if (dbTag) dbTag.remove();
        if (!altTag) {
          altTag = document.createElement("span");
          altTag.className = "tag-badge tag-badge-alt-version";
          altTag.textContent = "Alternate Version (Will Overwrite)";
          tagsContainer.appendChild(altTag);
        }
      } else {
        if (dbTag) dbTag.remove();
        if (altTag) altTag.remove();
      }
    }

    // 5. Update Download Button
    if (isActiveInProgress) {
      const progress = activeDl.progress || 0;
      const status = activeDl.status;
      
      downloadBtn.disabled = false;
      downloadBtn.setAttribute("data-active-download", "true");
      downloadBtn.setAttribute("data-torrent-id", activeDl.torbox_id);
      
      const statusUpper = status.toUpperCase();
      const isHovered = downloadBtn.matches(":hover");
      downloadBtn.setAttribute("data-normal-text", `${statusUpper} (${progress}%)`);
      if (!isHovered) {
        downloadBtn.innerHTML = `${statusUpper} (${progress}%)`;
        downloadBtn.className = "btn btn-primary btn-status-active";
      }
    } else if (dlOption.in_database || dlOption.downloaded) {
      downloadBtn.disabled = false;
      downloadBtn.innerHTML = "RE-DOWNLOAD";
      downloadBtn.className = "btn btn-secondary";
      downloadBtn.setAttribute("data-overwrite", "true");
      downloadBtn.removeAttribute("data-active-download");
      downloadBtn.removeAttribute("data-torrent-id");
      downloadBtn.removeAttribute("data-normal-text");
    } else if (isSavedInDb) {
      downloadBtn.disabled = false;
      downloadBtn.innerHTML = "DOWNLOAD & REPLACE";
      downloadBtn.className = "btn btn-primary";
      downloadBtn.setAttribute("data-overwrite", "true");
      downloadBtn.removeAttribute("data-active-download");
      downloadBtn.removeAttribute("data-torrent-id");
      downloadBtn.removeAttribute("data-normal-text");
    } else {
      downloadBtn.disabled = false;
      downloadBtn.innerHTML = "DOWNLOAD";
      downloadBtn.className = "btn btn-primary";
      downloadBtn.setAttribute("data-overwrite", "false");
      downloadBtn.removeAttribute("data-active-download");
      downloadBtn.removeAttribute("data-torrent-id");
      downloadBtn.removeAttribute("data-normal-text");
    }
  });
}

// Renders the (filtered) list of search results
function renderSearchResults() {
  syncSearchResultsWithDownloads();

  const container = document.getElementById("results-list");
  if (!container) return;

  if (!state.searchResults || state.searchResults.length === 0) {
    container.innerHTML = '<div class="empty-state">EXECUTE SEARCH QUERY TO LOAD RESULTS</div>';
    return;
  }

  const filteredData = getFilteredResults();
  
  if (filteredData.length === 0) {
    container.innerHTML = '<div class="empty-state">NO RELEASES FOUND MATCHING FILTERS</div>';
    return;
  }

  container.innerHTML = "";
  filteredData.forEach((item, index) => {
    const cardEl = document.createElement("div");
    const isSavedInDb = item.in_database || item.downloads.some(d => d.in_database || d.downloaded);
    cardEl.className = isSavedInDb ? "media-card in-database animate-slide" : "media-card animate-slide";
    
    const downloads = item.downloads;
    const defaultOption = downloads[0];

    // Build select dropdown option listing
    let optionsHtml = "";
    downloads.forEach((dl, dlIdx) => {
      const displaySize = formatBytes(dl.size);
      const isSaved = dl.in_database || dl.downloaded;
      const marker = isSaved ? " • [ON SERVER]" : "";
      const isTopRecommended = dlIdx === 0 && (dl.relevancy_score ?? 0) > 0;
      const recMarker = isTopRecommended ? " • Recommended" : "";
      let typeMarker = "";
      if (dl.is_season_pack) {
        const sStr = dl.season ? `S${String(dl.season).padStart(2, '0')}` : "FULL";
        typeMarker = ` • [SEASON PACK: ${sStr}]`;
      } else if (dl.is_tv && dl.season && dl.episode) {
        typeMarker = ` • [EPISODE: S${String(dl.season).padStart(2, '0')}E${String(dl.episode).padStart(2, '0')}]`;
      }
      const aiMarker = dl.is_ai ? " • [AI]" : "";
      const camMarker = dl.is_cam ? " • [CAM/TS]" : "";
      optionsHtml += `
        <option value="${dlIdx}">
          [${displaySize} | Seeds: ${escapeHtml(dl.seeders)}]${recMarker}${marker}${typeMarker}${aiMarker}${camMarker} - ${escapeHtml(dl.title)}
        </option>
      `;
    });

    const isTV = item.is_tv;
    const yearText = item.year ? `(${item.year})` : "";
    const categoryBadge = isTV ? `<span class="media-type-badge">TV</span>` : `<span class="media-type-badge">MOVIE</span>`;
    const dbBadge = isSavedInDb ? `
      <span class="media-in-db-badge" title="This media is already saved on the server database">
        <svg width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round" style="vertical-align: -1px; margin-right: 2px;"><ellipse cx="12" cy="5" rx="9" ry="3"/><path d="M21 12c0 1.66-4 3-9 3s-9-1.34-9-3"/><path d="M3 5v14c0 1.66 4 3 9 3s9-1.34 9-3V5"/></svg>
        ON SERVER
      </span>
    ` : "";
    
    // Poster representation
    const posterHtml = item.poster_url 
      ? `<img src="${escapeHtml(item.poster_url)}" alt="Poster" style="width: 100%; height: 100%; object-fit: cover;">`
      : `<span>${isTV ? 'TV' : 'FILM'}</span>`;
      
    // Compute current size range for the filtered downloads list
    const sizes = downloads.map(d => d.size);
    const minSizeStr = formatBytes(Math.min(...sizes));
    const maxSizeStr = formatBytes(Math.max(...sizes));
    const sizeRangeText = minSizeStr === maxSizeStr ? minSizeStr : `${minSizeStr} - ${maxSizeStr}`;

    cardEl.innerHTML = `
      <div class="media-card-main">
        <div class="media-poster-stub">
          ${posterHtml}
        </div>
        <div class="media-card-info">
          <div class="media-title-line">
            <span>${escapeHtml(item.clean_title)} ${escapeHtml(yearText)}</span>
            ${categoryBadge}
            ${dbBadge}
          </div>
          <div class="media-meta-line">
            <span>Size Range: <strong>${escapeHtml(sizeRangeText)}</strong></span>
            <span>Releases: <strong>${downloads.length}</strong></span>
          </div>
          <div class="media-tags" id="card-tags-${index}">
            <!-- Reactive badges populated by javascript -->
          </div>
        </div>
      </div>
      
      <div class="media-card-actions">
        <select class="form-input" id="select-dl-${index}">
          ${optionsHtml}
        </select>
        <button class="btn btn-primary" id="btn-dl-${index}">DOWNLOAD</button>
        ${isTV ? `
          <button class="btn btn-secondary btn-tv-tracker" id="btn-tv-tracker-${index}" title="Check seasons, library completion, and missing episodes">
            <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round" style="vertical-align: -1px; margin-right: 3px;"><path d="M4 6h16M4 12h16M4 18h7"/></svg>
            Seasons & Episodes
          </button>
        ` : ''}
      </div>
      ${isTV ? `<div class="tv-season-drawer" id="tv-drawer-${index}" style="display: none;"></div>` : ''}
    `;

    container.appendChild(cardEl);
    
    if (isTV) {
      const trackerBtn = cardEl.querySelector(`#btn-tv-tracker-${index}`);
      if (trackerBtn) {
        trackerBtn.addEventListener("click", () => {
          toggleTvDrawer(index, item);
        });
      }
    }

    const selectEl = cardEl.querySelector(`#select-dl-${index}`);
    const tagsContainer = cardEl.querySelector(`#card-tags-${index}`);
    const downloadBtn = cardEl.querySelector(`#btn-dl-${index}`);

    const updateBadges = (dlOption) => {
      tagsContainer.innerHTML = "";
      
      if (dlOption.resolution !== "Unknown") {
        tagsContainer.innerHTML += `<span class="tag-badge">${escapeHtml(dlOption.resolution)}</span>`;
      }
      dlOption.features.forEach(feat => {
        tagsContainer.innerHTML += `<span class="tag-badge">${escapeHtml(feat)}</span>`;
      });
      if (dlOption.source !== "Unknown") {
        tagsContainer.innerHTML += `<span class="tag-badge">${escapeHtml(dlOption.source)}</span>`;
      }
      if (dlOption.codec !== "Unknown") {
        tagsContainer.innerHTML += `<span class="tag-badge">${escapeHtml(dlOption.codec)}</span>`;
      }
      dlOption.audio.forEach(aud => {
        tagsContainer.innerHTML += `<span class="tag-badge">${escapeHtml(aud)}</span>`;
      });
      
      if (dlOption.is_ai) {
        tagsContainer.innerHTML += `<span class="tag-badge tag-badge-ai">AI Upscale</span>`;
      }
      if (dlOption.is_cam) {
        tagsContainer.innerHTML += `<span class="tag-badge tag-badge-cam">CAM / TS</span>`;
      }
      if (dlOption === downloads[0] && (dlOption.relevancy_score ?? 0) > 0) {
        tagsContainer.innerHTML += `<span class="tag-badge tag-badge-recommended">★ Recommended</span>`;
      }
      
      if (dlOption.is_season_pack) {
        const sStr = dlOption.season ? `S${String(dlOption.season).padStart(2, '0')}` : "FULL";
        tagsContainer.innerHTML += `<span class="tag-badge tag-badge-season-pack">Season Pack (${sStr})</span>`;
      } else if (dlOption.is_tv && dlOption.season && dlOption.episode) {
        tagsContainer.innerHTML += `<span class="tag-badge tag-badge-episode">S${String(dlOption.season).padStart(2, '0')}E${String(dlOption.episode).padStart(2, '0')}</span>`;
      }
      
      tagsContainer.innerHTML += `<span class="tag-badge" style="border-style: solid; opacity: 0.6;">${escapeHtml(dlOption.indexer)}</span>`;
      
      const currentSavedInDb = item.in_database || downloads.some(d => d.in_database || d.downloaded);
      if (dlOption.in_database || dlOption.downloaded) {
        tagsContainer.innerHTML += `<span class="tag-badge tag-badge-in-db">✓ Saved on Server</span>`;
      } else if (currentSavedInDb) {
        tagsContainer.innerHTML += `<span class="tag-badge tag-badge-alt-version">Alternate Version (Will Overwrite)</span>`;
      }
      
      // Update download button state
      const activeDl = state.downloads.find(d => areMagnetsEqual(d.magnet, dlOption.download_url));
      const isActiveInProgress = activeDl && !activeDl.status.toLowerCase().includes("completed") && !activeDl.status.toLowerCase().includes("failed");

      if (isActiveInProgress) {
        const progress = activeDl.progress || 0;
        const status = activeDl.status;
        
        downloadBtn.disabled = false;
        downloadBtn.setAttribute("data-active-download", "true");
        downloadBtn.setAttribute("data-torrent-id", activeDl.torbox_id);
        
        const statusUpper = status.toUpperCase();
        downloadBtn.innerHTML = `${statusUpper} (${progress}%)`;
        downloadBtn.className = "btn btn-primary btn-status-active";
        downloadBtn.setAttribute("data-normal-text", `${statusUpper} (${progress}%)`);
      } else if (dlOption.in_database || dlOption.downloaded) {
        downloadBtn.disabled = false;
        downloadBtn.innerHTML = "RE-DOWNLOAD";
        downloadBtn.className = "btn btn-secondary";
        downloadBtn.setAttribute("data-overwrite", "true");
        downloadBtn.removeAttribute("data-active-download");
        downloadBtn.removeAttribute("data-torrent-id");
        downloadBtn.removeAttribute("data-normal-text");
      } else if (currentSavedInDb) {
        downloadBtn.disabled = false;
        downloadBtn.innerHTML = "DOWNLOAD & REPLACE";
        downloadBtn.className = "btn btn-primary";
        downloadBtn.setAttribute("data-overwrite", "true");
        downloadBtn.removeAttribute("data-active-download");
        downloadBtn.removeAttribute("data-torrent-id");
        downloadBtn.removeAttribute("data-normal-text");
      } else {
        downloadBtn.disabled = false;
        downloadBtn.innerHTML = "DOWNLOAD";
        downloadBtn.className = "btn btn-primary";
        downloadBtn.setAttribute("data-overwrite", "false");
        downloadBtn.removeAttribute("data-active-download");
        downloadBtn.removeAttribute("data-torrent-id");
        downloadBtn.removeAttribute("data-normal-text");
      }
    };

    updateBadges(defaultOption);

    // Hover listeners for active download cancel button sync
    downloadBtn.addEventListener("mouseenter", () => {
      if (downloadBtn.getAttribute("data-active-download") === "true" && downloadBtn.getAttribute("data-normal-text")) {
        downloadBtn.textContent = "CANCEL";
        downloadBtn.className = "btn btn-danger";
      }
    });

    downloadBtn.addEventListener("mouseleave", () => {
      if (downloadBtn.getAttribute("data-active-download") === "true" && downloadBtn.getAttribute("data-normal-text")) {
        downloadBtn.textContent = downloadBtn.getAttribute("data-normal-text") || "DOWNLOADING";
        downloadBtn.className = "btn btn-primary btn-status-active";
      }
    });

    selectEl.addEventListener("change", (e) => {
      const idx = parseInt(e.target.value);
      updateBadges(downloads[idx]);
    });

    downloadBtn.addEventListener("click", () => {
      if (downloadBtn.getAttribute("data-active-download") === "true") {
        const torboxId = downloadBtn.getAttribute("data-torrent-id");
        if (confirm("Are you sure you want to cancel this transfer and delete any incomplete files?")) {
          downloadBtn.disabled = true;
          downloadBtn.textContent = "ABORTING...";
          cancelDownload(torboxId);
        }
        return;
      }
      
      const dlIdx = parseInt(selectEl.value);
      const selectedDl = downloads[dlIdx];
      const isOverwrite = downloadBtn.getAttribute("data-overwrite") === "true";
      
      triggerDownload(
        selectedDl.download_url,
        item.clean_title,
        selectedDl.title,
        isTV ? "tv" : "movie",
        item.year,
        selectedDl.season,
        selectedDl.episode,
        selectedDl.size,
        downloadBtn,
        isOverwrite
      );
    });
  });
}

function renderActiveDownloads() {
  const container = document.getElementById("sidebar-downloads-list");
  if (!container) return;

  if (state.downloads.length === 0) {
    container.innerHTML = '<div class="empty-state">NO ACTIVE TRANSFERS</div>';
    return;
  }

  container.innerHTML = "";
  state.downloads.forEach(dl => {
    container.innerHTML += `<div class="dl-item animate-slide" id="dl-item-${dl.torbox_id}">${renderDownloadItem(dl)}</div>`;
  });
}

function renderDownloadItem(dl) {
  const progress = dl.progress || 0;
  const statusClass = getStatusClass(dl.status);
  const sizeText = dl.size ? formatBytes(dl.size) : "";
  
  const statusLower = (dl.status || "").toLowerCase();
  const isCompleted = statusLower.includes("completed") || statusLower.includes("downloaded");
  const isFailed = statusLower.includes("failed") || statusLower.includes("error") || statusLower.includes("stalled") || statusLower.includes("paused") || statusLower.includes("interrupted");
  const isActive = !isCompleted && !isFailed;
  
  const isAdmin = state.user && state.user.group_name === "Admin";
  const isOwner = state.user && (
    dl.user_id === undefined || dl.user_id === null || Number(dl.user_id) === Number(state.user.id)
  );
  const canControl = isAdmin || isOwner;
  
  let cancelBtnHtml = "";
  let resumeBtnHtml = "";
  if (isFailed && canControl) {
    resumeBtnHtml = `<button class="btn btn-secondary btn-resume-dl" data-torbox-id="${dl.torbox_id}" style="padding: 0.15rem 0.4rem; font-size: 0.6rem; font-family: var(--font-mono); height: 18px; line-height: 1; border-radius: 0; margin-top: 4px; margin-right: 4px;">RESUME</button>`;
    cancelBtnHtml = `<button class="btn btn-danger btn-cancel-dl" data-torbox-id="${dl.torbox_id}" style="padding: 0.15rem 0.4rem; font-size: 0.6rem; font-family: var(--font-mono); height: 18px; line-height: 1; border-radius: 0; margin-top: 4px;">CLEAR</button>`;
  } else if (isCompleted && canControl) {
    cancelBtnHtml = `<button class="btn btn-danger btn-cancel-dl" data-torbox-id="${dl.torbox_id}" style="padding: 0.15rem 0.4rem; font-size: 0.6rem; font-family: var(--font-mono); height: 18px; line-height: 1; border-radius: 0; margin-top: 4px;">DELETE</button>`;
  } else if (isActive && canControl) {
    cancelBtnHtml = `<button class="btn btn-danger btn-cancel-dl" data-torbox-id="${dl.torbox_id}" style="padding: 0.15rem 0.4rem; font-size: 0.6rem; font-family: var(--font-mono); height: 18px; line-height: 1; border-radius: 0; margin-top: 4px;">CANCEL</button>`;
  }
  
  const displayTitle = escapeHtml(dl.title || dl.filename || "Unknown Torrent");
  const displaySubtitle = escapeHtml((dl.filename && dl.filename !== dl.title) ? dl.filename : "");
  
  return `
      <div class="dl-item-header">
        <div style="min-width: 0; flex-grow: 1;">
          <div class="dl-item-title" title="${displayTitle}">${displayTitle}</div>
          ${displaySubtitle ? `<div class="dl-item-subtitle" title="${displaySubtitle}">${displaySubtitle}</div>` : ""}
        </div>
        <div style="display: flex; flex-direction: column; align-items: flex-end; gap: 0.25rem; flex-shrink: 0;">
          <span class="dl-item-status dl-status-${statusClass}">${escapeHtml(dl.status)}</span>
          <div style="display: flex; gap: 2px;">
            ${resumeBtnHtml}
            ${cancelBtnHtml}
          </div>
        </div>
      </div>
      <div class="dl-progress-track">
        <div class="dl-progress-bar" style="width: ${progress}%;"></div>
      </div>
      <div class="dl-item-meta">
        <span>${progress}% ${sizeText ? `(${sizeText})` : ""}</span>
        <span class="speed">${dl.speed ? formatSpeed(dl.speed) : ""}</span>
      </div>
  `;
}

// Downloads Realtime UI update
function updateDownloadProgressUI(data) {
  const torrentId = data.id;
  const status = data.status;
  const progress = data.progress;
  const speed = data.speed;
  const size = data.size;

  const isAdminOrMod = state.user && (state.user.group_name === "Admin" || state.user.group_name === "Moderator");
  const isOwner = state.user && (data.user_id === undefined || data.user_id === null || Number(data.user_id) === Number(state.user.id));
  
  // If not admin/mod and not owner, ignore this progress update entirely
  if (!isAdminOrMod && !isOwner) {
    return;
  }

  const downloadListEl = document.getElementById("sidebar-downloads-list");
  if (downloadListEl) {
    let itemEl = document.getElementById(`dl-item-${torrentId}`);
    if (!itemEl) {
      itemEl = document.createElement("div");
      itemEl.className = "dl-item animate-slide";
      itemEl.id = `dl-item-${torrentId}`;
      itemEl.innerHTML = renderDownloadItem({
        torbox_id: torrentId,
        title: data.title,
        filename: data.filename,
        status: status,
        progress: progress,
        speed: speed,
        size: size,
        user_id: data.user_id
      });
      
      const emptyStateEl = downloadListEl.querySelector(".empty-state");
      if (emptyStateEl) emptyStateEl.remove();
      
      downloadListEl.insertBefore(itemEl, downloadListEl.firstChild);
    } else {
      itemEl.innerHTML = renderDownloadItem({
        torbox_id: torrentId,
        title: data.title || itemEl.querySelector(".dl-item-title").textContent,
        filename: data.filename || "",
        status: status,
        progress: progress,
        speed: speed,
        size: size,
        user_id: data.user_id
      });
    }
  }

  // Update admin downloads table if visible
  const adminStatusEl = document.getElementById(`admin-dl-status-${torrentId}`);
  if (adminStatusEl) {
    const statusLower = (status || "").toLowerCase();
    const isCompleted = statusLower.includes("completed") || statusLower.includes("downloaded");
    const isFailed = statusLower.includes("failed") || statusLower.includes("error") || statusLower.includes("stalled") || statusLower.includes("paused") || statusLower.includes("interrupted");
    const isDownloading = statusLower.includes("downloading") || statusLower.includes("moving");

    let badgeClass = "badge-queued";
    if (isCompleted) badgeClass = "badge-completed";
    else if (isDownloading) badgeClass = "badge-downloading";
    else if (isFailed) badgeClass = "badge-failed";

    const progressText = progress !== undefined ? `${progress}%` : "0%";
    const speedText = speed && speed > 0 ? ` • ${formatSpeed(speed)}` : "";
    adminStatusEl.className = `admin-badge ${badgeClass}`;
    adminStatusEl.innerHTML = `${escapeHtml(status.toUpperCase())} (${escapeHtml(progressText)}${speedText})`;
    
    const adminSizeEl = document.getElementById(`admin-dl-size-${torrentId}`);
    if (adminSizeEl && size) {
      adminSizeEl.innerHTML = formatBytes(size);
    }
    
    const adminBtnEl = document.getElementById(`admin-dl-btn-${torrentId}`);
    if (adminBtnEl) {
      let btnHtml = "";
      const isAdmin = state.user && state.user.group_name === "Admin";
      const canControl = isAdmin || isOwner;
      if (canControl) {
        if (isCompleted) {
          btnHtml = `<button class="btn btn-danger btn-admin-action" data-action="delete" data-torbox-id="${torrentId}" style="padding: 0.25rem 0.5rem; font-size: 0.7rem; height: 28px; border-radius: 0;">DELETE</button>`;
        } else if (isFailed) {
          btnHtml = `<button class="btn btn-secondary btn-admin-action" data-action="resume" data-torbox-id="${torrentId}" style="padding: 0.25rem 0.5rem; font-size: 0.7rem; height: 28px; border-radius: 0; margin-right: 4px;">RESUME</button>` +
                    `<button class="btn btn-danger btn-admin-action" data-action="delete" data-torbox-id="${torrentId}" style="padding: 0.25rem 0.5rem; font-size: 0.7rem; height: 28px; border-radius: 0;">CLEAR</button>`;
        } else {
          btnHtml = `<button class="btn btn-danger btn-admin-action" data-action="cancel" data-torbox-id="${torrentId}" style="padding: 0.25rem 0.5rem; font-size: 0.7rem; height: 28px; border-radius: 0;">CANCEL</button>`;
        }
      } else {
        btnHtml = `<span style="font-size: 0.7rem; color: var(--text-muted); font-style: italic;">No Access</span>`;
      }
      adminBtnEl.innerHTML = btnHtml;
    }
  }

  const matchingStateDl = state.downloads.find(d => String(d.torbox_id) === String(torrentId));
  if (matchingStateDl) {
    matchingStateDl.status = status;
    matchingStateDl.progress = progress;
    matchingStateDl.speed = speed;
    matchingStateDl.size = size;
    if (data.magnet) matchingStateDl.magnet = data.magnet;
    if (data.user_id) matchingStateDl.user_id = data.user_id;
  } else {
    state.downloads.unshift({
      torbox_id: torrentId,
      title: data.title,
      filename: data.filename,
      magnet: data.magnet,
      status: status,
      progress: progress,
      speed: speed,
      size: size,
      user_id: data.user_id
    });
  }
  updateSidebarBadge();
  updateSearchResultButtons();
  if (state.currentView === "popular") {
    renderPopularGrid();
  }
}

// Sidebar logic
function toggleSidebar() {
  state.sidebarOpen = !state.sidebarOpen;
  const appEl = document.getElementById("app");
  if (state.sidebarOpen) {
    appEl.classList.add("sidebar-open");
  } else {
    appEl.classList.remove("sidebar-open");
  }
}

function updateSidebarBadge() {
  const badgeEl = document.getElementById("downloads-badge");
  if (!badgeEl) return;
  
  const activeCount = state.downloads.filter(d => {
    const s = d.status.toLowerCase();
    return !s.includes("completed") && !s.includes("failed");
  }).length;
  
  if (activeCount > 0) {
    badgeEl.textContent = activeCount;
    badgeEl.style.display = "flex";
  } else {
    badgeEl.style.display = "none";
  }
}

// Formatting & helpers
function getStatusClass(status) {
  const stat = status.toLowerCase();
  if (stat.includes("completed") || stat.includes("downloaded")) return "completed";
  if (stat.includes("downloading")) return "downloading";
  if (stat.includes("moving") || stat.includes("transferring")) return "moving";
  if (stat.includes("queued")) return "queued";
  return "failed";
}

function formatSpeed(bytesPerSec) {
  if (!bytesPerSec || bytesPerSec === 0) return "";
  let val = bytesPerSec;
  for (const unit of ["B/s", "KB/s", "MB/s", "GB/s"]) {
    if (val < 1024) return `${val.toFixed(1)} ${unit}`;
    val /= 1024;
  }
  return `${val.toFixed(1)} TB/s`;
}

function formatBytes(bytes) {
  if (!bytes || bytes === 0) return "0 B";
  let val = bytes;
  for (const unit of ["B", "KB", "MB", "GB", "TB"]) {
    if (val < 1024) return `${val.toFixed(1)} ${unit}`;
    val /= 1024;
  }
  return `${val.toFixed(1)} PB`;
}

// Event Listeners setups
function setupLoginListeners() {
  // Direct redirection callback handles OAuth
}

function setupAppShellListeners() {
  document.getElementById("nav-downloads-toggle").addEventListener("click", toggleSidebar);
  document.getElementById("downloads-sidebar-close").addEventListener("click", toggleSidebar);
  
  document.getElementById("nav-logout").addEventListener("click", logout);
  
  const searchNavBtn = document.getElementById("nav-search");
  if (searchNavBtn) {
    searchNavBtn.addEventListener("click", () => {
      navigate("dashboard");
    });
  }

  const popularNavBtn = document.getElementById("nav-popular");
  if (popularNavBtn) {
    popularNavBtn.addEventListener("click", () => {
      navigate("popular");
    });
  }

  const adminNavBtn = document.getElementById("nav-admin");
  if (adminNavBtn) {
    adminNavBtn.addEventListener("click", () => {
      state.adminActiveTab = (state.user && state.user.group_name === "Admin") ? "users" : "downloads";
      navigate("admin");
    });
  }
  
  document.getElementById("brand-link").addEventListener("click", (e) => {
    e.preventDefault();
    navigate("dashboard");
  });
  
  // Delegate click events for the download cancel/delete/resume buttons
  document.getElementById("downloads-sidebar").addEventListener("click", async (e) => {
    if (e.target.classList.contains("btn-resume-dl")) {
      const torboxId = e.target.getAttribute("data-torbox-id");
      e.target.disabled = true;
      e.target.textContent = "RESUMING...";
      await resumeDownload(torboxId);
    } else if (e.target.classList.contains("btn-cancel-dl")) {
      const torboxId = e.target.getAttribute("data-torbox-id");
      const isDelete = e.target.textContent === "DELETE";
      const confirmMsg = isDelete
        ? "Are you sure you want to delete this downloaded item and all its files from the server?"
        : "Are you sure you want to cancel this transfer and delete any files from the server?";
      if (confirm(confirmMsg)) {
        e.target.disabled = true;
        e.target.textContent = isDelete ? "DELETING..." : "ABORTING...";
        await cancelDownload(torboxId);
      }
    }
  });
}

async function resumeDownload(torboxId) {
  try {
    const headers = {
      "Content-Type": "application/json"
    };
    if (state.token) {
      headers["Authorization"] = `Bearer ${state.token}`;
    }
    const resp = await fetch("/api/torbox/control", {
      method: "POST",
      headers: headers,
      body: JSON.stringify({ torbox_id: torboxId, action: "resume" })
    });
    if (resp.ok) {
      fetchDownloads();
    } else {
      const errData = await resp.json();
      alert(`Failed to resume: ${errData.error}`);
      fetchDownloads();
    }
  } catch (err) {
    console.error("Resume download failure:", err);
    alert("Network error resuming download.");
    fetchDownloads();
  }
}

async function cancelDownload(torboxId) {
  try {
    const headers = {
      "Content-Type": "application/json"
    };
    if (state.token) {
      headers["Authorization"] = `Bearer ${state.token}`;
    }
    const resp = await fetch("/api/torbox/control", {
      method: "POST",
      headers: headers,
      body: JSON.stringify({ torbox_id: torboxId, action: "delete" })
    });
    if (resp.ok) {
      // Remove from state downloads array
      state.downloads = state.downloads.filter(d => String(d.torbox_id) !== String(torboxId));
      
      // Remove from DOM
      const itemEl = document.getElementById(`dl-item-${torboxId}`);
      if (itemEl) itemEl.remove();
      
      // Reset empty state placeholder if none left
      const listEl = document.getElementById("sidebar-downloads-list");
      if (listEl && listEl.querySelectorAll(".dl-item").length === 0) {
        listEl.innerHTML = '<div class="empty-state">NO ACTIVE TRANSFERS</div>';
      }
      
      updateSidebarBadge();
      updateSearchResultButtons();
    } else {
      const errData = await resp.json();
      alert(`Failed to cancel: ${errData.error}`);
      fetchDownloads();
    }
  } catch (err) {
    console.error("Cancel download failure:", err);
    alert("Network error cancelling download.");
    fetchDownloads();
  }
}

function setupDashboardContentListeners() {
  // Toggle advanced filters slide expansion
  const toggleFiltersBtn = document.getElementById("btn-toggle-filters");
  const filtersPanel = document.getElementById("advanced-filters");
  
  // Load and populate from localStorage
  const savedSearch = safeStorage.getItem("rico_recent_search");
  let saved = null;
  if (savedSearch) {
    try {
      saved = JSON.parse(savedSearch);
    } catch (e) {}
  }
  
  if (saved) {
    document.getElementById("search-input").value = saved.query || "";
    document.getElementById("filter-category").value = saved.category || "";
    document.getElementById("filter-resolution").value = saved.resolution || "";
    document.getElementById("filter-min-seeds").value = saved.minSeeds || "0";
    document.getElementById("filter-max-size").value = saved.maxSize || "0";
    document.getElementById("filter-sort-by").value = saved.sortBy || "relevancy-desc";
    
    if (saved.filtersOpen) {
      filtersPanel.style.display = "block";
      toggleFiltersBtn.textContent = "Filters ▴";
    } else {
      filtersPanel.style.display = "none";
      toggleFiltersBtn.textContent = "Filters ▾";
    }
  }
  
  toggleFiltersBtn.addEventListener("click", () => {
    if (filtersPanel.style.display === "none") {
      filtersPanel.style.display = "block";
      toggleFiltersBtn.textContent = "Filters ▴";
    } else {
      filtersPanel.style.display = "none";
      toggleFiltersBtn.textContent = "Filters ▾";
    }
    saveRecentSearch();
  });

  // Clear button click listener
  const clearBtn = document.getElementById("btn-clear-search");
  const searchInput = document.getElementById("search-input");
  if (clearBtn && searchInput) {
    clearBtn.addEventListener("click", () => {
      searchInput.value = "";
      document.getElementById("filter-category").value = "";
      document.getElementById("filter-resolution").value = "";
      document.getElementById("filter-min-seeds").value = "0";
      document.getElementById("filter-max-size").value = "0";
      document.getElementById("filter-sort-by").value = "relevancy-desc";
      state.searchResults = [];
      saveRecentSearch();
      renderSearchResults();
      updateClearButtonVisibility();
    });
    
    searchInput.addEventListener("input", () => {
      saveRecentSearch();
      updateClearButtonVisibility();
    });
    searchInput.addEventListener("keydown", (e) => {
      if (e.key === "Enter") {
        e.preventDefault();
        searchInput.blur();
        if (document.activeElement && typeof document.activeElement.blur === "function") {
          document.activeElement.blur();
        }
        const query = searchInput.value;
        const category = document.getElementById("filter-category") ? document.getElementById("filter-category").value : "";
        searchTrackers(query, category);
      }
    });
  }

  // Search submission
  const searchForm = document.getElementById("search-form");
  if (searchForm) {
    searchForm.addEventListener("submit", (e) => {
      e.preventDefault();
      if (searchInput) searchInput.blur();
      if (document.activeElement && typeof document.activeElement.blur === "function") {
        document.activeElement.blur();
      }
      const query = searchInput ? searchInput.value : "";
      const category = document.getElementById("filter-category") ? document.getElementById("filter-category").value : "";
      searchTrackers(query, category);
    });
  }

  // Attach dynamic real-time input change triggers to advanced filters
  const filterElements = [
    "filter-category",
    "filter-resolution",
    "filter-min-seeds",
    "filter-max-size",
    "filter-sort-by"
  ];
  filterElements.forEach(id => {
    const el = document.getElementById(id);
    if (el) {
      const handleFilterChange = () => {
        saveRecentSearch();
        renderSearchResults();
        updateClearButtonVisibility();
      };
      el.addEventListener("input", handleFilterChange);
      el.addEventListener("change", handleFilterChange);
    }
  });

  // Set initial clear button visibility
  updateClearButtonVisibility();
}

// Settings listeners removed (merged into admin panel)

// PENDING APPROVAL VIEW & HELPERS
function renderPendingApproval() {
  const name = state.user ? (state.user.full_name || state.user.username) : "User";
  return `
    <div class="auth-wrapper animate-slide">
      <div class="auth-card">
        <h1>RICO.CX</h1>
        <p style="margin-top: 1rem; font-size: 0.95rem; color: var(--text-primary);">Account Approval Pending</p>
        <p style="margin-top: 0.5rem; font-size: 0.8rem; color: var(--text-secondary);">
          Hello, <strong>${name}</strong>. Your account has been registered, but it has not been approved yet.
        </p>
        <p style="margin-top: 0.5rem; font-size: 0.8rem; color: var(--text-secondary); margin-bottom: 2rem;">
          Please contact an Administrator to approve your access.
        </p>
        <button id="btn-pending-logout" class="google-auth-btn" style="background-color: var(--danger); color: white;">Logout</button>
      </div>
    </div>
  `;
}

function setupPendingListeners() {
  const logoutBtn = document.getElementById("btn-pending-logout");
  if (logoutBtn) {
    logoutBtn.addEventListener("click", logout);
  }
}

// ADMIN VIEW & HELPERS
// ADMIN VIEW & HELPERS
function renderAdminContent() {
  const isAdmin = state.user && state.user.group_name === "Admin";
  const isMod = state.user && state.user.group_name === "Moderator";
  
  const usersTabClass = state.adminActiveTab === "users" ? "btn btn-primary" : "btn";
  const downloadsTabClass = state.adminActiveTab === "downloads" ? "btn btn-primary" : "btn";
  const settingsTabClass = state.adminActiveTab === "settings" ? "btn btn-primary" : "btn";
  
  let tabsHtml = "";
  if (isAdmin) {
    tabsHtml = `
      <button id="tab-admin-downloads" class="${downloadsTabClass}" style="flex: 1; border-radius: 0;">All Downloads</button>
      <button id="tab-admin-users" class="${usersTabClass}" style="flex: 1; border-radius: 0;">Users Directory</button>
      <button id="tab-admin-settings" class="${settingsTabClass}" style="flex: 1; border-radius: 0;">Server Settings</button>
    `;
  } else if (isMod) {
    tabsHtml = `
      <button id="tab-admin-downloads" class="${downloadsTabClass}" style="flex: 1; border-radius: 0;">All Downloads</button>
    `;
  }
  
  const showUsersDisplay = state.adminActiveTab === "users" ? "block" : "none";
  const showDownloadsDisplay = state.adminActiveTab === "downloads" ? "block" : "none";
  const showSettingsDisplay = state.adminActiveTab === "settings" ? "block" : "none";

  return `
    <div class="settings-box animate-slide">
      <div style="margin-bottom: 1.5rem;">
        <h2>ADMINISTRATION PANEL</h2>
        <p style="color: var(--text-secondary); margin-bottom: 0;">System telemetry, user management, and server orchestration.</p>
      </div>

      <!-- Real-time KPI Stats Grid -->
      <div id="admin-stats-grid" class="admin-stats-grid">
        <div class="admin-stat-card">
          <div class="admin-stat-header">
            <span>Database Size</span>
            <span class="admin-stat-icon" aria-hidden="true">
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><ellipse cx="12" cy="5" rx="9" ry="3"/><path d="M21 12c0 1.66-4 3-9 3s-9-1.34-9-3"/><path d="M3 5v14c0 1.66 4 3 9 3s9-1.34 9-3V5"/></svg>
            </span>
          </div>
          <div id="stat-db-size" class="admin-stat-value">Loading...</div>
          <div id="stat-db-sub" class="admin-stat-sub">SQLite (WAL Mode)</div>
        </div>
        <div class="admin-stat-card">
          <div class="admin-stat-header">
            <span>Library Storage</span>
            <span class="admin-stat-icon" aria-hidden="true">
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect width="20" height="8" x="2" y="2" rx="2" ry="2"/><rect width="20" height="8" x="2" y="14" rx="2" ry="2"/><line x1="6" x2="6.01" y1="6" y2="6"/><line x1="6" x2="6.01" y1="18" y2="18"/></svg>
            </span>
          </div>
          <div id="stat-storage-size" class="admin-stat-value">Loading...</div>
          <div id="stat-storage-sub" class="admin-stat-sub">Library Mount</div>
        </div>
        <div class="admin-stat-card">
          <div class="admin-stat-header">
            <span>Total Downloads</span>
            <span class="admin-stat-icon" aria-hidden="true">
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/><polyline points="7 10 12 15 17 10"/><line x1="12" x2="12" y1="15" y2="3"/></svg>
            </span>
          </div>
          <div id="stat-dl-count" class="admin-stat-value">Loading...</div>
          <div id="stat-dl-sub" class="admin-stat-sub">Tracked Releases</div>
        </div>
        <div class="admin-stat-card">
          <div class="admin-stat-header">
            <span>User Accounts</span>
            <span class="admin-stat-icon" aria-hidden="true">
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M16 21v-2a4 4 0 0 0-4-4H6a4 4 0 0 0-4 4v2"/><circle cx="9" cy="7" r="4"/><path d="M22 21v-2a4 4 0 0 0-3-3.87"/><path d="M16 3.13a4 4 0 0 1 0 7.75"/></svg>
            </span>
          </div>
          <div id="stat-user-count" class="admin-stat-value">Loading...</div>
          <div id="stat-user-sub" class="admin-stat-sub">System Users</div>
        </div>
      </div>
      
      <!-- Admin Tab Headers -->
      <div style="display: flex; gap: 0.5rem; border-bottom: 1px solid var(--border-color); padding-bottom: 1rem; margin-bottom: 1.5rem;">
        ${tabsHtml}
      </div>

      <!-- Tab Content: Downloads -->
      <div id="admin-downloads-section" style="display: ${showDownloadsDisplay};">
        <!-- Filters & Searches -->
        <div style="display: flex; flex-direction: column; gap: 0.75rem; margin-bottom: 1.5rem; border: 1px solid var(--border-color); padding: 1rem; background-color: var(--bg-primary);">
          <div style="display: flex; gap: 0.5rem; flex-wrap: wrap;">
            <input type="text" id="admin-search-dl" class="form-input" placeholder="Search title or filename..." style="flex: 2; min-width: 180px;">
            <select id="admin-filter-status" class="form-input" style="flex: 1; min-width: 120px;">
              <option value="">All Statuses</option>
              <option value="queued">Queued</option>
              <option value="downloading">Downloading / Moving</option>
              <option value="completed">Completed</option>
              <option value="failed">Failed</option>
            </select>
            <select id="admin-sort-by" class="form-input" style="flex: 1; min-width: 120px;">
              <option value="created_at">Date / Time Added</option>
              <option value="size">File Size</option>
              <option value="status">Status</option>
              <option value="username">User</option>
              <option value="title">Title</option>
            </select>
            <select id="admin-sort-order" class="form-input" style="flex: 0.5; min-width: 80px;">
              <option value="desc">DESC</option>
              <option value="asc">ASC</option>
            </select>
          </div>
          <div style="display: flex; justify-content: flex-end; gap: 0.5rem;">
            <button id="btn-admin-filter-reset" class="btn" style="padding: 0.35rem 0.75rem; font-size: 0.75rem; border-radius: 0;">Reset</button>
            <button id="btn-admin-filter-apply" class="btn btn-primary" style="padding: 0.35rem 1rem; font-size: 0.75rem; border-radius: 0;">Apply Filters</button>
          </div>
        </div>

        <div style="margin-bottom: 1rem; display: flex; align-items: center; gap: 0.75rem;">
          <h3 style="font-size: 0.85rem; text-transform: uppercase; letter-spacing: 0.05em; color: var(--text-secondary); font-weight: 600; margin: 0;">System Torrent Queue</h3>
          <span style="font-size: 0.7rem; color: var(--text-muted); font-family: var(--font-mono);">• Real-time Live Sync</span>
        </div>

        <!-- Desktop Downloads Table -->
        <div id="admin-downloads-table-container" class="admin-table-container" style="overflow-x: auto; border: 1px solid var(--border-color); background-color: var(--bg-secondary); padding: 0.5rem;">
          <table class="admin-table">
            <thead>
              <tr>
                <th style="padding: 0.75rem 0.5rem;">Torrent / Release</th>
                <th style="padding: 0.75rem 0.5rem;">Date & Time Added</th>
                <th style="padding: 0.75rem 0.5rem;">User</th>
                <th style="padding: 0.75rem 0.5rem;">Size</th>
                <th style="padding: 0.75rem 0.5rem;">Status & Progress</th>
                <th style="padding: 0.75rem 0.5rem; text-align: right;">Action</th>
              </tr>
            </thead>
            <tbody id="admin-downloads-list">
              <tr>
                <td colspan="6" class="empty-state" style="padding: 2rem;">Loading downloads...</td>
              </tr>
            </tbody>
          </table>
        </div>

        <!-- Mobile Downloads Card View -->
        <div id="admin-downloads-cards-mobile" class="admin-mobile-cards"></div>
      </div>

      <!-- Tab Content: Users -->
      <div id="admin-users-section" style="display: ${showUsersDisplay};">
        <div style="margin-bottom: 1rem; display: flex; align-items: center; gap: 0.75rem;">
          <h3 style="font-size: 0.85rem; text-transform: uppercase; letter-spacing: 0.05em; color: var(--text-secondary); font-weight: 600; margin: 0;">User Accounts & Approvals</h3>
          <span style="font-size: 0.7rem; color: var(--text-muted); font-family: var(--font-mono);">• Sorted by Recent Activity</span>
        </div>

        <!-- Desktop Users Table -->
        <div id="admin-users-table-container" class="admin-table-container" style="overflow-x: auto; border: 1px solid var(--border-color); background-color: var(--bg-secondary); padding: 0.5rem;">
          <table class="admin-table">
            <thead>
              <tr>
                <th style="padding: 0.75rem 0.5rem;">User</th>
                <th style="padding: 0.75rem 0.5rem;">Joined Date</th>
                <th style="padding: 0.75rem 0.5rem;">Role / Group</th>
                <th style="padding: 0.75rem 0.5rem; text-align: right;">Downloads</th>
                <th style="padding: 0.75rem 0.5rem; text-align: right;">Actions</th>
              </tr>
            </thead>
            <tbody id="admin-users-list">
              <tr>
                <td colspan="5" class="empty-state" style="padding: 2rem;">Loading users...</td>
              </tr>
            </tbody>
          </table>
        </div>

        <!-- Mobile Users Card View -->
        <div id="admin-users-cards-mobile" class="admin-mobile-cards"></div>
      </div>

      <!-- Tab Content: Server Settings -->
      <div id="admin-settings-section" style="display: ${showSettingsDisplay};">
        <div style="margin-bottom: 1rem;">
          <h3 style="font-size: 0.85rem; text-transform: uppercase; letter-spacing: 0.05em; color: var(--text-secondary); font-weight: 600;">Server Settings</h3>
        </div>
        <div id="settings-status" class="alert-box alert-success" style="display: none; margin-bottom: 1.5rem; padding: 0.75rem 1rem; border-radius: 8px; font-size: 0.875rem; border: 1px solid #10b98133; color: var(--success); background: #10b9811a;">Server settings successfully updated.</div>
        <form id="settings-form" onsubmit="return false;" style="display: flex; flex-direction: column; gap: 1.25rem; max-width: 600px;">
          <div class="form-group">
            <label class="form-label" for="prowlarr-url">Prowlarr URL</label>
            <input type="text" id="prowlarr-url" class="form-input" placeholder="e.g. http://localhost:9696">
          </div>
          <div class="form-group">
            <label class="form-label" for="prowlarr-key">Prowlarr API Key</label>
            <input type="password" id="prowlarr-key" class="form-input" placeholder="Enter Prowlarr API Key">
          </div>
          <div class="form-group">
            <label class="form-label" for="torbox-key">Torbox API Key</label>
            <input type="password" id="torbox-key" class="form-input" placeholder="Enter Torbox API Key">
          </div>
          <div class="form-group">
            <label class="form-label" for="tmdb-key">TMDb API Key</label>
            <input type="password" id="tmdb-key" class="form-input" placeholder="Enter TMDb API Key">
          </div>
          <div class="form-group">
            <label class="form-label" for="library-path">Library Path</label>
            <input type="text" id="library-path" class="form-input" placeholder="e.g. /data/library">
            <div style="font-size: 0.75rem; color: var(--text-muted); margin-top: 0.25rem;">
              Local storage mount for downloads. Files are sorted into 'MOVIES' / 'TV SHOWS'.
            </div>
          </div>
          <div style="display: flex; gap: 1rem; margin-top: 0.5rem;">
            <button type="submit" class="btn btn-primary">Save Server Config</button>
          </div>
        </form>
      </div>
    </div>
  `;
}

let adminSyncTimer = null;

function startAdminSync() {
  stopAdminSync();
  fetchAdminStats();
  adminSyncTimer = setInterval(() => {
    if (state.currentView === "admin") {
      fetchAdminStats();
      if (state.adminActiveTab === "downloads") {
        fetchAdminDownloads();
      }
    } else {
      stopAdminSync();
    }
  }, 5000);
}

function stopAdminSync() {
  if (adminSyncTimer) {
    clearInterval(adminSyncTimer);
    adminSyncTimer = null;
  }
}

async function fetchAdminStats() {
  const dbSizeEl = document.getElementById("stat-db-size");
  const dbSubEl = document.getElementById("stat-db-sub");
  const storageSizeEl = document.getElementById("stat-storage-size");
  const storageSubEl = document.getElementById("stat-storage-sub");
  const dlCountEl = document.getElementById("stat-dl-count");
  const dlSubEl = document.getElementById("stat-dl-sub");
  const userCountEl = document.getElementById("stat-user-count");
  const userSubEl = document.getElementById("stat-user-sub");

  if (!dbSizeEl) return;

  try {
    const headers = {};
    if (state.token) {
      headers["Authorization"] = `Bearer ${state.token}`;
    }
    const resp = await fetch("/api/admin/stats", { headers });
    if (resp.ok) {
      const stats = await resp.json();
      
      // Database
      if (stats.database) {
        dbSizeEl.textContent = stats.database.size_formatted || "0 B";
        const walInfo = stats.database.wal_size_bytes > 0 ? ` (WAL: ${stats.database.wal_size_formatted})` : "";
        dbSubEl.textContent = `SQLite [${stats.database.journal_mode || 'WAL'}]${walInfo}`;
      }

      // Storage
      if (stats.storage) {
        if (stats.storage.total_bytes > 0) {
          storageSizeEl.textContent = stats.storage.used_formatted || "0 B";
          storageSubEl.textContent = `${stats.storage.free_formatted} Free of ${stats.storage.total_formatted} (${stats.storage.usage_percent}% Used)`;
        } else {
          storageSizeEl.textContent = "Mounted";
          storageSubEl.textContent = stats.storage.library_path || "Library Mount";
        }
      }

      // Downloads
      if (stats.downloads) {
        dlCountEl.textContent = `${stats.downloads.total_count}`;
        dlSubEl.textContent = `${stats.downloads.completed_count} Done • ${stats.downloads.active_count} Active (${stats.downloads.total_downloaded_formatted})`;
      }

      // Users
      if (stats.users) {
        userCountEl.textContent = `${stats.users.total_count}`;
        userSubEl.textContent = `${stats.users.approved_count} Approved • ${stats.users.pending_count} Pending`;
      }
    }
  } catch (err) {
    console.error("Failed to fetch admin stats:", err);
  }
}

async function fetchServerSettings() {
  const prowlarrUrlEl = document.getElementById("prowlarr-url");
  const prowlarrKeyEl = document.getElementById("prowlarr-key");
  const torboxKeyEl = document.getElementById("torbox-key");
  const tmdbKeyEl = document.getElementById("tmdb-key");
  const libraryPathEl = document.getElementById("library-path");
  
  if (!prowlarrUrlEl) return;
  
  try {
    const headers = {};
    if (state.token) {
      headers["Authorization"] = `Bearer ${state.token}`;
    }
    const resp = await fetch("/api/settings", { headers });
    if (resp.ok) {
      const s = await resp.json();
      prowlarrUrlEl.value = s.prowlarr_url || "";
      prowlarrKeyEl.value = s.prowlarr_api_key || "";
      torboxKeyEl.value = s.torbox_api_key || "";
      tmdbKeyEl.value = s.tmdb_api_key || "";
      libraryPathEl.value = s.library_path || "";
    }
  } catch (err) {
    console.error("Failed to fetch server settings:", err);
  }
}

function setupAdminContentListeners() {
  const tabUsers = document.getElementById("tab-admin-users");
  const tabDownloads = document.getElementById("tab-admin-downloads");
  const tabSettings = document.getElementById("tab-admin-settings");
  
  const usersSec = document.getElementById("admin-users-section");
  const downloadsSec = document.getElementById("admin-downloads-section");
  const settingsSec = document.getElementById("admin-settings-section");
  
  if (tabUsers) {
    tabUsers.addEventListener("click", () => {
      tabUsers.className = "btn btn-primary";
      if (tabDownloads) tabDownloads.className = "btn";
      if (tabSettings) tabSettings.className = "btn";
      
      if (usersSec) usersSec.style.display = "block";
      if (downloadsSec) downloadsSec.style.display = "none";
      if (settingsSec) settingsSec.style.display = "none";
      
      state.adminActiveTab = "users";
      fetchAdminUsers();
      fetchAdminStats();
    });
  }
  
  if (tabDownloads) {
    tabDownloads.addEventListener("click", () => {
      tabDownloads.className = "btn btn-primary";
      if (tabUsers) tabUsers.className = "btn";
      if (tabSettings) tabSettings.className = "btn";
      
      if (usersSec) usersSec.style.display = "none";
      downloadsSec.style.display = "block";
      if (settingsSec) settingsSec.style.display = "none";
      
      state.adminActiveTab = "downloads";
      fetchAdminDownloads();
      fetchAdminStats();
    });
  }
  
  if (tabSettings) {
    tabSettings.addEventListener("click", () => {
      tabSettings.className = "btn btn-primary";
      if (tabUsers) tabUsers.className = "btn";
      if (tabDownloads) tabDownloads.className = "btn";
      
      if (usersSec) usersSec.style.display = "none";
      if (downloadsSec) downloadsSec.style.display = "none";
      if (settingsSec) settingsSec.style.display = "block";
      
      state.adminActiveTab = "settings";
      fetchServerSettings();
      fetchAdminStats();
    });
  }
  
  const applyFilterBtn = document.getElementById("btn-admin-filter-apply");
  if (applyFilterBtn) {
    applyFilterBtn.addEventListener("click", fetchAdminDownloads);
  }
  
  const resetFilterBtn = document.getElementById("btn-admin-filter-reset");
  if (resetFilterBtn) {
    resetFilterBtn.addEventListener("click", () => {
      document.getElementById("admin-search-dl").value = "";
      document.getElementById("admin-filter-status").value = "";
      document.getElementById("admin-sort-by").value = "created_at";
      document.getElementById("admin-sort-order").value = "desc";
      fetchAdminDownloads();
    });
  }

  const usersListEl = document.getElementById("admin-users-list");
  if (usersListEl) {
    usersListEl.addEventListener("change", async (e) => {
      if (e.target.tagName === "SELECT") {
        const userId = e.target.getAttribute("data-user-id");
        const groupName = e.target.value;
        await updateAdminUserRole(userId, groupName);
      }
    });

    usersListEl.addEventListener("click", async (e) => {
      if (e.target.classList.contains("btn-approve-user")) {
        const userId = e.target.getAttribute("data-user-id");
        await updateAdminUserRole(userId, "User");
      } else if (e.target.classList.contains("btn-delete-user")) {
        const userId = e.target.getAttribute("data-user-id");
        if (confirm("Are you sure you want to completely delete this user and their data?")) {
          await deleteAdminUser(userId);
        }
      }
    });
  }

  // Mobile users cards listeners
  const usersMobileCardsEl = document.getElementById("admin-users-cards-mobile");
  if (usersMobileCardsEl) {
    usersMobileCardsEl.addEventListener("change", async (e) => {
      if (e.target.tagName === "SELECT") {
        const userId = e.target.getAttribute("data-user-id");
        const groupName = e.target.value;
        await updateAdminUserRole(userId, groupName);
      }
    });

    usersMobileCardsEl.addEventListener("click", async (e) => {
      if (e.target.classList.contains("btn-approve-user")) {
        const userId = e.target.getAttribute("data-user-id");
        await updateAdminUserRole(userId, "User");
      } else if (e.target.classList.contains("btn-delete-user")) {
        const userId = e.target.getAttribute("data-user-id");
        if (confirm("Are you sure you want to completely delete this user and their data?")) {
          await deleteAdminUser(userId);
        }
      }
    });
  }

  const handleAdminDlAction = async (e) => {
    if (e.target.classList.contains("btn-admin-action")) {
      const torboxId = e.target.getAttribute("data-torbox-id");
      const action = e.target.getAttribute("data-action");
      if (action === "resume") {
        e.target.disabled = true;
        e.target.textContent = "RESUMING...";
        await resumeDownload(torboxId);
        fetchAdminDownloads();
        fetchAdminStats();
      } else {
        const confirmMsg = action === "delete"
          ? "Are you sure you want to delete this completed download and remove its files from the server?"
          : "Are you sure you want to cancel this transfer and remove any temporary files?";
        if (confirm(confirmMsg)) {
          e.target.disabled = true;
          e.target.textContent = action === "delete" ? "DELETING..." : "ABORTING...";
          await cancelDownload(torboxId);
          fetchAdminDownloads();
          fetchAdminStats();
        }
      }
    }
  };

  const downloadsListEl = document.getElementById("admin-downloads-list");
  if (downloadsListEl) {
    downloadsListEl.addEventListener("click", handleAdminDlAction);
  }

  const downloadsMobileCardsEl = document.getElementById("admin-downloads-cards-mobile");
  if (downloadsMobileCardsEl) {
    downloadsMobileCardsEl.addEventListener("click", handleAdminDlAction);
  }

  const settingsForm = document.getElementById("settings-form");
  if (settingsForm) {
    const prowlarrUrlEl = document.getElementById("prowlarr-url");
    const prowlarrKeyEl = document.getElementById("prowlarr-key");
    const torboxKeyEl = document.getElementById("torbox-key");
    const tmdbKeyEl = document.getElementById("tmdb-key");
    const libraryPathEl = document.getElementById("library-path");
    
    settingsForm.addEventListener("submit", async (e) => {
      e.preventDefault();
      const statusEl = document.getElementById("settings-status");
      if (statusEl) statusEl.style.display = "none";
      
      const settings = {
        prowlarr_url: prowlarrUrlEl.value,
        prowlarr_api_key: prowlarrKeyEl.value,
        torbox_api_key: torboxKeyEl.value,
        tmdb_api_key: tmdbKeyEl.value,
        library_path: libraryPathEl.value
      };
      
      try {
        const headers = {
          "Content-Type": "application/json"
        };
        if (state.token) {
          headers["Authorization"] = `Bearer ${state.token}`;
        }
        const resp = await fetch("/api/settings", {
          method: "POST",
          headers: headers,
          body: JSON.stringify(settings)
        });
        
        const resData = await resp.json();
        if (resp.ok) {
          if (statusEl) {
            statusEl.style.display = "block";
            statusEl.scrollIntoView({ behavior: "smooth" });
          }
          fetchAdminStats();
        } else {
          alert("Failed to update config: " + resData.error);
        }
      } catch (err) {
        console.error("Save config failure:", err);
        alert("System connection error saving config.");
      }
    });
  }

  fetchAdminStats();

  if (state.adminActiveTab === "users") {
    fetchAdminUsers();
  } else if (state.adminActiveTab === "downloads") {
    fetchAdminDownloads();
  } else if (state.adminActiveTab === "settings") {
    fetchServerSettings();
  }
}

async function fetchAdminUsers() {
  const container = document.getElementById("admin-users-list");
  const mobileContainer = document.getElementById("admin-users-cards-mobile");
  if (!container) return;
  
  try {
    const headers = {};
    if (state.token) {
      headers["Authorization"] = `Bearer ${state.token}`;
    }
    const resp = await fetch("/api/admin/users", { headers });
    if (resp.ok) {
      const users = await resp.json();
      renderAdminUsersList(users);
    } else {
      const err = await resp.json();
      const errHtml = `<tr><td colspan="5" class="empty-state" style="color: var(--danger); padding: 1.5rem;">Failed to load users: ${escapeHtml(err.error)}</td></tr>`;
      container.innerHTML = errHtml;
      if (mobileContainer) mobileContainer.innerHTML = `<div class="empty-state" style="color: var(--danger);">${escapeHtml(err.error)}</div>`;
    }
  } catch (e) {
    console.error(e);
    container.innerHTML = `<tr><td colspan="5" class="empty-state" style="color: var(--danger); padding: 1.5rem;">Network error loading users.</td></tr>`;
    if (mobileContainer) mobileContainer.innerHTML = `<div class="empty-state" style="color: var(--danger);">Network error loading users.</div>`;
  }
}

function renderAdminUsersList(users) {
  const container = document.getElementById("admin-users-list");
  const mobileContainer = document.getElementById("admin-users-cards-mobile");
  if (!container) return;
  
  if (users.length === 0) {
    const emptyHtml = `<tr><td colspan="5" class="empty-state" style="padding: 2rem;">No user accounts found.</td></tr>`;
    container.innerHTML = emptyHtml;
    if (mobileContainer) mobileContainer.innerHTML = `<div class="empty-state">No user accounts found.</div>`;
    return;
  }
  
  const isAdmin = state.user && state.user.group_name === "Admin";
  
  // Desktop table rows
  container.innerHTML = users.map(u => {
    const isSelf = state.user && Number(u.id) === Number(state.user.id);
    const dObj = new Date(u.created_at);
    const dateFormatted = !isNaN(dObj.getTime()) ? dObj.toLocaleDateString(undefined, { year: 'numeric', month: 'short', day: 'numeric' }) : "N/A";
    const timeFormatted = !isNaN(dObj.getTime()) ? dObj.toLocaleTimeString(undefined, { hour: '2-digit', minute: '2-digit' }) : "";
    const sizeText = u.total_downloaded_bytes ? formatBytes(u.total_downloaded_bytes) : "0 B";
    
    const lastDlObj = u.last_downloaded_at ? new Date(u.last_downloaded_at) : null;
    const lastDlFormatted = lastDlObj && !isNaN(lastDlObj.getTime())
      ? `Last active: ${lastDlObj.toLocaleDateString(undefined, { month: 'short', day: 'numeric', year: 'numeric' })}`
      : "No downloads yet";

    const isUnapproved = u.group_id === null || u.group_name === "None (Pending Approval)";
    
    let roleActionHtml = "";
    if (!isAdmin) {
      const labelClass = isUnapproved ? "color: var(--danger); font-weight: bold;" : "color: var(--text-primary);";
      roleActionHtml = `<span style="${labelClass}">${escapeHtml(u.group_name)}</span>`;
    } else {
      const selectedNone = isUnapproved ? "selected" : "";
      const selectedUser = u.group_name === "User" ? "selected" : "";
      const selectedMod = u.group_name === "Moderator" ? "selected" : "";
      const selectedAdmin = u.group_name === "Admin" ? "selected" : "";
      
      roleActionHtml = `
        <select class="form-input admin-role-select" data-user-id="${u.id}" style="padding: 0.25rem 0.5rem; font-size: 0.75rem; width: 140px; height: 30px; display: inline-block;">
          <option value="None" ${selectedNone}>Pending Approval</option>
          <option value="User" ${selectedUser}>User</option>
          <option value="Moderator" ${selectedMod}>Moderator</option>
          <option value="Admin" ${selectedAdmin}>Admin</option>
        </select>
      `;
    }
    
    let actionsHtml = "";
    if (isAdmin) {
      if (isUnapproved) {
        actionsHtml += `
          <button class="btn btn-primary btn-approve-user" data-user-id="${u.id}" style="padding: 0.25rem 0.5rem; font-size: 0.7rem; height: 28px; border-radius: 0;">APPROVE</button>
        `;
      }
      if (!isSelf) {
        actionsHtml += `
          <button class="btn btn-danger btn-delete-user" data-user-id="${u.id}" style="padding: 0.25rem 0.5rem; font-size: 0.7rem; height: 28px; margin-left: 4px; border-radius: 0;">DELETE</button>
        `;
      } else {
        actionsHtml += `<span style="font-size: 0.7rem; color: var(--text-muted); font-style: italic;">Self</span>`;
      }
    } else {
      actionsHtml = `<span style="font-size: 0.7rem; color: var(--text-muted); font-style: italic;">Read-Only</span>`;
    }
    
    return `
      <tr>
        <td style="vertical-align: middle;">
          <div style="display: flex; align-items: center; gap: 0.75rem;">
            <img src="${escapeHtml(u.profile_picture || FALLBACK_AVATAR)}" style="width: 32px; height: 32px; border-radius: 50%; border: 1px solid var(--border-color); flex-shrink: 0;">
            <div style="display: flex; flex-direction: column; min-width: 0;">
              <strong style="color: var(--text-primary); font-size: 0.85rem; white-space: nowrap; overflow: hidden; text-overflow: ellipsis;">${escapeHtml(u.full_name || u.username)}</strong>
              <span style="font-size: 0.72rem; color: var(--text-secondary); white-space: nowrap; overflow: hidden; text-overflow: ellipsis;">${escapeHtml(u.username)}</span>
            </div>
          </div>
        </td>
        <td style="color: var(--text-secondary); vertical-align: middle; white-space: nowrap;">
          <div class="admin-datetime">
            <span class="admin-datetime-date">${dateFormatted}</span>
            <span class="admin-datetime-time">${timeFormatted}</span>
          </div>
        </td>
        <td style="vertical-align: middle; white-space: nowrap;">${roleActionHtml}</td>
        <td style="text-align: right; color: var(--text-primary); vertical-align: middle; white-space: nowrap;">
          <strong>${u.total_downloads}</strong> releases (${sizeText})<br>
          <span style="font-size: 0.7rem; color: var(--text-secondary);">${lastDlFormatted}</span>
        </td>
        <td style="text-align: right; vertical-align: middle; white-space: nowrap;">
          ${actionsHtml}
        </td>
      </tr>
    `;
  }).join("");

  // Mobile users cards
  if (mobileContainer) {
    mobileContainer.innerHTML = users.map(u => {
      const isSelf = state.user && Number(u.id) === Number(state.user.id);
      const dObj = new Date(u.created_at);
      const dateFormatted = !isNaN(dObj.getTime()) ? dObj.toLocaleDateString(undefined, { year: 'numeric', month: 'short', day: 'numeric' }) : "N/A";
      const sizeText = u.total_downloaded_bytes ? formatBytes(u.total_downloaded_bytes) : "0 B";
      const lastDlObj = u.last_downloaded_at ? new Date(u.last_downloaded_at) : null;
      const lastDlFormatted = lastDlObj && !isNaN(lastDlObj.getTime())
        ? `Last: ${lastDlObj.toLocaleDateString(undefined, { month: 'short', day: 'numeric', year: 'numeric' })}`
        : "No downloads";
      const isUnapproved = u.group_id === null || u.group_name === "None (Pending Approval)";
      
      let roleHtml = "";
      if (isAdmin) {
        const selectedNone = isUnapproved ? "selected" : "";
        const selectedUser = u.group_name === "User" ? "selected" : "";
        const selectedMod = u.group_name === "Moderator" ? "selected" : "";
        const selectedAdmin = u.group_name === "Admin" ? "selected" : "";
        roleHtml = `
          <select class="form-input admin-role-select" data-user-id="${u.id}" style="width: 100%; height: 32px; font-size: 0.8rem;">
            <option value="None" ${selectedNone}>Pending Approval</option>
            <option value="User" ${selectedUser}>User</option>
            <option value="Moderator" ${selectedMod}>Moderator</option>
            <option value="Admin" ${selectedAdmin}>Admin</option>
          </select>
        `;
      } else {
        roleHtml = `<strong>${escapeHtml(u.group_name)}</strong>`;
      }

      let actionsHtml = "";
      if (isAdmin) {
        if (isUnapproved) {
          actionsHtml += `<button class="btn btn-primary btn-approve-user" data-user-id="${u.id}" style="flex: 1; padding: 0.4rem; font-size: 0.75rem;">APPROVE</button>`;
        }
        if (!isSelf) {
          actionsHtml += `<button class="btn btn-danger btn-delete-user" data-user-id="${u.id}" style="flex: 1; padding: 0.4rem; font-size: 0.75rem;">DELETE</button>`;
        }
      }

      return `
        <div class="admin-mobile-card">
          <div class="admin-mobile-card-header">
            <div style="display: flex; align-items: center; gap: 0.6rem;">
              <img src="${escapeHtml(u.profile_picture || FALLBACK_AVATAR)}" style="width: 32px; height: 32px; border-radius: 50%; border: 1px solid var(--border-color);">
              <div>
                <strong style="color: var(--text-primary); font-size: 0.9rem;">${escapeHtml(u.full_name || u.username)}</strong><br>
                <span style="font-size: 0.75rem; color: var(--text-secondary);">${escapeHtml(u.username)}</span>
              </div>
            </div>
          </div>
          <div class="admin-mobile-card-meta">
            <div>
              <span style="font-size: 0.7rem; color: var(--text-muted); display: block;">JOINED</span>
              <span style="color: var(--text-primary); font-size: 0.8rem;">${dateFormatted}</span>
            </div>
            <div>
              <span style="font-size: 0.7rem; color: var(--text-muted); display: block;">ACTIVITY</span>
              <span style="color: var(--text-primary); font-size: 0.8rem;">${u.total_downloads} dls (${sizeText})</span>
              <span style="color: var(--text-secondary); font-size: 0.7rem; display: block;">${lastDlFormatted}</span>
            </div>
          </div>
          <div style="display: flex; flex-direction: column; gap: 0.5rem;">
            <div>
              <label style="font-size: 0.7rem; color: var(--text-muted); margin-bottom: 0.2rem; display: block;">ROLE</label>
              ${roleHtml}
            </div>
            ${actionsHtml ? `<div class="admin-mobile-card-actions" style="margin-top: 0.25rem;">${actionsHtml}</div>` : ''}
          </div>
        </div>
      `;
    }).join("");
  }
}

async function fetchAdminDownloads() {
  const container = document.getElementById("admin-downloads-list");
  const mobileContainer = document.getElementById("admin-downloads-cards-mobile");
  if (!container) return;
  
  const search = document.getElementById("admin-search-dl").value;
  const status = document.getElementById("admin-filter-status").value;
  const sort_by = document.getElementById("admin-sort-by").value;
  const sort_order = document.getElementById("admin-sort-order").value;
  
  try {
    const headers = {};
    if (state.token) {
      headers["Authorization"] = `Bearer ${state.token}`;
    }
    const queryParams = new URLSearchParams({
      search,
      status,
      sort_by,
      sort_order
    });
    const resp = await fetch(`/api/admin/downloads?${queryParams.toString()}`, { headers });
    if (resp.ok) {
      const downloads = await resp.json();
      renderAdminDownloadsList(downloads);
    } else {
      const err = await resp.json();
      const errHtml = `<tr><td colspan="6" class="empty-state" style="color: var(--danger); padding: 1.5rem;">Failed to load downloads: ${escapeHtml(err.error)}</td></tr>`;
      container.innerHTML = errHtml;
      if (mobileContainer) mobileContainer.innerHTML = `<div class="empty-state" style="color: var(--danger);">${escapeHtml(err.error)}</div>`;
    }
  } catch (e) {
    console.error(e);
    container.innerHTML = `<tr><td colspan="6" class="empty-state" style="color: var(--danger); padding: 1.5rem;">Network error loading downloads.</td></tr>`;
    if (mobileContainer) mobileContainer.innerHTML = `<div class="empty-state" style="color: var(--danger);">Network error loading downloads.</div>`;
  }
}

function renderAdminDownloadsList(downloads) {
  const container = document.getElementById("admin-downloads-list");
  const mobileContainer = document.getElementById("admin-downloads-cards-mobile");
  if (!container) return;
  
  if (downloads.length === 0) {
    const emptyHtml = `<tr><td colspan="6" class="empty-state" style="padding: 2rem;">No system downloads found.</td></tr>`;
    container.innerHTML = emptyHtml;
    if (mobileContainer) mobileContainer.innerHTML = `<div class="empty-state">No system downloads found.</div>`;
    return;
  }
  
  const isAdmin = state.user && state.user.group_name === "Admin";
  
  // Desktop table rows
  container.innerHTML = downloads.map(dl => {
    const sizeText = dl.size ? formatBytes(dl.size) : "0 B";
    const progressText = dl.progress !== undefined ? `${dl.progress}%` : "0%";
    const speedText = dl.speed && dl.speed > 0 ? ` • ${formatSpeed(dl.speed)}` : "";
    
    // Exact Date and Time Added
    const dObj = new Date(dl.created_at);
    const dateFormatted = !isNaN(dObj.getTime()) ? dObj.toLocaleDateString(undefined, { year: 'numeric', month: 'short', day: 'numeric' }) : "N/A";
    const timeFormatted = !isNaN(dObj.getTime()) ? dObj.toLocaleTimeString(undefined, { hour: '2-digit', minute: '2-digit', second: '2-digit' }) : "";
    
    const isOwner = state.user && Number(dl.user_id) === Number(state.user.id);
    const canControl = isAdmin || isOwner;
    
    const statusLower = (dl.status || "").toLowerCase();
    const isCompleted = statusLower.includes("completed") || statusLower.includes("downloaded");
    const isFailed = statusLower.includes("failed") || statusLower.includes("error") || statusLower.includes("stalled") || statusLower.includes("paused") || statusLower.includes("interrupted");
    const isDownloading = statusLower.includes("downloading") || statusLower.includes("moving");
    
    let btnHtml = "";
    if (canControl) {
      if (isCompleted) {
        btnHtml = `<button class="btn btn-danger btn-admin-action" data-action="delete" data-torbox-id="${dl.torbox_id}" style="padding: 0.25rem 0.5rem; font-size: 0.7rem; height: 28px; border-radius: 0;">DELETE</button>`;
      } else if (isFailed) {
        const resumeBtn = `<button class="btn btn-secondary btn-admin-action" data-action="resume" data-torbox-id="${dl.torbox_id}" style="padding: 0.25rem 0.5rem; font-size: 0.7rem; height: 28px; border-radius: 0; margin-right: 4px;">RESUME</button>`;
        const clearBtn = `<button class="btn btn-danger btn-admin-action" data-action="delete" data-torbox-id="${dl.torbox_id}" style="padding: 0.25rem 0.5rem; font-size: 0.7rem; height: 28px; border-radius: 0;">CLEAR</button>`;
        btnHtml = `${resumeBtn}${clearBtn}`;
      } else {
        btnHtml = `<button class="btn btn-danger btn-admin-action" data-action="cancel" data-torbox-id="${dl.torbox_id}" style="padding: 0.25rem 0.5rem; font-size: 0.7rem; height: 28px; border-radius: 0;">CANCEL</button>`;
      }
    } else {
      btnHtml = `<span style="font-size: 0.7rem; color: var(--text-muted); font-style: italic;">No Access</span>`;
    }
    
    let badgeClass = "badge-queued";
    if (isCompleted) badgeClass = "badge-completed";
    else if (isDownloading) badgeClass = "badge-downloading";
    else if (isFailed) badgeClass = "badge-failed";

    const isTv = dl.category === "tv" || (dl.title && (dl.title.includes("Season") || dl.title.includes("S0")));
    const catBadgeClass = isTv ? "badge-tv" : "badge-movie";
    const catLabel = isTv ? "TV" : "MOVIE";
    
    return `
      <tr id="admin-dl-row-${dl.torbox_id}">
        <td style="max-width: 280px; word-break: break-word;">
          <div style="display: flex; align-items: center; gap: 0.4rem; margin-bottom: 0.2rem;">
            <span class="admin-badge ${catBadgeClass}">${catLabel}</span>
            <strong style="color: var(--text-primary); font-size: 0.85rem;">${escapeHtml(dl.title || dl.filename || "Unknown Release")}</strong>
          </div>
          <span style="font-size: 0.7rem; color: var(--text-secondary); display: block; overflow: hidden; text-overflow: ellipsis; white-space: nowrap;">${escapeHtml(dl.filename || "")}</span>
        </td>
        <td style="vertical-align: middle;">
          <div class="admin-datetime">
            <span class="admin-datetime-date">${dateFormatted}</span>
            <span class="admin-datetime-time">${timeFormatted}</span>
          </div>
        </td>
        <td style="color: var(--text-secondary); vertical-align: middle;">
          <strong style="color: var(--text-primary); font-size: 0.8rem;">${escapeHtml(dl.full_name || dl.username)}</strong><br>
          <span style="font-size: 0.7rem; color: var(--text-secondary);">${escapeHtml(dl.username)}</span>
        </td>
        <td id="admin-dl-size-${dl.torbox_id}" style="color: var(--text-primary); font-weight: 500; vertical-align: middle;">${sizeText}</td>
        <td style="vertical-align: middle;">
          <span id="admin-dl-status-${dl.torbox_id}" class="admin-badge ${badgeClass}">
            ${escapeHtml(dl.status.toUpperCase())} (${escapeHtml(progressText)}${speedText})
          </span>
        </td>
        <td id="admin-dl-btn-${dl.torbox_id}" style="text-align: right; vertical-align: middle;">
          ${btnHtml}
        </td>
      </tr>
    `;
  }).join("");

  // Mobile downloads card list
  if (mobileContainer) {
    mobileContainer.innerHTML = downloads.map(dl => {
      const sizeText = dl.size ? formatBytes(dl.size) : "0 B";
      const progressText = dl.progress !== undefined ? `${dl.progress}%` : "0%";
      const speedText = dl.speed && dl.speed > 0 ? ` • ${formatSpeed(dl.speed)}` : "";
      
      const dObj = new Date(dl.created_at);
      const dateFormatted = !isNaN(dObj.getTime()) ? dObj.toLocaleDateString(undefined, { year: 'numeric', month: 'short', day: 'numeric' }) : "N/A";
      const timeFormatted = !isNaN(dObj.getTime()) ? dObj.toLocaleTimeString(undefined, { hour: '2-digit', minute: '2-digit', second: '2-digit' }) : "";
      
      const isOwner = state.user && Number(dl.user_id) === Number(state.user.id);
      const canControl = isAdmin || isOwner;
      
      const statusLower = (dl.status || "").toLowerCase();
      const isCompleted = statusLower.includes("completed") || statusLower.includes("downloaded");
      const isFailed = statusLower.includes("failed") || statusLower.includes("error") || statusLower.includes("stalled") || statusLower.includes("paused") || statusLower.includes("interrupted");
      const isDownloading = statusLower.includes("downloading") || statusLower.includes("moving");
      
      let btnHtml = "";
      if (canControl) {
        if (isCompleted) {
          btnHtml = `<button class="btn btn-danger btn-admin-action" data-action="delete" data-torbox-id="${dl.torbox_id}" style="padding: 0.4rem 0.75rem; font-size: 0.75rem;">DELETE</button>`;
        } else if (isFailed) {
          btnHtml = `
            <button class="btn btn-secondary btn-admin-action" data-action="resume" data-torbox-id="${dl.torbox_id}" style="padding: 0.4rem 0.75rem; font-size: 0.75rem;">RESUME</button>
            <button class="btn btn-danger btn-admin-action" data-action="delete" data-torbox-id="${dl.torbox_id}" style="padding: 0.4rem 0.75rem; font-size: 0.75rem;">CLEAR</button>
          `;
        } else {
          btnHtml = `<button class="btn btn-danger btn-admin-action" data-action="cancel" data-torbox-id="${dl.torbox_id}" style="padding: 0.4rem 0.75rem; font-size: 0.75rem;">CANCEL</button>`;
        }
      }

      let badgeClass = "badge-queued";
      if (isCompleted) badgeClass = "badge-completed";
      else if (isDownloading) badgeClass = "badge-downloading";
      else if (isFailed) badgeClass = "badge-failed";

      const isTv = dl.category === "tv" || (dl.title && (dl.title.includes("Season") || dl.title.includes("S0")));
      const catBadgeClass = isTv ? "badge-tv" : "badge-movie";
      const catLabel = isTv ? "TV" : "MOVIE";

      return `
        <div class="admin-mobile-card">
          <div class="admin-mobile-card-header">
            <div>
              <div style="display: flex; align-items: center; gap: 0.4rem; margin-bottom: 0.25rem;">
                <span class="admin-badge ${catBadgeClass}">${catLabel}</span>
                <span class="admin-badge ${badgeClass}">${escapeHtml(dl.status.toUpperCase())} (${escapeHtml(progressText)})</span>
              </div>
              <strong class="admin-mobile-card-title">${escapeHtml(dl.title || dl.filename || "Unknown Title")}</strong>
            </div>
          </div>
          <div class="admin-mobile-card-meta">
            <div>
              <span style="font-size: 0.7rem; color: var(--text-muted); display: block;">ADDED ON</span>
              <span style="color: var(--text-primary); font-size: 0.8rem; font-family: var(--font-mono);">${dateFormatted} ${timeFormatted}</span>
            </div>
            <div>
              <span style="font-size: 0.7rem; color: var(--text-muted); display: block;">SIZE & SPEED</span>
              <span style="color: var(--text-primary); font-size: 0.8rem; font-family: var(--font-mono);">${sizeText}${speedText}</span>
            </div>
            <div>
              <span style="font-size: 0.7rem; color: var(--text-muted); display: block;">REQUESTED BY</span>
              <span style="color: var(--text-secondary); font-size: 0.8rem;">${escapeHtml(dl.full_name || dl.username)}</span>
            </div>
          </div>
          ${btnHtml ? `<div class="admin-mobile-card-actions">${btnHtml}</div>` : ''}
        </div>
      `;
    }).join("");
  }
}

async function updateAdminUserRole(userId, groupName) {
  try {
    const headers = {
      "Content-Type": "application/json"
    };
    if (state.token) {
      headers["Authorization"] = `Bearer ${state.token}`;
    }
    const resp = await fetch("/api/admin/users/update_role", {
      method: "POST",
      headers,
      body: JSON.stringify({ user_id: userId, group_name: groupName })
    });
    if (resp.ok) {
      fetchAdminUsers();
      fetchAdminStats();
    } else {
      const err = await resp.json();
      alert(`Failed to update role: ${err.error}`);
      fetchAdminUsers();
    }
  } catch (e) {
    console.error(e);
    alert("Network error updating user role.");
  }
}

async function deleteAdminUser(userId) {
  try {
    const headers = {
      "Content-Type": "application/json"
    };
    if (state.token) {
      headers["Authorization"] = `Bearer ${state.token}`;
    }
    const resp = await fetch("/api/admin/users/delete", {
      method: "POST",
      headers,
      body: JSON.stringify({ user_id: userId })
    });
    if (resp.ok) {
      fetchAdminUsers();
      fetchAdminStats();
    } else {
      const err = await resp.json();
      alert(`Failed to delete user: ${err.error}`);
    }
  } catch (e) {
    console.error(e);
    alert("Network error deleting user.");
  }
}

// LOGIN VIEW
function renderLogin() {
  return `
    <div class="auth-wrapper animate-slide">
      <div class="auth-card" style="text-align: center;">
        <h1>RICO.CX</h1>
        <p style="color: var(--text-secondary); margin-bottom: 2rem;">Torrent Search & Download Manager</p>
        
        <div id="login-error" class="alert-box alert-error" style="display: none;"></div>
        
        <div style="margin-top: 1rem;">
          <a href="/api/auth/google/login" class="google-auth-btn" style="display: flex; align-items: center; justify-content: center; gap: 0.75rem; text-decoration: none; width: 100%;">
            <svg width="18" height="18" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg" style="background: white; border-radius: 2px; padding: 1px;">
              <path d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92c-.26 1.37-1.04 2.53-2.21 3.31v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.09z" fill="#4285F4"/>
              <path d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z" fill="#34A853"/>
              <path d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.06H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.94l2.85-2.22.81-.63z" fill="#FBBC05"/>
              <path d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.06l3.66 2.84c.87-2.6 3.3-4.52 6.16-4.52z" fill="#EA4335"/>
            </svg>
            <span>Sign in with Google</span>
          </a>
        </div>
      </div>
    </div>
  `;
}

function handleDownloadAddedSocket(data) {
  const isAdminOrMod = state.user && (state.user.group_name === "Admin" || state.user.group_name === "Moderator");
  const isOwner = state.user && (data.user_id === undefined || data.user_id === null || Number(data.user_id) === Number(state.user.id));
  
  if (!isAdminOrMod && !isOwner) {
    return;
  }
  
  const exists = state.downloads.some(d => String(d.torbox_id) === String(data.torbox_id));
  if (!exists) {
    state.downloads.unshift(data);
    renderActiveDownloads();
    updateSidebarBadge();
    updateSearchResultButtons();
    if (state.currentView === "popular") {
      renderPopularGrid();
    }
  }
  
  if (state.currentView === "admin") {
    fetchAdminStats();
    if (state.adminActiveTab === "downloads") {
      fetchAdminDownloads();
    } else if (state.adminActiveTab === "users") {
      fetchAdminUsers();
    }
  }
}

function handleDownloadDeletedSocket(data) {
  const torboxId = data.torbox_id;
  
  state.downloads = state.downloads.filter(d => String(d.torbox_id) !== String(torboxId));
  
  const itemEl = document.getElementById(`dl-item-${torboxId}`);
  if (itemEl) {
    itemEl.remove();
  }
  
  const downloadListEl = document.getElementById("sidebar-downloads-list");
  if (downloadListEl && !downloadListEl.querySelector(".dl-item")) {
    downloadListEl.innerHTML = '<div class="empty-state">NO ACTIVE TRANSFERS</div>';
  }
  
  const adminRowEl = document.getElementById(`admin-dl-row-${torboxId}`);
  if (adminRowEl) {
    adminRowEl.remove();
    const adminListEl = document.getElementById("admin-downloads-list");
    if (adminListEl && !adminListEl.querySelector("tr")) {
      adminListEl.innerHTML = `<tr><td colspan="6" class="empty-state" style="padding: 2rem;">No system downloads found.</td></tr>`;
    }
  }
  
  updateSidebarBadge();
  updateSearchResultButtons();
  if (state.currentView === "popular") {
    renderPopularGrid();
  }

  if (state.currentView === "admin") {
    fetchAdminStats();
    if (state.adminActiveTab === "users") {
      fetchAdminUsers();
    }
  }
}

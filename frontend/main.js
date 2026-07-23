import { io } from "/socket.io.esm.min.js";

const FALLBACK_AVATAR = "data:image/svg+xml;utf8,<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24' fill='%2364748b'><circle cx='12' cy='12' r='12' fill='%231e293b'/><path d='M12 12c2.21 0 4-1.79 4-4s-1.79-4-4-4-4 1.79-4 4 1.79 4 4 4zm0 2c-2.67 0-8 1.34-8 4v2h16v-2c0-2.66-5.33-4-8-4z' fill='%2394a3b8'/></svg>";

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
  
  if (path === "/settings") {
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
  
  const mainContentEl = document.getElementById("main-content");
  
  // Reset and trigger page fade transition
  mainContentEl.classList.remove("animate-fade");
  void mainContentEl.offsetWidth; // Force reflow
  mainContentEl.classList.add("animate-fade");
  
  if (view === "dashboard") {
    mainContentEl.innerHTML = renderDashboardContent();
    setupDashboardContentListeners();
    renderSearchResults(); // Draw any existing search results
    fetchDownloads();
    if (pushState && window.location.pathname !== "/") {
      history.pushState({ view }, "", "/");
    }
  } else if (view === "admin") {
    const isAdminOrMod = state.user && (state.user.group_name === "Admin" || state.user.group_name === "Moderator");
    if (!isAdminOrMod) {
      navigate("dashboard", pushState);
      return;
    }
    if (!state.adminActiveTab) {
      state.adminActiveTab = (state.user.group_name === "Admin") ? "users" : "downloads";
    }
    mainContentEl.innerHTML = renderAdminContent();
    setupAdminContentListeners();
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
    }
  } catch (err) {
    console.error("Failed to fetch downloads:", err);
  }
}

async function searchTrackers(query, category) {
  const container = document.getElementById("results-list");
  const loaderEl = document.getElementById("search-loading");
  
  if (loaderEl) loaderEl.style.display = "flex";
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
    if (loaderEl) loaderEl.style.display = "none";
  }
}

async function triggerDownload(magnet, title, filename, category, year, season, episode, size, btn) {
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
      body: JSON.stringify({ magnet, title, filename, category, year, season, episode, size })
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
      btn.innerHTML = "DOWNLOAD";
      alert(`Download start failed: ${data.error}`);
    }
  } catch (err) {
    console.error("Trigger download failure:", err);
    btn.disabled = false;
    btn.innerHTML = "DOWNLOAD";
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
    <form id="search-form" class="search-block" onsubmit="return false;">
      <div class="search-row">
        <div class="search-input-wrapper">
          <input type="text" id="search-input" class="form-input" required placeholder="Search movies, TV shows, or paste a magnet link/torrent hash...">
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

// Settings view removed (merged into admin panel)

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
  if (sortBy === "seeds-desc") {
    filtered.sort((a, b) => b.downloads[0].seeders - a.downloads[0].seeders);
  } else if (sortBy === "size-desc") {
    filtered.sort((a, b) => b.downloads[0].size - a.downloads[0].size);
  } else if (sortBy === "size-asc") {
    filtered.sort((a, b) => a.downloads[0].size - b.downloads[0].size);
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

// Real-time button sync for active search results
function updateSearchResultButtons() {
  const cards = document.querySelectorAll(".media-card");
  if (cards.length === 0) return;
  
  const filteredData = getFilteredResults();
  
  cards.forEach((cardEl, index) => {
    const selectEl = cardEl.querySelector(`select`);
    const downloadBtn = cardEl.querySelector(`button[id^="btn-dl-"]`);
    if (!selectEl || !downloadBtn) return;
    
    const item = filteredData[index];
    if (!item) return;
    
    const downloads = item.downloads;
    const dlIdx = parseInt(selectEl.value);
    const dlOption = downloads[dlIdx];
    if (!dlOption) return;
    
    const activeDl = state.downloads.find(d => d.magnet === dlOption.download_url);
    
    if (dlOption.downloaded) {
      downloadBtn.disabled = true;
      downloadBtn.innerHTML = "DOWNLOADED";
      downloadBtn.className = "btn";
      downloadBtn.removeAttribute("data-active-download");
      downloadBtn.removeAttribute("data-torrent-id");
    } else if (activeDl) {
      const progress = activeDl.progress || 0;
      const status = activeDl.status;
      
      downloadBtn.disabled = false;
      downloadBtn.setAttribute("data-active-download", "true");
      downloadBtn.setAttribute("data-torrent-id", activeDl.torbox_id);
      
      const statusUpper = status.toUpperCase();
      const isHovered = downloadBtn.matches(':hover');
      downloadBtn.setAttribute("data-normal-text", `${statusUpper} (${progress}%)`);
      if (!isHovered) {
        downloadBtn.innerHTML = `${statusUpper} (${progress}%)`;
        downloadBtn.className = "btn btn-primary btn-status-active";
      }
    } else {
      downloadBtn.disabled = false;
      downloadBtn.innerHTML = "DOWNLOAD";
      downloadBtn.className = "btn btn-primary";
      downloadBtn.removeAttribute("data-active-download");
      downloadBtn.removeAttribute("data-torrent-id");
    }
  });
}

// Renders the (filtered) list of search results
function renderSearchResults() {
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
    cardEl.className = "media-card animate-slide";
    
    const downloads = item.downloads;
    const defaultOption = downloads[0];

    // Build select dropdown option listing
    let optionsHtml = "";
    downloads.forEach((dl, dlIdx) => {
      const displaySize = formatBytes(dl.size);
      const marker = dl.downloaded ? " [ALREADY DOWNLOADED]" : "";
      optionsHtml += `
        <option value="${dlIdx}">
          [${displaySize} | Seeds: ${dl.seeders}]${marker} - ${dl.title}
        </option>
      `;
    });

    const isTV = item.is_tv;
    const yearText = item.year ? `(${item.year})` : "";
    const categoryBadge = isTV ? `<span class="media-type-badge">TV</span>` : `<span class="media-type-badge">MOVIE</span>`;
    
    // Poster representation
    const posterHtml = item.poster_url 
      ? `<img src="${item.poster_url}" alt="Poster" style="width: 100%; height: 100%; object-fit: cover;">`
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
            <span>${item.clean_title} ${yearText}</span>
            ${categoryBadge}
          </div>
          <div class="media-meta-line">
            <span>Size Range: <strong>${sizeRangeText}</strong></span>
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
      </div>
    `;

    container.appendChild(cardEl);
    
    const selectEl = cardEl.querySelector(`#select-dl-${index}`);
    const tagsContainer = cardEl.querySelector(`#card-tags-${index}`);
    const downloadBtn = cardEl.querySelector(`#btn-dl-${index}`);

    const updateBadges = (dlOption) => {
      tagsContainer.innerHTML = "";
      
      if (dlOption.resolution !== "Unknown") {
        tagsContainer.innerHTML += `<span class="tag-badge">${dlOption.resolution}</span>`;
      }
      dlOption.features.forEach(feat => {
        tagsContainer.innerHTML += `<span class="tag-badge">${feat}</span>`;
      });
      if (dlOption.source !== "Unknown") {
        tagsContainer.innerHTML += `<span class="tag-badge">${dlOption.source}</span>`;
      }
      if (dlOption.codec !== "Unknown") {
        tagsContainer.innerHTML += `<span class="tag-badge">${dlOption.codec}</span>`;
      }
      dlOption.audio.forEach(aud => {
        tagsContainer.innerHTML += `<span class="tag-badge">${aud}</span>`;
      });
      
      tagsContainer.innerHTML += `<span class="tag-badge" style="border-style: solid; opacity: 0.6;">${dlOption.indexer}</span>`;
      
      // Update download button state
      const activeDl = state.downloads.find(d => d.magnet === dlOption.download_url);
      const isCompleted = dlOption.downloaded || (activeDl && activeDl.status === "completed");
      
      const isAdmin = state.user && state.user.group_name === "Admin";
      const downloadOwnerId = dlOption.user_id || (activeDl ? activeDl.user_id : null);
      const isOwner = state.user && (
        (downloadOwnerId !== null && Number(downloadOwnerId) === Number(state.user.id)) ||
        (activeDl && (activeDl.user_id === undefined || activeDl.user_id === null || Number(activeDl.user_id) === Number(state.user.id)))
      );
      
      const torboxId = dlOption.torbox_id || (activeDl ? activeDl.torbox_id : null);
      const canDelete = (isAdmin || isOwner) && torboxId;

      if (isCompleted) {
        if (canDelete) {
          downloadBtn.disabled = false;
          downloadBtn.innerHTML = "DELETE";
          downloadBtn.className = "btn btn-danger";
          downloadBtn.setAttribute("data-active-download", "true");
          downloadBtn.setAttribute("data-torrent-id", torboxId);
          downloadBtn.removeAttribute("data-normal-text");
        } else {
          downloadBtn.disabled = true;
          downloadBtn.innerHTML = "DOWNLOADED";
          downloadBtn.className = "btn";
          downloadBtn.removeAttribute("data-active-download");
          downloadBtn.removeAttribute("data-torrent-id");
          downloadBtn.removeAttribute("data-normal-text");
        }
      } else if (activeDl) {
        const progress = activeDl.progress || 0;
        const status = activeDl.status;
        
        downloadBtn.disabled = false;
        downloadBtn.setAttribute("data-active-download", "true");
        downloadBtn.setAttribute("data-torrent-id", activeDl.torbox_id);
        
        const statusUpper = status.toUpperCase();
        downloadBtn.innerHTML = `${statusUpper} (${progress}%)`;
        downloadBtn.className = "btn btn-primary btn-status-active";
        downloadBtn.setAttribute("data-normal-text", `${statusUpper} (${progress}%)`);
      } else {
        downloadBtn.disabled = false;
        downloadBtn.innerHTML = "DOWNLOAD";
        downloadBtn.className = "btn btn-primary";
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
        const isDelete = downloadBtn.textContent === "DELETE";
        const confirmMsg = isDelete
          ? "Are you sure you want to delete this downloaded item and all its files from the server?"
          : "Are you sure you want to cancel this transfer and delete any files from the server?";
        if (confirm(confirmMsg)) {
          downloadBtn.disabled = true;
          downloadBtn.textContent = isDelete ? "DELETING..." : "ABORTING...";
          cancelDownload(torboxId);
        }
        return;
      }
      
      const dlIdx = parseInt(selectEl.value);
      const selectedDl = downloads[dlIdx];
      
      triggerDownload(
        selectedDl.download_url,
        item.clean_title,
        selectedDl.title,
        isTV ? "tv" : "movie",
        item.year,
        selectedDl.season,
        selectedDl.episode,
        selectedDl.size,
        downloadBtn
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
  
  // Show Cancel button only for active downloads. Show DELETE button for completed downloads if owned or Admin.
  const isInactive = statusClass.includes("completed") || statusClass.includes("failed");
  
  const isAdmin = state.user && state.user.group_name === "Admin";
  const isOwner = state.user && (
    dl.user_id === undefined || dl.user_id === null || Number(dl.user_id) === Number(state.user.id)
  );
  const canDelete = isAdmin || isOwner;
  
  let cancelBtnHtml = "";
  if (!isInactive) {
    cancelBtnHtml = `<button class="btn btn-danger btn-cancel-dl" data-torbox-id="${dl.torbox_id}" style="padding: 0.15rem 0.4rem; font-size: 0.6rem; font-family: var(--font-mono); height: 18px; line-height: 1; border-radius: 0; margin-top: 4px;">CANCEL</button>`;
  } else if (statusClass.includes("completed") && canDelete) {
    cancelBtnHtml = `<button class="btn btn-danger btn-cancel-dl" data-torbox-id="${dl.torbox_id}" style="padding: 0.15rem 0.4rem; font-size: 0.6rem; font-family: var(--font-mono); height: 18px; line-height: 1; border-radius: 0; margin-top: 4px;">DELETE</button>`;
  }
  
  const displayTitle = dl.title || dl.filename || "Unknown Torrent";
  const displaySubtitle = (dl.filename && dl.filename !== dl.title) ? dl.filename : "";
  
  return `
      <div class="dl-item-header">
        <div style="min-width: 0; flex-grow: 1;">
          <div class="dl-item-title" title="${displayTitle}">${displayTitle}</div>
          ${displaySubtitle ? `<div class="dl-item-subtitle" title="${displaySubtitle}">${displaySubtitle}</div>` : ""}
        </div>
        <div style="display: flex; flex-direction: column; align-items: flex-end; gap: 0.25rem; flex-shrink: 0;">
          <span class="dl-item-status dl-status-${statusClass}">${dl.status}</span>
          ${cancelBtnHtml}
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
    const statusClass = getStatusClass(status);
    const progressText = progress !== undefined ? `${progress}%` : "0%";
    adminStatusEl.className = `dl-item-status dl-status-${statusClass}`;
    adminStatusEl.innerHTML = `${status.toUpperCase()} (${progressText})`;
    
    const adminSizeEl = document.getElementById(`admin-dl-size-${torrentId}`);
    if (adminSizeEl && size) {
      adminSizeEl.innerHTML = formatBytes(size);
    }
    
    const adminBtnEl = document.getElementById(`admin-dl-btn-${torrentId}`);
    if (adminBtnEl) {
      const isCompleted = status.toLowerCase().includes("completed");
      const isFailed = status.toLowerCase().includes("failed");
      let btnHtml = "";
      
      const isAdmin = state.user && state.user.group_name === "Admin";
      const canControl = isAdmin || isOwner;
      if (canControl) {
        if (isCompleted) {
          btnHtml = `<button class="btn btn-danger btn-admin-action" data-action="delete" data-torbox-id="${torrentId}" style="padding: 0.15rem 0.4rem; font-size: 0.65rem; height: 24px; line-height: 1; border-radius: 0;">DELETE</button>`;
        } else if (!isFailed) {
          btnHtml = `<button class="btn btn-danger btn-admin-action" data-action="cancel" data-torbox-id="${torrentId}" style="padding: 0.15rem 0.4rem; font-size: 0.65rem; height: 24px; line-height: 1; border-radius: 0;">CANCEL</button>`;
        } else {
          btnHtml = `<button class="btn btn-danger btn-admin-action" data-action="delete" data-torbox-id="${torrentId}" style="padding: 0.15rem 0.4rem; font-size: 0.65rem; height: 24px; line-height: 1; border-radius: 0;">CLEAR</button>`;
        }
      } else {
        btnHtml = `<span style="font-size: 0.65rem; color: var(--text-muted); font-style: italic;">No Access</span>`;
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
  
  // Delegate click events for the download cancel/delete buttons
  document.getElementById("downloads-sidebar").addEventListener("click", async (e) => {
    if (e.target.classList.contains("btn-cancel-dl")) {
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
    document.getElementById("filter-sort-by").value = saved.sortBy || "seeds-desc";
    
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
      document.getElementById("filter-sort-by").value = "seeds-desc";
      state.searchResults = [];
      saveRecentSearch();
      renderSearchResults();
      updateClearButtonVisibility();
    });
    
    searchInput.addEventListener("input", () => {
      saveRecentSearch();
      updateClearButtonVisibility();
    });
  }

  // Search submission
  const searchForm = document.getElementById("search-form");
  searchForm.addEventListener("submit", (e) => {
    e.preventDefault();
    const query = searchInput.value;
    const category = document.getElementById("filter-category").value;
    searchTrackers(query, category);
  });

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
      <button id="tab-admin-users" class="${usersTabClass}" style="flex: 1; border-radius: 0;">Users Directory</button>
      <button id="tab-admin-downloads" class="${downloadsTabClass}" style="flex: 1; border-radius: 0;">All Downloads</button>
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
      <h2>ADMINISTRATION PANEL</h2>
      <p style="color: var(--text-secondary); margin-bottom: 1.5rem;">Manage users, view system downloads, and configure server settings.</p>
      
      <!-- Admin Tab Headers -->
      <div style="display: flex; gap: 0.5rem; border-bottom: 1px solid var(--border-color); padding-bottom: 1rem; margin-bottom: 1.5rem;">
        ${tabsHtml}
      </div>

      <!-- Tab Content: Users -->
      <div id="admin-users-section" style="display: ${showUsersDisplay};">
        <div style="margin-bottom: 1rem; display: flex; justify-content: space-between; align-items: center;">
          <h3 style="font-size: 0.85rem; text-transform: uppercase; letter-spacing: 0.05em; color: var(--text-secondary); font-weight: 600;">User Accounts & Approvals</h3>
          <button id="btn-refresh-users" class="btn" style="padding: 0.25rem 0.75rem; font-size: 0.75rem; border-radius: 0;">Refresh</button>
        </div>
        <div id="admin-users-table-container" style="overflow-x: auto; border: 1px solid var(--border-color); background-color: var(--bg-secondary); padding: 0.5rem;">
          <table style="width: 100%; border-collapse: collapse; text-align: left; font-size: 0.8rem; font-family: var(--font-mono);">
            <thead>
              <tr style="border-bottom: 1px solid var(--border-color); color: var(--text-secondary); text-transform: uppercase; font-size: 0.7rem;">
                <th style="padding: 0.75rem 0.5rem;">User</th>
                <th style="padding: 0.75rem 0.5rem;">Joined</th>
                <th style="padding: 0.75rem 0.5rem;">Role / Group</th>
                <th style="padding: 0.75rem 0.5rem; text-align: right;">Stats</th>
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
      </div>

      <!-- Tab Content: Downloads -->
      <div id="admin-downloads-section" style="display: ${showDownloadsDisplay};">
        <!-- Filters & Searches -->
        <div style="display: flex; flex-direction: column; gap: 0.75rem; margin-bottom: 1.5rem; border: 1px solid var(--border-color); padding: 1rem; background-color: var(--bg-primary);">
          <div style="display: flex; gap: 0.5rem; flex-wrap: wrap;">
            <input type="text" id="admin-search-dl" class="form-input" placeholder="Search by title..." style="flex: 2; min-width: 180px;">
            <select id="admin-filter-status" class="form-input" style="flex: 1; min-width: 120px;">
              <option value="">All Statuses</option>
              <option value="queued">Queued</option>
              <option value="downloading">Downloading</option>
              <option value="moving">Moving</option>
              <option value="completed">Completed</option>
              <option value="failed">Failed</option>
            </select>
            <select id="admin-sort-by" class="form-input" style="flex: 1; min-width: 120px;">
              <option value="created_at">Date Created</option>
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

        <div style="margin-bottom: 1rem; display: flex; justify-content: space-between; align-items: center;">
          <h3 style="font-size: 0.85rem; text-transform: uppercase; letter-spacing: 0.05em; color: var(--text-secondary); font-weight: 600;">System Torrent Queue</h3>
          <button id="btn-refresh-downloads" class="btn" style="padding: 0.25rem 0.75rem; font-size: 0.75rem; border-radius: 0;">Refresh</button>
        </div>
        <div id="admin-downloads-table-container" style="overflow-x: auto; border: 1px solid var(--border-color); background-color: var(--bg-secondary); padding: 0.5rem;">
          <table style="width: 100%; border-collapse: collapse; text-align: left; font-size: 0.8rem; font-family: var(--font-mono);">
            <thead>
              <tr style="border-bottom: 1px solid var(--border-color); color: var(--text-secondary); text-transform: uppercase; font-size: 0.7rem;">
                <th style="padding: 0.75rem 0.5rem;">Torrent</th>
                <th style="padding: 0.75rem 0.5rem;">User</th>
                <th style="padding: 0.75rem 0.5rem;">Size</th>
                <th style="padding: 0.75rem 0.5rem;">Status</th>
                <th style="padding: 0.75rem 0.5rem; text-align: right;">Action</th>
              </tr>
            </thead>
            <tbody id="admin-downloads-list">
              <tr>
                <td colspan="5" class="empty-state" style="padding: 2rem;">Loading downloads...</td>
              </tr>
            </tbody>
          </table>
        </div>
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
    });
  }
  
  const refreshUsersBtn = document.getElementById("btn-refresh-users");
  if (refreshUsersBtn) {
    refreshUsersBtn.addEventListener("click", fetchAdminUsers);
  }
  
  const refreshDownloadsBtn = document.getElementById("btn-refresh-downloads");
  if (refreshDownloadsBtn) {
    refreshDownloadsBtn.addEventListener("click", fetchAdminDownloads);
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

  const downloadsListEl = document.getElementById("admin-downloads-list");
  if (downloadsListEl) {
    downloadsListEl.addEventListener("click", async (e) => {
      if (e.target.classList.contains("btn-admin-action")) {
        const torboxId = e.target.getAttribute("data-torbox-id");
        const action = e.target.getAttribute("data-action");
        const confirmMsg = action === "delete"
          ? "Are you sure you want to delete this completed download and remove its files from the server?"
          : "Are you sure you want to cancel this transfer and remove any temporary files?";
        if (confirm(confirmMsg)) {
          e.target.disabled = true;
          e.target.textContent = action === "delete" ? "DELETING..." : "ABORTING...";
          await cancelDownload(torboxId);
          fetchAdminDownloads();
        }
      }
    });
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
        } else {
          alert("Failed to update config: " + resData.error);
        }
      } catch (err) {
        console.error("Save config failure:", err);
        alert("System connection error saving config.");
      }
    });
  }

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
      container.innerHTML = `<tr><td colspan="5" class="empty-state" style="color: var(--danger); padding: 1.5rem;">Failed to load users: ${err.error}</td></tr>`;
    }
  } catch (e) {
    console.error(e);
    container.innerHTML = `<tr><td colspan="5" class="empty-state" style="color: var(--danger); padding: 1.5rem;">Network error loading users.</td></tr>`;
  }
}

function renderAdminUsersList(users) {
  const container = document.getElementById("admin-users-list");
  if (!container) return;
  
  if (users.length === 0) {
    container.innerHTML = `<tr><td colspan="5" class="empty-state" style="padding: 2rem;">No user accounts found.</td></tr>`;
    return;
  }
  
  const isAdmin = state.user && state.user.group_name === "Admin";
  
  container.innerHTML = users.map(u => {
    const isSelf = state.user && Number(u.id) === Number(state.user.id);
    const joinDate = new Date(u.created_at).toLocaleDateString();
    const sizeText = u.total_downloaded_bytes ? formatBytes(u.total_downloaded_bytes) : "0 B";
    
    const isUnapproved = u.group_id === null || u.group_name === "None (Pending Approval)";
    
    let roleActionHtml = "";
    if (!isAdmin) {
      const labelClass = isUnapproved ? "color: var(--danger); font-weight: bold;" : "color: var(--text-primary);";
      roleActionHtml = `<span style="${labelClass}">${u.group_name}</span>`;
    } else {
      const selectedNone = isUnapproved ? "selected" : "";
      const selectedUser = u.group_name === "User" ? "selected" : "";
      const selectedMod = u.group_name === "Moderator" ? "selected" : "";
      const selectedAdmin = u.group_name === "Admin" ? "selected" : "";
      
      roleActionHtml = `
        <select class="form-input admin-role-select" data-user-id="${u.id}" style="padding: 0.15rem 0.5rem; font-size: 0.75rem; width: 140px; height: 26px; line-height: 1; display: inline-block;">
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
          <button class="btn btn-primary btn-approve-user" data-user-id="${u.id}" style="padding: 0.15rem 0.4rem; font-size: 0.65rem; height: 24px; line-height: 1; border-radius: 0;">APPROVE</button>
        `;
      }
      if (!isSelf) {
        actionsHtml += `
          <button class="btn btn-danger btn-delete-user" data-user-id="${u.id}" style="padding: 0.15rem 0.4rem; font-size: 0.65rem; height: 24px; line-height: 1; margin-left: 4px; border-radius: 0;">DELETE</button>
        `;
      } else {
        actionsHtml += `<span style="font-size: 0.65rem; color: var(--text-muted); font-style: italic;">Self</span>`;
      }
    } else {
      actionsHtml = `<span style="font-size: 0.65rem; color: var(--text-muted); font-style: italic;">Read-Only</span>`;
    }
    
    return `
      <tr style="border-bottom: 1px solid var(--border-color);">
        <td style="padding: 0.75rem 0.5rem; display: flex; align-items: center; gap: 0.5rem;">
          <img src="${u.profile_picture || FALLBACK_AVATAR}" style="width: 20px; height: 20px; border-radius: 50%; border: 1px solid var(--border-color);">
          <div style="display: flex; flex-direction: column;">
            <strong style="color: var(--text-primary); font-size: 0.8rem;">${u.full_name || u.username}</strong>
            <span style="font-size: 0.65rem; color: var(--text-muted);">${u.username}</span>
          </div>
        </td>
        <td style="padding: 0.75rem 0.5rem; color: var(--text-secondary); vertical-align: middle;">${joinDate}</td>
        <td style="padding: 0.75rem 0.5rem; vertical-align: middle;">${roleActionHtml}</td>
        <td style="padding: 0.75rem 0.5rem; text-align: right; color: var(--text-secondary); vertical-align: middle;">
          <strong>${u.total_downloads}</strong> releases<br>
          <span style="font-size: 0.65rem; color: var(--text-muted);">${sizeText}</span>
        </td>
        <td style="padding: 0.75rem 0.5rem; text-align: right; vertical-align: middle;">
          ${actionsHtml}
        </td>
      </tr>
    `;
  }).join("");
}

async function fetchAdminDownloads() {
  const container = document.getElementById("admin-downloads-list");
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
      container.innerHTML = `<tr><td colspan="5" class="empty-state" style="color: var(--danger); padding: 1.5rem;">Failed to load downloads: ${err.error}</td></tr>`;
    }
  } catch (e) {
    console.error(e);
    container.innerHTML = `<tr><td colspan="5" class="empty-state" style="color: var(--danger); padding: 1.5rem;">Network error loading downloads.</td></tr>`;
  }
}

function renderAdminDownloadsList(downloads) {
  const container = document.getElementById("admin-downloads-list");
  if (!container) return;
  
  if (downloads.length === 0) {
    container.innerHTML = `<tr><td colspan="5" class="empty-state" style="padding: 2rem;">No system downloads found.</td></tr>`;
    return;
  }
  
  const isAdmin = state.user && state.user.group_name === "Admin";
  
  container.innerHTML = downloads.map(dl => {
    const sizeText = dl.size ? formatBytes(dl.size) : "0 B";
    const progressText = dl.progress !== undefined ? `${dl.progress}%` : "0%";
    const dateText = new Date(dl.created_at).toLocaleDateString();
    
    const isOwner = state.user && Number(dl.user_id) === Number(state.user.id);
    const canControl = isAdmin || isOwner;
    
    const isCompleted = dl.status.toLowerCase().includes("completed");
    const isFailed = dl.status.toLowerCase().includes("failed");
    
    let btnHtml = "";
    if (canControl) {
      if (isCompleted) {
        btnHtml = `<button class="btn btn-danger btn-admin-action" data-action="delete" data-torbox-id="${dl.torbox_id}" style="padding: 0.15rem 0.4rem; font-size: 0.65rem; height: 24px; line-height: 1; border-radius: 0;">DELETE</button>`;
      } else if (!isFailed) {
        btnHtml = `<button class="btn btn-danger btn-admin-action" data-action="cancel" data-torbox-id="${dl.torbox_id}" style="padding: 0.15rem 0.4rem; font-size: 0.65rem; height: 24px; line-height: 1; border-radius: 0;">CANCEL</button>`;
      } else {
        btnHtml = `<button class="btn btn-danger btn-admin-action" data-action="delete" data-torbox-id="${dl.torbox_id}" style="padding: 0.15rem 0.4rem; font-size: 0.65rem; height: 24px; line-height: 1; border-radius: 0;">CLEAR</button>`;
      }
    } else {
      btnHtml = `<span style="font-size: 0.65rem; color: var(--text-muted); font-style: italic;">No Access</span>`;
    }
    
    const statusClass = getStatusClass(dl.status);
    
    return `
      <tr id="admin-dl-row-${dl.torbox_id}" style="border-bottom: 1px solid var(--border-color);">
        <td style="padding: 0.75rem 0.5rem; max-width: 320px; word-break: break-all;">
          <strong style="color: var(--text-primary); font-size: 0.80rem;">${dl.title || dl.filename || "Unknown Title"}</strong><br>
          <span style="font-size: 0.65rem; color: var(--text-muted);">${dl.filename || ""}</span><br>
          <span style="font-size: 0.65rem; color: var(--text-muted);">${dateText}</span>
        </td>
        <td style="padding: 0.75rem 0.5rem; color: var(--text-secondary); vertical-align: middle;">
          <strong>${dl.full_name}</strong><br>
          <span style="font-size: 0.65rem; color: var(--text-muted);">${dl.username}</span>
        </td>
        <td id="admin-dl-size-${dl.torbox_id}" style="padding: 0.75rem 0.5rem; color: var(--text-secondary); vertical-align: middle;">${sizeText}</td>
        <td style="padding: 0.75rem 0.5rem; vertical-align: middle;">
          <span id="admin-dl-status-${dl.torbox_id}" class="dl-item-status dl-status-${statusClass}" style="padding: 0.1rem 0.3rem; border: 1px solid var(--border-color); font-size: 0.65rem; display: inline-block;">
            ${dl.status.toUpperCase()} (${progressText})
          </span>
        </td>
        <td id="admin-dl-btn-${dl.torbox_id}" style="padding: 0.75rem 0.5rem; text-align: right; vertical-align: middle;">
          ${btnHtml}
        </td>
      </tr>
    `;
  }).join("");
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
  }
  
  if (state.currentView === "admin") {
    fetchAdminDownloads();
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
      adminListEl.innerHTML = `<tr><td colspan="5" class="empty-state" style="padding: 2rem;">No system downloads found.</td></tr>`;
    }
  }
  
  updateSidebarBadge();
  updateSearchResultButtons();
}

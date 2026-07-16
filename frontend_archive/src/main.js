import "./index.css";
import { io } from "https://cdn.socket.io/4.7.4/socket.io.esm.min.js";

// Application State
let state = {
  user: null,
  token: localStorage.getItem("session_token"),
  currentView: "login", // 'login', 'dashboard', 'settings'
  searchResults: [],
  downloads: [],
  socket: null
};

// Main Entry Point
document.addEventListener("DOMContentLoaded", () => {
  initApp();
});

async function initApp() {
  const success = await fetchCurrentUser();
  if (success) {
    console.log("Sign in successful for email:", state.user.username);
    navigate("dashboard");
    initSocket();
  } else {
    logout();
  }
}

// Navigation & Views Router
function navigate(view) {
  state.currentView = view;
  const appContainer = document.getElementById("app");
  
  if (view === "login") {
    appContainer.innerHTML = renderLogin();
    setupLoginListeners();
  } else if (view === "dashboard") {
    appContainer.innerHTML = renderDashboard();
    setupDashboardListeners();
    fetchDownloads();
  } else if (view === "settings") {
    appContainer.innerHTML = renderSettings();
    setupSettingsListeners();
  }
}

// WebSocket Setup
function initSocket() {
  if (state.socket) return;

  const socketUrl = window.location.origin;
  state.socket = io(socketUrl, {
    transports: ["websocket", "polling"]
  });

  state.socket.on("connect", () => {
    console.log("WebSocket connected to backend");
  });

  state.socket.on("download_progress", (data) => {
    console.log("Progress update:", data);
    updateDownloadProgressUI(data);
  });

  state.socket.on("disconnect", () => {
    console.log("WebSocket disconnected");
  });
}

// API Requests
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
        localStorage.setItem("session_token", state.token);
      }
      return true;
    }
    return false;
  } catch (err) {
    console.error("Error fetching current user:", err);
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
    }
  } catch (err) {
    console.error("Error fetching downloads:", err);
  }
}

// Real-Time Progress UI Updater
function updateDownloadProgressUI(data) {
  // Find card progress bar (if searching/downloading card matches)
  const torrentId = data.id;
  const status = data.status;
  const progress = data.progress;
  const speed = data.speed;

  // 1. Update the downloads panel item if it exists, otherwise prepend it
  const downloadListEl = document.getElementById("downloads-list");
  if (downloadListEl) {
    let itemEl = document.getElementById(`dl-item-${torrentId}`);
    if (!itemEl) {
      // Create new download entry
      const tempDiv = document.createElement("div");
      tempDiv.innerHTML = renderDownloadItem({
        torbox_id: torrentId,
        filename: data.title,
        status: status,
        progress: progress,
        speed: speed,
        size: data.size
      });
      itemEl = tempDiv.firstElementChild;
      downloadListEl.insertBefore(itemEl, downloadListEl.firstChild);
    } else {
      // Update existing item
      const statusEl = itemEl.querySelector(".download-item-status");
      const progressTextEl = itemEl.querySelector(".progress-text");
      const speedTextEl = itemEl.querySelector(".speed-text");
      const progressBarEl = itemEl.querySelector(".progress-bar");

      statusEl.textContent = status;
      statusEl.className = `download-item-status status-${getStatusClass(status)}`;
      progressTextEl.innerHTML = `${progress}% ${data.size ? `<span class="size-text">(${formatBytes(data.size)})</span>` : ""}`;
      speedTextEl.textContent = formatSpeed(speed);
      progressBarEl.style.width = `${progress}%`;
    }
  }

  // 2. Find and update download progress in active card dropdown button/state
  const downloadBtns = document.querySelectorAll(`button[data-torrent-id="${torrentId}"]`);
  downloadBtns.forEach(btn => {
    btn.disabled = true;
    btn.innerHTML = `<span class="spinner"></span> ${status} (${progress}%)`;
    if (status === "completed") {
      btn.innerHTML = "Downloaded";
      btn.className = "btn btn-secondary";
    }
  });
}

function getStatusClass(status) {
  const stat = status.toLowerCase();
  if (stat.includes("completed") || stat.includes("downloaded")) return "completed";
  if (stat.includes("downloading")) return "downloading";
  if (stat.includes("moving") || stat.includes("transferring")) return "moving";
  if (stat.includes("queued")) return "queued";
  return "failed";
}

function formatSpeed(bytesPerSec) {
  if (bytesPerSec === 0) return "";
  let val = bytesPerSec;
  for (const unit of ["B/s", "KB/s", "MB/s", "GB/s"]) {
    if (val < 1024) return `${val.toFixed(1)} ${unit}`;
    val /= 1024;
  }
  return `${val.toFixed(1)} TB/s`;
}

function formatBytes(bytes) {
  if (bytes === 0) return "0 B";
  let val = bytes;
  for (const unit of ["B", "KB", "MB", "GB", "TB"]) {
    if (val < 1024) return `${val.toFixed(1)} ${unit}`;
    val /= 1024;
  }
  return `${val.toFixed(1)} PB`;
}

// User Actions
async function login(username, password) {
  const errorEl = document.getElementById("login-error");
  if (errorEl) errorEl.style.display = "none";

  try {
    const resp = await fetch("/api/auth/login", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ username, password })
    });

    const data = await resp.json();
    if (resp.ok) {
      state.token = data.token;
      state.user = data.user;
      localStorage.setItem("session_token", data.token);
      navigate("dashboard");
      initSocket();
    } else {
      if (errorEl) {
        errorEl.textContent = data.error || "Login failed.";
        errorEl.style.display = "block";
      }
    }
  } catch (err) {
    console.error("Login request failed:", err);
    if (errorEl) {
      errorEl.textContent = "Server connection error.";
      errorEl.style.display = "block";
    }
  }
}

function logout() {
  fetch("/api/auth/logout", {
    method: "POST"
  }).catch(() => {});
  
  state.token = null;
  state.user = null;
  localStorage.removeItem("session_token");
  if (state.socket) {
    state.socket.disconnect();
    state.socket = null;
  }
  navigate("login");
}

async function searchTrackers(query, category) {
  const resultsContainer = document.getElementById("results-list");
  const loadingEl = document.getElementById("search-loading");
  
  if (loadingEl) loadingEl.style.display = "block";
  resultsContainer.innerHTML = "";
  
  try {
    const headers = {};
    if (state.token) {
      headers["Authorization"] = `Bearer ${state.token}`;
    }
    const resp = await fetch(`/api/search?q=${encodeURIComponent(query)}&category=${category || ""}`, { headers });
    const resData = await resp.json();
    if (resp.ok) {
      state.searchResults = resData.data;
      renderSearchResults();
    } else {
      resultsContainer.innerHTML = `<div class="alert alert-error">Error: ${resData.error}</div>`;
    }
  } catch (err) {
    console.error("Search failed:", err);
    resultsContainer.innerHTML = `<div class="alert alert-error">Failed to query search client.</div>`;
  } finally {
    if (loadingEl) loadingEl.style.display = "none";
  }
}

async function triggerDownload(magnet, title, filename, category, year, season, episode, btn) {
  btn.disabled = true;
  btn.innerHTML = `<span class="spinner"></span> Queuing...`;

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
      body: JSON.stringify({ magnet, title, filename, category, year, season, episode })
    });
    
    const data = await resp.json();
    if (resp.ok) {
      btn.setAttribute("data-torrent-id", data.torbox_id);
      btn.innerHTML = `Queued (Torbox)`;
      fetchDownloads();
    } else {
      btn.disabled = false;
      btn.innerHTML = "Download";
      alert(`Download failed: ${data.error}`);
    }
  } catch (err) {
    console.error("Download trigger failed:", err);
    btn.disabled = false;
    btn.innerHTML = "Download";
    alert("Download failed to trigger.");
  }
}

// Render Templates
function renderLogin() {
  return `
    <div class="auth-wrapper">
      <div class="glass-panel auth-card animate-fade-in" style="text-align: center;">
        <h1 class="logo auth-title" style="justify-content: center;">RICO.CX</h1>
        <p class="auth-subtitle">Torrent Search & Download Manager</p>
        
        <div id="login-error" class="alert alert-error" style="display: none;"></div>
        
        <div style="margin-top: 2rem;">
          <a href="/api/auth/google/login" class="btn btn-primary" style="display: inline-flex; align-items: center; gap: 0.75rem; text-decoration: none; width: 100%; justify-content: center; padding: 0.75rem;">
            <svg width="18" height="18" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg" style="background: white; border-radius: 2px; padding: 1px;">
              <path d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92c-.26 1.37-1.04 2.53-2.21 3.31v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.09z" fill="#4285F4"/>
              <path d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z" fill="#34A853"/>
              <path d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.06H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.94l2.85-2.22.81-.63z" fill="#FBBC05"/>
              <path d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.06l3.66 2.84c.87-2.6 3.3-4.52 6.16-4.52z" fill="#EA4335"/>
            </svg>
            Sign in with Google
          </a>
        </div>
      </div>
    </div>
  `;
}

function renderDashboard() {
  const name = state.user.full_name || state.user.username;
  const avatar = state.user.profile_picture || 'https://www.gravatar.com/avatar/00000000000000000000000000000000?d=mp&f=y';
  const role = state.user.group_name || 'User';

  return `
    <header class="glass-panel">
      <h1 class="logo">RICO.CX</h1>
      <div class="nav-buttons">
        <div class="user-profile">
          <img src="${avatar}" alt="Profile" class="profile-pic">
          <div class="profile-info">
            <span class="profile-name">${name}</span>
            <span class="profile-role">${role}</span>
          </div>
        </div>
        <button id="nav-settings" class="btn btn-secondary">Settings</button>
        <button id="nav-logout" class="btn btn-danger">Logout</button>
      </div>
    </header>
    
    <div class="glass-panel search-container">
      <form id="search-form" class="search-controls" onsubmit="return false;">
        <input type="text" id="search-input" class="form-input" required placeholder="Search movies, TV shows, or paste a magnet link/torrent hash...">
        <select id="search-category" class="form-input category-select">
          <option value="">All Categories</option>
          <option value="movie">Movies</option>
          <option value="tv">TV Shows</option>
        </select>
        <button type="submit" class="btn btn-primary">Search</button>
      </form>
    </div>
    
    <div class="dashboard-grid">
      <!-- Search Results column -->
      <section>
        <div class="results-header">
          <h2>Search Results</h2>
          <div id="search-loading" style="display: none;"><span class="spinner"></span> Searching indexers...</div>
        </div>
        <div id="results-list" class="results-grid">
          <div class="text-muted" style="text-align: center; padding: 3rem;">Search for media files to get started.</div>
        </div>
      </section>
      
      <!-- Active Downloads column -->
      <section class="glass-panel downloads-panel">
        <h2>Active Downloads</h2>
        <div id="downloads-list" class="downloads-list">
          <div class="text-muted" style="text-align: center; padding: 2rem;">No active downloads.</div>
        </div>
      </section>
    </div>
  `;
}

function renderSettings() {
  return `
    <header class="glass-panel">
      <h1 class="logo">RICO.CX</h1>
      <div class="nav-buttons">
        <button id="nav-back" class="btn btn-secondary">← Back</button>
        <button id="nav-logout" class="btn btn-danger">Logout</button>
      </div>
    </header>
    
    <div class="glass-panel settings-container animate-fade-in">
      <h2>Server Settings</h2>
      <p class="text-muted" style="margin-bottom: 1.5rem;">Configure your indexers search and downloader API credentials. These settings are securely stored in your user profile.</p>
      
      <div id="settings-status" class="alert alert-success" style="display: none;">Settings saved successfully.</div>
      
      <form id="settings-form" onsubmit="return false;">
        <div class="form-group">
          <label class="form-label" for="prowlarr-url">Prowlarr API URL</label>
          <input type="url" id="prowlarr-url" class="form-input" placeholder="http://localhost:9696">
        </div>
        
        <div class="form-group">
          <label class="form-label" for="prowlarr-key">Prowlarr API Key</label>
          <input type="password" id="prowlarr-key" class="form-input" placeholder="••••••••••••••••••••••••••••••••">
        </div>
        
        <div class="form-group">
          <label class="form-label" for="torbox-key">Torbox API Key</label>
          <input type="password" id="torbox-key" class="form-input" placeholder="••••••••••••••••••••••••••••••••">
        </div>
        
        <div class="form-group">
          <label class="form-label" for="library-path">Local Library Root Folder</label>
          <input type="text" id="library-path" class="form-input" placeholder="./library">
          <small class="text-muted" style="margin-top: 0.25rem;">The path on the server where downloads will be saved. Uses separate 'MOVIES' and 'TV SHOWS' folders.</small>
        </div>
        
        <button type="submit" class="btn btn-primary" style="margin-top: 1rem;">Save Configuration</button>
      </form>
    </div>
  `;
}

// Render Search Results Card
function renderSearchResults() {
  const container = document.getElementById("results-list");
  if (state.searchResults.length === 0) {
    container.innerHTML = '<div class="text-muted" style="text-align: center; padding: 3rem;">No results found. Try adjusting your query.</div>';
    return;
  }

  container.innerHTML = "";
  state.searchResults.forEach((item, index) => {
    const cardEl = document.createElement("div");
    cardEl.className = "glass-panel result-card animate-fade-in";
    cardEl.style.animationDelay = `${index * 0.05}s`;
    
    // Sort downloads within aggregated item
    const downloads = item.downloads;
    const defaultOption = downloads[0];

    // Build options select
    let optionsHtml = "";
    downloads.forEach((dl, dlIdx) => {
      const displaySize = formatBytes(dl.size);
      const badgesStr = [
        dl.resolution !== "Unknown" ? dl.resolution : "",
        dl.codec !== "Unknown" ? dl.codec : "",
        dl.source !== "Unknown" ? dl.source : "",
        dl.features.join(" "),
        dl.audio.join(" ")
      ].filter(Boolean).join(" | ");
      
      optionsHtml += `
        <option value="${dlIdx}">
          [${displaySize} | Seeds: ${dl.seeders}] - ${dl.title}
        </option>
      `;
    });

    const isTV = item.is_tv;
    const yearText = item.year ? `(${item.year})` : "";
    const categoryBadge = isTV ? `<span class="badge badge-tv">TV SHOW</span>` : `<span class="badge badge-movie">MOVIE</span>`;
    
    const posterHtml = item.poster_url 
      ? `<img src="${item.poster_url}" alt="Poster" class="card-poster-img" style="width: 100%; height: 100%; object-fit: cover; border-radius: inherit;">`
      : `<span>${isTV ? 'TV' : 'Movie'}</span><span style="font-size: 0.5rem; opacity: 0.7;">RICO</span>`;
      
    cardEl.innerHTML = `
      <div class="card-header">
        <div class="card-poster">
          ${posterHtml}
        </div>
        <div class="card-title-area">
          <div class="card-title">
            ${item.clean_title} ${yearText}
            ${categoryBadge}
          </div>
          <div class="card-meta">
            <span>Size Range: <strong>${item.size_range}</strong></span>
            <span>Options: <strong>${downloads.length}</strong></span>
          </div>
          <div class="card-tags" id="card-tags-${index}">
            <!-- Badges will be generated dynamically on select option -->
          </div>
        </div>
      </div>
      
      <div class="download-selector">
        <select class="form-input download-select" id="select-dl-${index}">
          ${optionsHtml}
        </select>
        <button class="btn btn-primary btn-dl-trigger" id="btn-dl-${index}">Download</button>
      </div>
    `;

    container.appendChild(cardEl);
    
    // Set up dynamic updates for badge tags based on selection
    const selectEl = cardEl.querySelector(`#select-dl-${index}`);
    const tagsContainer = cardEl.querySelector(`#card-tags-${index}`);
    const downloadBtn = cardEl.querySelector(`#btn-dl-${index}`);

    const updateBadges = (dlOption) => {
      tagsContainer.innerHTML = "";
      
      // Resolution Badge
      if (dlOption.resolution !== "Unknown") {
        tagsContainer.innerHTML += `<span class="badge badge-res">${dlOption.resolution}</span>`;
      }
      // Features (HDR/Dolby Vision)
      dlOption.features.forEach(feat => {
        if (feat.includes("HDR")) {
          tagsContainer.innerHTML += `<span class="badge badge-hdr">${feat}</span>`;
        } else if (feat.includes("DV")) {
          tagsContainer.innerHTML += `<span class="badge badge-dv">${feat}</span>`;
        } else {
          tagsContainer.innerHTML += `<span class="badge badge-res">${feat}</span>`;
        }
      });
      // Source & Codec
      if (dlOption.source !== "Unknown") {
        tagsContainer.innerHTML += `<span class="badge badge-res">${dlOption.source}</span>`;
      }
      if (dlOption.codec !== "Unknown") {
        tagsContainer.innerHTML += `<span class="badge badge-res">${dlOption.codec}</span>`;
      }
      // Audio
      dlOption.audio.forEach(aud => {
        tagsContainer.innerHTML += `<span class="badge badge-res">${aud}</span>`;
      });
      // Indexer Badge
      tagsContainer.innerHTML += `<span class="badge" style="background: rgba(255,255,255,0.03); color: var(--text-muted); border: 1px solid rgba(255,255,255,0.05);">${dlOption.indexer}</span>`;
    };

    // Initialize with first option
    updateBadges(defaultOption);

    // Update tags when selection changes
    selectEl.addEventListener("change", (e) => {
      const idx = parseInt(e.target.value);
      updateBadges(downloads[idx]);
    });

    // Handle download button click
    downloadBtn.addEventListener("click", () => {
      const dlIdx = parseInt(selectEl.value);
      const selectedDl = downloads[dlIdx];
      
      // Trigger download request
      triggerDownload(
        selectedDl.download_url,
        item.clean_title,
        selectedDl.title,
        isTV ? "tv" : "movie",
        item.year,
        selectedDl.season,
        selectedDl.episode,
        downloadBtn
      );
    });
  });
}

// Render Active Downloads List
function renderActiveDownloads() {
  const container = document.getElementById("downloads-list");
  if (state.downloads.length === 0) {
    container.innerHTML = '<div class="text-muted" style="text-align: center; padding: 2rem;">No active downloads.</div>';
    return;
  }

  container.innerHTML = "";
  state.downloads.forEach(dl => {
    container.innerHTML += renderDownloadItem(dl);
  });
}

function renderDownloadItem(dl) {
  const progress = dl.progress || 0;
  const statusClass = getStatusClass(dl.status);
  const sizeText = dl.size ? formatBytes(dl.size) : "";
  
  return `
    <div class="download-item animate-fade-in" id="dl-item-${dl.torbox_id}">
      <div class="download-item-header">
        <div class="download-item-title" title="${dl.filename}">${dl.filename}</div>
        <span class="download-item-status status-${statusClass}">${dl.status}</span>
      </div>
      <div class="progress-container">
        <div class="progress-bar" style="width: ${progress}%;"></div>
      </div>
      <div class="download-item-meta">
        <span class="progress-text">${progress}% ${sizeText ? `<span class="size-text">(${sizeText})</span>` : ""}</span>
        <span class="speed-text">${dl.speed ? formatSpeed(dl.speed) : ""}</span>
      </div>
    </div>
  `;
}

// Listeners Setup
function setupLoginListeners() {
  // Login is handled directly via redirection to Google Auth
}

function setupDashboardListeners() {
  // Navigation
  document.getElementById("nav-logout").addEventListener("click", logout);
  document.getElementById("nav-settings").addEventListener("click", () => navigate("settings"));
  
  // Search Submission
  const searchForm = document.getElementById("search-form");
  searchForm.addEventListener("submit", (e) => {
    e.preventDefault();
    const queryEl = document.getElementById("search-input");
    const categoryEl = document.getElementById("search-category");
    searchTrackers(queryEl.value, categoryEl.value);
  });
}

function setupSettingsListeners() {
  document.getElementById("nav-back").addEventListener("click", () => navigate("dashboard"));
  document.getElementById("nav-logout").addEventListener("click", logout);
  
  // Populate form with existing user settings
  const prowlarrUrlEl = document.getElementById("prowlarr-url");
  const prowlarrKeyEl = document.getElementById("prowlarr-key");
  const torboxKeyEl = document.getElementById("torbox-key");
  const libraryPathEl = document.getElementById("library-path");
  
  if (state.user && state.user.settings) {
    const s = state.user.settings;
    prowlarrUrlEl.value = s.prowlarr_url || "";
    prowlarrKeyEl.value = s.prowlarr_api_key || "";
    torboxKeyEl.value = s.torbox_api_key || "";
    libraryPathEl.value = s.library_path || "";
  }
  
  const settingsForm = document.getElementById("settings-form");
  settingsForm.addEventListener("submit", async (e) => {
    e.preventDefault();
    const statusEl = document.getElementById("settings-status");
    statusEl.style.display = "none";
    
    const settings = {
      prowlarr_url: prowlarrUrlEl.value,
      prowlarr_api_key: prowlarrKeyEl.value,
      torbox_api_key: torboxKeyEl.value,
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
        state.user.settings = resData.settings;
        statusEl.style.display = "block";
        statusEl.scrollIntoView({ behavior: "smooth" });
      } else {
        alert("Failed to save settings: " + resData.error);
      }
    } catch (err) {
      console.error("Failed to save settings:", err);
      alert("Error saving settings.");
    }
  });
}

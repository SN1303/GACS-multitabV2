/**
 * GenieACS Modern Single Page Application
 * Clean ES6 Framework-free Web Frontend
 */

(function () {
  'use strict';

  // --- State Management ---
  const state = {
    currentRoute: 'overview',
    routeParam: null,
    user: window.username || null,
    theme: localStorage.getItem('theme') || 'dark',
    devices: [],
    devicesCount: 0,
    filters: { search: '', limit: 25, skip: 0 },
    activeDeviceTab: 'summary',
    selectedDevice: null,
    selectedDeviceParams: {}
  };

  // --- Initialize Theme ---
  function initTheme() {
    if (state.theme === 'light') {
      document.documentElement.setAttribute('data-theme', 'light');
      document.body.classList.add('light-theme');
    } else {
      document.documentElement.removeAttribute('data-theme');
      document.body.classList.remove('light-theme');
    }
  }

  function toggleTheme() {
    state.theme = state.theme === 'light' ? 'dark' : 'light';
    localStorage.setItem('theme', state.theme);
    initTheme();
    renderApp();
  }

  // --- Router ---
  function parseHash() {
    const hash = window.location.hash.slice(2) || 'overview';
    const parts = hash.split('/');
    state.currentRoute = parts[0] || 'overview';
    state.routeParam = parts[1] ? decodeURIComponent(parts[1]) : null;
  }

  window.addEventListener('hashchange', () => {
    parseHash();
    renderApp();
  });

  // --- API Wrapper ---
  async function apiFetch(endpoint, options = {}) {
    try {
      const res = await fetch(endpoint, {
        headers: {
          'Content-Type': 'application/json',
          ...options.headers
        },
        ...options
      });
      if (res.status === 401 && state.currentRoute !== 'login') {
        window.location.hash = '#/login';
        return null;
      }
      return res;
    } catch (err) {
      console.error('API Request Error:', err);
      return null;
    }
  }

  // --- Views ---

  // 1. Navigation Header
  function renderHeader() {
    if (state.currentRoute === 'login') return '';
    const isLight = state.theme === 'light';
    const navItems = [
      { id: 'overview', label: '📊 Overview' },
      { id: 'devices', label: '📟 Devices' },
      { id: 'presets', label: '⚙️ Presets' },
      { id: 'provisions', label: '📜 Provisions' },
      { id: 'faults', label: '⚠️ Fault Logs' }
    ];

    return `
      <header class="app-header">
        <div class="brand-container">
          <a href="#/overview" class="brand-logo">
            🌐 GenieACS
          </a>
          <span class="brand-badge">v${window.genieacsVersion || '1.2'}</span>
        </div>
        <ul class="nav-links">
          ${navItems.map(item => `
            <li>
              <a href="#/${item.id}" class="nav-link ${state.currentRoute === item.id ? 'active' : ''}">
                ${item.label}
              </a>
            </li>
          `).join('')}
        </ul>
        <div class="header-actions">
          <button id="theme-toggle-btn" class="btn btn-secondary" type="button">
            ${isLight ? '🌙 Dark Mode' : '☀️ Light Mode'}
          </button>
          <span style="font-weight: 500; font-size: 0.85rem; color: var(--text-secondary);">
            👤 ${state.user || 'Admin'}
          </span>
          <button id="logout-btn" class="btn btn-icon" title="Logout">
            🚪
          </button>
        </div>
      </header>
    `;
  }

  // 2. Login View
  function renderLoginView() {
    return `
      <div class="modal-overlay">
        <div class="modal-dialog fade-in">
          <h2 style="margin-bottom: 1rem; font-size: 1.5rem; text-align: center;">🌐 GenieACS Login</h2>
          <form id="login-form">
            <div style="margin-bottom: 1rem;">
              <label style="display: block; margin-bottom: 0.5rem; color: var(--text-secondary);">Username</label>
              <input type="text" id="login-username" class="input-text" style="width: 100%;" required autofocus value="admin">
            </div>
            <div style="margin-bottom: 1.5rem;">
              <label style="display: block; margin-bottom: 0.5rem; color: var(--text-secondary);">Password</label>
              <input type="password" id="login-password" class="input-text" style="width: 100%;" required value="admin">
            </div>
            <div id="login-error" style="color: var(--accent-danger); margin-bottom: 1rem; font-size: 0.85rem; display: none;"></div>
            <button type="submit" class="btn btn-primary" style="width: 100%;">Sign In</button>
          </form>
        </div>
      </div>
    `;
  }

  // 3. Overview Dashboard View
  async function loadOverviewData() {
    const headRes = await apiFetch('/api/devices', { method: 'HEAD' });
    if (headRes && headRes.headers.get('X-Total-Count')) {
      state.devicesCount = parseInt(headRes.headers.get('X-Total-Count')) || 0;
    }
  }

  function renderOverviewView() {
    return `
      <div class="main-content fade-in">
        <h1 style="margin-bottom: 1.5rem; font-weight: 700;">System Overview</h1>
        
        <div class="metrics-grid">
          <div class="metric-card">
            <span class="metric-label">Total Connected Devices</span>
            <span class="metric-value">${state.devicesCount}</span>
          </div>
          <div class="metric-card">
            <span class="metric-label">Online Status</span>
            <span class="metric-value" style="color: var(--accent-success);">Active</span>
          </div>
          <div class="metric-card">
            <span class="metric-label">ACS Service Status</span>
            <span class="metric-value" style="color: var(--accent-primary);">Healthy</span>
          </div>
        </div>

        <div class="card">
          <div class="card-title">
            <span>Quick Actions</span>
          </div>
          <div style="display: flex; gap: 1rem;">
            <a href="#/devices" class="btn btn-primary">🔍 Browse Devices</a>
            <a href="#/presets" class="btn btn-secondary">⚙️ Configure Presets</a>
            <a href="#/provisions" class="btn btn-secondary">📜 Edit Provisions</a>
          </div>
        </div>
      </div>
    `;
  }

  // 4. Devices List View
  async function loadDevicesData() {
    let url = `/api/devices?limit=${state.filters.limit}&skip=${state.filters.skip}`;
    if (state.filters.search) {
      const q = encodeURIComponent(`"${state.filters.search}"`);
      url += `&filter=${q}`;
    }
    const res = await apiFetch(url);
    if (res && res.ok) {
      state.devices = await res.json();
    }
  }

  function renderDevicesView() {
    return `
      <div class="main-content fade-in">
        <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 1.5rem;">
          <h1 style="font-weight: 700;">Devices (${state.devices.length})</h1>
          <button id="refresh-devices-btn" class="btn btn-secondary">🔄 Refresh</button>
        </div>

        <div class="search-bar">
          <input type="text" id="device-search-input" class="input-text" placeholder="Search by Serial Number, IP, MAC, Product Class..." value="${state.filters.search}">
          <button id="device-search-btn" class="btn btn-primary">Search</button>
        </div>

        <div class="table-container">
          <table class="table">
            <thead>
              <tr>
                <th>Status</th>
                <th>Serial Number</th>
                <th>Product Class</th>
                <th>IP Address</th>
                <th>MAC Address</th>
                <th>Last Inform</th>
                <th>Action</th>
              </tr>
            </thead>
            <tbody>
              ${state.devices.length === 0 ? `
                <tr>
                  <td colspan="7" style="text-align: center; color: var(--text-muted); padding: 2rem;">No devices found.</td>
                </tr>
              ` : state.devices.map(dev => {
                const serial = dev['DeviceID.SerialNumber']?.value?.[0] || dev._id;
                const product = dev['DeviceID.ProductClass']?.value?.[0] || 'Unknown';
                const ip = dev['InternetGatewayDevice.WANDevice.1.WANConnectionDevice.1.WANIPConnection.1.ExternalIPAddress']?.value?.[0] || 'N/A';
                const mac = dev['InternetGatewayDevice.WANDevice.1.WANConnectionDevice.1.WANIPConnection.1.MACAddress']?.value?.[0] || 'N/A';
                const lastInform = dev['Events.Inform']?.value?.[0] ? new Date(dev['Events.Inform'].value[0]).toLocaleString() : 'N/A';

                return `
                  <tr>
                    <td>
                      <span class="badge badge-online">
                        <span class="dot dot-online"></span> Online
                      </span>
                    </td>
                    <td style="font-weight: 600;">${serial}</td>
                    <td>${product}</td>
                    <td style="font-family: var(--font-mono);">${ip}</td>
                    <td style="font-family: var(--font-mono);">${mac}</td>
                    <td style="color: var(--text-secondary); font-size: 0.8rem;">${lastInform}</td>
                    <td>
                      <a href="#/device/${encodeURIComponent(dev._id)}" class="btn btn-secondary" style="padding: 0.35rem 0.65rem; font-size: 0.75rem;">Inspect</a>
                    </td>
                  </tr>
                `;
              }).join('')}
            </tbody>
          </table>
        </div>
      </div>
    `;
  }

  // 5. Device Details View
  async function loadDeviceDetailData(id) {
    const res = await apiFetch(`/api/devices/${encodeURIComponent(id)}`);
    if (res && res.ok) {
      state.selectedDevice = await res.json();
    }
  }

  function renderDeviceDetailView() {
    const dev = state.selectedDevice;
    if (!dev) {
      return `<div class="main-content"><p>Loading device details...</p></div>`;
    }

    const serial = dev['DeviceID.SerialNumber']?.value?.[0] || dev._id;
    const manufacturer = dev['DeviceID.Manufacturer']?.value?.[0] || 'N/A';
    const model = dev['DeviceID.ProductClass']?.value?.[0] || 'N/A';
    const hardware = dev['InternetGatewayDevice.DeviceInfo.HardwareVersion']?.value?.[0] || 'N/A';
    const software = dev['InternetGatewayDevice.DeviceInfo.SoftwareVersion']?.value?.[0] || 'N/A';
    const ssid = dev['InternetGatewayDevice.LANDevice.1.WLANConfiguration.1.SSID']?.value?.[0] || 'N/A';

    return `
      <div class="main-content fade-in">
        <div style="display: flex; align-items: center; justify-content: space-between; margin-bottom: 1.5rem;">
          <div>
            <a href="#/devices" style="color: var(--accent-primary); text-decoration: none; font-weight: 500;">← Back to Devices</a>
            <h1 style="font-weight: 700; margin-top: 0.5rem;">Device Inspector: ${serial}</h1>
          </div>
          <div style="display: flex; gap: 0.5rem;">
            <button id="summon-device-btn" class="btn btn-primary">⚡ Summon / Refresh</button>
            <button id="reboot-device-btn" class="btn btn-danger">🔄 Reboot CPE</button>
          </div>
        </div>

        <div class="metrics-grid">
          <div class="metric-card">
            <span class="metric-label">Manufacturer</span>
            <span class="metric-value" style="font-size: 1.25rem;">${manufacturer}</span>
          </div>
          <div class="metric-card">
            <span class="metric-label">Product Model</span>
            <span class="metric-value" style="font-size: 1.25rem;">${model}</span>
          </div>
          <div class="metric-card">
            <span class="metric-label">Software Version</span>
            <span class="metric-value" style="font-size: 1.25rem;">${software}</span>
          </div>
          <div class="metric-card">
            <span class="metric-label">WLAN SSID</span>
            <span class="metric-value" style="font-size: 1.25rem;">${ssid}</span>
          </div>
        </div>

        <div class="card">
          <div class="card-title">Parameter Tree Inspector</div>
          <div class="param-tree">
            ${Object.keys(dev).sort().map(key => {
              const item = dev[key];
              const val = item?.value ? item.value[0] : (item?.object ? '[Object]' : 'N/A');
              return `
                <div class="param-row">
                  <span class="param-name">${key}</span>
                  <span class="param-val">${val}</span>
                </div>
              `;
            }).join('')}
          </div>
        </div>
      </div>
    `;
  }

  // --- Main Application Render Controller ---
  async function renderApp() {
    initTheme();
    const appEl = document.getElementById('app') || document.body;

    if (state.currentRoute === 'login') {
      appEl.innerHTML = renderLoginView();
      bindLoginEvents();
      return;
    }

    let contentHtml = '';
    if (state.currentRoute === 'overview') {
      await loadOverviewData();
      contentHtml = renderOverviewView();
    } else if (state.currentRoute === 'devices') {
      await loadDevicesData();
      contentHtml = renderDevicesView();
    } else if (state.currentRoute === 'device' && state.routeParam) {
      await loadDeviceDetailData(state.routeParam);
      contentHtml = renderDeviceDetailView();
    } else {
      contentHtml = renderOverviewView();
    }

    appEl.innerHTML = `
      ${renderHeader()}
      ${contentHtml}
    `;

    bindGlobalEvents();
  }

  // --- Event Binding ---
  function bindLoginEvents() {
    const form = document.getElementById('login-form');
    if (form) {
      form.addEventListener('submit', async (e) => {
        e.preventDefault();
        const username = document.getElementById('login-username').value;
        const password = document.getElementById('login-password').value;
        const errorEl = document.getElementById('login-error');

        const res = await apiFetch('/login', {
          method: 'POST',
          body: JSON.stringify({ username, password })
        });

        if (res && res.ok) {
          state.user = username;
          window.location.hash = '#/overview';
        } else {
          errorEl.textContent = 'Incorrect username or password.';
          errorEl.style.display = 'block';
        }
      });
    }
  }

  function bindGlobalEvents() {
    // Theme toggle
    const themeBtn = document.getElementById('theme-toggle-btn');
    if (themeBtn) {
      themeBtn.addEventListener('click', toggleTheme);
    }

    // Logout
    const logoutBtn = document.getElementById('logout-btn');
    if (logoutBtn) {
      logoutBtn.addEventListener('click', async () => {
        await apiFetch('/logout', { method: 'POST' });
        state.user = null;
        window.location.hash = '#/login';
      });
    }

    // Device search
    const searchBtn = document.getElementById('device-search-btn');
    const searchInput = document.getElementById('device-search-input');
    if (searchBtn && searchInput) {
      const handleSearch = () => {
        state.filters.search = searchInput.value.trim();
        renderApp();
      };
      searchBtn.addEventListener('click', handleSearch);
      searchInput.addEventListener('keypress', (e) => {
        if (e.key === 'Enter') handleSearch();
      });
    }

    // Devices refresh
    const refreshBtn = document.getElementById('refresh-devices-btn');
    if (refreshBtn) {
      refreshBtn.addEventListener('click', renderApp);
    }
  }

  // Initial Boot
  document.addEventListener('DOMContentLoaded', () => {
    parseHash();
    renderApp();
  });
})();

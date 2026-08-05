/**
 * GenieACS Modern Single Page Application
 * Complete Multi-Feature Engine
 */

(function () {
  'use strict';

  // --- State Management ---
  const state = {
    currentRoute: 'overview',
    routeParam: null,
    user: window.username || 'admin',
    theme: localStorage.getItem('theme') || 'dark',
    devices: [],
    devicesCount: 0,
    presets: [],
    provisions: [],
    faults: [],
    filters: { search: '', limit: 50, skip: 0 },
    selectedDevice: null
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
    const rawHash = window.location.hash.replace(/^#\/?/, '') || 'overview';
    const parts = rawHash.split('/');
    
    if (parts[0] === 'device' || parts[0] === 'devices') {
      if (parts.length > 1 && parts[1]) {
        state.currentRoute = 'device';
        state.routeParam = decodeURIComponent(parts.slice(1).join('/'));
      } else {
        state.currentRoute = 'devices';
        state.routeParam = null;
      }
    } else {
      state.currentRoute = parts[0] || 'overview';
      state.routeParam = parts[1] ? decodeURIComponent(parts[1]) : null;
    }
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
      return res;
    } catch (err) {
      console.error('API Request Error:', err);
      return null;
    }
  }

  // --- Helper to Extract Device Parameter Values ---
  function getParamVal(dev, paramNames) {
    if (!dev) return 'N/A';
    if (!Array.isArray(paramNames)) paramNames = [paramNames];
    for (const name of paramNames) {
      if (dev[name]) {
        if (dev[name]._value !== undefined) return dev[name]._value;
        if (dev[name].value && dev[name].value[0] !== undefined) return dev[name].value[0];
        if (typeof dev[name] === 'string' || typeof dev[name] === 'number') return dev[name];
      }
    }
    return 'N/A';
  }

  // --- Navigation Header ---
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
              <a href="#/${item.id}" class="nav-link ${state.currentRoute === item.id || (state.currentRoute === 'device' && item.id === 'devices') ? 'active' : ''}">
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
            🚪 Logout
          </button>
        </div>
      </header>
    `;
  }

  // --- 1. Login View ---
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

  // --- 2. Overview Dashboard View ---
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
          <div class="card-title">Quick Actions</div>
          <div style="display: flex; gap: 1rem; flex-wrap: wrap;">
            <a href="#/devices" class="btn btn-primary">🔍 Browse Devices</a>
            <a href="#/presets" class="btn btn-secondary">⚙️ Configure Presets</a>
            <a href="#/provisions" class="btn btn-secondary">📜 Edit Provisions</a>
            <a href="#/faults" class="btn btn-secondary">⚠️ View Faults</a>
          </div>
        </div>
      </div>
    `;
  }

  // --- 3. Devices List View ---
  async function loadDevicesData() {
    let url = `/api/devices?limit=${state.filters.limit}&skip=${state.filters.skip}`;
    if (state.filters.search) {
      const q = encodeURIComponent(state.filters.search);
      url += `&query=${q}`;
    }
    const res = await apiFetch(url);
    if (res && res.ok) {
      state.devices = await res.json();
    } else {
      state.devices = [];
    }
  }

  function renderDevicesView() {
    return `
      <div class="main-content fade-in">
        <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 1.5rem; flex-wrap: wrap; gap: 1rem;">
          <h1 style="font-weight: 700;">Devices (${state.devices.length})</h1>
          <div style="display: flex; gap: 0.5rem;">
            <button id="refresh-devices-btn" class="btn btn-secondary">🔄 Refresh List</button>
          </div>
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
                <th>Device ID / Serial</th>
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
                  <td colspan="7" style="text-align: center; color: var(--text-muted); padding: 2rem;">No devices found in database. Click 'Refresh List' to retry.</td>
                </tr>
              ` : state.devices.map(dev => {
                const devId = dev._id || dev.id || (dev._deviceId && dev._deviceId._SerialNumber) || getParamVal(dev, ['DeviceID.SerialNumber']);
                const serial = getParamVal(dev, ['DeviceID.SerialNumber', '_deviceId._SerialNumber']) !== 'N/A' ? getParamVal(dev, ['DeviceID.SerialNumber', '_deviceId._SerialNumber']) : devId;
                const product = getParamVal(dev, ['DeviceID.ProductClass', '_deviceId._ProductClass']);
                const ip = getParamVal(dev, [
                  'InternetGatewayDevice.WANDevice.1.WANConnectionDevice.1.WANIPConnection.1.ExternalIPAddress',
                  'Device.IP.Interface.1.IPv4Address.1.IPAddress'
                ]);
                const mac = getParamVal(dev, [
                  'InternetGatewayDevice.WANDevice.1.WANConnectionDevice.1.WANIPConnection.1.MACAddress',
                  'Device.Ethernet.Interface.1.MACAddress'
                ]);
                const lastInformRaw = dev._lastInform || getParamVal(dev, 'Events.Inform');
                const lastInform = lastInformRaw && lastInformRaw !== 'N/A' ? new Date(lastInformRaw).toLocaleString() : 'N/A';

                return `
                  <tr>
                    <td>
                      <span class="badge badge-online">
                        <span class="dot dot-online"></span> Online
                      </span>
                    </td>
                    <td style="font-weight: 600; font-family: var(--font-mono);">${serial}</td>
                    <td>${product}</td>
                    <td style="font-family: var(--font-mono);">${ip}</td>
                    <td style="font-family: var(--font-mono);">${mac}</td>
                    <td style="color: var(--text-secondary); font-size: 0.8rem;">${lastInform}</td>
                    <td>
                      <a href="#/device/${encodeURIComponent(devId)}" class="btn btn-secondary" style="padding: 0.35rem 0.65rem; font-size: 0.75rem;">Inspect</a>
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

  // --- 4. Device Details View ---
  async function loadDeviceDetailData(id) {
    if (!id || id === 'undefined') return;

    // First try loaded in-memory state
    let found = state.devices.find(d => d._id === id || d.id === id || (d._deviceId && d._deviceId._SerialNumber === id));
    if (found) {
      state.selectedDevice = found;
      return;
    }

    // Try direct API GET endpoint
    let res = await apiFetch(`/api/devices/${encodeURIComponent(id)}`);
    if (res && res.ok) {
      state.selectedDevice = await res.json();
      return;
    }

    // Fallback: Query by _id or Serial Number
    const queryStr = JSON.stringify({ "$or": [{ "_id": id }, { "DeviceID.SerialNumber": id }] });
    res = await apiFetch(`/api/devices?query=${encodeURIComponent(queryStr)}`);
    if (res && res.ok) {
      const arr = await res.json();
      if (arr && arr.length > 0) {
        state.selectedDevice = arr[0];
      }
    }
  }

  function renderDeviceDetailView() {
    const dev = state.selectedDevice;
    if (!dev) {
      return `
        <div class="main-content">
          <p style="padding: 2rem;">Loading device details for ID: <code>${state.routeParam}</code>...</p>
        </div>
      `;
    }

    const serial = dev._id || getParamVal(dev, ['DeviceID.SerialNumber', '_deviceId._SerialNumber']);
    const manufacturer = getParamVal(dev, ['DeviceID.Manufacturer', '_deviceId._Manufacturer']);
    const model = getParamVal(dev, ['DeviceID.ProductClass', '_deviceId._ProductClass']);
    const software = getParamVal(dev, ['InternetGatewayDevice.DeviceInfo.SoftwareVersion', 'Device.DeviceInfo.SoftwareVersion']);
    const ssid = getParamVal(dev, ['InternetGatewayDevice.LANDevice.1.WLANConfiguration.1.SSID', 'Device.WiFi.SSID.1.SSID']);
    const pass = getParamVal(dev, ['InternetGatewayDevice.LANDevice.1.WLANConfiguration.1.KeyPassphrase', 'Device.WiFi.AccessPoint.1.Security.KeyPassphrase']);

    return `
      <div class="main-content fade-in">
        <div style="display: flex; align-items: center; justify-content: space-between; margin-bottom: 1.5rem; flex-wrap: wrap; gap: 1rem;">
          <div>
            <a href="#/devices" style="color: var(--accent-primary); text-decoration: none; font-weight: 500;">← Back to Devices List</a>
            <h1 style="font-weight: 700; margin-top: 0.5rem; font-family: var(--font-mono);">Device: ${serial}</h1>
          </div>
          <div style="display: flex; gap: 0.5rem;">
            <button id="summon-device-btn" class="btn btn-primary">⚡ Summon / Refresh</button>
            <button id="reboot-device-btn" class="btn btn-danger">🔄 Reboot CPE</button>
          </div>
        </div>

        <div class="metrics-grid">
          <div class="metric-card">
            <span class="metric-label">Manufacturer</span>
            <span class="metric-value" style="font-size: 1.15rem;">${manufacturer}</span>
          </div>
          <div class="metric-card">
            <span class="metric-label">Product Model</span>
            <span class="metric-value" style="font-size: 1.15rem;">${model}</span>
          </div>
          <div class="metric-card">
            <span class="metric-label">Software Version</span>
            <span class="metric-value" style="font-size: 1.15rem;">${software}</span>
          </div>
          <div class="metric-card">
            <span class="metric-label">WLAN SSID</span>
            <span class="metric-value" style="font-size: 1.15rem; color: var(--accent-primary);">${ssid}</span>
          </div>
        </div>

        <!-- Quick Wi-Fi & LAN Controller -->
        <div class="card">
          <div class="card-title">📶 Quick Wi-Fi Controller</div>
          <form id="wifi-config-form" style="display: grid; grid-template-columns: repeat(auto-fit, minmax(240px, 1fr)); gap: 1rem; margin-top: 1rem;">
            <div>
              <label style="display: block; margin-bottom: 0.35rem; color: var(--text-secondary);">Wi-Fi SSID</label>
              <input type="text" id="wifi-ssid-input" class="input-text" style="width: 100%;" value="${ssid !== 'N/A' ? ssid : ''}">
            </div>
            <div>
              <label style="display: block; margin-bottom: 0.35rem; color: var(--text-secondary);">Wi-Fi WPA Passphrase</label>
              <input type="text" id="wifi-pass-input" class="input-text" style="width: 100%;" value="${pass !== 'N/A' ? pass : ''}">
            </div>
            <div style="display: flex; align-items: flex-end;">
              <button type="submit" class="btn btn-primary" style="width: 100%;">💾 Apply Wi-Fi Settings</button>
            </div>
          </form>
        </div>

        <!-- TR-069 Parameter Tree Inspector -->
        <div class="card">
          <div class="card-title">
            <span>🌳 TR-069 Parameter Tree</span>
            <input type="text" id="param-filter-input" class="input-text" placeholder="Filter parameters..." style="font-size: 0.8rem; padding: 0.35rem 0.75rem; width: 220px;">
          </div>
          <div class="param-tree" id="param-tree-container">
            ${Object.keys(dev).sort().map(key => {
              const item = dev[key];
              let val = 'N/A';
              if (item && typeof item === 'object') {
                if (item._value !== undefined) val = item._value;
                else if (item.value && item.value[0] !== undefined) val = item.value[0];
                else if (item._object) val = '[Object]';
                else val = JSON.stringify(item);
              } else {
                val = String(item);
              }
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

  // --- 5. Presets View ---
  async function loadPresetsData() {
    const res = await apiFetch('/api/presets');
    if (res && res.ok) {
      state.presets = await res.json();
    }
  }

  function renderPresetsView() {
    return `
      <div class="main-content fade-in">
        <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 1.5rem;">
          <h1 style="font-weight: 700;">Presets (${state.presets.length})</h1>
        </div>
        <div class="table-container">
          <table class="table">
            <thead>
              <tr>
                <th>Name / ID</th>
                <th>Weight</th>
                <th>Channel</th>
                <th>Events</th>
                <th>Provision</th>
              </tr>
            </thead>
            <tbody>
              ${state.presets.length === 0 ? `
                <tr><td colspan="5" style="text-align: center; color: var(--text-muted); padding: 2rem;">No presets found.</td></tr>
              ` : state.presets.map(p => `
                <tr>
                  <td style="font-weight: 600;">${p._id}</td>
                  <td>${p.weight || 0}</td>
                  <td>${p.channel || 'default'}</td>
                  <td>${p.events || '*'}</td>
                  <td style="color: var(--accent-primary);">${p.provision || 'N/A'}</td>
                </tr>
              `).join('')}
            </tbody>
          </table>
        </div>
      </div>
    `;
  }

  // --- 6. Provisions View ---
  async function loadProvisionsData() {
    const res = await apiFetch('/api/provisions');
    if (res && res.ok) {
      state.provisions = await res.json();
    }
  }

  function renderProvisionsView() {
    return `
      <div class="main-content fade-in">
        <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 1.5rem;">
          <h1 style="font-weight: 700;">Provisions (${state.provisions.length})</h1>
        </div>
        <div class="table-container">
          <table class="table">
            <thead>
              <tr>
                <th>Provision ID</th>
                <th>Script Snippet</th>
              </tr>
            </thead>
            <tbody>
              ${state.provisions.length === 0 ? `
                <tr><td colspan="2" style="text-align: center; color: var(--text-muted); padding: 2rem;">No provisions found.</td></tr>
              ` : state.provisions.map(pr => `
                <tr>
                  <td style="font-weight: 600; width: 200px;">${pr._id}</td>
                  <td>
                    <pre style="font-family: var(--font-mono); font-size: 0.8rem; background: var(--bg-main); padding: 0.5rem; border-radius: 6px; overflow-x: auto;">${pr.script || ''}</pre>
                  </td>
                </tr>
              `).join('')}
            </tbody>
          </table>
        </div>
      </div>
    `;
  }

  // --- 7. Fault Logs View ---
  async function loadFaultsData() {
    const res = await apiFetch('/api/faults');
    if (res && res.ok) {
      state.faults = await res.json();
    }
  }

  function renderFaultsView() {
    return `
      <div class="main-content fade-in">
        <h1 style="font-weight: 700; margin-bottom: 1.5rem;">Fault Logs (${state.faults.length})</h1>
        <div class="table-container">
          <table class="table">
            <thead>
              <tr>
                <th>Timestamp</th>
                <th>Device ID</th>
                <th>Code</th>
                <th>Message</th>
              </tr>
            </thead>
            <tbody>
              ${state.faults.length === 0 ? `
                <tr><td colspan="4" style="text-align: center; color: var(--text-muted); padding: 2rem;">No fault logs detected. Systems normal.</td></tr>
              ` : state.faults.map(f => `
                <tr>
                  <td style="font-size: 0.8rem;">${new Date(f.timestamp).toLocaleString()}</td>
                  <td style="font-family: var(--font-mono);">${f.device || f._id}</td>
                  <td style="color: var(--accent-danger); font-weight: 600;">${f.code || 'ERR'}</td>
                  <td>${f.message || 'N/A'}</td>
                </tr>
              `).join('')}
            </tbody>
          </table>
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
    } else if (state.currentRoute === 'presets') {
      await loadPresetsData();
      contentHtml = renderPresetsView();
    } else if (state.currentRoute === 'provisions') {
      await loadProvisionsData();
      contentHtml = renderProvisionsView();
    } else if (state.currentRoute === 'faults') {
      await loadFaultsData();
      contentHtml = renderFaultsView();
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

    // Devices search
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

    // Devices refresh button
    const refreshBtn = document.getElementById('refresh-devices-btn');
    if (refreshBtn) {
      refreshBtn.addEventListener('click', renderApp);
    }

    // Summon device button
    const summonBtn = document.getElementById('summon-device-btn');
    if (summonBtn && state.selectedDevice) {
      summonBtn.addEventListener('click', async () => {
        summonBtn.disabled = true;
        summonBtn.textContent = '⏳ Summoning CPE...';
        const tasks = [{ name: 'getParameterValues', parameterNames: ['InternetGatewayDevice.', 'Device.'] }];
        const res = await apiFetch(`/api/devices/${encodeURIComponent(state.selectedDevice._id)}/tasks`, {
          method: 'POST',
          body: JSON.stringify(tasks)
        });
        if (res && res.ok) {
          alert('CPE Summon triggered successfully!');
          renderApp();
        } else {
          alert('Failed to summon CPE or device offline.');
          summonBtn.disabled = false;
          summonBtn.textContent = '⚡ Summon / Refresh';
        }
      });
    }

    // Reboot CPE button
    const rebootBtn = document.getElementById('reboot-device-btn');
    if (rebootBtn && state.selectedDevice) {
      rebootBtn.addEventListener('click', async () => {
        if (!confirm('Are you sure you want to reboot this CPE device?')) return;
        rebootBtn.disabled = true;
        rebootBtn.textContent = '⏳ Requesting Reboot...';
        const tasks = [{ name: 'reboot' }];
        const res = await apiFetch(`/api/devices/${encodeURIComponent(state.selectedDevice._id)}/tasks`, {
          method: 'POST',
          body: JSON.stringify(tasks)
        });
        if (res && res.ok) {
          alert('Reboot task committed!');
        } else {
          alert('Failed to commit reboot task.');
        }
        rebootBtn.disabled = false;
        rebootBtn.textContent = '🔄 Reboot CPE';
      });
    }

    // Wi-Fi Config Form Submit
    const wifiForm = document.getElementById('wifi-config-form');
    if (wifiForm && state.selectedDevice) {
      wifiForm.addEventListener('submit', async (e) => {
        e.preventDefault();
        const newSsid = document.getElementById('wifi-ssid-input').value;
        const newPass = document.getElementById('wifi-pass-input').value;

        const tasks = [
          {
            name: 'setParameterValues',
            parameterValues: [
              ['InternetGatewayDevice.LANDevice.1.WLANConfiguration.1.SSID', newSsid, 'xsd:string'],
              ['InternetGatewayDevice.LANDevice.1.WLANConfiguration.1.KeyPassphrase', newPass, 'xsd:string']
            ]
          }
        ];

        const res = await apiFetch(`/api/devices/${encodeURIComponent(state.selectedDevice._id)}/tasks`, {
          method: 'POST',
          body: JSON.stringify(tasks)
        });

        if (res && res.ok) {
          alert('Wi-Fi configuration task committed successfully!');
        } else {
          alert('Failed to apply Wi-Fi configuration.');
        }
      });
    }

    // Parameter Tree Filter Input
    const paramFilterInput = document.getElementById('param-filter-input');
    const paramContainer = document.getElementById('param-tree-container');
    if (paramFilterInput && paramContainer) {
      paramFilterInput.addEventListener('input', (e) => {
        const filterVal = e.target.value.toLowerCase();
        const rows = paramContainer.querySelectorAll('.param-row');
        rows.forEach(row => {
          const name = row.querySelector('.param-name')?.textContent.toLowerCase() || '';
          const val = row.querySelector('.param-val')?.textContent.toLowerCase() || '';
          if (name.includes(filterVal) || val.includes(filterVal)) {
            row.style.display = 'flex';
          } else {
            row.style.display = 'none';
          }
        });
      });
    }
  }

  // Initial Boot
  document.addEventListener('DOMContentLoaded', () => {
    parseHash();
    renderApp();
  });
})();

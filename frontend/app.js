/**
 * frontend\app.js
 * Main Frontend Logic: Handles map initialization, data fetching, filtering, 
 * search functionality, and real-time dashboard updates.
 */

document.addEventListener('DOMContentLoaded', () => {
    // Check if user is logged in
    const token = localStorage.getItem('auth_token');
    if (!token && !window.location.pathname.endsWith('login.html') && !window.location.pathname.endsWith('signup.html')) {
        window.location.href = 'login.html';
        return;
    }

    console.log("🚀 NYC Taxi Dashboard - Frontend Started");
    const API_BASE = 'http://127.0.0.1:5000/api';

    // Display user email
    const userEmail = localStorage.getItem('user_email');
    if (userEmail) {
        const userDisplay = document.getElementById('userDisplay');
        if (userDisplay) userDisplay.textContent = userEmail;
    }

    // Logout functionality
    const logoutBtn = document.getElementById('logoutBtn');
    if (logoutBtn) {
        logoutBtn.addEventListener('click', (e) => {
            e.preventDefault();
            localStorage.removeItem('auth_token');
            localStorage.removeItem('user_email');
            window.location.href = 'login.html';
        });
    }

    // Initialize Map
    const map = L.map('map').setView([40.7128, -74.0060], 11);
    L.tileLayer('https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png', {
        attribution: '&copy; OpenStreetMap &copy; CARTO'
    }).addTo(map);

    const startDateInput = document.getElementById('startDate');
    const endDateInput = document.getElementById('endDate');
    const boroughFilter = document.getElementById('boroughFilter');
    const boroughDropdown = document.getElementById('boroughDropdown');
    const boroughTrigger = document.getElementById('boroughTrigger');
    const boroughMenu = document.getElementById('boroughMenu');
    const selectedBoroughSpan = document.getElementById('selectedBorough');
    const zoneSearch = document.getElementById('zoneSearch');
    const searchResults = document.getElementById('searchResults');
    const detailsPanel = document.getElementById('detailsPanel');
    const closePanelBtn = document.getElementById('closePanelBtn');
    const hoverTooltip = document.getElementById('hoverTooltip');
    const loadingState = document.getElementById('loadingState');
    const emptyState = document.getElementById('emptyState');
    const boroughPanel = document.getElementById('boroughPanel');
    const closeBoroughPanelBtn = document.getElementById('closeBoroughPanelBtn');
    const chartLoadingOverlay = document.getElementById('chartLoadingOverlay');

    let geoLayer;
    let allZones = [];
    let gapZones = [];
    let activeFilter = 'all';
    let zonesByBorough = {}; // Cache zones by borough for submenus
    let activeTab = 'rush-hour'; // Default tab

    // Debounce Helper
    function debounce(func, wait) {
        let timeout;
        return function executedFunction(...args) {
            const later = () => {
                clearTimeout(timeout);
                func(...args);
            };
            clearTimeout(timeout);
            timeout = setTimeout(later, wait);
        };
    }

    // Fetch Summary Stats with Filters
    async function updateSummary() {
        try {
            const startDate = startDateInput.value;
            const endDate = endDateInput.value;
            const borough = boroughFilter.value;
            const url = new URL(`${API_BASE}/trips/summary`);
            if (startDate) url.searchParams.append('start_date', startDate);
            if (endDate) url.searchParams.append('end_date', endDate);
            if (borough !== 'all') url.searchParams.append('borough', borough);

            const resp = await fetch(url);
            if (!resp.ok) throw new Error(`API Error: ${resp.status}`);

            const data = await resp.json();

            // Update new Persona-specific labels and remove loading state
            const healthElem = document.getElementById('systemHealth');
            const speedElem = document.getElementById('avgMobilitySpeed');
            const anomaliesElem = document.getElementById('totalAnomalies');

            healthElem.textContent = `${data.systemHealth || 0}%`;
            speedElem.textContent = `${data.avgMobilitySpeed || 0} MPH`;
            anomaliesElem.textContent = (data.totalAnomalies || 0).toLocaleString();

            // Populate Anomaly Tooltip
            if (data.anomalyDetails) {
                document.getElementById('speedAnomCount').textContent = data.anomalyDetails.speed.toLocaleString();
                document.getElementById('fareAnomCount').textContent = data.anomalyDetails.fare.toLocaleString();
            }

            [healthElem, speedElem, anomaliesElem].forEach(el => {
                const card = el.closest('.stat-card');
                if (card) card.classList.remove('loading');
            });

            // Add a "Diagnostic Status" check
            const healthCard = healthElem.closest('.stat-card');
            if (data.systemHealth < 95) {
                healthCard.style.color = '#ff7b72'; // Warning red
            } else {
                healthCard.style.color = '#3fb950'; // Healthy green
            }
        } catch (err) {
            console.error('Error fetching summary:', err);
        }
    }

    // Fetch and Render Zones
    async function loadZones() {
        console.log("🗺️ Loading Diagnostic Maps...");
        loadingState.classList.remove('hidden');
        try {
            const resp = await fetch(`${API_BASE}/zones`);
            if (!resp.ok) throw new Error(`API Error: ${resp.status}`);

            const zones = await resp.json();
            allZones = zones;

            const featureCollection = {
                type: 'FeatureCollection',
                features: zones.map(zone => ({
                    type: 'Feature',
                    geometry: zone.geometry,
                    properties: {
                        id: zone.id,
                        borough: zone.borough,
                        zone: zone.zone
                    }
                }))
            };

            geoLayer = L.geoJSON(featureCollection, {
                style: (feature) => ({
                    color: '#c9d1d9',
                    weight: 1,
                    fillOpacity: 0.1,
                    fillColor: '#58a6ff'
                }),
                onEachFeature: (feature, layer) => {
                    // Hover tooltip
                    layer.on('mouseover', (e) => {
                        const props = feature.properties;
                        const gap = gapZones.find(g => g.zone === props.zone);
                        const status = gap ? '⚠️ Underserved' : '✓ Normal Coverage';

                        hoverTooltip.innerHTML = `
                            <strong>${props.zone}</strong><br>
                            <small>${props.borough}</small><br>
                            <small>${status}</small>
                        `;
                        hoverTooltip.classList.add('visible');
                        updateTooltipPosition(e.originalEvent);
                    });

                    layer.on('mousemove', (e) => {
                        updateTooltipPosition(e.originalEvent);
                    });

                    layer.on('mouseout', () => {
                        hoverTooltip.classList.remove('visible');
                    });

                    // Click to open details panel
                    layer.on('click', () => {
                        openDetailsPanel(feature.properties);
                    });

                    layer.bindPopup(`<b>${feature.properties.zone}</b><br>${feature.properties.borough}`);
                }
            }).addTo(map);

            if (zones.length > 0) map.fitBounds(geoLayer.getBounds());

            loadingState.classList.add('hidden');
            // Load Coverage Gaps (Economic Insight)
            loadCoverageGaps();
        } catch (err) {
            console.error('Error loading zones:', err);
            loadingState.classList.add('hidden');
        }
    }

    async function loadCoverageGaps() {
        try {
            const resp = await fetch(`${API_BASE}/trips/gaps`);
            const gaps = await resp.json();
            console.log("Economic Gaps:", gaps);
            gapZones = gaps;

            // Find zones on map and highlight in orange
            geoLayer.eachLayer(layer => {
                const zoneName = layer.feature.properties.zone;
                const gap = gaps.find(g => g.zone === zoneName);
                if (gap) {
                    layer.setStyle({
                        fillColor: '#f0883e',
                        fillOpacity: 0.6,
                        color: '#f0883e',
                        weight: 2
                    });
                    layer.bindPopup(`⚠️ <b>Underserved: ${zoneName}</b><br>Drop-offs are ${gap.ratio}x Pick-ups.`);
                }
            });
        } catch (err) { console.error(err); }
    }

    // Update Map Styling and View based on Filter
    function updateMapFilter() {
        if (!geoLayer) return;
        const selectedBorough = boroughFilter.value;
        const filteredLayers = [];

        // Diagnostic Map Reset: Ensure all weights and colors are restored before re-applying filter
        geoLayer.eachLayer((layer) => {
            const props = layer.feature.properties;
            const borough = props.borough;
            const isActive = (selectedBorough === 'all' || borough === selectedBorough);

            // Check if this is a known underserved area
            const isGap = gapZones.find(g => g.zone === props.zone);
            const baseColor = isGap ? '#f0883e' : '#58a6ff';
            const outlineColor = isGap ? '#f0883e' : '#c9d1d9';

            if (isActive) {
                layer.setStyle({
                    color: outlineColor,
                    fillColor: baseColor,
                    weight: selectedBorough === 'all' ? (isGap ? 2 : 1) : 3,
                    fillOpacity: selectedBorough === 'all' ? (isGap ? 0.5 : 0.1) : 0.4
                });
                filteredLayers.push(layer);
            } else {
                layer.setStyle({
                    color: '#c9d1d9',
                    fillColor: baseColor,
                    weight: 0.5,
                    fillOpacity: 0.02 // Very faint for non-active boroughs
                });
            }
        });

        if (filteredLayers.length > 0 && selectedBorough !== 'all') {
            const group = L.featureGroup(filteredLayers);
            map.fitBounds(group.getBounds(), { padding: [20, 20] });
        } else if (selectedBorough === 'all' && geoLayer) {
            map.fitBounds(geoLayer.getBounds());
        }
    }

    async function loadHourlyChart() {
        chartLoadingOverlay.classList.remove('hidden');
        try {
            const startDate = startDateInput.value;
            const endDate = endDateInput.value;
            const borough = boroughFilter.value;

            const url = new URL(`${API_BASE}/trips/hourly`);
            if (startDate) url.searchParams.append('start_date', startDate);
            if (endDate) url.searchParams.append('end_date', endDate);
            if (borough !== 'all') url.searchParams.append('borough', borough);

            const resp = await fetch(url);
            const data = await resp.json();

            const chartStatus = Chart.getChart("mainChart");
            if (chartStatus !== undefined) chartStatus.destroy();

            const ctx = document.getElementById('mainChart').getContext('2d');

            // Peak hour identification (Rush Hour)
            const hours = Object.keys(data);
            const counts = Object.values(data).map(d => d.trips);
            const maxVal = Math.max(...counts);

            new Chart(ctx, {
                type: 'bar',
                data: {
                    labels: hours.map(h => `${h}:00`),
                    datasets: [{
                        label: 'Trip Volume',
                        data: counts,
                        backgroundColor: counts.map(c => c === maxVal && c > 0 ? '#f0883e' : '#58a6ff'),
                        borderRadius: 4
                    }]
                },
                options: {
                    responsive: true,
                    plugins: {
                        legend: { display: false },
                        tooltip: {
                            callbacks: {
                                label: (context) => {
                                    const hour = context.label.split(':')[0];
                                    const speed = data[hour].speed;
                                    return [`Trips: ${context.raw}`, `Avg Speed: ${speed} MPH` + (speed < 5 && context.raw > 0 ? ' (⚠️ Congested)' : '')];
                                }
                            }
                        }
                    },
                    scales: {
                        y: { beginAtZero: true, grid: { color: 'rgba(255,255,255,0.1)' } },
                        x: { grid: { display: false } }
                    }
                }
            });
        } catch (err) {
            console.error('Error loading hourly chart:', err);
        } finally {
            chartLoadingOverlay.classList.add('hidden');
        }
    }

    async function loadChart() {
        if (activeTab === 'rush-hour') {
            await loadHourlyChart();
            return;
        }

        chartLoadingOverlay.classList.remove('hidden');
        try {
            const startDate = startDateInput.value;
            const endDate = endDateInput.value;
            const borough = boroughFilter.value;
            const url = new URL(`${API_BASE}/trips/revenue`);
            if (startDate) url.searchParams.append('start_date', startDate);
            if (endDate) url.searchParams.append('end_date', endDate);
            if (borough !== 'all') url.searchParams.append('borough', borough);

            const resp = await fetch(url);
            const data = await resp.json();

            const chartStatus = Chart.getChart("mainChart");
            if (chartStatus !== undefined) chartStatus.destroy();

            const ctx = document.getElementById('mainChart').getContext('2d');
            new Chart(ctx, {
                type: 'bar',
                data: {
                    labels: Object.keys(data),
                    datasets: [{
                        label: 'Congestion Index (Lower is Better)',
                        data: Object.values(data),
                        backgroundColor: '#ff7b72',
                        borderColor: '#ff7b72',
                        borderWidth: 1
                    }]
                },
                options: {
                    responsive: true,
                    plugins: {
                        legend: { display: false }
                    },
                    scales: { y: { beginAtZero: true } }
                }
            });
        } catch (err) {
            console.error('Error loading chart:', err);
        } finally {
            chartLoadingOverlay.classList.add('hidden');
        }
    }

    // Event Listeners
    const tabBtns = document.querySelectorAll('.tab-btn');
    tabBtns.forEach(btn => {
        btn.addEventListener('click', () => {
            tabBtns.forEach(b => b.classList.remove('active'));
            btn.classList.add('active');
            activeTab = btn.dataset.tab;
            loadChart();
        });
    });

    const refreshDashboard = debounce(() => {
        const p1 = updateSummary();
        const p2 = loadChart();
        Promise.all([p1, p2]).then(() => console.log("✨ Dashboard Refresh Complete"));
    }, 400);

    startDateInput.addEventListener('change', refreshDashboard);
    endDateInput.addEventListener('change', refreshDashboard);

    boroughFilter.addEventListener('change', () => {
        updateSummary();
        loadChart();
        updateMapFilter();
    });

    // Search functionality
    zoneSearch.addEventListener('input', (e) => {
        const query = e.target.value.toLowerCase().trim();

        if (query.length === 0) {
            searchResults.classList.remove('active');
            return;
        }

        const matches = allZones.filter(zone =>
            zone.zone.toLowerCase().includes(query) ||
            zone.borough.toLowerCase().includes(query)
        ).slice(0, 10);

        if (matches.length > 0) {
            searchResults.innerHTML = matches.map(zone => `
                <div class="search-result-item" data-zone-id="${zone.id}">
                    <strong>${zone.zone}</strong>
                    <small>${zone.borough}</small>
                </div>
            `).join('');
            searchResults.classList.add('active');

            // Add click handlers to results
            searchResults.querySelectorAll('.search-result-item').forEach(item => {
                item.addEventListener('click', () => {
                    const zoneId = parseInt(item.dataset.zoneId);

                    // Reset borough filter to 'all' to ensure the searched zone is visible
                    boroughFilter.value = 'all';
                    selectedBoroughSpan.textContent = 'All Boroughs';
                    document.querySelectorAll('.dropdown-item').forEach(i => i.classList.remove('active'));

                    updateMapFilter();
                    updateSummary();
                    loadChart();
                    zoomToZone(zoneId);

                    searchResults.classList.remove('active');
                    zoneSearch.value = '';
                });
            });
        } else {
            searchResults.innerHTML = '<div class="search-result-item">No zones found</div>';
            searchResults.classList.add('active');
        }
    });

    // Close search results when clicking outside
    document.addEventListener('click', (e) => {
        if (!e.target.closest('.search-container')) {
            searchResults.classList.remove('active');
        }
    });

    // Custom Borough Dropdown
    boroughTrigger.addEventListener('click', (e) => {
        e.stopPropagation();
        boroughDropdown.classList.toggle('open');
    });

    // Close dropdown when clicking outside
    document.addEventListener('click', (e) => {
        if (!boroughDropdown.contains(e.target)) {
            boroughDropdown.classList.remove('open');
        }
    });

    // Populate zone submenus on hover
    document.querySelectorAll('.dropdown-item.has-submenu').forEach(item => {
        const boroughName = item.dataset.borough;
        const submenu = item.querySelector('.submenu');

        item.addEventListener('mouseenter', () => {
            // Populate submenu if not already done
            if (!submenu.hasChildNodes()) {
                const zones = allZones.filter(z => z.borough === boroughName);

                if (zones.length === 0) {
                    submenu.innerHTML = '<div class="submenu-loading">No zones found</div>';
                } else {
                    submenu.innerHTML = zones.map(zone =>
                        `<div class="submenu-item" data-zone-id="${zone.id}" data-zone-name="${zone.zone}">
                            ${zone.zone}
                        </div>`
                    ).join('');

                    // Add click handlers to zone items
                    submenu.querySelectorAll('.submenu-item').forEach(zoneItem => {
                        zoneItem.addEventListener('click', (e) => {
                            e.stopPropagation();
                            const zoneName = zoneItem.dataset.zoneName;
                            const zoneId = zoneItem.dataset.zoneId;
                            const zoneData = allZones.find(z => z.id == zoneId);

                            if (zoneData) {
                                // Update dropdown display
                                selectedBoroughSpan.textContent = zoneName;
                                boroughDropdown.classList.remove('open');

                                // Reset borough filter to 'all' when focusing a specific zone
                                // to ensure the zone isn't obscured by a previous filter
                                boroughFilter.value = 'all';
                                document.querySelectorAll('.dropdown-item').forEach(i => i.classList.remove('active'));

                                updateMapFilter();
                                updateSummary();
                                loadChart();
                                zoomToZone(parseInt(zoneId));
                            }
                        });
                    });
                }
            }
        });
    });

    // Handle borough selection (clicking on borough name, not zone)
    document.querySelectorAll('.dropdown-item').forEach(item => {
        item.addEventListener('click', (e) => {
            // Only handle direct clicks on the item, not submenu items
            if (e.target.classList.contains('submenu-item')) return;

            const borough = item.dataset.borough;

            // Update active state
            document.querySelectorAll('.dropdown-item').forEach(i => i.classList.remove('active'));
            item.classList.add('active');

            // Update display
            selectedBoroughSpan.textContent = item.querySelector('span').textContent;

            // Update hidden select for compatibility
            boroughFilter.value = borough;

            // Close dropdown
            boroughDropdown.classList.remove('open');

            // Update data
            updateSummary();
            loadChart();
            updateMapFilter();
            openBoroughPanel(borough === 'all' ? null : borough);
        });
    });

    // Filter chips
    document.querySelectorAll('.chip').forEach(chip => {
        chip.addEventListener('click', () => {
            document.querySelectorAll('.chip').forEach(c => c.classList.remove('active'));
            chip.classList.add('active');

            activeFilter = chip.dataset.filter;
            applyQuickFilter(activeFilter);
        });
    });

    // Details panel close button
    closePanelBtn.addEventListener('click', () => {
        detailsPanel.classList.remove('open');
    });

    closeBoroughPanelBtn.addEventListener('click', () => {
        boroughPanel.classList.remove('open');
    });

    // Helper: Zoom to specific zone
    function zoomToZone(zoneId) {
        geoLayer.eachLayer(layer => {
            if (layer.feature.properties.id === zoneId) {
                map.fitBounds(layer.getBounds(), { padding: [50, 50] });
                layer.openPopup();
                openDetailsPanel(layer.feature.properties);
            }
        });
    }

    // Helper: Apply quick filters
    function applyQuickFilter(filter) {
        if (!geoLayer) return;

        let visibleCount = 0;

        geoLayer.eachLayer(layer => {
            const zoneName = layer.feature.properties.zone;
            const isGap = gapZones.find(g => g.zone === zoneName);
            let show = false;

            if (filter === 'all') {
                show = true;
            } else if (filter === 'underserved') {
                show = !!isGap;
            } else if (filter === 'normal') {
                show = !isGap;
            }

            if (show) {
                layer.setStyle({ opacity: 1, fillOpacity: isGap ? 0.6 : 0.3 });
                visibleCount++;
            } else {
                layer.setStyle({ opacity: 0.1, fillOpacity: 0.05 });
            }
        });

        // Show empty state if no zones visible
        if (visibleCount === 0) {
            emptyState.style.display = 'flex';
        } else {
            emptyState.style.display = 'none';
        }
    }


    // Helper: Open details panel with detailed statistics
    async function openDetailsPanel(properties) {
        console.log('🔍 Opening panel for zone:', properties.zone, 'ID:', properties.id);

        // Close borough panel when opening zone details
        boroughPanel.classList.remove('open');

        const gap = gapZones.find(g => g.zone === properties.zone);
        const status = gap ? '⚠️ Underserved Area' : '✓ Normal Coverage';

        // Update header
        document.getElementById('panelZoneName').textContent = properties.zone;

        // Show loading state in panel content
        const panelContent = document.querySelector('#detailsPanel .panel-content');
        panelContent.innerHTML = `
            <div class="panel-section">
                <h4>Location</h4>
                <p>${properties.borough}</p>
            </div>
            <div class="panel-section">
                <h4>Status</h4>
                <p style="color: ${gap ? '#f0883e' : '#3fb950'}">${status}</p>
                ${gap ? `<small style="color: #8b949e;">Drop-offs are ${gap.ratio}x pick-ups</small>` : ''}
            </div>
            <div class="panel-section loading-stats">
                <div class="spinner" style="width: 30px; height: 30px;"></div>
                <p>Loading statistics for ${properties.zone}...</p>
            </div>
        `;

        // Open panel
        detailsPanel.classList.add('open');

        // Fetch detailed statistics
        try {
            const apiUrl = `${API_BASE}/zones/${properties.id}/stats`;
            console.log('📡 Fetching stats from:', apiUrl);

            const resp = await fetch(apiUrl);
            if (!resp.ok) {
                throw new Error(`HTTP ${resp.status}: ${resp.statusText}`);
            }

            const stats = await resp.json();
            console.log('✅ Received stats:', stats);

            // Update panel with detailed information
            panelContent.innerHTML = `
                <div class="panel-section">
                    <h4>Location</h4>
                    <p>${stats.borough}</p>
                </div>
                
                <div class="panel-section">
                    <h4>Status</h4>
                    <p style="color: ${gap ? '#f0883e' : '#3fb950'}">${status}</p>
                    ${gap ? `<small style="color: #8b949e;">Drop-offs are ${gap.ratio}x pick-ups</small>` : ''}
                </div>
                
                <div class="panel-section">
                    <h4>Trip Activity</h4>
                    <div class="stat-row">
                        <span>Pick-ups:</span>
                        <strong>${stats.pickupCount.toLocaleString()}</strong>
                    </div>
                    <div class="stat-row">
                        <span>Drop-offs:</span>
                        <strong>${stats.dropoffCount.toLocaleString()}</strong>
                    </div>
                    <div class="stat-row">
                        <span>Arriving Passengers (DO):</span>
                        <strong>${stats.dropoffPassengers.toLocaleString()}</strong>
                    </div>
                    <div class="stat-row">
                        <span>Departing Passengers (PU):</span>
                        <strong>${stats.pickupPassengers.toLocaleString()}</strong>
                    </div>
                </div>
                
                <div class="panel-section">
                    <h4>Trip Metrics</h4>
                    <div class="stat-row">
                        <span>Avg Distance:</span>
                        <strong>${stats.avgDistance} mi</strong>
                    </div>
                    <div class="stat-row">
                        <span>Avg Duration:</span>
                        <strong>${stats.avgDuration} min</strong>
                    </div>
                    <div class="stat-row">
                        <span>Avg Speed:</span>
                        <strong>${stats.avgSpeed} mph</strong>
                    </div>
                    <div class="stat-row">
                        <span>Avg Fare:</span>
                        <strong>$${stats.avgFare}</strong>
                    </div>
                </div>
                
                <div class="panel-section">
                    <h4>Performance vs Borough</h4>
                    <div class="stat-row">
                        <span>Borough Avg Speed:</span>
                        <strong>${stats.boroughAvgSpeed} mph</strong>
                    </div>
                    <div class="stat-row">
                        <span>Speed Difference:</span>
                        <strong style="color: ${stats.speedComparison >= 0 ? '#3fb950' : '#ff7b72'}">
                            ${stats.speedComparison >= 0 ? '+' : ''}${stats.speedComparison}%
                        </strong>
                    </div>
                </div>
                
                <div class="panel-section">
                    <h4>Coverage Analysis</h4>
                    <p class="info-text">
                        ${stats.coverageRatio > 2
                    ? `⚠️ This zone receives ${stats.coverageRatio}x more drop-offs than pick-ups, indicating potential service gaps.`
                    : stats.coverageRatio < 0.5
                        ? `📍 This zone has ${(1 / stats.coverageRatio).toFixed(1)}x more pick-ups than drop-offs, suggesting it's primarily a departure point.`
                        : `✓ This zone has balanced pick-up and drop-off activity (ratio: ${stats.coverageRatio}).`
                }
                    </p>
                </div>
            `;

            console.log('✅ Panel updated successfully for', stats.zone);

        } catch (err) {
            console.error('❌ Error fetching zone stats:', err);
            panelContent.innerHTML = `
                <div class="panel-section">
                    <h4>Location</h4>
                    <p>${properties.borough}</p>
                </div>
                <div class="panel-section">
                    <h4>Status</h4>
                    <p style="color: ${gap ? '#f0883e' : '#3fb950'}">${status}</p>
                </div>
                <div class="panel-section">
                    <p style="color: #ff7b72;">❌ Failed to load detailed statistics</p>
                    <small style="color: #8b949e;">${err.message}</small>
                </div>
            `;
        }
    }


    // Helper: Update tooltip position
    function updateTooltipPosition(event) {
        const offset = 15;
        hoverTooltip.style.left = (event.clientX + offset) + 'px';
        hoverTooltip.style.top = (event.clientY + offset) + 'px';
    }

    // Focus Mode (Full Screen) Toggle
    const fullscreenBtn = document.getElementById('fullscreenBtn');
    if (fullscreenBtn) {
        fullscreenBtn.addEventListener('click', () => {
            document.body.classList.toggle('focus-mode');
            const isFocus = document.body.classList.contains('focus-mode');

            fullscreenBtn.innerHTML = isFocus
                ? `<svg viewBox="0 0 24 24" width="20" height="20" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><line x1="18" y1="6" x2="6" y2="18"></line><line x1="6" y1="6" x2="18" y2="18"></line></svg>`
                : `<svg viewBox="0 0 24 24" width="20" height="20" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><path d="M15 3h6v6M9 21H3v-6M21 3l-7 7M3 21l7-7"/></svg>`;

            // Critical for Leaflet when container changes size
            setTimeout(() => {
                map.invalidateSize();
                if (geoLayer) map.fitBounds(geoLayer.getBounds());
            }, 300);
        });
    }

    // Helper: Open borough details panel
    async function openBoroughPanel(boroughName) {
        if (!boroughName || boroughName === 'all') {
            boroughPanel.classList.remove('open');
            return;
        }

        console.log('🏛️ Opening borough panel for:', boroughName);
        const panelContent = document.getElementById('boroughPanelContent');
        document.getElementById('panelBoroughName').textContent = `${boroughName} Analysis`;

        // Close zone details panel when opening borough stats
        detailsPanel.classList.remove('open');

        // Show loading
        panelContent.innerHTML = `
            <div class="loading-stats">
                <div class="spinner" style="width: 30px; height: 30px;"></div>
                <p>Aggregating data for ${boroughName}...</p>
            </div>
        `;

        boroughPanel.classList.add('open');

        try {
            const startDate = document.getElementById('startDate').value;
            const endDate = document.getElementById('endDate').value;
            const url = `${API_BASE}/boroughs/${boroughName}/stats?start_date=${startDate}&end_date=${endDate}`;

            const resp = await fetch(url);
            if (!resp.ok) throw new Error('API Failure');
            const stats = await resp.json();

            panelContent.innerHTML = `
                <div class="panel-section">
                    <h4>Overview</h4>
                    <div class="stat-row">
                        <span>Total Zones:</span>
                        <strong>${stats.zoneCount.toLocaleString()}</strong>
                    </div>
                    <div class="stat-row">
                        <span>Total Trips:</span>
                        <strong>${stats.totalTrips.toLocaleString()}</strong>
                    </div>
                </div>

                <div class="panel-section">
                    <h4>Passenger Distribution</h4>
                    <div class="stat-row">
                        <span>Arriving (DO):</span>
                        <strong>${stats.dropoffPassengers.toLocaleString()}</strong>
                    </div>
                    <div class="stat-row">
                        <span>Departing (PU):</span>
                        <strong>${stats.pickupPassengers.toLocaleString()}</strong>
                    </div>
                </div>

                <div class="panel-section">
                    <h4>Efficiency Metrics</h4>
                    <div class="stat-row">
                        <span>Avg Speed:</span>
                        <strong>${stats.avgSpeed} mph</strong>
                    </div>
                    <div class="stat-row">
                        <span>Avg distance:</span>
                        <strong>${stats.avgDistance} mi</strong>
                    </div>
                </div>

                <div class="panel-section">
                    <h4>Network Health</h4>
                    <div class="stat-row underserved-row" title="Click to highlight these zones on map">
                        <span>Underserved Zones:</span>
                        <strong style="color: ${stats.underservedCount > 0 ? '#f0883e' : '#3fb950'}">
                            ${stats.underservedCount}
                        </strong>
                    </div>
                </div>

                <div class="panel-section">
                    <h4>Top Activity Zones</h4>
                    ${stats.topZones.map(z => `
                        <div class="stat-row">
                            <span style="font-size: 0.8rem;">${z.zone}</span>
                            <strong>${z.trips} trips</strong>
                        </div>
                    `).join('')}
                </div>
            `;

            // Add interactivity to underserved count
            const underservedRow = panelContent.querySelector('.underserved-row');
            if (underservedRow && stats.underservedCount > 0) {
                const ids = stats.underservedZones.map(z => z.id);
                underservedRow.addEventListener('click', () => {
                    highlightBoroughZones(boroughName, ids);
                });
            }
        } catch (err) {
            console.error('Error loading borough stats:', err);
            panelContent.innerHTML = `
                <div class="panel-section">
                    <p style="color: #ff7b72;">❌ Error loading borough data</p>
                </div>
            `;
        }
    }

    // Helper: Highlight specific zones within a borough
    function highlightBoroughZones(boroughName, specialIds, color = '#f0883e') {
        if (!geoLayer) return;

        console.log('🎯 Highlighting special zones in:', boroughName, specialIds);

        geoLayer.eachLayer((layer) => {
            const borough = layer.feature.properties.borough;
            const zoneId = layer.feature.properties.id;

            if (borough === boroughName) {
                if (specialIds.includes(zoneId)) {
                    layer.setStyle({
                        weight: 4,
                        fillOpacity: 0.8,
                        fillColor: color,
                        color: color
                    });
                    // Bring to front
                    if (!L.Browser.ie && !L.Browser.opera && !L.Browser.edge) {
                        layer.bringToFront();
                    }
                } else {
                    layer.setStyle({
                        weight: 1.5,
                        fillOpacity: 0.15,
                        fillColor: '#58a6ff',
                        color: '#c9d1d9'
                    });
                }
            } else {
                layer.setStyle({
                    weight: 0.5,
                    fillOpacity: 0.05,
                    fillColor: '#58a6ff'
                });
            }
        });
    }

    // --- Diagnostic Report Logic ---
    const generateReportBtn = document.getElementById('generateReportBtn');
    const reportModal = document.getElementById('reportModal');
    const closeReportBtn = document.getElementById('closeReportBtn');
    const printReportBtn = document.getElementById('printReportBtn');

    async function generateReport() {
        const startDate = startDateInput.value;
        const endDate = endDateInput.value;
        const borough = boroughFilter.value;

        const url = new URL(`${API_BASE}/report`);
        if (startDate) url.searchParams.append('start_date', startDate);
        if (endDate) url.searchParams.append('end_date', endDate);
        if (borough !== 'all') url.searchParams.append('borough', borough);

        try {
            generateReportBtn.disabled = true;
            generateReportBtn.textContent = "Processing...";

            const resp = await fetch(url);
            if (!resp.ok) throw new Error("Report failed");
            const data = await resp.json();

            // Populate Metadata
            document.getElementById('reportMetadata').innerHTML = `
                Scope: <strong>${data.metadata.scope}</strong> | 
                Period: <strong>${data.metadata.period}</strong> | 
                Generated: <strong>${data.metadata.generatedAt}</strong>
                ${data.metadata.boroughMetadata && data.metadata.boroughMetadata.zoneCount ? ` | Total Zones: <strong>${data.metadata.boroughMetadata.zoneCount}</strong>` : ''}
            `;
            // Populate Summary
            const summaryGrid = document.getElementById('reportSummary');
            const metrics = [
                { label: 'Total Trips', val: data.summary.totalTrips.toLocaleString() },
                { label: 'Revenue', val: `$${data.summary.totalRevenue.toLocaleString()}` },
                { label: 'Avg Speed', val: `${data.summary.avgSpeed} MPH` },
                { label: 'Avg Distance', val: `${data.summary.avgDistance} MI` },
                { label: 'Health Score', val: `${data.summary.systemHealth}%` },
                { label: 'Choke Points', val: data.summary.activeChokePoints }
            ];

            // Add Passenger Distribution and Total Zones if borough metadata exists
            if (data.metadata.boroughMetadata && data.metadata.boroughMetadata.pickupPassengers !== undefined) {
                metrics.push({ label: 'Total Zones', val: data.metadata.boroughMetadata.zoneCount });
                metrics.push({ label: 'PU Passengers', val: data.metadata.boroughMetadata.pickupPassengers.toLocaleString() });
                metrics.push({ label: 'DO Passengers', val: data.metadata.boroughMetadata.dropoffPassengers.toLocaleString() });
            }
            summaryGrid.innerHTML = metrics.map(m => `
                <div class="report-stat-card">
                    <small>${m.label}</small>
                    <strong>${m.val}</strong>
                </div>
            `).join('');

            // Populate Top Zones
            const tbody = document.querySelector('#reportTopZones tbody');
            tbody.innerHTML = data.topZones.map(z => `
                <tr>
                    <td><strong>${z.zone}</strong></td>
                    <td>${z.borough}</td>
                    <td>${z.trips.toLocaleString()}</td>
                    <td>${z.speed} MPH</td>
                </tr>
            `).join('');

            // Populate Gaps (Use full list if borough metadata for better detail)
            const gapsList = document.getElementById('reportGaps');
            const displayGaps = (data.metadata.boroughMetadata && data.metadata.boroughMetadata.underservedZones)
                ? data.metadata.boroughMetadata.underservedZones
                : data.coverageGaps;

            if (displayGaps && displayGaps.length > 0) {
                gapsList.innerHTML = displayGaps.map(g => `
                    <div class="report-stat-card" style="margin-bottom: 0.5rem; border-left: 4px solid #f0883e;">
                        <strong>${g.zone} (${g.borough || data.metadata.scope})</strong>
                        <p style="margin:0; font-size:0.85rem; color:#57606a;">
                            Critical service gap detected. ${g.ratio ? `Drop-offs exceed pick-ups by ${g.ratio}x.` : 'Underserved area.'}
                        </p>
                    </div>
                `).join('');
            } else {
                gapsList.innerHTML = "<p>No critical coverage gaps detected in this scope.</p>";
            }

            // Show Modal
            reportModal.classList.add('open');

        } catch (err) {
            console.error("Report generation error:", err);
            alert("Failed to generate report. Please check server connection.");
        } finally {
            generateReportBtn.disabled = false;
            generateReportBtn.textContent = "Generate Report";
        }
    }

    generateReportBtn.addEventListener('click', generateReport);
    closeReportBtn.addEventListener('click', () => reportModal.classList.remove('open'));
    printReportBtn.addEventListener('click', () => window.print());

    // Close on overlay click
    reportModal.addEventListener('click', (e) => {
        if (e.target === reportModal) reportModal.classList.remove('open');
    });

    // Init order: loadZones needs to finish before updateMapFilter works
    updateSummary();
    loadZones().then(() => {
        updateMapFilter();
    });
    loadChart();
});

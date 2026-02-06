/**
 * DMARC Dashboard - Geographic Map Page Module
 * World map with circle markers (choropleth), country popups, IP geolocation, top countries panel.
 * Requires Leaflet.js CDN in index.html.
 *
 * Security: All dynamic content uses safe DOM construction (textContent, createElement).
 */
(function() {
    'use strict';

    var API_BASE = '/api';

    // Country centroids for circle marker placement (ISO Alpha-2 -> [lat, lng])
    var COUNTRY_CENTROIDS = {
        US:[39.8,-98.6],CA:[56.1,-106.3],GB:[55.4,-3.4],DE:[51.2,10.5],FR:[46.2,2.2],
        JP:[36.2,138.3],CN:[35.9,104.2],IN:[20.6,78.9],BR:[-14.2,-51.9],AU:[-25.3,133.8],
        RU:[61.5,105.3],ZA:[-30.6,22.9],MX:[23.6,-102.6],KR:[35.9,127.8],IT:[41.9,12.6],
        ES:[40.5,-3.7],NL:[52.1,5.3],SE:[60.1,18.6],NO:[60.5,8.5],FI:[61.9,25.7],
        DK:[56.3,9.5],PL:[51.9,19.1],CH:[46.8,8.2],AT:[47.5,14.6],BE:[50.5,4.5],
        IE:[53.1,-8.2],PT:[39.4,-8.2],SG:[1.4,103.8],HK:[22.4,114.1],TW:[23.7,121.0],
        NZ:[-40.9,174.9],AR:[-38.4,-63.6],CL:[-35.7,-71.5],CO:[4.6,-74.3],
        EG:[26.8,30.8],NG:[9.1,8.7],KE:[-1.3,36.8],GH:[7.9,-1.0],
        TH:[15.9,100.9],VN:[14.1,108.3],MY:[4.2,101.7],ID:[-0.8,113.9],
        PH:[12.9,121.8],PK:[30.4,69.3],BD:[23.7,90.4],LK:[7.9,80.8],
        SA:[23.9,45.1],AE:[23.4,53.8],IL:[31.0,34.9],TR:[39.0,35.2],
        UA:[48.4,31.2],CZ:[49.8,15.5],RO:[45.9,24.9],HU:[47.2,19.5],
        GR:[39.1,21.8],HR:[45.1,15.2],BG:[42.7,25.5],RS:[44.0,21.0],
        SK:[48.7,19.7],LT:[55.2,23.9],LV:[56.9,24.1],EE:[58.6,25.0],
        IS:[64.9,-19.0],MT:[35.9,14.4],LU:[49.8,6.1],CY:[35.1,33.4],
        PE:[-9.2,-75.0],VE:[6.4,-66.6],EC:[-1.8,-78.2],BO:[-16.3,-63.6],
        UY:[-32.5,-55.8],PY:[-23.4,-58.4],CR:[9.7,-83.8],PA:[8.5,-80.8],
        DO:[18.7,-70.2],CU:[21.5,-77.8],JM:[18.1,-77.3],TT:[10.7,-61.2],
        GT:[15.8,-90.2],HN:[15.2,-86.2],SV:[13.8,-88.9],NI:[12.9,-85.2],
        MA:[31.8,-7.1],TN:[33.9,9.5],DZ:[28.0,1.7],LY:[26.3,17.2],
        SD:[12.9,30.2],ET:[9.1,40.5],TZ:[-6.4,34.9],UG:[1.4,32.3],
        RW:[-1.9,29.9],AO:[-11.2,17.9],MZ:[-18.7,35.5],ZW:[-19.0,29.2],
        CM:[7.4,12.4],SN:[14.5,-14.5],CI:[7.5,-5.5],ML:[17.6,-4.0],
        BF:[12.2,-1.6],NE:[17.6,8.1],TD:[15.5,18.7],MG:[-18.8,46.9],
        MM:[21.9,95.9],KH:[12.6,105.0],LA:[19.9,102.5],NP:[28.4,84.1],
        AF:[33.9,67.7],IQ:[33.2,43.7],IR:[32.4,53.7],SY:[35.0,38.5],
        JO:[30.6,36.2],LB:[33.9,35.9],KW:[29.3,47.5],QA:[25.4,51.2],
        BH:[26.0,50.6],OM:[21.5,55.9],YE:[15.6,48.5]
    };

    function countryFlag(code) {
        if (!code || code.length !== 2) return '';
        var c = code.toUpperCase();
        return String.fromCodePoint(0x1F1E6 + c.charCodeAt(0) - 65) +
               String.fromCodePoint(0x1F1E6 + c.charCodeAt(1) - 65);
    }

    /**
     * Create a DOM element with properties and children.
     */
    function el(tag, props, children) {
        var elem = document.createElement(tag);
        if (props) {
            Object.keys(props).forEach(function(key) {
                if (key === 'textContent') {
                    elem.textContent = props[key];
                } else if (key === 'className') {
                    elem.className = props[key];
                } else if (key === 'hidden') {
                    elem.hidden = props[key];
                } else if (key === 'style') {
                    elem.setAttribute('style', props[key]);
                } else {
                    elem.setAttribute(key, props[key]);
                }
            });
        }
        if (children) {
            children.forEach(function(child) {
                if (typeof child === 'string') {
                    elem.appendChild(document.createTextNode(child));
                } else if (child) {
                    elem.appendChild(child);
                }
            });
        }
        return elem;
    }

    var GeoMapPage = {
        initialized: false,
        map: null,
        markers: [],
        lookupMarker: null,
        selectedDays: 30,
        geoData: [],

        init: function() {
            if (this.initialized) return;
            this.initialized = true;
            this._buildPage();
            this._bindEvents();
        },

        load: function() {
            var self = this;
            // Delay map init slightly to let the section become visible
            setTimeout(function() {
                self._initMap();
                self._loadGeoData();
            }, 100);
        },

        destroy: function() {
            this._clearMarkers();
        },

        _buildPage: function() {
            var section = document.getElementById('page-geomap');
            if (!section) return;

            section.textContent = '';

            var page = el('div', { className: 'geomap-page' });

            // Header
            var header = el('div', { className: 'geomap-header' });
            header.appendChild(el('h2', { className: 'page-title', textContent: 'Geographic Map' }));

            var controls = el('div', { className: 'geomap-controls' });
            var daysSelector = el('div', { className: 'geomap-days-selector' });
            [{ d: 7, label: '7d' }, { d: 30, label: '30d' }, { d: 90, label: '90d' }].forEach(function(opt) {
                daysSelector.appendChild(el('button', {
                    className: 'btn-sm geomap-days-btn' + (opt.d === 30 ? ' active' : ''),
                    'data-days': String(opt.d),
                    textContent: opt.label
                }));
            });
            controls.appendChild(daysSelector);
            controls.appendChild(el('button', { id: 'geoResetView', className: 'btn-ghost btn-sm', textContent: 'Reset View', title: 'Reset map view' }));
            header.appendChild(controls);
            page.appendChild(header);

            // Layout: map + side panel
            var layout = el('div', { className: 'geomap-layout' });

            // Map area
            var mapArea = el('div', { className: 'geomap-map-area' });

            // IP lookup bar
            var lookupBar = el('div', { className: 'geomap-ip-lookup' });
            lookupBar.appendChild(el('input', {
                type: 'text', id: 'geoIPInput', className: 'geomap-ip-input',
                placeholder: 'Lookup IP location...', autocomplete: 'off'
            }));
            lookupBar.appendChild(el('button', { id: 'geoIPLookupBtn', className: 'btn-primary btn-sm', textContent: 'Pin' }));
            mapArea.appendChild(lookupBar);

            // Map container
            mapArea.appendChild(el('div', { id: 'geoMapContainer', className: 'geomap-container' }));

            // Legend
            var legend = el('div', { className: 'geomap-legend' });
            legend.appendChild(el('span', { className: 'geomap-legend-label', textContent: 'Email Volume:' }));
            var gradientDiv = el('div', { className: 'geomap-legend-gradient' });
            gradientDiv.appendChild(el('span', { textContent: 'Low' }));
            gradientDiv.appendChild(el('div', { className: 'geomap-gradient-bar' }));
            gradientDiv.appendChild(el('span', { textContent: 'High' }));
            legend.appendChild(gradientDiv);
            mapArea.appendChild(legend);

            layout.appendChild(mapArea);

            // Side panel
            var sidePanel = el('div', { className: 'geomap-side-panel' });
            sidePanel.appendChild(el('h3', { textContent: 'Top Countries' }));
            var topCountries = el('div', { id: 'geoTopCountries', className: 'geomap-top-countries' });
            topCountries.appendChild(el('div', { className: 'loading', textContent: 'Loading...' }));
            sidePanel.appendChild(topCountries);
            layout.appendChild(sidePanel);

            page.appendChild(layout);
            section.appendChild(page);
        },

        _bindEvents: function() {
            var self = this;

            // Days selector
            var section = document.getElementById('page-geomap');
            if (section) {
                section.addEventListener('click', function(e) {
                    var btn = e.target.closest('.geomap-days-btn');
                    if (btn) {
                        var days = parseInt(btn.dataset.days, 10);
                        self.selectedDays = days;
                        section.querySelectorAll('.geomap-days-btn').forEach(function(b) { b.classList.remove('active'); });
                        btn.classList.add('active');
                        self._loadGeoData();
                    }
                });
            }

            // Reset view
            var resetBtn = document.getElementById('geoResetView');
            if (resetBtn) {
                resetBtn.addEventListener('click', function() {
                    if (self.map) self.map.setView([20, 0], 2);
                });
            }

            // IP lookup
            var lookupBtn = document.getElementById('geoIPLookupBtn');
            var ipInput = document.getElementById('geoIPInput');
            if (lookupBtn) {
                lookupBtn.addEventListener('click', function() { self._lookupIP(); });
            }
            if (ipInput) {
                ipInput.addEventListener('keydown', function(e) {
                    if (e.key === 'Enter') self._lookupIP();
                });
            }
        },

        _initMap: function() {
            if (this.map) {
                this.map.invalidateSize();
                return;
            }

            var container = document.getElementById('geoMapContainer');
            if (!container) return;

            if (typeof L === 'undefined') {
                container.textContent = 'Leaflet.js not loaded. Please check CDN link in index.html.';
                return;
            }

            this.map = L.map('geoMapContainer', {
                center: [20, 0],
                zoom: 2,
                minZoom: 2,
                maxZoom: 12,
                worldCopyJump: true
            });

            L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
                attribution: '&copy; OpenStreetMap contributors',
                maxZoom: 18
            }).addTo(this.map);
        },

        _loadGeoData: async function() {
            try {
                var response = await fetch(API_BASE + '/analytics/geolocation/map?days=' + this.selectedDays);
                if (!response.ok) throw new Error('HTTP ' + response.status);
                var data = await response.json();
                this.geoData = Array.isArray(data) ? data : [];
                this._renderChoropleth();
                this._renderTopCountries();
            } catch (err) {
                console.error('Failed to load geo data:', err);
                var panel = document.getElementById('geoTopCountries');
                if (panel) {
                    panel.textContent = '';
                    panel.appendChild(el('div', { className: 'threat-error', textContent: 'Failed to load geographic data' }));
                }
            }
        },

        _renderChoropleth: function() {
            this._clearMarkers();
            if (!this.map || this.geoData.length === 0) return;

            // Find max volume for scaling
            var maxVol = 1;
            for (var i = 0; i < this.geoData.length; i++) {
                if (this.geoData[i].total_emails > maxVol) {
                    maxVol = this.geoData[i].total_emails;
                }
            }

            var self = this;
            this.geoData.forEach(function(country) {
                var centroid = COUNTRY_CENTROIDS[country.country_code];
                if (!centroid) return;

                var ratio = country.total_emails / maxVol;
                var radius = Math.max(8, Math.sqrt(ratio) * 40);
                var color = self._volumeColor(ratio);
                var passRate = country.total_emails > 0
                    ? ((country.pass_count / country.total_emails) * 100).toFixed(1)
                    : '0.0';
                var failRate = country.total_emails > 0
                    ? ((country.fail_count / country.total_emails) * 100).toFixed(1)
                    : '0.0';

                var marker = L.circleMarker(centroid, {
                    radius: radius,
                    fillColor: color,
                    color: '#ffffff',
                    weight: 1,
                    opacity: 0.9,
                    fillOpacity: 0.7
                }).addTo(self.map);

                // Build popup using safe DOM methods
                var popupEl = el('div', { className: 'geomap-popup' });
                popupEl.appendChild(el('h4', { textContent: countryFlag(country.country_code) + ' ' + (country.country_name || country.country_code) }));
                var stats = el('div', { className: 'geomap-popup-stats' });
                stats.appendChild(el('div', null, [
                    el('strong', { textContent: 'Total Emails: ' }),
                    document.createTextNode((country.total_emails || 0).toLocaleString())
                ]));
                var passDiv = el('div', null, [el('strong', { textContent: 'Pass Rate: ' })]);
                passDiv.appendChild(el('span', { style: 'color:var(--accent-success)', textContent: passRate + '%' }));
                stats.appendChild(passDiv);
                var failDiv = el('div', null, [el('strong', { textContent: 'Fail Rate: ' })]);
                failDiv.appendChild(el('span', { style: 'color:var(--accent-danger)', textContent: failRate + '%' }));
                stats.appendChild(failDiv);
                stats.appendChild(el('div', null, [
                    el('strong', { textContent: 'Unique IPs: ' }),
                    document.createTextNode((country.unique_ips || 0).toLocaleString())
                ]));
                popupEl.appendChild(stats);

                marker.bindPopup(popupEl);
                self.markers.push(marker);
            });
        },

        _renderTopCountries: function() {
            var panel = document.getElementById('geoTopCountries');
            if (!panel) return;

            panel.textContent = '';

            if (this.geoData.length === 0) {
                panel.appendChild(el('div', { className: 'threat-empty', textContent: 'No geographic data available' }));
                return;
            }

            var sorted = this.geoData.slice().sort(function(a, b) {
                return (b.total_emails || 0) - (a.total_emails || 0);
            });

            var maxVol = sorted[0] ? sorted[0].total_emails : 1;

            sorted.slice(0, 20).forEach(function(country, idx) {
                var pct = maxVol > 0 ? ((country.total_emails / maxVol) * 100).toFixed(0) : 0;
                var passRate = country.total_emails > 0
                    ? ((country.pass_count / country.total_emails) * 100).toFixed(1)
                    : '0.0';

                var item = el('div', { className: 'geomap-country-item' });
                item.appendChild(el('div', { className: 'geomap-country-rank', textContent: String(idx + 1) }));

                var info = el('div', { className: 'geomap-country-info' });
                info.appendChild(el('div', {
                    className: 'geomap-country-name',
                    textContent: countryFlag(country.country_code) + ' ' + (country.country_name || country.country_code)
                }));

                var barWrap = el('div', { className: 'geomap-country-bar-wrap' });
                barWrap.appendChild(el('div', { className: 'geomap-country-bar', style: 'width:' + pct + '%' }));
                info.appendChild(barWrap);

                var meta = el('div', { className: 'geomap-country-meta' });
                meta.appendChild(el('span', { textContent: (country.total_emails || 0).toLocaleString() + ' emails' }));
                meta.appendChild(el('span', { className: 'geomap-pass-rate', textContent: passRate + '% pass' }));
                info.appendChild(meta);

                item.appendChild(info);
                panel.appendChild(item);
            });
        },

        _lookupIP: async function() {
            var input = document.getElementById('geoIPInput');
            if (!input) return;
            var ip = input.value.trim();
            if (!ip || !/^[\d.:a-fA-F]+$/.test(ip)) return;

            try {
                var response = await fetch(API_BASE + '/analytics/geolocation/lookup/' + encodeURIComponent(ip));
                if (!response.ok) throw new Error('HTTP ' + response.status);
                var data = await response.json();

                if (this.lookupMarker && this.map) {
                    this.map.removeLayer(this.lookupMarker);
                    this.lookupMarker = null;
                }

                if (data.latitude && data.longitude && this.map) {
                    this.lookupMarker = L.marker([data.latitude, data.longitude]).addTo(this.map);

                    // Build popup with safe DOM methods
                    var popupEl = el('div', { className: 'geomap-popup' });
                    popupEl.appendChild(el('h4', { textContent: data.ip || ip }));
                    var stats = el('div', { className: 'geomap-popup-stats' });
                    stats.appendChild(el('div', null, [el('strong', { textContent: 'Country: ' }), document.createTextNode(data.country || 'N/A')]));
                    stats.appendChild(el('div', null, [el('strong', { textContent: 'City: ' }), document.createTextNode(data.city || 'N/A')]));
                    stats.appendChild(el('div', null, [el('strong', { textContent: 'ISP: ' }), document.createTextNode(data.isp || 'N/A')]));
                    stats.appendChild(el('div', null, [el('strong', { textContent: 'Coords: ' }), document.createTextNode(data.latitude.toFixed(4) + ', ' + data.longitude.toFixed(4))]));
                    popupEl.appendChild(stats);

                    this.lookupMarker.bindPopup(popupEl).openPopup();
                    this.map.setView([data.latitude, data.longitude], 6);
                } else {
                    if (typeof showNotification === 'function') {
                        showNotification('No location data found for ' + ip, 'error');
                    }
                }
            } catch (err) {
                if (typeof showNotification === 'function') {
                    showNotification('Failed to look up IP location: ' + err.message, 'error');
                }
            }
        },

        _clearMarkers: function() {
            if (this.map) {
                for (var i = 0; i < this.markers.length; i++) {
                    this.map.removeLayer(this.markers[i]);
                }
            }
            this.markers = [];
        },

        _volumeColor: function(ratio) {
            // Light blue to dark blue gradient
            var r = Math.round(200 - ratio * 170);
            var g = Math.round(220 - ratio * 180);
            var b = Math.round(255 - ratio * 50);
            return 'rgb(' + r + ',' + g + ',' + b + ')';
        }
    };

    // Register with router
    window.DMARC = window.DMARC || {};
    window.DMARC.GeoMapPage = GeoMapPage;

    if (window.DMARC.Router) {
        window.DMARC.Router.register('geomap', GeoMapPage);
    }
})();

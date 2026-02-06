/**
 * DMARC Dashboard - Saved Views Module
 *
 * Two parts:
 *   1. Quick-switch dropdown near the filter bar on the dashboard
 *   2. Full management page (#page-saved-views) with list, rename, delete, set default
 */
(function() {
    'use strict';

    var API_BASE = '/api';

    var SavedViewsPage = {
        initialized: false,
        containerId: 'page-saved-views',
        views: [],
        quickSwitchInitialized: false,

        // ---- Quick Switch (filter bar integration) ----

        initQuickSwitch: function() {
            if (this.quickSwitchInitialized) return;
            this.quickSwitchInitialized = true;

            var filterActions = document.querySelector('.filter-actions');
            if (!filterActions) return;

            var self = this;

            // Create saved views dropdown container
            var wrapper = document.createElement('div');
            wrapper.className = 'dropdown';
            wrapper.id = 'savedViewsQuickSwitch';
            wrapper.style.position = 'relative';

            var trigger = document.createElement('button');
            trigger.className = 'btn-ghost btn-sm';
            trigger.type = 'button';
            trigger.textContent = 'Saved Views';
            wrapper.appendChild(trigger);

            var menu = document.createElement('div');
            menu.className = 'dropdown-menu';
            menu.id = 'savedViewsQuickMenu';
            menu.hidden = true;
            menu.style.cssText = 'min-width: 220px; max-height: 320px; overflow-y: auto;';
            wrapper.appendChild(menu);

            trigger.addEventListener('click', function(e) {
                e.stopPropagation();
                var isHidden = menu.hidden;
                menu.hidden = !isHidden;
                if (!menu.hidden) {
                    self._loadViews(function() {
                        self._renderQuickMenu(menu);
                    });
                }
            });

            document.addEventListener('click', function(e) {
                if (!wrapper.contains(e.target)) {
                    menu.hidden = true;
                }
            });

            filterActions.appendChild(wrapper);
        },

        _renderQuickMenu: function(menu) {
            while (menu.firstChild) menu.removeChild(menu.firstChild);
            var self = this;

            if (this.views.length === 0) {
                var empty = document.createElement('div');
                empty.style.cssText = 'padding: 16px; text-align: center; color: var(--text-muted); font-size: 0.85rem;';
                empty.textContent = 'No saved views';
                menu.appendChild(empty);
            } else {
                this.views.forEach(function(view) {
                    var btn = document.createElement('button');
                    btn.setAttribute('role', 'menuitem');
                    btn.style.cssText = 'display: flex; align-items: center; gap: 8px; width: 100%;';
                    if (view.is_default) {
                        var star = document.createElement('span');
                        star.textContent = '*';
                        star.style.color = 'var(--accent-warning)';
                        btn.appendChild(star);
                    }
                    var nameSpan = document.createElement('span');
                    nameSpan.textContent = view.name;
                    btn.appendChild(nameSpan);
                    if (view.use_count) {
                        var countSpan = document.createElement('span');
                        countSpan.style.cssText = 'margin-left: auto; font-size: 0.75rem; color: var(--text-muted);';
                        countSpan.textContent = view.use_count + 'x';
                        btn.appendChild(countSpan);
                    }
                    btn.addEventListener('click', function() {
                        self._applyView(view);
                        menu.hidden = true;
                    });
                    menu.appendChild(btn);
                });
            }

            // Divider
            var divider = document.createElement('div');
            divider.className = 'dropdown-divider';
            divider.setAttribute('role', 'separator');
            menu.appendChild(divider);

            // Save current filters
            var saveBtn = document.createElement('button');
            saveBtn.setAttribute('role', 'menuitem');
            saveBtn.textContent = 'Save Current Filters...';
            saveBtn.addEventListener('click', function() {
                menu.hidden = true;
                self._showSaveModal();
            });
            menu.appendChild(saveBtn);

            // Manage link
            var manageBtn = document.createElement('button');
            manageBtn.setAttribute('role', 'menuitem');
            manageBtn.textContent = 'Manage Views';
            manageBtn.addEventListener('click', function() {
                menu.hidden = true;
                if (window.DMARC && window.DMARC.Router) {
                    window.DMARC.Router.navigate('saved-views');
                }
            });
            menu.appendChild(manageBtn);
        },

        _showSaveModal: function() {
            var self = this;

            // Create a simple modal overlay
            var overlay = document.createElement('div');
            overlay.className = 'modal';
            overlay.setAttribute('role', 'dialog');
            overlay.setAttribute('aria-modal', 'true');
            overlay.style.cssText = 'display: flex;';

            var content = document.createElement('div');
            content.className = 'modal-content';
            content.style.maxWidth = '400px';

            var header = document.createElement('div');
            header.className = 'modal-header';
            var title = document.createElement('h2');
            title.textContent = 'Save Current View';
            header.appendChild(title);
            var closeBtn = document.createElement('button');
            closeBtn.className = 'modal-close';
            closeBtn.setAttribute('aria-label', 'Close');
            closeBtn.textContent = 'X';
            closeBtn.addEventListener('click', function() {
                document.body.removeChild(overlay);
            });
            header.appendChild(closeBtn);
            content.appendChild(header);

            var body = document.createElement('div');
            body.className = 'modal-body';
            body.style.padding = '24px';

            var label = document.createElement('label');
            label.textContent = 'View Name';
            label.style.cssText = 'display: block; font-size: 0.85rem; font-weight: 500; color: var(--text-secondary); margin-bottom: 8px;';
            body.appendChild(label);

            var input = document.createElement('input');
            input.type = 'text';
            input.placeholder = 'e.g., Failed last 7 days';
            input.style.cssText = 'width: 100%; padding: 8px 12px; border: 1px solid var(--border-color); border-radius: 6px; background: var(--bg-primary); color: var(--text-primary); font-size: 0.9rem;';
            body.appendChild(input);

            var defaultLabel = document.createElement('label');
            defaultLabel.style.cssText = 'display: flex; align-items: center; gap: 8px; margin-top: 12px; font-size: 0.85rem; color: var(--text-secondary); cursor: pointer;';
            var defaultCheck = document.createElement('input');
            defaultCheck.type = 'checkbox';
            defaultLabel.appendChild(defaultCheck);
            defaultLabel.appendChild(document.createTextNode('Set as default view'));
            body.appendChild(defaultLabel);

            content.appendChild(body);

            var footer = document.createElement('div');
            footer.style.cssText = 'padding: 16px 24px; display: flex; justify-content: flex-end; gap: 8px; border-top: 1px solid var(--border-color);';
            var cancelBtn = document.createElement('button');
            cancelBtn.className = 'btn-secondary';
            cancelBtn.textContent = 'Cancel';
            cancelBtn.addEventListener('click', function() {
                document.body.removeChild(overlay);
            });
            footer.appendChild(cancelBtn);

            var saveModalBtn = document.createElement('button');
            saveModalBtn.className = 'btn-primary';
            saveModalBtn.textContent = 'Save View';
            saveModalBtn.addEventListener('click', function() {
                var name = input.value.trim();
                if (!name) {
                    input.style.borderColor = 'var(--accent-danger)';
                    return;
                }
                self._saveCurrentView(name, defaultCheck.checked, function() {
                    document.body.removeChild(overlay);
                });
            });
            footer.appendChild(saveModalBtn);
            content.appendChild(footer);

            overlay.appendChild(content);

            // Close on backdrop click
            overlay.addEventListener('click', function(e) {
                if (e.target === overlay) {
                    document.body.removeChild(overlay);
                }
            });

            document.body.appendChild(overlay);
            input.focus();
        },

        _saveCurrentView: function(name, isDefault, callback) {
            // Gather current filters from DOM
            var filters = {};
            var domainFilter = document.getElementById('domainFilter');
            if (domainFilter && domainFilter.value) filters.domain = domainFilter.value;
            var dateRangeFilter = document.getElementById('dateRangeFilter');
            if (dateRangeFilter && dateRangeFilter.value) filters.days = dateRangeFilter.value;
            var spfFilter = document.getElementById('spfFilter');
            if (spfFilter && spfFilter.value) filters.spf = spfFilter.value;
            var dkimFilter = document.getElementById('dkimFilter');
            if (dkimFilter && dkimFilter.value) filters.dkim = dkimFilter.value;
            var dispositionFilter = document.getElementById('dispositionFilter');
            if (dispositionFilter && dispositionFilter.value) filters.disposition = dispositionFilter.value;
            var sourceIpFilter = document.getElementById('sourceIpFilter');
            if (sourceIpFilter && sourceIpFilter.value) filters.source_ip = sourceIpFilter.value;
            var orgNameFilter = document.getElementById('orgNameFilter');
            if (orgNameFilter && orgNameFilter.value) filters.org_name = orgNameFilter.value;

            fetch(API_BASE + '/saved-views', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ name: name, filters: filters, is_default: isDefault })
            })
            .then(function(r) {
                if (r.ok) {
                    if (typeof showNotification === 'function') {
                        showNotification('View "' + name + '" saved', 'success');
                    }
                    if (callback) callback();
                } else {
                    if (typeof showNotification === 'function') {
                        showNotification('Failed to save view', 'error');
                    }
                }
            })
            .catch(function() {
                if (typeof showNotification === 'function') {
                    showNotification('Failed to save view', 'error');
                }
            });
        },

        _applyView: function(view) {
            if (!view || !view.filters) return;
            var f = view.filters;

            // Apply to filter form elements
            var domainFilter = document.getElementById('domainFilter');
            if (domainFilter) domainFilter.value = f.domain || '';
            var dateRangeFilter = document.getElementById('dateRangeFilter');
            if (dateRangeFilter) dateRangeFilter.value = f.days || '365';
            var spfFilter = document.getElementById('spfFilter');
            if (spfFilter) spfFilter.value = f.spf || '';
            var dkimFilter = document.getElementById('dkimFilter');
            if (dkimFilter) dkimFilter.value = f.dkim || '';
            var dispositionFilter = document.getElementById('dispositionFilter');
            if (dispositionFilter) dispositionFilter.value = f.disposition || '';
            var sourceIpFilter = document.getElementById('sourceIpFilter');
            if (sourceIpFilter) sourceIpFilter.value = f.source_ip || '';
            var orgNameFilter = document.getElementById('orgNameFilter');
            if (orgNameFilter) orgNameFilter.value = f.org_name || '';

            // Trigger apply
            var applyBtn = document.getElementById('applyFiltersBtn');
            if (applyBtn) applyBtn.click();

            if (typeof showNotification === 'function') {
                showNotification('Applied view: ' + view.name, 'info');
            }
        },

        _loadViews: function(callback) {
            var self = this;
            fetch(API_BASE + '/saved-views')
                .then(function(r) { return r.ok ? r.json() : []; })
                .then(function(data) {
                    self.views = Array.isArray(data) ? data : [];
                    if (callback) callback();
                })
                .catch(function() {
                    self.views = [];
                    if (callback) callback();
                });
        },

        // ---- Full Page ----

        init: function() {
            if (this.initialized) return;
            this.initialized = true;

            this.initQuickSwitch();

            var container = document.getElementById(this.containerId);
            if (!container) return;

            // Page header
            var header = document.createElement('div');
            header.className = 'page-header';
            var h1 = document.createElement('h1');
            h1.textContent = 'Saved Views';
            header.appendChild(h1);
            var desc = document.createElement('p');
            desc.className = 'page-description';
            desc.textContent = 'Manage your saved filter configurations for quick access.';
            header.appendChild(desc);
            container.appendChild(header);

            // Body
            var body = document.createElement('div');
            body.className = 'page-body';
            body.id = 'savedViewsBody';
            container.appendChild(body);
        },

        load: function() {
            if (!this.quickSwitchInitialized) this.initQuickSwitch();
            this._loadViewsPage();
        },

        _loadViewsPage: function() {
            var body = document.getElementById('savedViewsBody');
            if (!body) return;
            var self = this;

            body.textContent = '';
            var loadingDiv = document.createElement('div');
            loadingDiv.style.cssText = 'text-align: center; padding: 48px; color: var(--text-muted);';
            loadingDiv.textContent = 'Loading saved views...';
            body.appendChild(loadingDiv);

            this._loadViews(function() {
                self._renderViewsPage(body);
            });
        },

        _renderViewsPage: function(body) {
            body.textContent = '';
            var self = this;

            if (this.views.length === 0) {
                var empty = document.createElement('div');
                empty.style.cssText = 'text-align: center; padding: 64px; color: var(--text-muted);';
                var emptyTitle = document.createElement('h3');
                emptyTitle.style.cssText = 'margin-bottom: 8px; color: var(--text-primary);';
                emptyTitle.textContent = 'No saved views yet';
                empty.appendChild(emptyTitle);
                var emptyDesc = document.createElement('p');
                emptyDesc.textContent = 'Save your current filter configuration from the dashboard filter bar.';
                empty.appendChild(emptyDesc);
                body.appendChild(empty);
                return;
            }

            var table = document.createElement('table');
            table.style.cssText = 'width: 100%;';
            var thead = document.createElement('thead');
            var headerRow = document.createElement('tr');
            ['Default', 'Name', 'Filters', 'Used', 'Last Used', 'Created', 'Actions'].forEach(function(text) {
                var th = document.createElement('th');
                th.setAttribute('scope', 'col');
                th.textContent = text;
                headerRow.appendChild(th);
            });
            thead.appendChild(headerRow);
            table.appendChild(thead);

            var tbody = document.createElement('tbody');

            this.views.forEach(function(view) {
                var tr = document.createElement('tr');

                // Default star
                var tdDefault = document.createElement('td');
                tdDefault.style.textAlign = 'center';
                var starBtn = document.createElement('button');
                starBtn.className = 'btn-ghost btn-sm';
                starBtn.style.color = view.is_default ? 'var(--accent-warning)' : 'var(--text-muted)';
                starBtn.textContent = view.is_default ? '* Default' : 'Set';
                starBtn.title = view.is_default ? 'Default view' : 'Set as default';
                if (!view.is_default) {
                    starBtn.addEventListener('click', function() {
                        self._setDefault(view.id);
                    });
                }
                tdDefault.appendChild(starBtn);
                tr.appendChild(tdDefault);

                // Name
                var tdName = document.createElement('td');
                tdName.style.fontWeight = '500';
                tdName.textContent = view.name;
                tr.appendChild(tdName);

                // Filters summary
                var tdFilters = document.createElement('td');
                tdFilters.style.cssText = 'font-size: 0.8rem; color: var(--text-secondary); max-width: 250px;';
                tdFilters.textContent = self._summarizeFilters(view.filters);
                tr.appendChild(tdFilters);

                // Use count
                var tdUse = document.createElement('td');
                tdUse.textContent = (view.use_count || 0) + ' times';
                tr.appendChild(tdUse);

                // Last used
                var tdLastUsed = document.createElement('td');
                tdLastUsed.textContent = view.last_used_at ? new Date(view.last_used_at).toLocaleDateString() : 'Never';
                tr.appendChild(tdLastUsed);

                // Created
                var tdCreated = document.createElement('td');
                tdCreated.textContent = view.created_at ? new Date(view.created_at).toLocaleDateString() : '';
                tr.appendChild(tdCreated);

                // Actions
                var tdActions = document.createElement('td');
                var actionsDiv = document.createElement('div');
                actionsDiv.style.cssText = 'display: flex; gap: 4px;';

                var applyBtn = document.createElement('button');
                applyBtn.className = 'btn-ghost btn-sm';
                applyBtn.textContent = 'Apply';
                applyBtn.addEventListener('click', function() {
                    self._applyView(view);
                    if (window.DMARC && window.DMARC.Router) {
                        window.DMARC.Router.navigate('dashboard');
                    }
                });
                actionsDiv.appendChild(applyBtn);

                var renameBtn = document.createElement('button');
                renameBtn.className = 'btn-ghost btn-sm';
                renameBtn.textContent = 'Rename';
                renameBtn.addEventListener('click', function() {
                    self._renameView(view);
                });
                actionsDiv.appendChild(renameBtn);

                var deleteBtn = document.createElement('button');
                deleteBtn.className = 'btn-ghost btn-sm';
                deleteBtn.style.color = 'var(--accent-danger)';
                deleteBtn.textContent = 'Delete';
                deleteBtn.addEventListener('click', function() {
                    self._deleteView(view.id, view.name);
                });
                actionsDiv.appendChild(deleteBtn);

                tdActions.appendChild(actionsDiv);
                tr.appendChild(tdActions);

                tbody.appendChild(tr);
            });

            table.appendChild(tbody);

            var tableWrapper = document.createElement('div');
            tableWrapper.className = 'table-container';
            tableWrapper.appendChild(table);
            body.appendChild(tableWrapper);
        },

        _summarizeFilters: function(filters) {
            if (!filters) return 'No filters';
            var parts = [];
            if (filters.domain) parts.push('Domain: ' + filters.domain);
            if (filters.days) parts.push('Days: ' + filters.days);
            if (filters.spf) parts.push('SPF: ' + filters.spf);
            if (filters.dkim) parts.push('DKIM: ' + filters.dkim);
            if (filters.disposition) parts.push('Disposition: ' + filters.disposition);
            if (filters.source_ip) parts.push('IP: ' + filters.source_ip);
            if (filters.org_name) parts.push('Org: ' + filters.org_name);
            return parts.length > 0 ? parts.join(', ') : 'All defaults';
        },

        _setDefault: function(id) {
            var self = this;
            fetch(API_BASE + '/saved-views/' + encodeURIComponent(id) + '/set-default', { method: 'POST' })
                .then(function(r) {
                    if (r.ok) {
                        if (typeof showNotification === 'function') {
                            showNotification('Default view updated', 'success');
                        }
                        self._loadViewsPage();
                    }
                })
                .catch(function() {});
        },

        _renameView: function(view) {
            var self = this;
            var newName = prompt('Rename view:', view.name);
            if (newName && newName.trim() && newName.trim() !== view.name) {
                fetch(API_BASE + '/saved-views/' + encodeURIComponent(view.id), {
                    method: 'PATCH',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ name: newName.trim() })
                })
                .then(function(r) {
                    if (r.ok) {
                        if (typeof showNotification === 'function') {
                            showNotification('View renamed', 'success');
                        }
                        self._loadViewsPage();
                    }
                })
                .catch(function() {});
            }
        },

        _deleteView: function(id, name) {
            if (!confirm('Delete saved view "' + name + '"?')) return;
            var self = this;
            fetch(API_BASE + '/saved-views/' + encodeURIComponent(id), { method: 'DELETE' })
                .then(function(r) {
                    if (r.ok) {
                        if (typeof showNotification === 'function') {
                            showNotification('Deleted view: ' + name, 'info');
                        }
                        self._loadViewsPage();
                    }
                })
                .catch(function() {});
        },

        destroy: function() {
            // Nothing to clean up
        }
    };

    // Expose module
    window.DMARC = window.DMARC || {};
    window.DMARC.SavedViewsPage = SavedViewsPage;

    // Register with router
    if (window.DMARC.Router) {
        window.DMARC.Router.register('saved-views', SavedViewsPage);
    }
})();

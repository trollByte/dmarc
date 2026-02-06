/**
 * DMARC Dashboard - Notifications Module
 *
 * Two parts:
 *   1. Header notification bell with unread count badge and dropdown panel
 *   2. Full notifications page (#page-notifications) with list, filters, and actions
 *
 * Polls for unread count every 60 seconds.
 */
(function() {
    'use strict';

    var API_BASE = '/api';
    var POLL_INTERVAL = 60000;

    // SVG icon helper - creates SVG elements safely using DOM APIs
    function createSvgIcon(paths, opts) {
        var ns = 'http://www.w3.org/2000/svg';
        var svg = document.createElementNS(ns, 'svg');
        svg.setAttribute('class', (opts && opts.className) || 'icon');
        svg.setAttribute('viewBox', '0 0 24 24');
        svg.setAttribute('fill', 'none');
        svg.setAttribute('stroke', 'currentColor');
        svg.setAttribute('stroke-width', '2');
        svg.setAttribute('aria-hidden', 'true');
        if (opts && opts.style) svg.style.cssText = opts.style;
        paths.forEach(function(p) {
            var el;
            if (p.type === 'path') {
                el = document.createElementNS(ns, 'path');
                el.setAttribute('d', p.d);
            } else if (p.type === 'circle') {
                el = document.createElementNS(ns, 'circle');
                el.setAttribute('cx', p.cx);
                el.setAttribute('cy', p.cy);
                el.setAttribute('r', p.r);
            } else if (p.type === 'line') {
                el = document.createElementNS(ns, 'line');
                el.setAttribute('x1', p.x1);
                el.setAttribute('y1', p.y1);
                el.setAttribute('x2', p.x2);
                el.setAttribute('y2', p.y2);
            } else if (p.type === 'polyline') {
                el = document.createElementNS(ns, 'polyline');
                el.setAttribute('points', p.points);
            } else if (p.type === 'rect') {
                el = document.createElementNS(ns, 'rect');
                el.setAttribute('x', p.x);
                el.setAttribute('y', p.y);
                el.setAttribute('width', p.width);
                el.setAttribute('height', p.height);
                if (p.rx) el.setAttribute('rx', p.rx);
                if (p.ry) el.setAttribute('ry', p.ry);
            }
            if (el) svg.appendChild(el);
        });
        return svg;
    }

    var ICONS = {
        bell: function(opts) {
            return createSvgIcon([
                {type: 'path', d: 'M18 8A6 6 0 0 0 6 8c0 7-3 9-3 9h18s-3-2-3-9'},
                {type: 'path', d: 'M13.73 21a2 2 0 0 1-3.46 0'}
            ], opts);
        },
        file: function(opts) {
            return createSvgIcon([
                {type: 'path', d: 'M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z'},
                {type: 'polyline', points: '14 2 14 8 20 8'}
            ], opts);
        },
        info: function(opts) {
            return createSvgIcon([
                {type: 'circle', cx: '12', cy: '12', r: '10'},
                {type: 'line', x1: '12', y1: '16', x2: '12', y2: '12'},
                {type: 'line', x1: '12', y1: '8', x2: '12.01', y2: '8'}
            ], opts);
        }
    };

    var NotificationsPage = {
        initialized: false,
        containerId: 'page-notifications',
        bellInitialized: false,
        pollTimer: null,
        currentPage: 1,
        perPage: 20,
        unreadOnly: false,
        totalItems: 0,

        // ---- Header Bell (always active) ----

        initBell: function() {
            if (this.bellInitialized) return;
            this.bellInitialized = true;

            var self = this;
            var container = this._findBellInsertionPoint();
            if (!container) return;

            // Create notification center wrapper
            var center = document.createElement('div');
            center.className = 'notification-center';
            center.id = 'notificationCenter';

            // Bell button
            var trigger = document.createElement('button');
            trigger.className = 'btn-icon notification-trigger';
            trigger.setAttribute('aria-label', 'Notifications');
            trigger.title = 'Notifications';
            trigger.appendChild(ICONS.bell());
            var badge = document.createElement('span');
            badge.className = 'notification-badge';
            badge.id = 'notifBadge';
            badge.setAttribute('data-count', '0');
            trigger.appendChild(badge);
            center.appendChild(trigger);

            // Dropdown panel
            var panel = document.createElement('div');
            panel.className = 'notification-panel';
            panel.id = 'notifPanel';
            panel.hidden = true;

            var panelHeader = document.createElement('div');
            panelHeader.className = 'notification-panel-header';
            var h3 = document.createElement('h3');
            h3.textContent = 'Notifications';
            panelHeader.appendChild(h3);
            var markAllBtn = document.createElement('button');
            markAllBtn.className = 'notification-mark-read';
            markAllBtn.textContent = 'Mark all read';
            markAllBtn.addEventListener('click', function(e) {
                e.stopPropagation();
                self._markAllRead();
            });
            panelHeader.appendChild(markAllBtn);
            panel.appendChild(panelHeader);

            var list = document.createElement('div');
            list.className = 'notification-list';
            list.id = 'notifPanelList';
            panel.appendChild(list);

            var footer = document.createElement('div');
            footer.style.cssText = 'padding: 12px 20px; border-top: 1px solid var(--border-color); text-align: center;';
            var viewAll = document.createElement('a');
            viewAll.href = '#notifications';
            viewAll.textContent = 'View All Notifications';
            viewAll.style.cssText = 'font-size: 0.85rem; color: var(--accent-primary); text-decoration: none; font-weight: 500;';
            viewAll.addEventListener('click', function() {
                panel.hidden = true;
            });
            footer.appendChild(viewAll);
            panel.appendChild(footer);

            center.appendChild(panel);

            // Insert before theme toggle
            var themeToggle = document.getElementById('themeToggle');
            if (themeToggle && themeToggle.parentNode === container) {
                container.insertBefore(center, themeToggle);
            } else {
                container.appendChild(center);
            }

            // Toggle panel
            trigger.addEventListener('click', function(e) {
                e.stopPropagation();
                var isHidden = panel.hidden;
                panel.hidden = !isHidden;
                if (!panel.hidden) {
                    self._loadPanelNotifications();
                }
            });

            // Close panel on outside click
            document.addEventListener('click', function(e) {
                if (!center.contains(e.target)) {
                    panel.hidden = true;
                }
            });

            // Start polling
            this._pollUnreadCount();
            this.pollTimer = setInterval(function() {
                self._pollUnreadCount();
            }, POLL_INTERVAL);
        },

        _findBellInsertionPoint: function() {
            return document.querySelector('.action-group-secondary');
        },

        _pollUnreadCount: function() {
            var badge = document.getElementById('notifBadge');
            if (!badge) return;
            fetch(API_BASE + '/notifications/count')
                .then(function(r) { return r.ok ? r.json() : null; })
                .then(function(data) {
                    if (!data) return;
                    var count = data.unread_count || 0;
                    badge.textContent = count > 99 ? '99+' : (count > 0 ? String(count) : '');
                    badge.setAttribute('data-count', String(count));
                })
                .catch(function() {});
        },

        _loadPanelNotifications: function() {
            var list = document.getElementById('notifPanelList');
            if (!list) return;
            var self = this;

            list.textContent = '';
            var loadingMsg = document.createElement('div');
            loadingMsg.style.cssText = 'padding: 24px; text-align: center; color: var(--text-muted);';
            loadingMsg.textContent = 'Loading...';
            list.appendChild(loadingMsg);

            fetch(API_BASE + '/notifications?page=1&per_page=5&unread_only=false')
                .then(function(r) { return r.ok ? r.json() : null; })
                .then(function(data) {
                    list.textContent = '';
                    if (!data || !data.items || data.items.length === 0) {
                        var empty = document.createElement('div');
                        empty.className = 'notification-empty';
                        empty.appendChild(ICONS.bell({style: 'width:48px;height:48px;margin-bottom:12px;opacity:0.5;'}));
                        var p = document.createElement('p');
                        p.textContent = 'No notifications';
                        empty.appendChild(p);
                        list.appendChild(empty);
                        return;
                    }
                    data.items.forEach(function(item) {
                        list.appendChild(self._createNotificationItem(item, true));
                    });
                })
                .catch(function() {
                    list.textContent = '';
                    var errMsg = document.createElement('div');
                    errMsg.style.cssText = 'padding: 24px; text-align: center; color: var(--text-muted);';
                    errMsg.textContent = 'Failed to load';
                    list.appendChild(errMsg);
                });
        },

        _createNotificationItem: function(item, compact) {
            var div = document.createElement('div');
            div.className = 'notification-item' + (item.is_read ? '' : ' unread');
            div.setAttribute('data-id', item.id);

            var iconClass = 'info';
            var iconFn = ICONS.info;
            if (item.type === 'alert') {
                iconClass = 'warning';
                iconFn = ICONS.bell;
            } else if (item.type === 'report') {
                iconClass = 'success';
                iconFn = ICONS.file;
            }

            var iconDiv = document.createElement('div');
            iconDiv.className = 'notification-item-icon ' + iconClass;
            iconDiv.appendChild(iconFn());
            div.appendChild(iconDiv);

            var content = document.createElement('div');
            content.className = 'notification-item-content';
            var title = document.createElement('div');
            title.className = 'notification-item-title';
            title.textContent = item.title || '';
            content.appendChild(title);
            if (!compact) {
                var msg = document.createElement('div');
                msg.className = 'notification-item-message';
                msg.textContent = item.message || '';
                content.appendChild(msg);
            }
            var time = document.createElement('div');
            time.className = 'notification-item-time';
            time.textContent = this._timeAgo(item.created_at);
            content.appendChild(time);
            div.appendChild(content);

            return div;
        },

        _timeAgo: function(dateStr) {
            if (!dateStr) return '';
            var now = Date.now();
            var then = new Date(dateStr).getTime();
            var diff = Math.floor((now - then) / 1000);
            if (diff < 60) return 'just now';
            if (diff < 3600) return Math.floor(diff / 60) + 'm ago';
            if (diff < 86400) return Math.floor(diff / 3600) + 'h ago';
            if (diff < 604800) return Math.floor(diff / 86400) + 'd ago';
            return new Date(dateStr).toLocaleDateString();
        },

        _markAllRead: function() {
            var self = this;
            fetch(API_BASE + '/notifications/read-all', { method: 'POST' })
                .then(function(r) {
                    if (r.ok) {
                        self._pollUnreadCount();
                        self._loadPanelNotifications();
                        if (window.DMARC && window.DMARC.Router && window.DMARC.Router.getCurrentPage() === 'notifications') {
                            self._loadFullPage();
                        }
                        if (typeof showNotification === 'function') {
                            showNotification('All notifications marked as read', 'success');
                        }
                    }
                })
                .catch(function() {});
        },

        // ---- Full Page ----

        init: function() {
            if (this.initialized) return;
            this.initialized = true;

            // Always init the bell
            this.initBell();

            var container = document.getElementById(this.containerId);
            if (!container) return;

            var self = this;

            // Page header
            var header = document.createElement('div');
            header.className = 'page-header';
            var headerRow = document.createElement('div');
            headerRow.style.cssText = 'display: flex; justify-content: space-between; align-items: center; flex-wrap: wrap; gap: 12px;';

            var headerLeft = document.createElement('div');
            var h1 = document.createElement('h1');
            h1.textContent = 'Notifications';
            headerLeft.appendChild(h1);
            var desc = document.createElement('p');
            desc.className = 'page-description';
            desc.textContent = 'View and manage your notification history.';
            headerLeft.appendChild(desc);
            headerRow.appendChild(headerLeft);

            var headerActions = document.createElement('div');
            headerActions.style.cssText = 'display: flex; gap: 8px; align-items: center;';

            // Unread only toggle
            var toggleLabel = document.createElement('label');
            toggleLabel.style.cssText = 'display: flex; align-items: center; gap: 6px; font-size: 0.85rem; color: var(--text-secondary); cursor: pointer;';
            var toggleCheck = document.createElement('input');
            toggleCheck.type = 'checkbox';
            toggleCheck.id = 'notifUnreadToggle';
            toggleCheck.addEventListener('change', function() {
                self.unreadOnly = this.checked;
                self.currentPage = 1;
                self._loadFullPage();
            });
            toggleLabel.appendChild(toggleCheck);
            toggleLabel.appendChild(document.createTextNode('Unread only'));
            headerActions.appendChild(toggleLabel);

            // Mark all read button
            var markAllPageBtn = document.createElement('button');
            markAllPageBtn.className = 'btn-secondary btn-sm';
            markAllPageBtn.textContent = 'Mark All Read';
            markAllPageBtn.addEventListener('click', function() {
                self._markAllRead();
            });
            headerActions.appendChild(markAllPageBtn);

            headerRow.appendChild(headerActions);
            header.appendChild(headerRow);
            container.appendChild(header);

            // Body
            var body = document.createElement('div');
            body.className = 'page-body';
            body.id = 'notifPageBody';
            container.appendChild(body);
        },

        load: function() {
            if (!this.bellInitialized) this.initBell();
            this._loadFullPage();
        },

        _loadFullPage: function() {
            var body = document.getElementById('notifPageBody');
            if (!body) return;
            var self = this;

            body.textContent = '';
            var loadingDiv = document.createElement('div');
            loadingDiv.style.cssText = 'text-align: center; padding: 48px; color: var(--text-muted);';
            loadingDiv.textContent = 'Loading notifications...';
            body.appendChild(loadingDiv);

            var params = 'page=' + this.currentPage + '&per_page=' + this.perPage;
            if (this.unreadOnly) params += '&unread_only=true';

            fetch(API_BASE + '/notifications?' + params)
                .then(function(r) { return r.ok ? r.json() : null; })
                .then(function(data) {
                    if (!data) {
                        body.textContent = '';
                        var errDiv = document.createElement('div');
                        errDiv.style.cssText = 'text-align: center; padding: 48px; color: var(--text-muted);';
                        errDiv.textContent = 'Failed to load notifications.';
                        body.appendChild(errDiv);
                        return;
                    }
                    self.totalItems = data.total || 0;
                    self._renderFullPage(body, data);
                })
                .catch(function() {
                    body.textContent = '';
                    var errDiv = document.createElement('div');
                    errDiv.style.cssText = 'text-align: center; padding: 48px; color: var(--text-muted);';
                    errDiv.textContent = 'Failed to load notifications.';
                    body.appendChild(errDiv);
                });
        },

        _renderFullPage: function(body, data) {
            body.textContent = '';
            var self = this;

            if (!data.items || data.items.length === 0) {
                var empty = document.createElement('div');
                empty.style.cssText = 'text-align: center; padding: 64px; color: var(--text-muted);';
                empty.appendChild(ICONS.bell({style: 'width:48px;height:48px;margin-bottom:12px;opacity:0.5;'}));
                var emptyText = document.createElement('p');
                emptyText.style.fontSize = '1rem';
                emptyText.textContent = 'No notifications';
                empty.appendChild(emptyText);
                body.appendChild(empty);
                return;
            }

            // Notifications list
            var list = document.createElement('div');
            list.className = 'table-container';
            list.style.cssText = 'border: 1px solid var(--border-color); border-radius: 12px; overflow: hidden;';

            data.items.forEach(function(item) {
                var row = self._createNotificationItem(item, false);

                // Add action buttons
                var actions = document.createElement('div');
                actions.style.cssText = 'display: flex; gap: 8px; margin-left: auto; align-items: flex-start; flex-shrink: 0;';

                if (!item.is_read) {
                    var readBtn = document.createElement('button');
                    readBtn.className = 'btn-ghost btn-sm';
                    readBtn.textContent = 'Mark Read';
                    readBtn.addEventListener('click', function(e) {
                        e.stopPropagation();
                        self._markRead(item.id);
                    });
                    actions.appendChild(readBtn);
                }

                var delBtn = document.createElement('button');
                delBtn.className = 'btn-ghost btn-sm';
                delBtn.style.color = 'var(--accent-danger)';
                delBtn.textContent = 'Delete';
                delBtn.addEventListener('click', function(e) {
                    e.stopPropagation();
                    self._deleteNotification(item.id);
                });
                actions.appendChild(delBtn);

                row.appendChild(actions);
                list.appendChild(row);
            });

            body.appendChild(list);

            // Pagination
            var totalPages = Math.ceil(this.totalItems / this.perPage);
            if (totalPages > 1) {
                var pag = document.createElement('div');
                pag.style.cssText = 'display: flex; justify-content: center; gap: 8px; margin-top: 16px;';

                if (this.currentPage > 1) {
                    var prevBtn = document.createElement('button');
                    prevBtn.className = 'btn-secondary btn-sm';
                    prevBtn.textContent = 'Previous';
                    prevBtn.addEventListener('click', function() {
                        self.currentPage--;
                        self._loadFullPage();
                    });
                    pag.appendChild(prevBtn);
                }

                var pageInfo = document.createElement('span');
                pageInfo.style.cssText = 'display: flex; align-items: center; font-size: 0.85rem; color: var(--text-secondary);';
                pageInfo.textContent = 'Page ' + this.currentPage + ' of ' + totalPages;
                pag.appendChild(pageInfo);

                if (this.currentPage < totalPages) {
                    var nextBtn = document.createElement('button');
                    nextBtn.className = 'btn-secondary btn-sm';
                    nextBtn.textContent = 'Next';
                    nextBtn.addEventListener('click', function() {
                        self.currentPage++;
                        self._loadFullPage();
                    });
                    pag.appendChild(nextBtn);
                }

                body.appendChild(pag);
            }
        },

        _markRead: function(id) {
            var self = this;
            fetch(API_BASE + '/notifications/' + encodeURIComponent(id) + '/read', { method: 'POST' })
                .then(function(r) {
                    if (r.ok) {
                        self._pollUnreadCount();
                        self._loadFullPage();
                    }
                })
                .catch(function() {});
        },

        _deleteNotification: function(id) {
            var self = this;
            fetch(API_BASE + '/notifications/' + encodeURIComponent(id), { method: 'DELETE' })
                .then(function(r) {
                    if (r.ok) {
                        self._pollUnreadCount();
                        self._loadFullPage();
                        if (typeof showNotification === 'function') {
                            showNotification('Notification deleted', 'success');
                        }
                    }
                })
                .catch(function() {});
        },

        destroy: function() {
            // Keep polling running -- bell is always active
        },

        /** Stop polling entirely (call on logout) */
        stopPolling: function() {
            if (this.pollTimer) {
                clearInterval(this.pollTimer);
                this.pollTimer = null;
            }
        }
    };

    // Expose module
    window.DMARC = window.DMARC || {};
    window.DMARC.NotificationsPage = NotificationsPage;

    // Register with router
    if (window.DMARC.Router) {
        window.DMARC.Router.register('notifications', NotificationsPage);
    }
})();

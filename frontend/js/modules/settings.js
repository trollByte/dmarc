/**
 * DMARC Dashboard - Settings/Profile Page Module
 * Tabbed layout: Profile, Password, API Keys, Two-Factor Auth.
 * Available to all authenticated users.
 *
 * All user-supplied data is inserted via textContent or safe DOM methods.
 */
(function() {
    'use strict';

    var API_BASE = '/api';

    function el(tag, attrs, children) {
        var elem = document.createElement(tag);
        if (attrs) {
            Object.keys(attrs).forEach(function(key) {
                if (key === 'className') elem.className = attrs[key];
                else if (key === 'textContent') elem.textContent = attrs[key];
                else if (key.indexOf('on') === 0) elem.addEventListener(key.slice(2).toLowerCase(), attrs[key]);
                else elem.setAttribute(key, attrs[key]);
            });
        }
        if (children) {
            if (typeof children === 'string') elem.textContent = children;
            else if (Array.isArray(children)) children.forEach(function(c) { if (c) elem.appendChild(c); });
            else elem.appendChild(children);
        }
        return elem;
    }

    var SettingsPage = {
        initialized: false,
        activeTab: 'profile',
        apiKeys: [],
        totpEnabled: false,
        backupCodes: null,

        init: function() {
            if (this.initialized) return;
            this.initialized = true;
            this._renderSkeleton();
            this._bindEvents();
        },

        load: function() {
            this._loadActiveTab();
        },

        destroy: function() {},

        _renderSkeleton: function() {
            var container = document.getElementById('page-settings');
            if (!container) return;
            container.textContent = '';

            // Page header
            container.appendChild(el('div', { className: 'page-header' }, [
                el('div', { className: 'page-header-left' }, [
                    el('h2', null, 'Settings')
                ])
            ]));

            // Tab navigation
            var tabs = el('div', { className: 'settings-tabs', role: 'tablist', 'aria-label': 'Settings sections' });
            var tabDefs = [
                { id: 'profile', label: 'Profile' },
                { id: 'password', label: 'Password' },
                { id: 'api-keys', label: 'API Keys' },
                { id: 'two-factor', label: 'Two-Factor Auth' }
            ];
            for (var i = 0; i < tabDefs.length; i++) {
                var t = tabDefs[i];
                var btn = el('button', {
                    className: 'settings-tab' + (t.id === 'profile' ? ' active' : ''),
                    role: 'tab',
                    'aria-selected': t.id === 'profile' ? 'true' : 'false',
                    'aria-controls': 'settings-panel-' + t.id,
                    'data-tab': t.id
                }, t.label);
                tabs.appendChild(btn);
            }
            container.appendChild(tabs);

            // Tab panels
            container.appendChild(this._buildProfilePanel());
            container.appendChild(this._buildPasswordPanel());
            container.appendChild(this._buildApiKeysPanel());
            container.appendChild(this._buildTwoFactorPanel());
        },

        // ==================== Profile Tab ====================
        _buildProfilePanel: function() {
            var panel = el('div', {
                className: 'settings-panel',
                id: 'settings-panel-profile',
                role: 'tabpanel'
            });

            var card = el('div', { className: 'settings-card' });
            card.appendChild(el('h3', null, 'Profile Information'));

            var grid = el('div', { className: 'settings-info-grid' });
            grid.appendChild(this._infoRow('Username', 'settings-profile-username'));
            grid.appendChild(this._infoRow('Email', 'settings-profile-email'));
            grid.appendChild(this._infoRow('Role', 'settings-profile-role'));
            grid.appendChild(this._infoRow('Account Created', 'settings-profile-created'));
            grid.appendChild(this._infoRow('Two-Factor Auth', 'settings-profile-2fa'));
            card.appendChild(grid);
            panel.appendChild(card);
            return panel;
        },

        _infoRow: function(label, valueId) {
            var row = el('div', { className: 'settings-info-row' });
            row.appendChild(el('dt', { className: 'settings-info-label' }, label));
            row.appendChild(el('dd', { className: 'settings-info-value', id: valueId }, '-'));
            return row;
        },

        _loadProfile: function() {
            var user = window.DMARC && window.DMARC.currentUser;
            if (!user) return;

            var setField = function(id, value) {
                var elem = document.getElementById(id);
                if (elem) elem.textContent = value || '-';
            };

            setField('settings-profile-username', user.username);
            setField('settings-profile-email', user.email);
            setField('settings-profile-role', user.role ? user.role.charAt(0).toUpperCase() + user.role.slice(1) : '-');
            setField('settings-profile-created', user.created_at ? new Date(user.created_at).toLocaleDateString() : '-');
            setField('settings-profile-2fa', user.totp_enabled ? 'Enabled' : 'Disabled');
            this.totpEnabled = !!user.totp_enabled;
        },

        // ==================== Password Tab ====================
        _buildPasswordPanel: function() {
            var panel = el('div', {
                className: 'settings-panel',
                id: 'settings-panel-password',
                role: 'tabpanel',
                hidden: ''
            });

            var card = el('div', { className: 'settings-card' });
            card.appendChild(el('h3', null, 'Change Password'));

            var form = el('form', { id: 'settings-password-form', autocomplete: 'off' });
            form.appendChild(this._formGroup('settings-current-password', 'Current Password', 'password', { required: '', autocomplete: 'current-password' }));
            form.appendChild(this._formGroup('settings-new-password', 'New Password', 'password', { required: '', minlength: '8', autocomplete: 'new-password' }));

            // Strength indicator
            var strengthWrap = el('div', { className: 'password-strength', id: 'settings-password-strength' });
            strengthWrap.appendChild(el('div', { className: 'password-strength-bar' }, [
                el('div', { className: 'password-strength-fill', id: 'settings-strength-fill' })
            ]));
            strengthWrap.appendChild(el('span', { className: 'password-strength-label', id: 'settings-strength-label' }));
            form.appendChild(strengthWrap);

            form.appendChild(this._formGroup('settings-confirm-password', 'Confirm New Password', 'password', { required: '', autocomplete: 'new-password' }));
            form.appendChild(el('div', { className: 'form-error', id: 'settings-password-error', hidden: '' }));
            form.appendChild(el('div', { className: 'form-actions' }, [
                el('button', { type: 'submit', className: 'btn-primary', id: 'settings-password-submit' }, 'Change Password')
            ]));
            card.appendChild(form);
            panel.appendChild(card);
            return panel;
        },

        _checkPasswordStrength: function(password) {
            var score = 0;
            if (password.length >= 8) score++;
            if (password.length >= 12) score++;
            if (/[a-z]/.test(password) && /[A-Z]/.test(password)) score++;
            if (/\d/.test(password)) score++;
            if (/[^a-zA-Z0-9]/.test(password)) score++;

            var levels = ['Very Weak', 'Weak', 'Fair', 'Strong', 'Very Strong'];
            var colors = ['#ef4444', '#f97316', '#eab308', '#22c55e', '#16a34a'];
            var level = Math.min(score, levels.length - 1);

            var fill = document.getElementById('settings-strength-fill');
            var label = document.getElementById('settings-strength-label');
            if (fill) {
                fill.style.width = ((score / 5) * 100) + '%';
                fill.style.backgroundColor = colors[level];
            }
            if (label) label.textContent = password ? levels[level] : '';
        },

        _handleChangePassword: function() {
            var self = this;
            var currentPassword = document.getElementById('settings-current-password').value;
            var newPassword = document.getElementById('settings-new-password').value;
            var confirmPassword = document.getElementById('settings-confirm-password').value;
            var errorEl = document.getElementById('settings-password-error');
            var submitBtn = document.getElementById('settings-password-submit');

            if (newPassword !== confirmPassword) {
                if (errorEl) { errorEl.textContent = 'New passwords do not match.'; errorEl.hidden = false; }
                return;
            }
            if (newPassword.length < 8) {
                if (errorEl) { errorEl.textContent = 'Password must be at least 8 characters.'; errorEl.hidden = false; }
                return;
            }

            if (errorEl) errorEl.hidden = true;
            if (submitBtn) { submitBtn.disabled = true; submitBtn.textContent = 'Changing...'; }

            fetch(API_BASE + '/users/me/change-password', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ current_password: currentPassword, new_password: newPassword })
            }).then(function(response) {
                if (!response.ok) return response.json().then(function(d) { throw new Error(d.detail || 'Failed to change password'); });
                return response.json();
            }).then(function() {
                showNotification('Password changed successfully', 'success');
                var form = document.getElementById('settings-password-form');
                if (form) form.reset();
                self._checkPasswordStrength('');
            }).catch(function(err) {
                if (errorEl) { errorEl.textContent = err.message; errorEl.hidden = false; }
            }).finally(function() {
                if (submitBtn) { submitBtn.disabled = false; submitBtn.textContent = 'Change Password'; }
            });
        },

        // ==================== API Keys Tab ====================
        _buildApiKeysPanel: function() {
            var panel = el('div', {
                className: 'settings-panel',
                id: 'settings-panel-api-keys',
                role: 'tabpanel',
                hidden: ''
            });

            var card = el('div', { className: 'settings-card' });
            var headerRow = el('div', { className: 'settings-card-header' }, [
                el('h3', null, 'API Keys'),
                el('button', { className: 'btn-primary btn-sm', id: 'settings-create-key-btn' }, 'Create API Key')
            ]);
            card.appendChild(headerRow);

            // New key creation form (hidden initially)
            var createForm = el('div', { className: 'settings-create-key-form', id: 'settings-create-key-form', hidden: '' });
            var form = el('form', { id: 'settings-key-form' });
            form.appendChild(this._formGroup('settings-key-name', 'Key Name', 'text', { required: '', placeholder: 'e.g. CI/CD Pipeline', maxlength: '100' }));

            var expiryGroup = el('div', { className: 'form-group' });
            expiryGroup.appendChild(el('label', { 'for': 'settings-key-expiry' }, 'Expires In'));
            var expirySelect = el('select', { id: 'settings-key-expiry' });
            [['30', '30 days'], ['60', '60 days'], ['90', '90 days'], ['180', '180 days'], ['365', '1 year'], ['0', 'Never']].forEach(function(opt) {
                expirySelect.appendChild(el('option', { value: opt[0] }, opt[1]));
            });
            expiryGroup.appendChild(expirySelect);
            form.appendChild(expiryGroup);

            form.appendChild(el('div', { className: 'form-actions' }, [
                el('button', { type: 'button', className: 'btn-secondary btn-sm', id: 'settings-key-cancel' }, 'Cancel'),
                el('button', { type: 'submit', className: 'btn-primary btn-sm', id: 'settings-key-submit' }, 'Create Key')
            ]));
            createForm.appendChild(form);
            card.appendChild(createForm);

            // New key display (shown once after creation)
            var newKeyDisplay = el('div', { className: 'settings-new-key-display', id: 'settings-new-key-display', hidden: '' });
            newKeyDisplay.appendChild(el('div', { className: 'alert alert-warning' }, [
                el('strong', null, 'Copy your API key now. '),
                el('span', null, 'You will not be able to see it again.')
            ]));
            var keyValueRow = el('div', { className: 'settings-key-value-row' });
            keyValueRow.appendChild(el('code', { className: 'settings-key-value', id: 'settings-new-key-value' }));
            keyValueRow.appendChild(el('button', { className: 'btn-secondary btn-sm', id: 'settings-copy-key-btn' }, 'Copy'));
            newKeyDisplay.appendChild(keyValueRow);
            newKeyDisplay.appendChild(el('button', { className: 'btn-ghost btn-sm', id: 'settings-dismiss-key-btn' }, 'Done'));
            card.appendChild(newKeyDisplay);

            // API keys table
            var tableWrap = el('div', { className: 'table-container' });
            var table = el('table', { className: 'data-table', id: 'settings-keys-table' });
            var thead = el('thead');
            var headRow = el('tr');
            ['Name', 'Created', 'Expires', 'Last Used', 'Actions'].forEach(function(h) {
                headRow.appendChild(el('th', null, h));
            });
            thead.appendChild(headRow);
            table.appendChild(thead);
            table.appendChild(el('tbody', { id: 'settings-keys-body' }, [
                el('tr', null, [el('td', { colspan: '5', className: 'loading' }, 'Loading API keys...')])
            ]));
            tableWrap.appendChild(table);
            card.appendChild(tableWrap);

            panel.appendChild(card);
            return panel;
        },

        _loadApiKeys: function() {
            var self = this;
            fetch(API_BASE + '/users/me/api-keys', {
                headers: { 'Content-Type': 'application/json' }
            }).then(function(response) {
                if (!response.ok) throw new Error('Failed to load API keys');
                return response.json();
            }).then(function(data) {
                self.apiKeys = Array.isArray(data) ? data : (data.keys || data.items || []);
                self._renderApiKeysTable();
            }).catch(function(err) {
                console.error('Error loading API keys:', err);
                var tbody = document.getElementById('settings-keys-body');
                if (tbody) {
                    tbody.textContent = '';
                    var tr = el('tr');
                    tr.appendChild(el('td', { colspan: '5', className: 'table-error' }, 'Failed to load API keys.'));
                    tbody.appendChild(tr);
                }
            });
        },

        _renderApiKeysTable: function() {
            var self = this;
            var tbody = document.getElementById('settings-keys-body');
            if (!tbody) return;
            tbody.textContent = '';

            if (this.apiKeys.length === 0) {
                var tr = el('tr');
                tr.appendChild(el('td', { colspan: '5', className: 'table-empty' }, 'No API keys created yet.'));
                tbody.appendChild(tr);
                return;
            }

            for (var i = 0; i < this.apiKeys.length; i++) {
                (function(key) {
                    var tr = el('tr');
                    tr.appendChild(el('td', { className: 'td-primary' }, key.name || 'Unnamed'));
                    tr.appendChild(el('td', null, key.created_at ? new Date(key.created_at).toLocaleDateString() : '-'));

                    var expiresText = key.expires_at ? new Date(key.expires_at).toLocaleDateString() : 'Never';
                    if (key.expires_at && new Date(key.expires_at) < new Date()) {
                        var td = el('td');
                        td.appendChild(el('span', { className: 'badge badge-danger' }, 'Expired'));
                        tr.appendChild(td);
                    } else {
                        tr.appendChild(el('td', null, expiresText));
                    }

                    tr.appendChild(el('td', null, key.last_used_at ? new Date(key.last_used_at).toLocaleDateString() : 'Never'));

                    var actionTd = el('td', { className: 'td-actions' });
                    var revokeBtn = el('button', { className: 'btn-danger btn-sm' }, 'Revoke');
                    revokeBtn.addEventListener('click', function() { self._revokeApiKey(key.id); });
                    actionTd.appendChild(revokeBtn);
                    tr.appendChild(actionTd);

                    tbody.appendChild(tr);
                })(this.apiKeys[i]);
            }
        },

        _handleCreateApiKey: function() {
            var self = this;
            var name = document.getElementById('settings-key-name').value.trim();
            var expiresInDays = parseInt(document.getElementById('settings-key-expiry').value, 10);
            var submitBtn = document.getElementById('settings-key-submit');

            if (!name) return;

            if (submitBtn) { submitBtn.disabled = true; submitBtn.textContent = 'Creating...'; }

            var body = { name: name };
            if (expiresInDays > 0) body.expires_in_days = expiresInDays;

            fetch(API_BASE + '/users/me/api-keys', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(body)
            }).then(function(response) {
                if (!response.ok) return response.json().then(function(d) { throw new Error(d.detail || 'Failed to create API key'); });
                return response.json();
            }).then(function(data) {
                // Show the key value once
                var keyValue = data.key || data.api_key || data.token || '';
                var display = document.getElementById('settings-new-key-display');
                var valueEl = document.getElementById('settings-new-key-value');
                if (display && valueEl && keyValue) {
                    valueEl.textContent = keyValue;
                    display.hidden = false;
                }

                // Hide create form
                var createForm = document.getElementById('settings-create-key-form');
                if (createForm) createForm.hidden = true;

                var form = document.getElementById('settings-key-form');
                if (form) form.reset();

                showNotification('API key created', 'success');
                self._loadApiKeys();
            }).catch(function(err) {
                showNotification(err.message, 'error');
            }).finally(function() {
                if (submitBtn) { submitBtn.disabled = false; submitBtn.textContent = 'Create Key'; }
            });
        },

        _revokeApiKey: function(keyId) {
            var self = this;
            if (!confirm('Are you sure you want to revoke this API key?')) return;

            fetch(API_BASE + '/users/me/api-keys/' + encodeURIComponent(keyId), {
                method: 'DELETE',
                headers: { 'Content-Type': 'application/json' }
            }).then(function(response) {
                if (!response.ok) throw new Error('Failed to revoke API key');
                showNotification('API key revoked', 'success');
                self._loadApiKeys();
            }).catch(function(err) {
                showNotification(err.message, 'error');
            });
        },

        // ==================== Two-Factor Auth Tab ====================
        _buildTwoFactorPanel: function() {
            var panel = el('div', {
                className: 'settings-panel',
                id: 'settings-panel-two-factor',
                role: 'tabpanel',
                hidden: ''
            });

            // Status card
            var statusCard = el('div', { className: 'settings-card', id: 'settings-2fa-status-card' });
            statusCard.appendChild(el('h3', null, 'Two-Factor Authentication'));

            var statusRow = el('div', { className: 'settings-2fa-status' });
            statusRow.appendChild(el('span', null, 'Status: '));
            statusRow.appendChild(el('span', { id: 'settings-2fa-status-badge', className: 'badge badge-gray' }, 'Loading...'));
            statusCard.appendChild(statusRow);

            statusCard.appendChild(el('p', { className: 'settings-2fa-desc' },
                'Two-factor authentication adds an extra layer of security to your account by requiring a code from your authenticator app in addition to your password.'));

            // Setup section (shown when 2FA is disabled)
            var setupSection = el('div', { id: 'settings-2fa-setup', hidden: '' });
            setupSection.appendChild(el('button', { className: 'btn-primary', id: 'settings-2fa-enable-btn' }, 'Enable Two-Factor Authentication'));

            // QR code area
            var qrArea = el('div', { id: 'settings-2fa-qr-area', hidden: '' });
            qrArea.appendChild(el('h4', null, 'Scan this QR code with your authenticator app'));
            qrArea.appendChild(el('div', { className: 'settings-2fa-qr-container' }, [
                el('img', { id: 'settings-2fa-qr-img', alt: 'TOTP QR Code', className: 'settings-2fa-qr-img' })
            ]));
            qrArea.appendChild(el('div', { className: 'settings-2fa-secret-row' }, [
                el('span', null, 'Manual entry key: '),
                el('code', { id: 'settings-2fa-secret' })
            ]));

            var verifyForm = el('form', { id: 'settings-2fa-verify-form' });
            verifyForm.appendChild(this._formGroup('settings-2fa-code', 'Verification Code', 'text', {
                required: '', pattern: '[0-9]{6}', maxlength: '6', placeholder: 'Enter 6-digit code', autocomplete: 'one-time-code'
            }));
            verifyForm.appendChild(el('div', { className: 'form-error', id: 'settings-2fa-verify-error', hidden: '' }));
            verifyForm.appendChild(el('div', { className: 'form-actions' }, [
                el('button', { type: 'submit', className: 'btn-primary', id: 'settings-2fa-verify-btn' }, 'Verify and Enable')
            ]));
            qrArea.appendChild(verifyForm);
            setupSection.appendChild(qrArea);
            statusCard.appendChild(setupSection);

            // Disable section (shown when 2FA is enabled)
            var disableSection = el('div', { id: 'settings-2fa-disable', hidden: '' });
            var disableForm = el('form', { id: 'settings-2fa-disable-form' });
            disableForm.appendChild(this._formGroup('settings-2fa-disable-code', 'Enter TOTP code to disable', 'text', {
                required: '', pattern: '[0-9]{6}', maxlength: '6', placeholder: '6-digit code', autocomplete: 'one-time-code'
            }));
            disableForm.appendChild(el('div', { className: 'form-error', id: 'settings-2fa-disable-error', hidden: '' }));
            disableForm.appendChild(el('div', { className: 'form-actions' }, [
                el('button', { type: 'submit', className: 'btn-danger' }, 'Disable Two-Factor Auth')
            ]));
            disableSection.appendChild(disableForm);

            // Backup codes button
            disableSection.appendChild(el('div', { className: 'settings-2fa-backup-section' }, [
                el('button', { className: 'btn-secondary', id: 'settings-2fa-backup-btn' }, 'Generate Backup Codes')
            ]));
            statusCard.appendChild(disableSection);

            // Backup codes display
            var backupDisplay = el('div', { id: 'settings-2fa-backup-display', className: 'settings-2fa-backup-display', hidden: '' });
            backupDisplay.appendChild(el('h4', null, 'Backup Codes'));
            backupDisplay.appendChild(el('p', { className: 'alert alert-warning' },
                'Save these codes in a safe place. Each code can only be used once.'));
            backupDisplay.appendChild(el('pre', { id: 'settings-2fa-backup-codes', className: 'settings-2fa-codes' }));
            backupDisplay.appendChild(el('div', { className: 'form-actions' }, [
                el('button', { className: 'btn-secondary btn-sm', id: 'settings-2fa-copy-codes' }, 'Copy Codes'),
                el('button', { className: 'btn-secondary btn-sm', id: 'settings-2fa-download-codes' }, 'Download')
            ]));
            statusCard.appendChild(backupDisplay);

            panel.appendChild(statusCard);
            return panel;
        },

        _loadTwoFactor: function() {
            var user = window.DMARC && window.DMARC.currentUser;
            this.totpEnabled = !!(user && user.totp_enabled);
            this._updateTwoFactorUI();
        },

        _updateTwoFactorUI: function() {
            var badge = document.getElementById('settings-2fa-status-badge');
            var setupSection = document.getElementById('settings-2fa-setup');
            var disableSection = document.getElementById('settings-2fa-disable');

            if (badge) {
                badge.textContent = this.totpEnabled ? 'Enabled' : 'Disabled';
                badge.className = this.totpEnabled ? 'badge badge-success' : 'badge badge-gray';
            }

            if (setupSection) setupSection.hidden = this.totpEnabled;
            if (disableSection) disableSection.hidden = !this.totpEnabled;
        },

        _handleEnableSetup: function() {
            var self = this;
            var enableBtn = document.getElementById('settings-2fa-enable-btn');
            if (enableBtn) { enableBtn.disabled = true; enableBtn.textContent = 'Loading...'; }

            fetch(API_BASE + '/totp/setup', {
                headers: { 'Content-Type': 'application/json' }
            }).then(function(response) {
                if (!response.ok) throw new Error('Failed to start 2FA setup');
                return response.json();
            }).then(function(data) {
                // Show QR code area
                var qrArea = document.getElementById('settings-2fa-qr-area');
                if (qrArea) qrArea.hidden = false;

                // Generate QR code as a data URI or use provisioning_uri
                var qrImg = document.getElementById('settings-2fa-qr-img');
                if (qrImg) {
                    // If the API returns a qr_uri (data URI) use it directly
                    if (data.qr_uri) {
                        qrImg.src = data.qr_uri;
                    } else if (data.provisioning_uri) {
                        // Use a QR code API to generate the image
                        qrImg.src = 'https://api.qrserver.com/v1/create-qr-code/?size=200x200&data=' + encodeURIComponent(data.provisioning_uri);
                    }
                }

                var secretEl = document.getElementById('settings-2fa-secret');
                if (secretEl) secretEl.textContent = data.secret || '';

                if (enableBtn) enableBtn.hidden = true;
            }).catch(function(err) {
                showNotification(err.message, 'error');
                if (enableBtn) { enableBtn.disabled = false; enableBtn.textContent = 'Enable Two-Factor Authentication'; }
            });
        },

        _handleVerifyTotp: function() {
            var self = this;
            var code = document.getElementById('settings-2fa-code').value.trim();
            var errorEl = document.getElementById('settings-2fa-verify-error');
            var verifyBtn = document.getElementById('settings-2fa-verify-btn');

            if (!code || code.length !== 6) {
                if (errorEl) { errorEl.textContent = 'Please enter a 6-digit code.'; errorEl.hidden = false; }
                return;
            }

            if (errorEl) errorEl.hidden = true;
            if (verifyBtn) { verifyBtn.disabled = true; verifyBtn.textContent = 'Verifying...'; }

            fetch(API_BASE + '/totp/enable', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ code: code })
            }).then(function(response) {
                if (!response.ok) return response.json().then(function(d) { throw new Error(d.detail || 'Invalid code'); });
                return response.json();
            }).then(function(data) {
                self.totpEnabled = true;
                self._updateTwoFactorUI();
                showNotification('Two-factor authentication enabled', 'success');

                // Hide QR area
                var qrArea = document.getElementById('settings-2fa-qr-area');
                if (qrArea) qrArea.hidden = true;
                var enableBtn = document.getElementById('settings-2fa-enable-btn');
                if (enableBtn) { enableBtn.hidden = false; enableBtn.disabled = false; enableBtn.textContent = 'Enable Two-Factor Authentication'; }

                // Update user object
                if (window.DMARC && window.DMARC.currentUser) {
                    window.DMARC.currentUser.totp_enabled = true;
                }

                // Show backup codes if returned
                if (data.backup_codes) {
                    self._showBackupCodes(data.backup_codes);
                } else {
                    // Generate backup codes automatically
                    self._generateBackupCodes();
                }
            }).catch(function(err) {
                if (errorEl) { errorEl.textContent = err.message; errorEl.hidden = false; }
            }).finally(function() {
                if (verifyBtn) { verifyBtn.disabled = false; verifyBtn.textContent = 'Verify and Enable'; }
            });
        },

        _handleDisableTotp: function() {
            var self = this;
            var code = document.getElementById('settings-2fa-disable-code').value.trim();
            var errorEl = document.getElementById('settings-2fa-disable-error');

            if (!code || code.length !== 6) {
                if (errorEl) { errorEl.textContent = 'Please enter a 6-digit code.'; errorEl.hidden = false; }
                return;
            }

            if (errorEl) errorEl.hidden = true;

            fetch(API_BASE + '/totp/disable', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ code: code })
            }).then(function(response) {
                if (!response.ok) return response.json().then(function(d) { throw new Error(d.detail || 'Invalid code'); });
                return response.json();
            }).then(function() {
                self.totpEnabled = false;
                self._updateTwoFactorUI();
                showNotification('Two-factor authentication disabled', 'success');

                if (window.DMARC && window.DMARC.currentUser) {
                    window.DMARC.currentUser.totp_enabled = false;
                }

                // Hide backup codes
                var backupDisplay = document.getElementById('settings-2fa-backup-display');
                if (backupDisplay) backupDisplay.hidden = true;

                var form = document.getElementById('settings-2fa-disable-form');
                if (form) form.reset();
            }).catch(function(err) {
                if (errorEl) { errorEl.textContent = err.message; errorEl.hidden = false; }
            });
        },

        _generateBackupCodes: function() {
            var self = this;
            fetch(API_BASE + '/totp/backup-codes', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' }
            }).then(function(response) {
                if (!response.ok) throw new Error('Failed to generate backup codes');
                return response.json();
            }).then(function(data) {
                var codes = data.backup_codes || data.codes || [];
                self._showBackupCodes(codes);
            }).catch(function(err) {
                showNotification(err.message, 'error');
            });
        },

        _showBackupCodes: function(codes) {
            this.backupCodes = codes;
            var display = document.getElementById('settings-2fa-backup-display');
            var codesEl = document.getElementById('settings-2fa-backup-codes');
            if (display) display.hidden = false;
            if (codesEl) {
                codesEl.textContent = (Array.isArray(codes) ? codes.join('\n') : String(codes));
            }
        },

        _copyBackupCodes: function() {
            if (!this.backupCodes) return;
            var text = Array.isArray(this.backupCodes) ? this.backupCodes.join('\n') : String(this.backupCodes);
            navigator.clipboard.writeText(text).then(function() {
                showNotification('Backup codes copied to clipboard', 'success');
            }).catch(function() {
                showNotification('Failed to copy', 'error');
            });
        },

        _downloadBackupCodes: function() {
            if (!this.backupCodes) return;
            var text = 'DMARC Dashboard - Backup Codes\n' +
                       '================================\n' +
                       'Generated: ' + new Date().toISOString() + '\n\n' +
                       (Array.isArray(this.backupCodes) ? this.backupCodes.join('\n') : String(this.backupCodes)) +
                       '\n\nKeep these codes safe. Each code can only be used once.';

            var blob = new Blob([text], { type: 'text/plain' });
            var url = URL.createObjectURL(blob);
            var a = document.createElement('a');
            a.href = url;
            a.download = 'dmarc-backup-codes.txt';
            document.body.appendChild(a);
            a.click();
            document.body.removeChild(a);
            URL.revokeObjectURL(url);
        },

        // ==================== Shared Helpers ====================
        _formGroup: function(id, label, type, attrs) {
            var group = el('div', { className: 'form-group' });
            group.appendChild(el('label', { 'for': id }, label));
            var inputAttrs = { type: type, id: id };
            if (attrs) Object.keys(attrs).forEach(function(k) { inputAttrs[k] = attrs[k]; });
            group.appendChild(el('input', inputAttrs));
            return group;
        },

        _bindEvents: function() {
            var self = this;

            // Tab switching
            var tabContainer = document.querySelector('#page-settings .settings-tabs');
            if (tabContainer) {
                tabContainer.addEventListener('click', function(e) {
                    var tab = e.target.closest('[data-tab]');
                    if (!tab) return;
                    self._switchTab(tab.getAttribute('data-tab'));
                });
            }

            // Password form
            var passwordForm = document.getElementById('settings-password-form');
            if (passwordForm) {
                passwordForm.addEventListener('submit', function(e) { e.preventDefault(); self._handleChangePassword(); });
            }

            // Password strength indicator
            var newPasswordInput = document.getElementById('settings-new-password');
            if (newPasswordInput) {
                newPasswordInput.addEventListener('input', function() { self._checkPasswordStrength(newPasswordInput.value); });
            }

            // API Key events
            var createKeyBtn = document.getElementById('settings-create-key-btn');
            if (createKeyBtn) {
                createKeyBtn.addEventListener('click', function() {
                    var form = document.getElementById('settings-create-key-form');
                    if (form) form.hidden = false;
                    createKeyBtn.hidden = true;
                });
            }

            var keyCancel = document.getElementById('settings-key-cancel');
            if (keyCancel) {
                keyCancel.addEventListener('click', function() {
                    var form = document.getElementById('settings-create-key-form');
                    if (form) form.hidden = true;
                    var btn = document.getElementById('settings-create-key-btn');
                    if (btn) btn.hidden = false;
                });
            }

            var keyForm = document.getElementById('settings-key-form');
            if (keyForm) {
                keyForm.addEventListener('submit', function(e) { e.preventDefault(); self._handleCreateApiKey(); });
            }

            var copyKeyBtn = document.getElementById('settings-copy-key-btn');
            if (copyKeyBtn) {
                copyKeyBtn.addEventListener('click', function() {
                    var val = document.getElementById('settings-new-key-value');
                    if (val) {
                        navigator.clipboard.writeText(val.textContent).then(function() {
                            showNotification('API key copied to clipboard', 'success');
                        }).catch(function() {
                            showNotification('Failed to copy', 'error');
                        });
                    }
                });
            }

            var dismissKeyBtn = document.getElementById('settings-dismiss-key-btn');
            if (dismissKeyBtn) {
                dismissKeyBtn.addEventListener('click', function() {
                    var display = document.getElementById('settings-new-key-display');
                    if (display) display.hidden = true;
                });
            }

            // 2FA events
            var enableBtn = document.getElementById('settings-2fa-enable-btn');
            if (enableBtn) {
                enableBtn.addEventListener('click', function() { self._handleEnableSetup(); });
            }

            var verifyForm = document.getElementById('settings-2fa-verify-form');
            if (verifyForm) {
                verifyForm.addEventListener('submit', function(e) { e.preventDefault(); self._handleVerifyTotp(); });
            }

            var disableForm = document.getElementById('settings-2fa-disable-form');
            if (disableForm) {
                disableForm.addEventListener('submit', function(e) { e.preventDefault(); self._handleDisableTotp(); });
            }

            var backupBtn = document.getElementById('settings-2fa-backup-btn');
            if (backupBtn) {
                backupBtn.addEventListener('click', function() { self._generateBackupCodes(); });
            }

            var copyCodes = document.getElementById('settings-2fa-copy-codes');
            if (copyCodes) {
                copyCodes.addEventListener('click', function() { self._copyBackupCodes(); });
            }

            var downloadCodes = document.getElementById('settings-2fa-download-codes');
            if (downloadCodes) {
                downloadCodes.addEventListener('click', function() { self._downloadBackupCodes(); });
            }
        },

        _switchTab: function(tabId) {
            this.activeTab = tabId;

            // Update tab buttons
            var tabs = document.querySelectorAll('#page-settings .settings-tab');
            tabs.forEach(function(tab) {
                var isActive = tab.getAttribute('data-tab') === tabId;
                tab.classList.toggle('active', isActive);
                tab.setAttribute('aria-selected', isActive ? 'true' : 'false');
            });

            // Show/hide panels
            var panels = document.querySelectorAll('#page-settings .settings-panel');
            panels.forEach(function(panel) {
                panel.hidden = panel.id !== 'settings-panel-' + tabId;
            });

            this._loadActiveTab();
        },

        _loadActiveTab: function() {
            switch (this.activeTab) {
                case 'profile':
                    this._loadProfile();
                    break;
                case 'password':
                    // No data to load - form is ready
                    break;
                case 'api-keys':
                    this._loadApiKeys();
                    break;
                case 'two-factor':
                    this._loadTwoFactor();
                    break;
            }
        },

        _openModal: function(id) {
            var modal = document.getElementById(id);
            if (typeof openModal === 'function') openModal(modal);
            else if (modal) modal.hidden = false;
        },

        _closeModal: function(id) {
            var modal = document.getElementById(id);
            if (typeof closeModal === 'function') closeModal(modal);
            else if (modal) modal.hidden = true;
        }
    };

    window.DMARC = window.DMARC || {};
    window.DMARC.SettingsPage = SettingsPage;

    if (window.DMARC.Router) {
        window.DMARC.Router.register('settings', SettingsPage);
    }
})();

/**
 * DMARC Dashboard - User Management Page Module (Admin Only)
 * Provides user CRUD, search/filter, role management, and account unlock.
 *
 * All user-supplied data is escaped via _escapeHtml() before DOM insertion.
 * innerHTML is used only for rendering structural templates with escaped values.
 */
(function() {
    'use strict';

    var API_BASE = '/api';

    function escapeHtml(str) {
        if (!str) return '';
        var div = document.createElement('div');
        div.appendChild(document.createTextNode(str));
        return div.innerHTML;
    }

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

    var UsersPage = {
        initialized: false,
        currentPage: 1,
        perPage: 20,
        searchQuery: '',
        users: [],
        totalUsers: 0,
        _deleteUserId: null,

        init: function() {
            if (this.initialized) return;
            this.initialized = true;
            this._renderSkeleton();
            this._bindEvents();
        },

        load: function() {
            this._fetchUsers();
        },

        destroy: function() {},

        _renderSkeleton: function() {
            var container = document.getElementById('page-users');
            if (!container) return;

            // Clear and build DOM safely
            container.textContent = '';

            // Page header
            var header = el('div', { className: 'page-header' }, [
                el('div', { className: 'page-header-left' }, [
                    el('h2', null, 'User Management'),
                    el('span', { className: 'page-header-subtitle', id: 'users-count-label' })
                ]),
                el('div', { className: 'page-header-right' }, [
                    el('button', { className: 'btn-primary', id: 'users-create-btn', textContent: ' Create User' })
                ])
            ]);
            container.appendChild(header);

            // Toolbar
            var toolbar = el('div', { className: 'page-toolbar' }, [
                el('div', { className: 'search-input-wrapper' }, [
                    el('input', { type: 'text', id: 'users-search', className: 'search-input', placeholder: 'Search by username or email...', autocomplete: 'off' })
                ])
            ]);
            container.appendChild(toolbar);

            // Table
            var table = el('div', { className: 'table-container' }, [
                el('table', { className: 'data-table', id: 'users-table' }, [
                    this._buildTableHead(),
                    el('tbody', { id: 'users-table-body' }, [
                        el('tr', null, [el('td', { colspan: '6', className: 'loading' }, 'Loading users...')])
                    ])
                ])
            ]);
            container.appendChild(table);

            // Pagination
            container.appendChild(el('div', { id: 'users-pagination', className: 'pagination' }));

            // Modals
            container.appendChild(this._buildCreateModal());
            container.appendChild(this._buildEditModal());
            container.appendChild(this._buildDeleteModal());
        },

        _buildTableHead: function() {
            var thead = el('thead');
            var tr = el('tr');
            ['Username', 'Email', 'Role', 'Status', 'Created', 'Actions'].forEach(function(text) {
                tr.appendChild(el('th', null, text));
            });
            thead.appendChild(tr);
            return thead;
        },

        _buildCreateModal: function() {
            var modal = el('div', { id: 'users-create-modal', className: 'modal', role: 'dialog', 'aria-modal': 'true', hidden: '' });
            var content = el('div', { className: 'modal-content' });
            var modalHeader = el('div', { className: 'modal-header' }, [
                el('h2', { id: 'users-modal-title' }, 'Create User'),
                el('button', { className: 'modal-close', id: 'users-create-modal-close', 'aria-label': 'Close', textContent: '\u00D7' })
            ]);
            var modalBody = el('div', { className: 'modal-body' });
            var form = el('form', { id: 'users-create-form', autocomplete: 'off' });

            form.appendChild(this._formGroup('users-form-username', 'Username', 'text', { required: '', minlength: '3', maxlength: '50', autocomplete: 'off' }));
            form.appendChild(this._formGroup('users-form-email', 'Email', 'email', { required: '', autocomplete: 'off' }));

            var pwGroup = this._formGroup('users-form-password', 'Password', 'password', { required: '', minlength: '8', autocomplete: 'new-password' });
            pwGroup.id = 'users-form-password-group';
            form.appendChild(pwGroup);

            // Role select
            var roleGroup = el('div', { className: 'form-group' });
            roleGroup.appendChild(el('label', { 'for': 'users-form-role' }, 'Role'));
            var roleSelect = el('select', { id: 'users-form-role' });
            [['viewer', 'Viewer'], ['analyst', 'Analyst'], ['admin', 'Admin']].forEach(function(opt) {
                roleSelect.appendChild(el('option', { value: opt[0] }, opt[1]));
            });
            roleGroup.appendChild(roleSelect);
            form.appendChild(roleGroup);

            form.appendChild(el('div', { className: 'form-error', id: 'users-form-error', hidden: '' }));

            var actions = el('div', { className: 'modal-actions' }, [
                el('button', { type: 'button', className: 'btn-secondary', id: 'users-form-cancel' }, 'Cancel'),
                el('button', { type: 'submit', className: 'btn-primary', id: 'users-form-submit' }, 'Create User')
            ]);
            form.appendChild(actions);

            modalBody.appendChild(form);
            content.appendChild(modalHeader);
            content.appendChild(modalBody);
            modal.appendChild(content);
            return modal;
        },

        _buildEditModal: function() {
            var modal = el('div', { id: 'users-edit-modal', className: 'modal', role: 'dialog', 'aria-modal': 'true', hidden: '' });
            var content = el('div', { className: 'modal-content' });
            var modalHeader = el('div', { className: 'modal-header' }, [
                el('h2', null, 'Edit User'),
                el('button', { className: 'modal-close', id: 'users-edit-modal-close', 'aria-label': 'Close', textContent: '\u00D7' })
            ]);
            var modalBody = el('div', { className: 'modal-body' });
            var form = el('form', { id: 'users-edit-form', autocomplete: 'off' });
            form.appendChild(el('input', { type: 'hidden', id: 'users-edit-id' }));
            form.appendChild(this._formGroup('users-edit-username', 'Username', 'text', { required: '', minlength: '3', maxlength: '50' }));
            form.appendChild(this._formGroup('users-edit-email', 'Email', 'email', { required: '' }));

            // Role select
            var roleGroup = el('div', { className: 'form-group' });
            roleGroup.appendChild(el('label', { 'for': 'users-edit-role' }, 'Role'));
            var roleSelect = el('select', { id: 'users-edit-role' });
            [['viewer', 'Viewer'], ['analyst', 'Analyst'], ['admin', 'Admin']].forEach(function(opt) {
                roleSelect.appendChild(el('option', { value: opt[0] }, opt[1]));
            });
            roleGroup.appendChild(roleSelect);
            form.appendChild(roleGroup);

            // Status select
            var statusGroup = el('div', { className: 'form-group' });
            statusGroup.appendChild(el('label', { 'for': 'users-edit-active' }, 'Status'));
            var statusSelect = el('select', { id: 'users-edit-active' });
            statusSelect.appendChild(el('option', { value: 'true' }, 'Active'));
            statusSelect.appendChild(el('option', { value: 'false' }, 'Inactive'));
            statusGroup.appendChild(statusSelect);
            form.appendChild(statusGroup);

            form.appendChild(el('div', { className: 'form-error', id: 'users-edit-error', hidden: '' }));

            var actions = el('div', { className: 'modal-actions' }, [
                el('button', { type: 'button', className: 'btn-secondary', id: 'users-edit-cancel' }, 'Cancel'),
                el('button', { type: 'submit', className: 'btn-primary' }, 'Save Changes')
            ]);
            form.appendChild(actions);

            modalBody.appendChild(form);
            content.appendChild(modalHeader);
            content.appendChild(modalBody);
            modal.appendChild(content);
            return modal;
        },

        _buildDeleteModal: function() {
            var modal = el('div', { id: 'users-delete-modal', className: 'modal', role: 'dialog', 'aria-modal': 'true', hidden: '' });
            var content = el('div', { className: 'modal-content modal-sm' });
            var modalHeader = el('div', { className: 'modal-header' }, [
                el('h2', null, 'Delete User'),
                el('button', { className: 'modal-close', id: 'users-delete-modal-close', 'aria-label': 'Close', textContent: '\u00D7' })
            ]);
            var modalBody = el('div', { className: 'modal-body' }, [
                el('p', { id: 'users-delete-message' }, 'Are you sure you want to delete this user? This action cannot be undone.'),
                el('div', { className: 'modal-actions' }, [
                    el('button', { type: 'button', className: 'btn-secondary', id: 'users-delete-cancel' }, 'Cancel'),
                    el('button', { type: 'button', className: 'btn-danger', id: 'users-delete-confirm' }, 'Delete User')
                ])
            ]);
            content.appendChild(modalHeader);
            content.appendChild(modalBody);
            modal.appendChild(content);
            return modal;
        },

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

            // Search with debounce
            var searchTimer = null;
            var searchInput = document.getElementById('users-search');
            if (searchInput) {
                searchInput.addEventListener('input', function() {
                    clearTimeout(searchTimer);
                    searchTimer = setTimeout(function() {
                        self.searchQuery = searchInput.value.trim();
                        self.currentPage = 1;
                        self._fetchUsers();
                    }, 300);
                });
            }

            // Create User button
            var createBtn = document.getElementById('users-create-btn');
            if (createBtn) {
                createBtn.addEventListener('click', function() { self._openCreateModal(); });
            }

            // Create form submit
            var createForm = document.getElementById('users-create-form');
            if (createForm) {
                createForm.addEventListener('submit', function(e) { e.preventDefault(); self._handleCreateUser(); });
            }

            // Create modal close/cancel
            var createClose = document.getElementById('users-create-modal-close');
            var createCancel = document.getElementById('users-form-cancel');
            if (createClose) createClose.addEventListener('click', function() { self._closeModal('users-create-modal'); });
            if (createCancel) createCancel.addEventListener('click', function() { self._closeModal('users-create-modal'); });

            // Edit form submit
            var editForm = document.getElementById('users-edit-form');
            if (editForm) {
                editForm.addEventListener('submit', function(e) { e.preventDefault(); self._handleEditUser(); });
            }

            // Edit modal close/cancel
            var editClose = document.getElementById('users-edit-modal-close');
            var editCancel = document.getElementById('users-edit-cancel');
            if (editClose) editClose.addEventListener('click', function() { self._closeModal('users-edit-modal'); });
            if (editCancel) editCancel.addEventListener('click', function() { self._closeModal('users-edit-modal'); });

            // Delete modal close/cancel
            var deleteClose = document.getElementById('users-delete-modal-close');
            var deleteCancel = document.getElementById('users-delete-cancel');
            if (deleteClose) deleteClose.addEventListener('click', function() { self._closeModal('users-delete-modal'); });
            if (deleteCancel) deleteCancel.addEventListener('click', function() { self._closeModal('users-delete-modal'); });

            // Table row actions via event delegation
            var tableBody = document.getElementById('users-table-body');
            if (tableBody) {
                tableBody.addEventListener('click', function(e) {
                    var btn = e.target.closest('[data-action]');
                    if (!btn) return;
                    var action = btn.getAttribute('data-action');
                    var userId = btn.getAttribute('data-user-id');
                    if (action === 'edit') self._openEditModal(userId);
                    else if (action === 'delete') self._openDeleteModal(userId);
                    else if (action === 'unlock') self._unlockUser(userId);
                });
            }
        },

        _fetchUsers: function() {
            var self = this;
            var url = API_BASE + '/users?page=' + this.currentPage + '&per_page=' + this.perPage;
            if (this.searchQuery) {
                url += '&search=' + encodeURIComponent(this.searchQuery);
            }

            fetch(url, {
                headers: { 'Content-Type': 'application/json' }
            }).then(function(response) {
                if (!response.ok) throw new Error('Failed to fetch users');
                return response.json();
            }).then(function(data) {
                if (Array.isArray(data)) {
                    self.users = data;
                    self.totalUsers = data.length;
                } else {
                    self.users = data.users || data.items || [];
                    self.totalUsers = data.total || self.users.length;
                }
                self._renderTable();
                self._renderPagination();
                self._updateCountLabel();
            }).catch(function(err) {
                console.error('Error fetching users:', err);
                var tbody = document.getElementById('users-table-body');
                if (tbody) {
                    tbody.textContent = '';
                    var tr = el('tr');
                    var td = el('td', { colspan: '6', className: 'table-error' });
                    td.appendChild(document.createTextNode('Failed to load users. '));
                    td.appendChild(el('button', { className: 'btn-link', onClick: function() { self._fetchUsers(); } }, 'Retry'));
                    tr.appendChild(td);
                    tbody.appendChild(tr);
                }
            });
        },

        _renderTable: function() {
            var tbody = document.getElementById('users-table-body');
            if (!tbody) return;
            tbody.textContent = '';

            if (this.users.length === 0) {
                var tr = el('tr');
                tr.appendChild(el('td', { colspan: '6', className: 'table-empty' },
                    this.searchQuery ? 'No users match your search.' : 'No users found.'));
                tbody.appendChild(tr);
                return;
            }

            for (var i = 0; i < this.users.length; i++) {
                var user = this.users[i];
                var tr = el('tr');
                tr.appendChild(el('td', { className: 'td-primary' }, user.username || ''));
                tr.appendChild(el('td', null, user.email || '-'));
                tr.appendChild(this._roleBadgeTd(user.role));
                tr.appendChild(this._statusBadgeTd(user));
                tr.appendChild(el('td', null, user.created_at ? new Date(user.created_at).toLocaleDateString() : '-'));
                tr.appendChild(this._actionsTd(user));
                tbody.appendChild(tr);
            }
        },

        _roleBadgeTd: function(role) {
            var td = el('td');
            var classes = { admin: 'badge badge-purple', analyst: 'badge badge-blue', viewer: 'badge badge-gray' };
            td.appendChild(el('span', { className: classes[role] || 'badge badge-gray' }, role || 'viewer'));
            return td;
        },

        _statusBadgeTd: function(user) {
            var td = el('td');
            if (user.is_locked || user.account_locked) {
                td.appendChild(el('span', { className: 'badge badge-danger' }, 'Locked'));
            } else if (user.is_active === false) {
                td.appendChild(el('span', { className: 'badge badge-gray' }, 'Inactive'));
            } else {
                td.appendChild(el('span', { className: 'badge badge-success' }, 'Active'));
            }
            return td;
        },

        _actionsTd: function(user) {
            var td = el('td', { className: 'td-actions' });
            var wrap = el('div', { className: 'action-buttons' });

            // Edit button
            wrap.appendChild(el('button', {
                className: 'btn-icon btn-sm',
                'data-action': 'edit',
                'data-user-id': String(user.id),
                title: 'Edit user'
            }, '\u270E'));

            // Unlock button (if locked)
            if (user.is_locked || user.account_locked) {
                wrap.appendChild(el('button', {
                    className: 'btn-icon btn-sm',
                    'data-action': 'unlock',
                    'data-user-id': String(user.id),
                    title: 'Unlock account'
                }, '\uD83D\uDD13'));
            }

            // Delete button (not for self)
            var currentUserId = window.DMARC && window.DMARC.currentUser ? window.DMARC.currentUser.id : null;
            if (!currentUserId || String(user.id) !== String(currentUserId)) {
                wrap.appendChild(el('button', {
                    className: 'btn-icon btn-sm btn-icon-danger',
                    'data-action': 'delete',
                    'data-user-id': String(user.id),
                    title: 'Delete user'
                }, '\uD83D\uDDD1'));
            }

            td.appendChild(wrap);
            return td;
        },

        _renderPagination: function() {
            var container = document.getElementById('users-pagination');
            if (!container) return;
            container.textContent = '';

            var totalPages = Math.ceil(this.totalUsers / this.perPage);
            if (totalPages <= 1) return;

            var self = this;
            var prevBtn = el('button', {
                className: 'btn-secondary btn-sm pagination-btn',
                disabled: this.currentPage <= 1 ? '' : undefined
            }, 'Previous');
            prevBtn.addEventListener('click', function() {
                if (self.currentPage > 1) { self.currentPage--; self._fetchUsers(); }
            });
            container.appendChild(prevBtn);

            var startPage = Math.max(1, this.currentPage - 2);
            var endPage = Math.min(totalPages, this.currentPage + 2);
            for (var p = startPage; p <= endPage; p++) {
                (function(page) {
                    var btn = el('button', {
                        className: 'btn-sm pagination-btn' + (page === self.currentPage ? ' pagination-btn-active' : '')
                    }, String(page));
                    btn.addEventListener('click', function() { self.currentPage = page; self._fetchUsers(); });
                    container.appendChild(btn);
                })(p);
            }

            var nextBtn = el('button', {
                className: 'btn-secondary btn-sm pagination-btn',
                disabled: this.currentPage >= totalPages ? '' : undefined
            }, 'Next');
            nextBtn.addEventListener('click', function() {
                if (self.currentPage < totalPages) { self.currentPage++; self._fetchUsers(); }
            });
            container.appendChild(nextBtn);
        },

        _updateCountLabel: function() {
            var label = document.getElementById('users-count-label');
            if (label) {
                label.textContent = this.totalUsers + ' user' + (this.totalUsers !== 1 ? 's' : '');
            }
        },

        // Create User
        _openCreateModal: function() {
            var form = document.getElementById('users-create-form');
            if (form) form.reset();
            var error = document.getElementById('users-form-error');
            if (error) error.hidden = true;
            var pwGroup = document.getElementById('users-form-password-group');
            if (pwGroup) pwGroup.style.display = '';
            var title = document.getElementById('users-modal-title');
            if (title) title.textContent = 'Create User';
            var submitBtn = document.getElementById('users-form-submit');
            if (submitBtn) submitBtn.textContent = 'Create User';
            this._openModal('users-create-modal');
        },

        _handleCreateUser: function() {
            var self = this;
            var username = document.getElementById('users-form-username').value.trim();
            var email = document.getElementById('users-form-email').value.trim();
            var password = document.getElementById('users-form-password').value;
            var role = document.getElementById('users-form-role').value;
            var errorEl = document.getElementById('users-form-error');

            if (!username || !email || !password) {
                if (errorEl) { errorEl.textContent = 'All fields are required.'; errorEl.hidden = false; }
                return;
            }

            var submitBtn = document.getElementById('users-form-submit');
            if (submitBtn) { submitBtn.disabled = true; submitBtn.textContent = 'Creating...'; }

            fetch(API_BASE + '/users', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ username: username, email: email, password: password, role: role })
            }).then(function(response) {
                if (!response.ok) return response.json().then(function(d) { throw new Error(d.detail || 'Failed to create user'); });
                return response.json();
            }).then(function() {
                self._closeModal('users-create-modal');
                showNotification('User created successfully', 'success');
                self._fetchUsers();
            }).catch(function(err) {
                if (errorEl) { errorEl.textContent = err.message; errorEl.hidden = false; }
            }).finally(function() {
                if (submitBtn) { submitBtn.disabled = false; submitBtn.textContent = 'Create User'; }
            });
        },

        // Edit User
        _openEditModal: function(userId) {
            var user = this._findUser(userId);
            if (!user) return;

            document.getElementById('users-edit-id').value = user.id;
            document.getElementById('users-edit-username').value = user.username || '';
            document.getElementById('users-edit-email').value = user.email || '';
            document.getElementById('users-edit-role').value = user.role || 'viewer';
            document.getElementById('users-edit-active').value = user.is_active !== false ? 'true' : 'false';
            var error = document.getElementById('users-edit-error');
            if (error) error.hidden = true;
            this._openModal('users-edit-modal');
        },

        _handleEditUser: function() {
            var self = this;
            var userId = document.getElementById('users-edit-id').value;
            var username = document.getElementById('users-edit-username').value.trim();
            var email = document.getElementById('users-edit-email').value.trim();
            var role = document.getElementById('users-edit-role').value;
            var isActive = document.getElementById('users-edit-active').value === 'true';
            var errorEl = document.getElementById('users-edit-error');

            fetch(API_BASE + '/users/' + encodeURIComponent(userId), {
                method: 'PATCH',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ username: username, email: email, role: role, is_active: isActive })
            }).then(function(response) {
                if (!response.ok) return response.json().then(function(d) { throw new Error(d.detail || 'Failed to update user'); });
                return response.json();
            }).then(function() {
                self._closeModal('users-edit-modal');
                showNotification('User updated successfully', 'success');
                self._fetchUsers();
            }).catch(function(err) {
                if (errorEl) { errorEl.textContent = err.message; errorEl.hidden = false; }
            });
        },

        // Delete User
        _openDeleteModal: function(userId) {
            var user = this._findUser(userId);
            if (!user) return;
            this._deleteUserId = userId;
            var msg = document.getElementById('users-delete-message');
            if (msg) {
                msg.textContent = 'Are you sure you want to delete user "' + (user.username || '') + '"? This action cannot be undone.';
            }
            this._openModal('users-delete-modal');

            var self = this;
            var confirmBtn = document.getElementById('users-delete-confirm');
            var newBtn = confirmBtn.cloneNode(true);
            confirmBtn.parentNode.replaceChild(newBtn, confirmBtn);
            newBtn.addEventListener('click', function() { self._handleDeleteUser(); });
        },

        _handleDeleteUser: function() {
            var self = this;
            var userId = this._deleteUserId;
            if (!userId) return;

            var confirmBtn = document.getElementById('users-delete-confirm');
            if (confirmBtn) { confirmBtn.disabled = true; confirmBtn.textContent = 'Deleting...'; }

            fetch(API_BASE + '/users/' + encodeURIComponent(userId), {
                method: 'DELETE',
                headers: { 'Content-Type': 'application/json' }
            }).then(function(response) {
                if (!response.ok) return response.json().then(function(d) { throw new Error(d.detail || 'Failed to delete user'); });
                self._closeModal('users-delete-modal');
                showNotification('User deleted successfully', 'success');
                self._fetchUsers();
            }).catch(function(err) {
                showNotification(err.message, 'error');
            }).finally(function() {
                if (confirmBtn) { confirmBtn.disabled = false; confirmBtn.textContent = 'Delete User'; }
            });
        },

        // Unlock User
        _unlockUser: function(userId) {
            var self = this;
            fetch(API_BASE + '/users/' + encodeURIComponent(userId) + '/unlock', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' }
            }).then(function(response) {
                if (!response.ok) throw new Error('Failed to unlock user');
                showNotification('User account unlocked', 'success');
                self._fetchUsers();
            }).catch(function(err) {
                showNotification(err.message, 'error');
            });
        },

        // Helpers
        _findUser: function(userId) {
            for (var i = 0; i < this.users.length; i++) {
                if (String(this.users[i].id) === String(userId)) return this.users[i];
            }
            return null;
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
    window.DMARC.UsersPage = UsersPage;

    if (window.DMARC.Router) {
        window.DMARC.Router.register('users', UsersPage);
    }
})();

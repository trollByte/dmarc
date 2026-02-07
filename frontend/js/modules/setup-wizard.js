/**
 * Setup Wizard — Browser-based first-run configuration.
 *
 * Checks /api/setup/status on page load. If the app is unconfigured,
 * shows a 5-step wizard overlay. Otherwise, falls through to the
 * normal login overlay.
 */

const SETUP_API = (window.DMARC_CONFIG?.apiBase || '/api') + '/setup';
let _setupStep = 1;
const SETUP_TOTAL_STEPS = 5;

/**
 * Check if the app needs setup. Called before showing the login form.
 * Returns true if setup wizard was shown, false if login should proceed.
 */
async function checkSetupNeeded() {
    try {
        const resp = await fetch(`${SETUP_API}/status`);
        if (!resp.ok) return false; // endpoint missing = already configured
        const data = await resp.json();
        if (!data.configured) {
            showSetupWizard();
            return true;
        }
    } catch (e) {
        // Network error or endpoint not found — assume configured
        console.warn('Setup status check failed, assuming configured:', e.message);
    }
    // Remove wizard from DOM so its inputs don't interfere with login selectors
    const overlay = document.getElementById('setupWizardOverlay');
    if (overlay) overlay.remove();
    return false;
}

function showSetupWizard() {
    const overlay = document.getElementById('setupWizardOverlay');
    if (overlay) overlay.style.display = '';
    _setupStep = 1;
    updateSetupStep();
}

function hideSetupWizard() {
    const overlay = document.getElementById('setupWizardOverlay');
    if (overlay) overlay.style.display = 'none';
}

function updateSetupStep() {
    // Hide all steps, show current
    for (let i = 1; i <= SETUP_TOTAL_STEPS; i++) {
        const el = document.getElementById('setupStep' + i);
        if (el) el.style.display = (i === _setupStep) ? '' : 'none';
    }
    // Update progress bar
    const bar = document.getElementById('setupProgressBar');
    if (bar) {
        bar.style.width = ((_setupStep / SETUP_TOTAL_STEPS) * 100) + '%';
    }
}

function setupWizardNext() {
    // Validate current step before advancing
    if (_setupStep === 3) {
        if (!validateAdminStep()) return;
    }
    if (_setupStep < SETUP_TOTAL_STEPS) {
        _setupStep++;
        updateSetupStep();
    }
}

function setupWizardBack() {
    if (_setupStep > 1) {
        _setupStep--;
        updateSetupStep();
    }
}

function validateAdminStep() {
    const email = document.getElementById('setupEmail')?.value?.trim();
    const password = document.getElementById('setupPassword')?.value;
    const confirm = document.getElementById('setupPasswordConfirm')?.value;
    const errorEl = document.getElementById('setupError');

    if (!email) {
        showSetupError(errorEl, 'Email is required.');
        return false;
    }
    if (!password || password.length < 8) {
        showSetupError(errorEl, 'Password must be at least 8 characters.');
        return false;
    }
    if (password !== confirm) {
        showSetupError(errorEl, 'Passwords do not match.');
        return false;
    }
    if (errorEl) errorEl.hidden = true;
    return true;
}

function showSetupError(el, msg) {
    if (el) {
        el.textContent = msg;
        el.hidden = false;
    }
}

async function setupWizardSubmit() {
    const btn = document.getElementById('setupSubmitBtn');
    if (btn) {
        btn.disabled = true;
        btn.textContent = 'Setting up...';
    }

    const body = {
        admin_email: document.getElementById('setupEmail')?.value?.trim(),
        admin_password: document.getElementById('setupPassword')?.value,
        email_host: document.getElementById('setupImapHost')?.value?.trim() || '',
        email_user: document.getElementById('setupImapUser')?.value?.trim() || '',
        email_password: document.getElementById('setupImapPass')?.value || '',
        maxmind_license_key: document.getElementById('setupMaxmindKey')?.value?.trim() || '',
    };

    try {
        const resp = await fetch(`${SETUP_API}/initialize`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(body),
        });

        if (!resp.ok) {
            const data = await resp.json().catch(() => ({}));
            throw new Error(data.detail || 'Setup failed. Please try again.');
        }

        // Success — advance to final step
        _setupStep = SETUP_TOTAL_STEPS;
        updateSetupStep();
    } catch (e) {
        // Show error on step 4
        const errorEl = document.getElementById('setupError');
        if (errorEl) {
            errorEl.textContent = e.message;
            errorEl.hidden = false;
        }
    } finally {
        if (btn) {
            btn.disabled = false;
            btn.textContent = 'Complete Setup';
        }
    }
}

function setupWizardFinish() {
    hideSetupWizard();
    // Pre-fill the login email
    const email = document.getElementById('setupEmail')?.value?.trim();
    const loginUsername = document.getElementById('loginUsername');
    if (email && loginUsername) {
        loginUsername.value = email;
    }
    // Focus password field
    document.getElementById('loginPassword')?.focus();
}

/**
 * login.js — Auth logic for BetweenYears
 */

const API_BASE = 'http://localhost:8000'; // FastAPI backend

const authForm = document.getElementById('auth-form');
const authCard = document.getElementById('auth-card');
const authTitle = document.getElementById('auth-title');
const authSubtitle = document.getElementById('auth-subtitle');
const toggleAuth = document.getElementById('toggle-auth');
const toggleText = document.getElementById('toggle-text');
const guestBtn = document.getElementById('guest-btn');

let isSignupMode = false;

// ── UI Interactions ──────────────────────────────────────────────────────────

toggleAuth.addEventListener('click', (e) => {
    e.preventDefault();
    isSignupMode = !isSignupMode;
    
    if (isSignupMode) {
        authCard.classList.add('is-signup');
        authTitle.innerText = "Become a Reflecter";
        authSubtitle.innerText = "Create space for your future self.";
        toggleText.innerHTML = 'Already have an account? <a href="#" id="toggle-auth">Sign In</a>';
    } else {
        authCard.classList.remove('is-signup');
        authTitle.innerText = "Welcome Back";
        authSubtitle.innerText = "Continue your journey of reflection.";
        toggleText.innerHTML = 'Don\'t have an account? <a href="#" id="toggle-auth">Sign Up</a>';
    }
    
    // Re-attach listener to the link inside innerHTML
    document.getElementById('toggle-auth').addEventListener('click', (e) => {
        e.preventDefault();
        toggleAuth.click();
    });
});

guestBtn.addEventListener('click', () => {
    localStorage.setItem('by_guest_mode', 'true');
    localStorage.removeItem('by_access_token');
    showToast('Entering as guest ✨', 'success');
    setTimeout(() => {
        window.location.href = 'betweenyears.html';
    }, 1200);
});

// ── Form Submission ──────────────────────────────────────────────────────────

authForm.addEventListener('submit', async (e) => {
    e.preventDefault();
    
    const email = document.getElementById('email').value;
    const password = document.getElementById('password').value;
    const name = document.getElementById('name').value;
    
    const submitBtn = isSignupMode ? document.getElementById('signup-btn') : document.getElementById('login-btn');
    submitBtn.classList.add('loading');
    submitBtn.disabled = true;

    try {
        let endpoint = isSignupMode ? '/auth/signup' : '/auth/login';
        let body = isSignupMode 
            ? { email, password, display_name: name }
            : { email, password };

        const response = await fetch(`${API_BASE}${endpoint}`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(body)
        });

        const data = await response.json();

        if (response.ok) {
            // Save tokens
            localStorage.setItem('by_access_token', data.access_token);
            localStorage.setItem('by_refresh_token', data.refresh_token);
            localStorage.setItem('by_user_id', data.user_id);
            localStorage.setItem('by_display_name', data.display_name || '');
            localStorage.removeItem('by_guest_mode');

            showToast(isSignupMode ? 'Account created! Welcome 🌱' : 'Welcome back ✨', 'success');
            
            setTimeout(() => {
                window.location.href = 'betweenyears.html';
            }, 1000);
        } else {
            showToast(data.detail || 'Authentication failed. Please try again.', 'error');
        }
    } catch (err) {
        showToast('System error. Is the backend running?', 'error');
        console.error(err);
    } finally {
        submitBtn.classList.remove('loading');
        submitBtn.disabled = false;
    }
});

// ── Toast System ─────────────────────────────────────────────────────────────

function showToast(message, type = 'success') {
    const toast = document.getElementById('toast');
    const toastMsg = document.getElementById('toast-msg');
    const toastIcon = document.getElementById('toast-icon');

    toastMsg.innerText = message;
    toastIcon.innerText = type === 'success' ? '✨' : '⚠️';
    
    if (type === 'error') toast.classList.add('error');
    else toast.classList.remove('error');

    toast.classList.add('show');
    
    setTimeout(() => {
        toast.classList.remove('show');
    }, 4000);
}

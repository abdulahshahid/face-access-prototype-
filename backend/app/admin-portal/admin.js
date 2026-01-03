// Use the same JavaScript from my previous answer, but save it to this file
// Copy the entire admin.js content from the previous answer here, but update the API base URL:
const API_BASE_URL = '/api/admin';  // Note: This is different!

// And update the authentication check
function checkAuth() {
    const token = localStorage.getItem('access_token');
    if (!token) {
        window.location.href = '/api/admin/portal/login';
        return false;
    }
    return true;
}

// Update all fetch calls to include the token
async function fetchWithAuth(url, options = {}) {
    const token = localStorage.getItem('access_token');
    if (!token) {
        window.location.href = '/api/admin/portal/login';
        return null;
    }
    
    const defaultOptions = {
        headers: {
            'Authorization': `Bearer ${token}`,
            'Content-Type': 'application/json',
            ...options.headers
        }
    };
    
    return fetch(url, { ...defaultOptions, ...options });
}
// Configuration
const API_BASE_URL = 'http://localhost:8000/api/v1';
let currentUserToDelete = null;
let attendeesData = [];
let currentPage = 1;
let pageSize = 10;
let totalPages = 1;

// Initialize admin portal
document.addEventListener('DOMContentLoaded', function() {
    // Check authentication
    const token = localStorage.getItem('adminToken');
    if (!token && !window.location.pathname.includes('admin.html')) {
        window.location.href = 'admin.html';
        return;
    }
    
    // Set admin email
    const adminEmail = localStorage.getItem('adminEmail') || 'admin@example.com';
    document.getElementById('adminEmail').textContent = adminEmail;
    
    // Setup navigation
    setupNavigation();
    
    // Load initial data
    if (document.querySelector('.content-section.active').id === 'dashboardSection') {
        loadDashboardData();
    } else if (document.querySelector('.content-section.active').id === 'attendeesSection') {
        loadAttendees();
    }
    
    // Setup file upload
    setupFileUpload();
    
    // Setup logout
    document.getElementById('logoutBtn').addEventListener('click', logout);
    
    // Setup threshold slider
    const thresholdSlider = document.getElementById('thresholdSlider');
    const thresholdValue = document.getElementById('thresholdValue');
    if (thresholdSlider) {
        thresholdSlider.addEventListener('input', function() {
            thresholdValue.textContent = this.value;
        });
    }
});

// Navigation
function setupNavigation() {
    const menuItems = document.querySelectorAll('.menu-item');
    const sections = document.querySelectorAll('.content-section');
    const pageTitle = document.getElementById('pageTitle');
    const pageSubtitle = document.getElementById('pageSubtitle');
    
    const sectionTitles = {
        'dashboard': 'Dashboard',
        'attendees': 'Attendee Management',
        'upload': 'Bulk Upload',
        'settings': 'Settings'
    };
    
    const sectionSubtitles = {
        'dashboard': 'System overview and analytics',
        'attendees': 'View, search, and manage all attendees',
        'upload': 'Upload CSV to bulk create attendee records',
        'settings': 'Configure system preferences and security'
    };
    
    menuItems.forEach(item => {
        item.addEventListener('click', function(e) {
            e.preventDefault();
            
            // Update active menu item
            menuItems.forEach(i => i.classList.remove('active'));
            this.classList.add('active');
            
            // Get target section
            const section = this.getAttribute('data-section');
            
            // Update active section
            sections.forEach(s => s.classList.remove('active'));
            document.getElementById(`${section}Section`).classList.add('active');
            
            // Update page title
            pageTitle.textContent = sectionTitles[section];
            pageSubtitle.textContent = sectionSubtitles[section];
            
            // Load data for section
            if (section === 'dashboard') {
                loadDashboardData();
            } else if (section === 'attendees') {
                loadAttendees();
            }
        });
    });
}

// Dashboard Data
async function loadDashboardData() {
    try {
        // Fetch total attendees
        const response = await fetch(`${API_BASE_URL}/attendees?limit=1`, {
            headers: {
                'Authorization': `Bearer ${localStorage.getItem('adminToken')}`
            }
        });
        
        if (response.ok) {
            const attendees = await response.json();
            document.getElementById('totalAttendees').textContent = attendees.length;
        }
        
        // Initialize charts
        initCharts();
        
    } catch (error) {
        console.error('Error loading dashboard:', error);
        showToast('Error loading dashboard data', 'error');
    }
}

// Charts
function initCharts() {
    // Registrations Timeline Chart
    const regCtx = document.getElementById('registrationsChart')?.getContext('2d');
    if (regCtx) {
        new Chart(regCtx, {
            type: 'line',
            data: {
                labels: ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun'],
                datasets: [{
                    label: 'Registrations',
                    data: [12, 19, 8, 15, 22, 18, 25],
                    borderColor: '#6366f1',
                    backgroundColor: 'rgba(99, 102, 241, 0.1)',
                    borderWidth: 2,
                    fill: true,
                    tension: 0.4
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                    legend: {
                        display: false
                    }
                },
                scales: {
                    y: {
                        beginAtZero: true,
                        grid: {
                            color: 'rgba(255, 255, 255, 0.05)'
                        },
                        ticks: {
                            color: 'rgba(255, 255, 255, 0.6)'
                        }
                    },
                    x: {
                        grid: {
                            color: 'rgba(255, 255, 255, 0.05)'
                        },
                        ticks: {
                            color: 'rgba(255, 255, 255, 0.6)'
                        }
                    }
                }
            }
        });
    }
    
    // Status Distribution Chart
    const statusCtx = document.getElementById('statusChart')?.getContext('2d');
    if (statusCtx) {
        new Chart(statusCtx, {
            type: 'doughnut',
            data: {
                labels: ['Verified', 'Registered', 'Pending', 'Blocked'],
                datasets: [{
                    data: [45, 30, 20, 5],
                    backgroundColor: [
                        'rgba(16, 185, 129, 0.8)',
                        'rgba(59, 130, 246, 0.8)',
                        'rgba(245, 158, 11, 0.8)',
                        'rgba(239, 68, 68, 0.8)'
                    ],
                    borderWidth: 0
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                    legend: {
                        position: 'right',
                        labels: {
                            color: 'rgba(255, 255, 255, 0.8)',
                            padding: 20
                        }
                    }
                }
            }
        });
    }
}

// Attendee Management
async function loadAttendees() {
    const tableBody = document.getElementById('attendeesTableBody');
    const loadingRow = document.getElementById('loadingRow');
    
    if (!tableBody) return;
    
    // Show loading
    if (loadingRow) {
        loadingRow.style.display = '';
    }
    
    try {
        const search = document.getElementById('attendeeSearch')?.value || '';
        const statusFilter = document.getElementById('statusFilter')?.value || '';
        const sortFilter = document.getElementById('sortFilter')?.value || 'newest';
        
        // Build query parameters
        let queryParams = `?skip=${(currentPage - 1) * pageSize}&limit=${pageSize}`;
        
        if (search) queryParams += `&search=${encodeURIComponent(search)}`;
        
        const response = await fetch(`${API_BASE_URL}/attendees${queryParams}`, {
            headers: {
                'Authorization': `Bearer ${localStorage.getItem('adminToken')}`
            }
        });
        
        if (response.ok) {
            attendeesData = await response.json();
            renderAttendeesTable(attendeesData);
            
            // Update pagination
            updatePagination();
        } else if (response.status === 401) {
            showToast('Session expired. Please login again.', 'error');
            logout();
        } else {
            throw new Error(`HTTP ${response.status}`);
        }
        
    } catch (error) {
        console.error('Error loading attendees:', error);
        
        // Fallback to mock data for demo
        if (window.location.hostname === 'localhost' || window.location.hostname === '127.0.0.1') {
            attendeesData = getMockAttendees();
            renderAttendeesTable(attendeesData);
            showToast('Using demo data (backend not reachable)', 'warning');
        } else {
            showToast('Error loading attendees', 'error');
        }
    } finally {
        if (loadingRow) {
            loadingRow.style.display = 'none';
        }
    }
}

function renderAttendeesTable(attendees) {
    const tableBody = document.getElementById('attendeesTableBody');
    if (!tableBody) return;
    
    tableBody.innerHTML = '';
    
    if (attendees.length === 0) {
        tableBody.innerHTML = `
            <tr>
                <td colspan="8" style="text-align: center; padding: 40px;">
                    <div style="color: rgba(255, 255, 255, 0.5);">
                        <i class="fas fa-users" style="font-size: 32px; margin-bottom: 16px; display: block;"></i>
                        No attendees found
                    </div>
                </td>
            </tr>
        `;
        return;
    }
    
    // Apply filters
    let filteredAttendees = [...attendees];
    
    const statusFilter = document.getElementById('statusFilter')?.value;
    if (statusFilter) {
        filteredAttendees = filteredAttendees.filter(a => a.status === statusFilter);
    }
    
    const sortFilter = document.getElementById('sortFilter')?.value || 'newest';
    filteredAttendees.sort((a, b) => {
        switch (sortFilter) {
            case 'oldest':
                return new Date(a.created_at) - new Date(b.created_at);
            case 'name':
                return a.name.localeCompare(b.name);
            case 'email':
                return a.email.localeCompare(b.email);
            default: // newest
                return new Date(b.created_at) - new Date(a.created_at);
        }
    });
    
    // Render rows
    filteredAttendees.forEach(attendee => {
        const row = document.createElement('tr');
        
        // Format dates
        const createdDate = new Date(attendee.created_at).toLocaleDateString();
        const lastAccess = attendee.last_access 
            ? new Date(attendee.last_access).toLocaleDateString()
            : 'Never';
        
        // Status badge
        const statusClass = `status-${attendee.status}`;
        const statusText = attendee.status.charAt(0).toUpperCase() + attendee.status.slice(1);
        
        row.innerHTML = `
            <td>${attendee.id}</td>
            <td>
                <div style="font-weight: 500;">${attendee.name || 'Unknown'}</div>
            </td>
            <td>${attendee.email}</td>
            <td>
                <code style="background: rgba(99, 102, 241, 0.1); padding: 4px 8px; border-radius: 4px; font-size: 12px;">
                    ${attendee.invite_code}
                </code>
            </td>
            <td><span class="status-badge ${statusClass}">${statusText}</span></td>
            <td>${createdDate}</td>
            <td>${lastAccess}</td>
            <td>
                <div style="display: flex; gap: 8px;">
                    <button class="btn-small" onclick="viewAttendee(${attendee.id})" title="View">
                        <i class="fas fa-eye"></i>
                    </button>
                    <button class="btn-small" onclick="editAttendee(${attendee.id})" title="Edit">
                        <i class="fas fa-edit"></i>
                    </button>
                    <button class="btn-small" onclick="confirmDelete(${attendee.id}, '${attendee.name || attendee.email}')" title="Delete">
                        <i class="fas fa-trash"></i>
                    </button>
                </div>
            </td>
        `;
        
        tableBody.appendChild(row);
    });
}

function searchAttendees() {
    currentPage = 1;
    loadAttendees();
}

function viewAttendee(id) {
    const attendee = attendeesData.find(a => a.id === id);
    if (attendee) {
        showToast(`Viewing ${attendee.name}`, 'info');
        // In a real app, you would show a detailed view modal
    }
}

function editAttendee(id) {
    const attendee = attendeesData.find(a => a.id === id);
    if (attendee) {
        showToast(`Editing ${attendee.name}`, 'info');
        // In a real app, you would show an edit modal
    }
}

function confirmDelete(id, name) {
    currentUserToDelete = id;
    document.getElementById('deleteUserName').textContent = name;
    document.getElementById('deleteModal').style.display = 'flex';
    
    // Setup delete confirmation
    document.getElementById('confirmDeleteBtn').onclick = deleteAttendee;
}

function closeModal() {
    document.getElementById('deleteModal').style.display = 'none';
    currentUserToDelete = null;
}

async function deleteAttendee() {
    if (!currentUserToDelete) return;
    
    try {
        const response = await fetch(`${API_BASE_URL}/attendees/${currentUserToDelete}`, {
            method: 'DELETE',
            headers: {
                'Authorization': `Bearer ${localStorage.getItem('adminToken')}`
            }
        });
        
        if (response.ok) {
            const result = await response.json();
            showToast(result.message || 'Attendee deleted successfully', 'success');
            
            // Reload attendees
            loadAttendees();
            
            // Close modal
            closeModal();
        } else if (response.status === 404) {
            showToast('Attendee not found', 'error');
            closeModal();
        } else {
            throw new Error(`HTTP ${response.status}`);
        }
        
    } catch (error) {
        console.error('Error deleting attendee:', error);
        showToast('Error deleting attendee', 'error');
    }
}

// Pagination
function updatePagination() {
    const totalAttendees = attendeesData.length;
    totalPages = Math.ceil(totalAttendees / pageSize);
    
    document.getElementById('currentPage').textContent = currentPage;
    document.getElementById('totalPages').textContent = totalPages;
    
    document.getElementById('prevPage').disabled = currentPage <= 1;
    document.getElementById('nextPage').disabled = currentPage >= totalPages;
}

function changePage(delta) {
    const newPage = currentPage + delta;
    if (newPage >= 1 && newPage <= totalPages) {
        currentPage = newPage;
        loadAttendees();
    }
}

function changePageSize() {
    const newSize = parseInt(document.getElementById('pageSize').value);
    if (newSize !== pageSize) {
        pageSize = newSize;
        currentPage = 1;
        loadAttendees();
    }
}

// File Upload
function setupFileUpload() {
    const dropArea = document.getElementById('dropArea');
    const fileInput = document.getElementById('csvFile');
    
    if (dropArea && fileInput) {
        // Click to browse
        dropArea.addEventListener('click', () => fileInput.click());
        
        // Drag and drop
        ['dragenter', 'dragover', 'dragleave', 'drop'].forEach(eventName => {
            dropArea.addEventListener(eventName, preventDefaults, false);
        });
        
        function preventDefaults(e) {
            e.preventDefault();
            e.stopPropagation();
        }
        
        ['dragenter', 'dragover'].forEach(eventName => {
            dropArea.addEventListener(eventName, highlight, false);
        });
        
        ['dragleave', 'drop'].forEach(eventName => {
            dropArea.addEventListener(eventName, unhighlight, false);
        });
        
        function highlight() {
            dropArea.style.borderColor = '#6366f1';
            dropArea.style.background = 'rgba(99, 102, 241, 0.05)';
        }
        
        function unhighlight() {
            dropArea.style.borderColor = '';
            dropArea.style.background = '';
        }
        
        // Handle file selection
        dropArea.addEventListener('drop', handleDrop, false);
        fileInput.addEventListener('change', handleFileSelect, false);
    }
}

function handleDrop(e) {
    const dt = e.dataTransfer;
    const files = dt.files;
    
    if (files.length > 0) {
        processFile(files[0]);
    }
}

function handleFileSelect(e) {
    const files = e.target.files;
    
    if (files.length > 0) {
        processFile(files[0]);
    }
}

async function processFile(file) {
    // Validate file
    if (!file.name.toLowerCase().endsWith('.csv')) {
        showToast('Please upload a CSV file', 'error');
        return;
    }
    
    if (file.size > 5 * 1024 * 1024) { // 5MB
        showToast('File size must be less than 5MB', 'error');
        return;
    }
    
    // Show progress
    const progress = document.getElementById('uploadProgress');
    const progressFill = document.getElementById('progressFill');
    const progressText = document.getElementById('progressText');
    const progressPercent = document.getElementById('progressPercent');
    
    progress.style.display = 'block';
    progressFill.style.width = '0%';
    progressText.textContent = 'Uploading...';
    progressPercent.textContent = '0%';
    
    // Simulate progress
    let progressValue = 0;
    const progressInterval = setInterval(() => {
        progressValue += 5;
        if (progressValue > 90) {
            clearInterval(progressInterval);
        }
        progressFill.style.width = `${progressValue}%`;
        progressPercent.textContent = `${progressValue}%`;
    }, 100);
    
    try {
        // Create FormData
        const formData = new FormData();
        formData.append('file', file);
        
        // Upload to API
        const response = await fetch(`${API_BASE_URL}/upload-csv`, {
            method: 'POST',
            headers: {
                'Authorization': `Bearer ${localStorage.getItem('adminToken')}`
            },
            body: formData
        });
        
        clearInterval(progressInterval);
        progressFill.style.width = '100%';
        progressPercent.textContent = '100%';
        
        if (response.ok) {
            const result = await response.json();
            showUploadResults(result);
            showToast(`Successfully uploaded ${result.success_count} attendees`, 'success');
            
            // Refresh attendees list
            loadAttendees();
        } else {
            throw new Error(`Upload failed: ${response.status}`);
        }
        
    } catch (error) {
        console.error('Upload error:', error);
        progressText.textContent = 'Upload failed';
        showToast('Error uploading file', 'error');
    }
}

function showUploadResults(result) {
    const resultsDiv = document.getElementById('uploadResults');
    const successCount = document.getElementById('successCount');
    const skippedCount = document.getElementById('skippedCount');
    const errorCount = document.getElementById('errorCount');
    const skippedEmailsDiv = document.getElementById('skippedEmails');
    
    successCount.textContent = result.success_count || 0;
    skippedCount.textContent = result.skipped_emails?.length || 0;
    errorCount.textContent = result.errors || 0;
    
    // Show skipped emails
    if (result.skipped_emails && result.skipped_emails.length > 0) {
        skippedEmailsDiv.innerHTML = `
            <h5>Skipped Emails (already exist):</h5>
            <ul>
                ${result.skipped_emails.map(email => `<li>${email}</li>`).join('')}
            </ul>
        `;
    } else {
        skippedEmailsDiv.innerHTML = '';
    }
    
    resultsDiv.style.display = 'block';
}

function downloadTemplate() {
    const template = `email,name
john@example.com,John Doe
jane@example.com,Jane Smith
alex@example.com,Alex Johnson`;

    const blob = new Blob([template], { type: 'text/csv' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = 'attendee_template.csv';
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
}

// Settings
function saveSettings() {
    const threshold = document.getElementById('thresholdSlider').value;
    const maxAttempts = document.getElementById('maxAttempts').value;
    const sessionTimeout = document.getElementById('sessionTimeout').value;
    const require2FA = document.getElementById('require2FA').checked;
    const emailAlerts = document.getElementById('emailAlerts').checked;
    const failedAttemptAlerts = document.getElementById('failedAttemptAlerts').checked;
    
    // Save to localStorage for demo
    localStorage.setItem('adminSettings', JSON.stringify({
        threshold,
        maxAttempts,
        sessionTimeout,
        require2FA,
        emailAlerts,
        failedAttemptAlerts,
        savedAt: new Date().toISOString()
    }));
    
    showToast('Settings saved successfully', 'success');
}

function resetSettings() {
    if (confirm('Reset all settings to default values?')) {
        document.getElementById('thresholdSlider').value = 0.75;
        document.getElementById('thresholdValue').textContent = '0.75';
        document.getElementById('maxAttempts').value = 3;
        document.getElementById('sessionTimeout').value = '30';
        document.getElementById('require2FA').checked = false;
        document.getElementById('emailAlerts').checked = true;
        document.getElementById('failedAttemptAlerts').checked = true;
        
        localStorage.removeItem('adminSettings');
        showToast('Settings reset to defaults', 'info');
    }
}

// Export
function exportAttendees() {
    if (attendeesData.length === 0) {
        showToast('No attendees to export', 'warning');
        return;
    }
    
    // Convert to CSV
    const headers = ['ID', 'Name', 'Email', 'Invite Code', 'Status', 'Created At'];
    const rows = attendeesData.map(a => [
        a.id,
        a.name || '',
        a.email,
        a.invite_code,
        a.status,
        new Date(a.created_at).toLocaleDateString()
    ]);
    
    const csvContent = [
        headers.join(','),
        ...rows.map(row => row.map(cell => `"${cell}"`).join(','))
    ].join('\n');
    
    // Download
    const blob = new Blob([csvContent], { type: 'text/csv' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `attendees_${new Date().toISOString().split('T')[0]}.csv`;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
    
    showToast('Attendees exported successfully', 'success');
}

// Authentication
function logout() {
    localStorage.removeItem('adminToken');
    localStorage.removeItem('adminEmail');
    window.location.href = 'admin.html';
}

// Toast Notifications
function showToast(message, type = 'info') {
    const container = document.getElementById('toastContainer');
    if (!container) return;
    
    const toast = document.createElement('div');
    toast.className = `toast ${type}`;
    
    const icons = {
        success: 'fas fa-check-circle',
        error: 'fas fa-exclamation-circle',
        warning: 'fas fa-exclamation-triangle',
        info: 'fas fa-info-circle'
    };
    
    toast.innerHTML = `
        <div class="toast-icon">
            <i class="${icons[type] || icons.info}"></i>
        </div>
        <div class="toast-content">
            <div class="toast-title">${type.charAt(0).toUpperCase() + type.slice(1)}</div>
            <div class="toast-message">${message}</div>
        </div>
        <button class="toast-close" onclick="this.parentElement.remove()">
            <i class="fas fa-times"></i>
        </button>
    `;
    
    container.appendChild(toast);
    
    // Auto-remove after 5 seconds
    setTimeout(() => {
        if (toast.parentElement) {
            toast.remove();
        }
    }, 5000);
}

// Mock data for demo
function getMockAttendees() {
    const names = [
        'John Doe', 'Jane Smith', 'Alex Johnson', 'Maria Garcia', 'David Brown',
        'Sarah Wilson', 'Michael Taylor', 'Emily Anderson', 'James Thomas', 'Emma Martinez'
    ];
    
    const statuses = ['pending', 'registered', 'verified', 'blocked'];
    
    return names.map((name, index) => ({
        id: index + 1,
        name: name,
        email: name.toLowerCase().replace(' ', '.') + '@example.com',
        invite_code: `INV${String(index + 1).padStart(3, '0')}${Math.random().toString(36).substr(2, 6).toUpperCase()}`,
        status: statuses[Math.floor(Math.random() * statuses.length)],
        created_at: new Date(Date.now() - Math.random() * 30 * 24 * 60 * 60 * 1000).toISOString(),
        last_access: Math.random() > 0.3 ? new Date(Date.now() - Math.random() * 7 * 24 * 60 * 60 * 1000).toISOString() : null
    }));
}
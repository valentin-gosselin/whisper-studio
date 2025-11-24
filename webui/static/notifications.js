/**
 * Centralized notifications system for Whisper Studio
 * Handles both temporary toast notifications and persistent in-app notifications
 */

/**
 * Show a temporary toast notification
 * @param {string} message - Message to display
 * @param {string} type - Notification type: 'success', 'error', 'info', 'warning'
 * @param {number} duration - Duration in ms (default: 4000)
 */
function showToast(message, type = 'info', duration = 4000) {
    const isDark = document.body.classList.contains('neon-night');

    const toast = document.createElement('div');
    toast.className = 'toast-notification';

    // Type-specific colors
    let bgColor, borderColor, textColor;

    if (isDark) {
        // Neon Night theme
        const colors = {
            success: { bg: 'rgba(0, 255, 200, 0.15)', border: '#00ffc8', text: '#00ffc8' },
            error: { bg: 'rgba(255, 0, 100, 0.15)', border: '#ff0064', text: '#ff0064' },
            warning: { bg: 'rgba(255, 200, 0, 0.15)', border: '#ffc800', text: '#ffc800' },
            info: { bg: 'rgba(0, 255, 255, 0.15)', border: '#00ffff', text: '#00ffff' }
        };
        const color = colors[type] || colors.info;
        bgColor = color.bg;
        borderColor = color.border;
        textColor = color.text;
    } else {
        // Light theme
        const colors = {
            success: { bg: 'rgba(76, 175, 80, 0.15)', border: '#4caf50', text: '#2e7d32' },
            error: { bg: 'rgba(244, 67, 54, 0.15)', border: '#f44336', text: '#c62828' },
            warning: { bg: 'rgba(255, 152, 0, 0.15)', border: '#ff9800', text: '#e65100' },
            info: { bg: 'rgba(33, 150, 243, 0.15)', border: '#2196f3', text: '#1565c0' }
        };
        const color = colors[type] || colors.info;
        bgColor = color.bg;
        borderColor = color.border;
        textColor = color.text;
    }

    // Toast styling with glassmorphism
    toast.style.cssText = `
        position: fixed;
        top: 80px;
        right: 20px;
        background: ${bgColor};
        backdrop-filter: blur(10px);
        -webkit-backdrop-filter: blur(10px);
        color: ${textColor};
        padding: 16px 20px;
        border-radius: 10px;
        border: 2px solid ${borderColor};
        box-shadow: 0 8px 32px rgba(0, 0, 0, 0.2);
        z-index: 10000;
        font-size: 14px;
        font-weight: 500;
        max-width: 400px;
        word-wrap: break-word;
        animation: slideInRight 0.3s ease-out;
    `;

    toast.textContent = message;
    document.body.appendChild(toast);

    // Auto-remove after duration
    setTimeout(() => {
        toast.style.animation = 'slideOutRight 0.3s ease-in';
        setTimeout(() => toast.remove(), 300);
    }, duration);
}

/**
 * Update notification badge count
 */
async function updateNotificationBadge() {
    try {
        const res = await fetch('/api/notifications/unread-count');
        const data = await res.json();

        const badge = document.getElementById('notification-badge');
        if (badge) {
            if (data.count > 0) {
                badge.textContent = data.count > 9 ? '9+' : data.count;
                badge.style.display = 'flex';
            } else {
                badge.style.display = 'none';
            }
        }
    } catch (error) {
        console.error('Failed to update notification badge:', error);
    }
}

/**
 * Mark notification as read
 * @param {number} notificationId - ID of the notification to mark as read
 */
async function markNotificationAsRead(notificationId) {
    try {
        const res = await fetch(`/api/notifications/${notificationId}/read`, {
            method: 'POST'
        });

        if (res.ok) {
            updateNotificationBadge();
            return true;
        }
    } catch (error) {
        console.error('Failed to mark notification as read:', error);
    }
    return false;
}

/**
 * Mark all notifications as read
 */
async function markAllNotificationsAsRead() {
    try {
        const res = await fetch('/api/notifications/read-all', {
            method: 'POST'
        });

        if (res.ok) {
            updateNotificationBadge();
            showToast('Toutes les notifications ont été marquées comme lues', 'success');
            return true;
        }
    } catch (error) {
        console.error('Failed to mark all notifications as read:', error);
        showToast('Erreur lors du marquage des notifications', 'error');
    }
    return false;
}

/**
 * Load recent notifications for dropdown
 */
async function loadRecentNotifications() {
    try {
        const res = await fetch('/api/notifications?per_page=3');
        const data = await res.json();

        const listElement = document.getElementById('notificationDropdownList');
        if (!listElement) return;

        if (data.notifications && data.notifications.length > 0) {
            listElement.innerHTML = data.notifications.map(notif => {
                const date = new Date(notif.created_at);
                const timeStr = formatRelativeTime(date);
                const unreadClass = !notif.is_read ? 'unread' : '';

                return `
                    <div class="notification-dropdown-item ${unreadClass}">
                        <a href="${notif.link_url || '/notifications'}"
                           class="notification-item-content"
                           style="text-decoration: none; color: inherit; display: block;"
                           onclick="markNotificationAsRead(${notif.id}); return true;">
                            <div class="notification-dropdown-message">${escapeHtml(notif.message)}</div>
                            <div class="notification-dropdown-time">${timeStr}</div>
                        </a>
                        <button class="notification-item-close"
                                onclick="markNotificationAsReadAndRemove(${notif.id}, event)"
                                title="Marquer comme lu">
                            <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                                <line x1="18" y1="6" x2="6" y2="18"></line>
                                <line x1="6" y1="6" x2="18" y2="18"></line>
                            </svg>
                        </button>
                    </div>
                `;
            }).join('');
        } else {
            listElement.innerHTML = '<div class="notification-dropdown-empty">Aucune notification</div>';
        }
    } catch (error) {
        console.error('Failed to load notifications:', error);
        const listElement = document.getElementById('notificationDropdownList');
        if (listElement) {
            listElement.innerHTML = '<div class="notification-dropdown-empty">Erreur de chargement</div>';
        }
    }
}

/**
 * Format relative time (e.g., "il y a 5 min")
 */
function formatRelativeTime(date) {
    const now = new Date();
    const diffMs = now - date;
    const diffMins = Math.floor(diffMs / 60000);
    const diffHours = Math.floor(diffMs / 3600000);
    const diffDays = Math.floor(diffMs / 86400000);

    if (diffMins < 1) return 'À l\'instant';
    if (diffMins < 60) return `il y a ${diffMins} min`;
    if (diffHours < 24) return `il y a ${diffHours}h`;
    if (diffDays < 7) return `il y a ${diffDays}j`;

    return date.toLocaleDateString('fr-FR', { day: '2-digit', month: '2-digit' });
}

/**
 * Escape HTML to prevent XSS
 */
function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

/**
 * Toggle notification dropdown
 */
function toggleNotificationDropdown() {
    const dropdown = document.getElementById('notificationDropdown');
    const userDropdown = document.getElementById('userMenuDropdown');

    if (dropdown) {
        const isShowing = dropdown.classList.contains('show');

        // Close user menu if open
        if (userDropdown) {
            userDropdown.classList.remove('show');
        }

        if (!isShowing) {
            // Just show - notifications are already pre-loaded
            dropdown.classList.add('show');
        } else {
            dropdown.classList.remove('show');
        }
    }
}

/**
 * Initialize notifications system
 */
function initNotifications() {
    // Update badge on page load
    updateNotificationBadge();

    // Pre-load notifications immediately for instant display
    loadRecentNotifications();

    // Poll for new notifications every 30 seconds (refresh badge AND dropdown content)
    setInterval(() => {
        updateNotificationBadge();
        loadRecentNotifications(); // Refresh dropdown content too
    }, 30000);

    // Setup notification bell toggle
    const bellToggle = document.getElementById('notificationBellToggle');
    if (bellToggle) {
        bellToggle.addEventListener('click', toggleNotificationDropdown);
    }

    // Close dropdown when clicking outside
    document.addEventListener('click', (e) => {
        const notificationMenu = document.querySelector('.notification-menu');
        const dropdown = document.getElementById('notificationDropdown');

        if (dropdown && !notificationMenu.contains(e.target)) {
            dropdown.classList.remove('show');
        }
    });
}

// Initialize on DOM ready
if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', initNotifications);
} else {
    initNotifications();
}

/**
 * Mark notification as read and remove from dropdown
 */
async function markNotificationAsReadAndRemove(notificationId, event) {
    event.preventDefault();
    event.stopPropagation();

    const success = await markNotificationAsRead(notificationId);
    if (success) {
        // Reload notifications to refresh the list
        loadRecentNotifications();
    }
}

/**
 * Mark all notifications as read from dropdown
 */
async function markAllAsReadFromDropdown() {
    const success = await markAllNotificationsAsRead();
    if (success) {
        // Reload notifications to refresh the list
        loadRecentNotifications();
    }
}

// Add CSS animations if not already present
if (!document.getElementById('notification-animations')) {
    const style = document.createElement('style');
    style.id = 'notification-animations';
    style.textContent = `
        @keyframes slideInRight {
            from {
                transform: translateX(400px);
                opacity: 0;
            }
            to {
                transform: translateX(0);
                opacity: 1;
            }
        }

        @keyframes slideOutRight {
            from {
                transform: translateX(0);
                opacity: 1;
            }
            to {
                transform: translateX(400px);
                opacity: 0;
            }
        }

        .toast-notification {
            animation: slideInRight 0.3s ease-out;
        }
    `;
    document.head.appendChild(style);
}

export function initSabyAuth() {
    const button = document.querySelector('[data-saby-auth]');

    if (!button) {
        return;
    }

    button.addEventListener('click', () => {
        const authUrl = button.dataset.authUrl;
        if (!authUrl) {
            return;
        }

        const popup = window.open(
            authUrl,
            'saby-oauth',
            'popup,width=600,height=700,resizable=yes,scrollbars=yes',
        );

        if (!popup) {
            showNotification(
                'Браузер заблокировал всплывающее окно. Разрешите popup для этого сайта.',
            );
            return;
        }

        button.disabled = true;
        popup.focus();

        // The callback closes the popup. Reload the opener after it closes
        // so the page reflects the new server-side session state.
        const popupWatcher = window.setInterval(() => {
            if (popup.closed) {
                window.clearInterval(popupWatcher);
                window.location.reload();
            }
        }, 400);
    });
}

function showNotification(message) {
    const container = document.getElementById('notifications');

    if (!container) {
        window.alert(message);
        return;
    }

    const notification = document.createElement('div');
    notification.className = 'notification notification--warning';
    notification.textContent = message;
    container.append(notification);
}

// Smart Healthcare Assistant - Main JS

// Auto-hide flash messages
setTimeout(() => {
    document.querySelectorAll('.flash').forEach(el => el.remove());
}, 4000);

// Smooth scroll to top on page load
window.scrollTo({ top: 0, behavior: 'smooth' });

// Add active class to current nav link
document.querySelectorAll('.nav-links a').forEach(link => {
    if (link.href === window.location.href) {
        link.style.color = '#fff';
        link.style.fontWeight = '700';
    }
});

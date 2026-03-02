/**
 * HomeworkAI — Main JS
 * Dark/light mode, mobile menu, password toggle, lightbox, loading overlay, UTC time
 */

// ── THEME TOGGLE ──────────────────────────────────────────────
const THEME_KEY = 'hwai-theme';
const html = document.documentElement;
const themeBtn = document.getElementById('themeToggle');

function applyTheme(theme) {
  html.setAttribute('data-theme', theme);
  localStorage.setItem(THEME_KEY, theme);
}

function initTheme() {
  const saved = localStorage.getItem(THEME_KEY);
  const preferred = saved || (window.matchMedia('(prefers-color-scheme: light)').matches ? 'light' : 'dark');
  applyTheme(preferred);
}

if (themeBtn) {
  themeBtn.addEventListener('click', () => {
    const current = html.getAttribute('data-theme');
    applyTheme(current === 'dark' ? 'light' : 'dark');
  });
}

initTheme();

// ── MOBILE MENU ───────────────────────────────────────────────
const mobileToggle = document.getElementById('mobileToggle');
const mobileMenu   = document.getElementById('mobileMenu');

if (mobileToggle && mobileMenu) {
  mobileToggle.addEventListener('click', (e) => {
    e.stopPropagation();
    mobileMenu.classList.toggle('open');
  });
  document.addEventListener('click', (e) => {
    if (!mobileToggle.contains(e.target) && !mobileMenu.contains(e.target)) {
      mobileMenu.classList.remove('open');
    }
  });
}

// ── PASSWORD TOGGLE ───────────────────────────────────────────
// Dùng Font Awesome icon thay vì emoji để đồng nhất giao diện
function togglePwd(inputId, btn) {
  const input = document.getElementById(inputId);
  if (!input) return;
  if (input.type === 'password') {
    input.type = 'text';
    btn.innerHTML = '<i class="fa-solid fa-eye-slash"></i>';
  } else {
    input.type = 'password';
    btn.innerHTML = '<i class="fa-solid fa-eye"></i>';
  }
}

// ── AUTO DISMISS FLASH ────────────────────────────────────────
document.querySelectorAll('.flash').forEach(flash => {
  setTimeout(() => {
    flash.style.opacity = '0';
    flash.style.transform = 'translateX(100%)';
    flash.style.transition = 'all 0.3s ease';
    setTimeout(() => flash.remove(), 300);
  }, 4500);
});

// ── SCORE BAR ANIMATION ───────────────────────────────────────
const bars = document.querySelectorAll('.score-fill, .crit-fill');
if (bars.length > 0 && 'IntersectionObserver' in window) {
  const observer = new IntersectionObserver((entries) => {
    entries.forEach(entry => {
      if (entry.isIntersecting) {
        entry.target.classList.add('animated');
        observer.unobserve(entry.target);
      }
    });
  }, { threshold: 0.2 });

  bars.forEach(bar => {
    const targetWidth = bar.style.width;
    bar.style.width = '0%';
    setTimeout(() => { bar.style.width = targetWidth; }, 100);
    observer.observe(bar);
  });
}

// ── UTC → LOCAL TIME CONVERSION ──────────────────────────────
(function convertLocalTimes() {
  document.querySelectorAll('time.local-time[data-utc]').forEach(el => {
    const raw = el.dataset.utc;
    if (!raw) return;
    const d = new Date(raw.replace(' ', 'T') + 'Z');
    if (isNaN(d.getTime())) return;
    el.textContent = d.toLocaleString('vi-VN', {
      year: 'numeric', month: '2-digit', day: '2-digit',
      hour: '2-digit', minute: '2-digit', hour12: false
    });
    el.title = d.toLocaleString('vi-VN', {
      weekday: 'long', year: 'numeric', month: 'long', day: 'numeric',
      hour: '2-digit', minute: '2-digit', second: '2-digit', hour12: false
    });
  });
})();

// ── LIGHTBOX ─────────────────────────────────────────────────
// Inject lightbox DOM once
(function initLightbox() {
  const lb = document.createElement('div');
  lb.id = 'hwai-lightbox';
  lb.setAttribute('role', 'dialog');
  lb.setAttribute('aria-modal', 'true');
  lb.innerHTML = `
    <button id="hwai-lightbox-close" aria-label="Đóng">
      <i class="fa-solid fa-xmark"></i>
    </button>
    <img id="hwai-lightbox-img" src="" alt="Xem ảnh lớn" />
  `;
  document.body.appendChild(lb);

  const lbImg   = document.getElementById('hwai-lightbox-img');
  const lbClose = document.getElementById('hwai-lightbox-close');

  function openLightbox(src, alt) {
    lbImg.src = src || '';
    lbImg.alt = alt || '';
    lb.classList.add('open');
    document.body.style.overflow = 'hidden';
  }

  function closeLightbox() {
    lb.classList.remove('open');
    document.body.style.overflow = '';
    lbImg.src = '';
  }

  // Close on backdrop click (not on image itself)
  lb.addEventListener('click', (e) => {
    if (e.target === lb || e.target === lbClose || lbClose.contains(e.target)) {
      closeLightbox();
    }
  });

  // Close on Escape
  document.addEventListener('keydown', (e) => {
    if (e.key === 'Escape' && lb.classList.contains('open')) closeLightbox();
  });

  // Auto-attach to all .lightbox-trigger images (and future ones via MutationObserver)
  function attachLightbox(img) {
    if (img._lbAttached) return;
    img._lbAttached = true;
    img.addEventListener('click', () => openLightbox(img.src, img.alt));
  }

  document.querySelectorAll('img.lightbox-trigger').forEach(attachLightbox);

  // Watch for dynamically added images (e.g. preview after file selection)
  const mo = new MutationObserver((mutations) => {
    mutations.forEach(m => {
      m.addedNodes.forEach(node => {
        if (node.nodeType !== 1) return;
        if (node.matches && node.matches('img.lightbox-trigger')) attachLightbox(node);
        node.querySelectorAll && node.querySelectorAll('img.lightbox-trigger').forEach(attachLightbox);
      });
    });
  });
  mo.observe(document.body, { childList: true, subtree: true });

  // Expose globally for inline usage
  window.hwaiLightbox = { open: openLightbox, close: closeLightbox };
})();

// ── LOADING OVERLAY ──────────────────────────────────────────
(function initLoading() {
  const overlay = document.createElement('div');
  overlay.id = 'hwai-loading';
  overlay.innerHTML = `
    <div class="hwai-loading-card">
      <div class="hwai-loading-spinner"></div>
      <div class="hwai-loading-title" id="hwai-loading-title">Đang xử lý</div>
      <div class="hwai-loading-sub hwai-loading-dots" id="hwai-loading-sub">Vui lòng chờ</div>
    </div>
  `;
  document.body.appendChild(overlay);

  window.hwaiLoading = {
    show(title, sub) {
      document.getElementById('hwai-loading-title').textContent = title || 'Đang xử lý';
      document.getElementById('hwai-loading-sub').textContent   = sub   || 'Vui lòng chờ';
      overlay.classList.add('open');
      document.body.style.overflow = 'hidden';
    },
    hide() {
      overlay.classList.remove('open');
      document.body.style.overflow = '';
    }
  };
})();

// ── FORM SUBMIT LOADING HOOKS ────────────────────────────────
// Tự động gắn loading overlay vào các form có data-loading-* attributes
// Ví dụ: <form data-loading-title="AI đang xử lý" data-loading-sub="Đang chấm bài">
document.addEventListener('DOMContentLoaded', () => {
  document.querySelectorAll('form[data-loading-title]').forEach(form => {
    form.addEventListener('submit', function() {
      const title = this.dataset.loadingTitle || 'Đang xử lý';
      const sub   = this.dataset.loadingSub   || 'Vui lòng chờ';
      if (window.hwaiLoading) window.hwaiLoading.show(title, sub);
    });
  });
});

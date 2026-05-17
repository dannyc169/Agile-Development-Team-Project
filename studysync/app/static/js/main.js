document.addEventListener('DOMContentLoaded', () => {
  document.querySelectorAll('.alert-close').forEach((button) => {
    button.addEventListener('click', () => {
      const alert = button.closest('.alert');
      if (alert) {
        alert.style.display = 'none';
      }
    });
  });


  document.querySelectorAll('[data-submit-on-change="true"]').forEach((field) => {
    field.addEventListener('change', () => {
      if (field.form) {
        field.form.submit();
      }
    });
  });

  const currentPath = window.location.pathname;
  document.querySelectorAll('.nav-link').forEach((link) => {
    link.classList.toggle('active', link.getAttribute('href') === currentPath);
  });

  const sidebar = document.querySelector('.sidebar');
  const sidebarOverlay = document.getElementById('sidebarOverlay');
  const mobileMenuBtn = document.getElementById('mobileMenuBtn');

  function closeSidebar() {
    if (sidebar) {
      sidebar.classList.remove('open');
    }
    if (sidebarOverlay) {
      sidebarOverlay.classList.remove('open');
    }
  }

  if (mobileMenuBtn) {
    mobileMenuBtn.addEventListener('click', () => {
      if (sidebar) {
        sidebar.classList.toggle('open');
      }
      if (sidebarOverlay) {
        sidebarOverlay.classList.toggle('open');
      }
    });
  }

  if (sidebarOverlay) {
    sidebarOverlay.addEventListener('click', closeSidebar);
  }

  document.querySelectorAll('.nav-link').forEach((link) => {
    link.addEventListener('click', () => {
      document.querySelectorAll('.nav-link').forEach((item) => item.classList.remove('active'));
      link.classList.add('active');
    });
  });

  const openUserModalBtn = document.getElementById('openUserModalBtn');
  const closeUserModalBtn = document.getElementById('closeUserModalBtn');
  const userModalOverlay = document.getElementById('userModalOverlay');
  const userModal = document.getElementById('userModal');

  function openUserModal() {
    if (!userModalOverlay || !userModal) {
      return;
    }
    userModalOverlay.classList.remove('hidden');
    userModal.classList.remove('hidden');
    userModalOverlay.setAttribute('aria-hidden', 'false');
    userModal.setAttribute('aria-hidden', 'false');
    document.body.classList.add('overflow-hidden');
    userModal.focus();
  }

  function closeUserModal() {
    if (!userModalOverlay || !userModal) {
      return;
    }
    userModalOverlay.classList.add('hidden');
    userModal.classList.add('hidden');
    userModalOverlay.setAttribute('aria-hidden', 'true');
    userModal.setAttribute('aria-hidden', 'true');
    document.body.classList.remove('overflow-hidden');
    if (openUserModalBtn) {
      openUserModalBtn.focus();
    }
  }

  if (openUserModalBtn) {
    openUserModalBtn.addEventListener('click', openUserModal);
  }
  if (closeUserModalBtn) {
    closeUserModalBtn.addEventListener('click', closeUserModal);
  }
  if (userModalOverlay) {
    userModalOverlay.addEventListener('click', closeUserModal);
  }

  document.addEventListener('keydown', (event) => {
    if (event.key === 'Escape' && userModal && !userModal.classList.contains('hidden')) {
      closeUserModal();
    }
  });
});

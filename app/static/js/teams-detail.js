function showTempStatus(el, msg, timeout = 2000) {
  if (!el) return;
  const prev = el.textContent;
  el.textContent = msg;
  el.style.display = '';
  setTimeout(() => {
    el.textContent = prev;
    el.style.display = 'none';
  }, timeout);
}

function copyTeamCode() {
  const codeEl = document.getElementById('teamCodeValue');
  const input = document.getElementById('inviteCodeInput');
  const statusEl = document.getElementById('copyStatus');
  const code = codeEl ? codeEl.textContent.trim() : '';

  if (!code) {
    alert('Team code not available.');
    return;
  }

  if (navigator.clipboard && window.isSecureContext) {
    navigator.clipboard.writeText(code).then(() => {
      showTempStatus(statusEl, 'Copied!');
    }).catch(() => {
      copyFromInputFallback(input, statusEl, 'Copied!');
    });
    return;
  }

  copyFromInputFallback(input, statusEl, 'Copied!');
}

function copyJoinLink() {
  const linkInput = document.getElementById('joinLinkInput');
  const joinLink = linkInput ? linkInput.value.trim() : '';
  const statusEl = document.getElementById('copyStatus');

  if (!joinLink) {
    alert('Join link not available.');
    return;
  }

  if (navigator.clipboard && window.isSecureContext) {
    navigator.clipboard.writeText(joinLink).then(() => {
      showTempStatus(statusEl, 'Join link copied!');
    }).catch(() => {
      copyFromInputFallback(linkInput, statusEl, 'Join link copied!');
    });
    return;
  }

  copyFromInputFallback(linkInput, statusEl, 'Join link copied!');
}

function copyFromInputFallback(input, statusEl, successMessage) {
  if (!input) {
    alert('Your browser does not support clipboard actions. Please copy manually.');
    return;
  }

  try {
    input.focus();
    input.select();
    document.execCommand('copy');
    showTempStatus(statusEl, successMessage);
  } catch (error) {
    alert('Your browser does not support clipboard actions. Please copy manually.');
  }
}

function openInviteModal() {
  const modal = document.getElementById('inviteModal');

  if (modal) {
    modal.classList.remove('hidden');
    modal.classList.add('flex');
  }
}

function closeInviteModal() {
  const modal = document.getElementById('inviteModal');

  if (modal) {
    modal.classList.add('hidden');
    modal.classList.remove('flex');
  }
}


document.addEventListener('DOMContentLoaded', () => {
  const copyCodeBtn = document.getElementById('copyCodeBtn');
  const modalCopyCodeBtn = document.getElementById('modalCopyCodeBtn');
  const copyJoinLinkBtn = document.getElementById('copyJoinLinkBtn');
  const openInviteModalBtn = document.getElementById('openInviteModalBtn');
  const inviteModal = document.getElementById('inviteModal');

  if (copyCodeBtn) {
    copyCodeBtn.addEventListener('click', copyTeamCode);
  }
  if (modalCopyCodeBtn) {
    modalCopyCodeBtn.addEventListener('click', copyTeamCode);
  }
  if (copyJoinLinkBtn) {
    copyJoinLinkBtn.addEventListener('click', copyJoinLink);
  }
  if (openInviteModalBtn) {
    openInviteModalBtn.addEventListener('click', openInviteModal);
  }

  document.querySelectorAll('.js-close-invite-modal').forEach((button) => {
    button.addEventListener('click', closeInviteModal);
  });

  if (inviteModal) {
    inviteModal.addEventListener('click', (event) => {
      if (event.target === inviteModal) {
        closeInviteModal();
      }
    });
  }
});

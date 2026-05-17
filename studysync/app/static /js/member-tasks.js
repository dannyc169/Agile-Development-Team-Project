document.addEventListener('DOMContentLoaded', () => {
  if (typeof flatpickr === 'function') {
    flatpickr('#memberEditDueDate', {
      dateFormat: 'Y-m-d',
      allowInput: false,
      minDate: '2000-01-01',
      maxDate: '2099-12-31'
    });
  }

  const modal = document.getElementById('memberEditModal');
  const form = document.getElementById('memberEditForm');

  if (!modal || !form) {
    return;
  }

  document.querySelectorAll('.member-edit-btn').forEach((button) => {
    button.addEventListener('click', () => {
      form.action = `/tasks/${button.dataset.taskId}/edit`;
      document.getElementById('memberEditTitle').value = button.dataset.title || '';
      document.getElementById('memberEditDescription').value = button.dataset.description || '';
      document.getElementById('memberEditPriority').value = button.dataset.priority || 'medium';
      document.getElementById('memberEditDueDate').value = button.dataset.dueDate || '';

      modal.classList.remove('hidden');
    });
  });

  function closeMemberEditModal() {
    modal.classList.add('hidden');
  }

  const closeModalButton = document.getElementById('closeMemberEditModal');
  const closeModalTopButton = document.getElementById('closeMemberEditModalTop');

  if (closeModalButton) {
    closeModalButton.addEventListener('click', closeMemberEditModal);
  }
  if (closeModalTopButton) {
    closeModalTopButton.addEventListener('click', closeMemberEditModal);
  }

  modal.addEventListener('click', (event) => {
    if (event.target === modal) {
      closeMemberEditModal();
    }
  });
});

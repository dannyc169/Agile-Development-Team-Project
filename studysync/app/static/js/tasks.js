document.addEventListener('DOMContentLoaded', () => {
  const datePickerOptions = {
    dateFormat: 'Y-m-d',
    allowInput: false,
    minDate: '2000-01-01',
    maxDate: '2099-12-31'
  };

  const createDueDatePicker = typeof flatpickr === 'function'
    ? flatpickr('#createDueDate', datePickerOptions)
    : null;
  const editDueDatePicker = typeof flatpickr === 'function'
    ? flatpickr('#editDueDate', datePickerOptions)
    : null;

  const teamMembersData = document.getElementById('teamMembersData');
  const teamMembersMap = teamMembersData ? JSON.parse(teamMembersData.textContent || '{}') : {};

  const newTaskBtn = document.getElementById('newTaskBtn');
  const createTeamSelect = document.getElementById('createTeamId');
  const assigneeField = document.getElementById('assigneeField');
  const assigneeSelect = document.getElementById('assigneeSelect');
  const newTaskPanel = document.getElementById('newTaskPanel');

  function updateAssigneeField() {
    if (!createTeamSelect || !assigneeField || !assigneeSelect) {
      return;
    }

    const teamId = createTeamSelect.value;
    const members = teamMembersMap[teamId];
    if (members && members.length > 0) {
      assigneeSelect.innerHTML = '<option value="">— No specific assignee —</option>';
      members.forEach((member) => {
        const option = document.createElement('option');
        option.value = member.id;
        option.textContent = member.username;
        assigneeSelect.appendChild(option);
      });
      assigneeField.classList.remove('hidden');
    } else {
      assigneeField.classList.add('hidden');
      assigneeSelect.innerHTML = '';
    }
  }

  if (newTaskBtn && createTeamSelect && newTaskPanel) {
    createTeamSelect.addEventListener('change', updateAssigneeField);

    newTaskBtn.addEventListener('click', () => {
      newTaskPanel.classList.toggle('hidden');
      updateAssigneeField();
    });

    const cancelBtn = document.getElementById('cancelBtn');
    if (cancelBtn) {
      cancelBtn.addEventListener('click', () => {
        newTaskPanel.classList.add('hidden');
        createTeamSelect.value = '';
        if (assigneeField) {
          assigneeField.classList.add('hidden');
        }
        if (assigneeSelect) {
          assigneeSelect.innerHTML = '';
        }
      });
    }

    const taskParams = new URLSearchParams(window.location.search);
    const shouldOpenCreate = taskParams.get('open_create') === '1';
    const preselectedTeamId = taskParams.get('team_id');

    if (preselectedTeamId) {
      createTeamSelect.value = preselectedTeamId;
      updateAssigneeField();
    }

    if (shouldOpenCreate) {
      newTaskPanel.classList.remove('hidden');
    }
  }

  let currentFilter = 'all';
  let currentSearch = '';
  let currentTeam = 'all';

  function applyFilters() {
    document.querySelectorAll('.task-card').forEach((card) => {
      const matchFilter = currentFilter === 'all' || card.dataset.status === currentFilter;
      const matchSearch = (card.dataset.title || '').includes(currentSearch);
      const matchTeam = currentTeam === 'all' || card.dataset.teamId === currentTeam;
      card.style.display = (matchFilter && matchSearch && matchTeam) ? '' : 'none';
    });

    ['overdue-section', 'today-section', 'upcoming-section', 'done-section'].forEach((id) => {
      const section = document.getElementById(id);
      if (!section) return;
      const hasVisible = Array.from(section.querySelectorAll('.task-card')).some((card) => card.style.display !== 'none');
      section.style.display = hasVisible ? '' : 'none';
    });
  }

  const teamFilter = document.getElementById('teamFilter');
  if (teamFilter) {
    teamFilter.addEventListener('change', function () {
      currentTeam = this.value;
      applyFilters();
    });
  }

  function setActiveFilterTab(activeTab) {
    document.querySelectorAll('.filter-tab').forEach((tab) => {
      tab.classList.remove('bg-indigo-600', 'text-white');
      tab.classList.add('text-gray-700', 'hover:bg-gray-100');
    });
    activeTab.classList.add('bg-indigo-600', 'text-white');
    activeTab.classList.remove('text-gray-700', 'hover:bg-gray-100');
  }

  document.querySelectorAll('.filter-tab').forEach((tab) => {
    tab.addEventListener('click', function () {
      setActiveFilterTab(this);
      currentFilter = this.dataset.filter;
      applyFilters();
    });
  });

  const searchInput = document.getElementById('searchInput');
  if (searchInput) {
    searchInput.addEventListener('input', function () {
      currentSearch = this.value.toLowerCase();
      applyFilters();
    });
  }

  const editModal = document.getElementById('editModal');
  const editForm = document.getElementById('editForm');

  if (!editModal || !editForm) {
    return;
  }

  const editModalTitle = document.getElementById('editModalTitle');
  const editTitle = document.getElementById('editTitle');
  const editDescription = document.getElementById('editDescription');
  const editDueDate = document.getElementById('editDueDate');
  const editPriority = document.getElementById('editPriority');
  const editPriorityHidden = document.getElementById('editPriorityHidden');
  const priorityLockedNote = document.getElementById('priorityLockedNote');
  const editTeamLabel = document.getElementById('editTeamLabel');
  const editTeamId = document.getElementById('editTeamId');
  const editTeamDisplay = document.getElementById('editTeamDisplay');
  const editSubmitBtn = document.getElementById('editSubmitBtn');
  const closeEditModal = document.getElementById('closeEditModal');

  function setReadOnlyClasses(field, isReadOnly) {
    if (!field) return;
    field.classList.toggle('bg-gray-50', isReadOnly);
    field.classList.toggle('text-gray-700', isReadOnly);
    field.classList.toggle('cursor-not-allowed', isReadOnly);
  }

  function setModalReadOnly(isReadOnly) {
    editModalTitle.textContent = isReadOnly ? 'View Task Detail' : 'Edit Task';

    editTitle.readOnly = isReadOnly;
    editDescription.readOnly = isReadOnly;
    editDueDate.disabled = isReadOnly;
    editPriority.disabled = isReadOnly;
    priorityLockedNote.classList.toggle('hidden', !isReadOnly);

    editTeamLabel.textContent = isReadOnly ? 'Assigned Team' : 'Assign to Team';
    editTeamId.classList.toggle('hidden', isReadOnly);
    editTeamId.disabled = isReadOnly;
    editTeamDisplay.classList.toggle('hidden', !isReadOnly);

    editSubmitBtn.classList.toggle('hidden', isReadOnly);
    closeEditModal.textContent = isReadOnly ? 'Close' : 'Cancel';

    [editTitle, editDescription, editDueDate, editPriority, editTeamId].forEach((field) => {
      setReadOnlyClasses(field, isReadOnly);
    });
  }

  document.querySelectorAll('.edit-btn').forEach((btn) => {
    btn.addEventListener('click', function () {
      const id = this.dataset.taskId;
      const isReadOnly = this.dataset.readOnly === '1';

      editForm.action = isReadOnly ? '#' : `/tasks/${id}/edit`;
      editTitle.value = this.dataset.title || '';
      editDescription.value = this.dataset.description || '';
      if (editDueDatePicker && typeof editDueDatePicker.setDate === 'function') {
        editDueDatePicker.setDate(this.dataset.dueDate || null);
      } else {
        editDueDate.value = this.dataset.dueDate || '';
      }
      editPriority.value = this.dataset.priority || 'medium';
      editTeamId.value = this.dataset.teamId || '';
      editTeamDisplay.value = this.dataset.teamName || 'No Team';

      editPriorityHidden.disabled = true;
      editPriorityHidden.value = this.dataset.priority || 'medium';

      setModalReadOnly(isReadOnly);
      editModal.classList.remove('hidden');
    });
  });

  editForm.addEventListener('submit', (event) => {
    if (editSubmitBtn.classList.contains('hidden')) {
      event.preventDefault();
    }
  });

  closeEditModal.addEventListener('click', () => {
    editModal.classList.add('hidden');
  });

  editModal.addEventListener('click', function (event) {
    if (event.target === this) {
      this.classList.add('hidden');
    }
  });
});

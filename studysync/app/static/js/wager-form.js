document.addEventListener('DOMContentLoaded', () => {
  const datePickerOptions = {
    dateFormat: 'Y-m-d',
    allowInput: false,
    minDate: '2000-01-01',
    maxDate: '2099-12-31'
  };

  if (typeof flatpickr === 'function') {
    flatpickr('#startDate', datePickerOptions);
    flatpickr('#endDate', datePickerOptions);
  }

  const page = document.getElementById('wagerFormPage');
  if (!page) {
    return;
  }

  const pointsPerTask = Number(page.dataset.pointsPerTask || 10);
  const pointsPreview = document.getElementById('points-preview');
  const selectedTaskCount = document.getElementById('selected-task-count');
  const totalPoints = document.getElementById('total-points');

  function setPointsPreview(count) {
    if (!pointsPreview || !selectedTaskCount || !totalPoints) {
      return;
    }

    selectedTaskCount.textContent = count;
    totalPoints.textContent = count * pointsPerTask;
    pointsPreview.classList.toggle('hidden', count <= 0);
  }

  const teamSelect = document.getElementById('team-select');
  const taskOptions = document.querySelectorAll('.js-task-option');

  if (teamSelect && taskOptions.length > 0) {
    const chooseTeamMessage = document.getElementById('choose-team-message');
    const noTaskMessage = document.getElementById('no-task-message');

    function updatePointsPreviewForCreate() {
      const visibleCheckedTasks = Array.from(taskOptions).filter((option) => {
        const checkbox = option.querySelector('input[type="checkbox"]');
        return !option.classList.contains('hidden') && checkbox && checkbox.checked;
      });

      setPointsPreview(visibleCheckedTasks.length);
    }

    function updateTaskVisibility() {
      const selectedTeam = teamSelect.value;
      let visibleCount = 0;

      taskOptions.forEach((option) => {
        const checkbox = option.querySelector('input[type="checkbox"]');

        if (selectedTeam && option.dataset.teamId === selectedTeam) {
          option.classList.remove('hidden');
          visibleCount += 1;
        } else {
          option.classList.add('hidden');

          if (checkbox) {
            checkbox.checked = false;
          }
        }
      });

      if (chooseTeamMessage && noTaskMessage) {
        if (!selectedTeam) {
          chooseTeamMessage.classList.remove('hidden');
          noTaskMessage.classList.add('hidden');
        } else if (visibleCount === 0) {
          chooseTeamMessage.classList.add('hidden');
          noTaskMessage.classList.remove('hidden');
        } else {
          chooseTeamMessage.classList.add('hidden');
          noTaskMessage.classList.add('hidden');
        }
      }

      updatePointsPreviewForCreate();
    }

    taskOptions.forEach((option) => {
      const checkbox = option.querySelector('input[type="checkbox"]');

      if (checkbox) {
        checkbox.addEventListener('change', updatePointsPreviewForCreate);
      }
    });

    teamSelect.addEventListener('change', updateTaskVisibility);
    updateTaskVisibility();
    return;
  }

  const checkboxes = document.querySelectorAll('.js-task-checkbox');

  if (checkboxes.length > 0) {
    function updatePointsPreviewForEdit() {
      const count = Array.from(checkboxes).filter((checkbox) => checkbox.checked).length;
      setPointsPreview(count);
    }

    checkboxes.forEach((checkbox) => {
      checkbox.addEventListener('change', updatePointsPreviewForEdit);
    });

    updatePointsPreviewForEdit();
  }
});

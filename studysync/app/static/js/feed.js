document.addEventListener('DOMContentLoaded', () => {
  document.querySelectorAll('.feed-team-select').forEach((select) => {
    select.addEventListener('change', () => {
      if (select.value) {
        window.location.href = select.value;
      }
    });
  });

  document.querySelectorAll('.comment-toggle-btn').forEach((button) => {
    button.addEventListener('click', () => {
      const reactionSection = button.closest('.reaction-section');
      const commentSection = reactionSection ? reactionSection.querySelector('.comment-section') : null;

      if (commentSection) {
        commentSection.classList.toggle('hidden');
      }
    });
  });
});

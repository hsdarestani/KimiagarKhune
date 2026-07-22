(function (window, document, $) {
  'use strict';

  if (!$) {
    return;
  }

  const ENDPOINT = '/get-lessons-for-student/';
  let requestSerial = 0;

  const state = {
    studentId: null,
    studentGradeId: null,
    studentGrade: '',
    majorCode: '',
    allowedGradeIds: [],
    gradeOptions: []
  };

  function normalizedUrl(value) {
    try {
      return new URL(value, window.location.origin).pathname;
    } catch (_error) {
      return String(value || '').split('?')[0];
    }
  }

  function buildGradeFilters(response) {
    const options = Array.isArray(response.grade_options) ? response.grade_options : [];
    const allowed = new Set((response.allowed_grade_ids || []).map(String));
    const studentGradeId = String(response.student_grade_id || '');
    const $container = $('.subjects-box .grade-filters').first();
    if (!$container.length || !options.length) {
      return;
    }

    $container.empty();
    options.forEach(function (option) {
      const id = String(option.id);
      const isAllowed = allowed.has(id);
      const isCurrent = id === studentGradeId;
      const $label = $('<label class="me-2"></label>')
        .toggleClass('plan-grade-disabled', !isAllowed)
        .toggleClass('plan-grade-current', isCurrent)
        .attr('data-grade-name', option.name);
      const $checkbox = $('<input type="checkbox" class="grade-filter">')
        .val(id)
        .prop('checked', isAllowed)
        .prop('disabled', !isAllowed)
        .attr('data-grade-name', option.name)
        .attr('aria-label', option.name);
      $label.append($checkbox).append(document.createTextNode(' ' + option.name));
      $container.append($label);
    });
  }

  function applyGradeFilter() {
    const activeGrades = new Set(
      $('.grade-filter:checked:not(:disabled)').map(function () {
        return String(this.value);
      }).get()
    );

    $('#specialized-task-list .task, #general-task-list .task').each(function () {
      const gradeId = String($(this).attr('data-grade') || '');
      $(this).toggle(activeGrades.has(gradeId));
    });
  }

  function applyResponse(response) {
    if (!response || response.error) {
      return;
    }

    state.studentId = String(response.student_id || $('#student-select').val() || '');
    state.studentGradeId = response.student_grade_id || null;
    state.studentGrade = response.student_grade || '';
    state.majorCode = response.major_code || '';
    state.allowedGradeIds = (response.allowed_grade_ids || []).map(String);
    state.gradeOptions = response.grade_options || [];

    buildGradeFilters(response);
    applyGradeFilter();
    document.body.setAttribute('data-plan-lesson-toolbar-ready', 'true');
    window.dispatchEvent(new CustomEvent('plan:lesson-toolbar-updated', {
      detail: Object.assign({}, state)
    }));
  }

  function fetchRules(studentId) {
    const id = String(studentId || '').trim();
    if (!id) {
      return;
    }
    const serial = ++requestSerial;
    $.ajax({
      url: ENDPOINT,
      method: 'GET',
      dataType: 'json',
      data: { student_id: id }
    }).done(function (response) {
      if (serial === requestSerial) {
        applyResponse(response);
      }
    }).fail(function (xhr) {
      console.error('Could not load lesson toolbar rules.', xhr.responseJSON || xhr.statusText);
    });
  }

  window.planLessonToolbarState = state;
  window.planLessonToolbarApply = applyResponse;
  window.planLessonToolbarFilter = applyGradeFilter;

  $(document)
    .off('change.planLessonToolbar', '.grade-filter')
    .on('change.planLessonToolbar', '.grade-filter', applyGradeFilter)
    .off('change.planLessonStudent', '#student-select')
    .on('change.planLessonStudent', '#student-select', function () {
      fetchRules(this.value);
    });

  $(document).ajaxSuccess(function (_event, xhr, settings) {
    if (normalizedUrl(settings && settings.url) !== ENDPOINT) {
      return;
    }
    const response = xhr.responseJSON;
    if (response) {
      window.setTimeout(function () {
        applyResponse(response);
      }, 0);
    }
  });

  $(function () {
    fetchRules($('#student-select').val());
  });
})(window, document, window.jQuery);

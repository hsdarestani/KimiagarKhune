(function (window, document, $) {
  'use strict';

  if (!$ || !$.fn.select2) {
    return;
  }

  const VERSION = '2026.08.02.1';
  let synchronizeQueued = false;

  function currentStudentId() {
    const runtimeId = window.planRuntimeState && window.planRuntimeState.studentId;
    return String(runtimeId || $('#student-select').val() || '').trim();
  }

  function markError($task, message) {
    $task
      .addClass('plan-chapter-load-error')
      .attr('data-plan-chapter-error', String(message || 'بارگذاری فصل‌ها انجام نشد.'));
  }

  function clearError($task) {
    $task
      .removeClass('plan-chapter-load-error')
      .removeAttr('data-plan-chapter-error');
  }

  function configureChapterSelect(task) {
    const $task = $(task);
    const $select = $task.find('.task-chapter').first();
    const lessonId = String($task.attr('data-lesson-id') || '').trim();

    if (!$select.length || !lessonId) {
      return;
    }
    if ($select.attr('data-plan-chapter-loader-version') === VERSION) {
      return;
    }

    const selectedValue = String($select.val() || '').trim();
    const selectedText = String($select.find('option:selected').text() || '').trim();

    if ($select.hasClass('select2-hidden-accessible')) {
      try {
        $select.select2('destroy');
      } catch (_error) {
        // A partially initialized legacy Select2 should not block recovery.
      }
    }

    if (selectedValue && !$select.find('option[value="' + selectedValue.replace(/"/g, '\\"') + '"]').length) {
      $select.append(new Option(selectedText || selectedValue, selectedValue, true, true));
    }

    $select.select2({
      placeholder: 'شماره فصل',
      dropdownParent: $task,
      width: '100%',
      theme: 'bootstrap-5',
      allowClear: true,
      language: {
        errorLoading: function () { return 'بارگذاری فصل‌ها انجام نشد'; },
        loadingMore: function () { return 'در حال بارگذاری…'; },
        noResults: function () { return 'فصلی برای این درس پیدا نشد'; },
        searching: function () { return 'در حال جست‌وجو…'; }
      },
      ajax: {
        url: '/get-chapters/',
        dataType: 'json',
        delay: 120,
        data: function (params) {
          return {
            student_id: currentStudentId(),
            lesson_id: lessonId,
            q: params.term || ''
          };
        },
        transport: function (params, success, failure) {
          const request = $.ajax(params);
          request.done(function (data) {
            clearError($task);
            success(data);
          });
          request.fail(function (xhr) {
            const payload = xhr.responseJSON || {};
            markError($task, payload.error || payload.message || 'بارگذاری فصل‌ها انجام نشد.');
            failure(xhr);
          });
          return request;
        },
        processResults: function (data) {
          return { results: Array.isArray(data) ? data : [] };
        }
      }
    });

    if (selectedValue) {
      $select.val(selectedValue).trigger('change.select2');
    }

    $select.attr('data-plan-chapter-loader-version', VERSION);
  }

  function synchronize() {
    synchronizeQueued = false;
    $('.calendar .calendar-task.extended-task').each(function () {
      configureChapterSelect(this);
    });
    if (document.body) {
      document.body.setAttribute('data-plan-chapter-loader-version', VERSION);
    }
  }

  function queueSynchronize() {
    if (synchronizeQueued) {
      return;
    }
    synchronizeQueued = true;
    window.requestAnimationFrame(synchronize);
  }

  function wrapTaskInitializer() {
    const previous = window.initCalendarTask;
    if (typeof previous !== 'function' || previous.planChapterLoaderWrapped) {
      return;
    }

    const wrapped = function (task) {
      const result = previous.apply(this, arguments);
      const element = task && task.jquery ? task[0] : task;
      if (element) {
        window.requestAnimationFrame(function () {
          configureChapterSelect(element);
        });
      }
      return result;
    };
    wrapped.planChapterLoaderWrapped = true;
    wrapped.planChapterLoaderOriginal = previous;
    window.initCalendarTask = wrapped;
  }

  function initialize() {
    wrapTaskInitializer();
    synchronize();

    const calendar = document.querySelector('.calendar');
    if (calendar) {
      new MutationObserver(queueSynchronize).observe(calendar, {
        childList: true,
        subtree: true
      });
    }

    $(document)
      .off('change.planChapterStudent', '#student-select')
      .on('change.planChapterStudent', '#student-select', function () {
        $('.task-chapter').removeAttr('data-plan-chapter-loader-version');
        queueSynchronize();
      });

    window.addEventListener('plan:interactions-ready', function () {
      wrapTaskInitializer();
      queueSynchronize();
    });
    window.addEventListener('plan:lesson-toolbar-updated', queueSynchronize);

    window.planChapterLoader = {
      version: VERSION,
      synchronize: synchronize
    };
  }

  $(initialize);
})(window, document, window.jQuery);

(function (window, document, $) {
  'use strict';

  if (!$ || !$.fn.select2) {
    return;
  }

  const VERSION = '2026.08.07.3';
  let synchronizeQueued = false;

  function currentStudentId() {
    const runtimeId = window.planRuntimeState && window.planRuntimeState.studentId;
    return String(runtimeId || $('#student-select').val() || '').trim();
  }

  function markError($task, message) {
    $task
      .addClass('plan-chapter-load-error')
      .attr('data-plan-chapter-error', String(message || 'بارگذاری سرفصل‌ها انجام نشد.'));
  }

  function clearError($task) {
    $task
      .removeClass('plan-chapter-load-error')
      .removeAttr('data-plan-chapter-error');
  }

  function chapterTemplate(item) {
    if (!item || item.loading) {
      return item && item.text ? item.text : '';
    }
    return $('<span class="plan-chapter-option-text"></span>').text(
      String(item.text || '').trim()
    );
  }

  function chapterSelection(item) {
    const text = String((item && item.text) || '').trim();
    return text || 'انتخاب سرفصل';
  }

  function keepDropdownInsideViewport() {
    const $dropdown = $('.select2-dropdown.plan-chapter-dropdown:visible').last();
    if (!$dropdown.length) {
      return;
    }

    const viewportWidth = Math.max(
      document.documentElement.clientWidth || 0,
      window.innerWidth || 0
    );
    const comfortableWidth = Math.min(390, Math.max(260, viewportWidth - 24));
    const $wrapper = $dropdown.closest('.select2-container.select2-container--open');
    const $positioned = $wrapper.length ? $wrapper : $dropdown;

    // Select2 writes the narrow lesson-card width on its outer positioned
    // wrapper. Widening only .select2-dropdown is therefore not enough. Set the
    // wrapper and make the dropdown fill it so long Persian headings stay readable.
    if ($wrapper.length) {
      $wrapper.css({
        width: comfortableWidth + 'px',
        minWidth: comfortableWidth + 'px',
        maxWidth: 'calc(100vw - 24px)'
      });
      $dropdown.css({
        width: '100%',
        minWidth: '100%',
        maxWidth: '100%'
      });
    } else {
      $dropdown.css({
        width: comfortableWidth + 'px',
        minWidth: comfortableWidth + 'px',
        maxWidth: 'calc(100vw - 24px)'
      });
    }

    const rect = $positioned[0].getBoundingClientRect();
    let delta = 0;
    if (rect.left < 12) {
      delta = 12 - rect.left;
    } else if (rect.right > viewportWidth - 12) {
      delta = (viewportWidth - 12) - rect.right;
    }
    if (delta) {
      const currentLeft = Number.parseFloat($positioned.css('left')) || 0;
      $positioned.css('left', currentLeft + delta + 'px');
    }
  }

  function activateChapterDropdown() {
    // This project ships a Select2 build without the optional dropdownCss
    // compatibility module. Add our styling hook after opening instead of using
    // dropdownCssClass, which otherwise throws "No select2/compat/dropdownCss".
    const $dropdown = $('.select2-dropdown:visible').last();
    if (!$dropdown.length) {
      return;
    }
    $dropdown.addClass('plan-chapter-dropdown');
    keepDropdownInsideViewport();
  }

  function settleChapterDropdown() {
    // Select2 performs its own final positioning around the open event. Apply the
    // readable width after that positioning too, so its inline width cannot win.
    window.requestAnimationFrame(function () {
      activateChapterDropdown();
      window.requestAnimationFrame(keepDropdownInsideViewport);
    });
    window.setTimeout(keepDropdownInsideViewport, 0);
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

    if (
      selectedValue &&
      !$select.find('option[value="' + selectedValue.replace(/"/g, '\\"') + '"]').length
    ) {
      $select.append(new Option(selectedText || selectedValue, selectedValue, true, true));
    }

    $select.select2({
      placeholder: 'انتخاب سرفصل',
      // The calendar column is intentionally narrow. Rendering the dropdown
      // inside the task made real chapter names look clipped/blank. Appending
      // to body lets the result list use a readable width without changing the
      // lesson card geometry.
      dropdownParent: $('body'),
      dropdownAutoWidth: true,
      width: '100%',
      theme: 'bootstrap-5',
      allowClear: true,
      templateResult: chapterTemplate,
      templateSelection: chapterSelection,
      escapeMarkup: function (markup) { return markup; },
      language: {
        errorLoading: function () { return 'بارگذاری سرفصل‌ها انجام نشد'; },
        loadingMore: function () { return 'در حال بارگذاری…'; },
        noResults: function () { return 'سرفصلی برای این درس پیدا نشد'; },
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
            markError(
              $task,
              payload.error || payload.message || 'بارگذاری سرفصل‌ها انجام نشد.'
            );
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

    $select
      .off('.planChapterVisibility')
      .on('select2:open.planChapterVisibility', settleChapterDropdown);

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
    window.addEventListener('resize', function () {
      window.requestAnimationFrame(keepDropdownInsideViewport);
    });

    window.planChapterLoader = {
      version: VERSION,
      synchronize: synchronize
    };
  }

  $(initialize);
})(window, document, window.jQuery);

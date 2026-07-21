(function (window, document, $) {
  'use strict';

  if (!$ || !$.ui) {
    return;
  }

  const PIXELS_PER_MINUTE = 35 / 60;
  const GRID_MINUTES = 15;
  const GRID_PIXELS = GRID_MINUTES * PIXELS_PER_MINUTE;
  const MIN_HEIGHT = GRID_PIXELS;
  const VERSION = '2026.07.21.2';

  function snap(value) {
    return Math.round(Number(value || 0) / GRID_PIXELS) * GRID_PIXELS;
  }

  function updateTime($task) {
    if (typeof window.updateTimeLabel === 'function') {
      window.updateTimeLabel($task);
    }
    const height = Math.max(MIN_HEIGHT, Number.parseFloat($task.css('height')) || $task.outerHeight());
    $task.attr('data-duration-minutes', Math.round(height / PIXELS_PER_MINUTE));
  }

  function overlaps($task, top, height, $container) {
    const bottom = top + height;
    let overlap = false;
    $container.children('.calendar-task:visible').not($task).each(function () {
      const $other = $(this);
      const otherTop = Number.parseFloat($other.css('top')) || 0;
      const otherBottom = otherTop + $other.outerHeight();
      if (!(bottom <= otherTop || top >= otherBottom)) {
        overlap = true;
        return false;
      }
    });
    return overlap;
  }

  function ensureHandle($task) {
    let $handle = $task.children('.plan-resize-handle');
    if (!$handle.length) {
      $handle = $('<div class="plan-resize-handle" title="برای تغییر زمان بکشید"><span></span></div>');
      $task.append($handle);
    }
    return $handle;
  }

  function bindPointerResize($task) {
    const $handle = ensureHandle($task);
    $handle.off('.planManualResize').on('pointerdown.planManualResize', function (event) {
      const originalEvent = event.originalEvent;
      if (window.readOnlyMode || (originalEvent.button !== undefined && originalEvent.button !== 0)) {
        return;
      }

      event.preventDefault();
      event.stopPropagation();
      event.stopImmediatePropagation();

      const startY = originalEvent.clientY;
      const startHeight = $task.outerHeight();
      const top = Number.parseFloat($task.css('top')) || 0;
      const $container = $task.parent();
      const maximum = Math.max(MIN_HEIGHT, $container.innerHeight() - top);
      let finished = false;

      $task.data('planManualResizeOriginalHeight', startHeight);
      $task.addClass('plan-resizing');
      $('body').addClass('plan-resize-cursor');

      if (this.setPointerCapture && originalEvent.pointerId !== undefined) {
        try {
          this.setPointerCapture(originalEvent.pointerId);
        } catch (_error) {}
      }

      function move(moveEvent) {
        const nativeEvent = moveEvent.originalEvent;
        const delta = nativeEvent.clientY - startY;
        const height = Math.max(MIN_HEIGHT, Math.min(snap(startHeight + delta), maximum));
        $task.css('height', height);
        updateTime($task);
        moveEvent.preventDefault();
      }

      function finish() {
        if (finished) {
          return;
        }
        finished = true;
        $(document).off('.planManualResizeActive');
        $('body').removeClass('plan-resize-cursor');

        const height = Math.max(MIN_HEIGHT, Math.min(snap($task.outerHeight()), maximum));
        if (overlaps($task, top, height, $container)) {
          $task.css('height', $task.data('planManualResizeOriginalHeight'));
        } else {
          $task.css('height', height);
        }
        $task.removeClass('plan-resizing');
        updateTime($task);
      }

      $(document)
        .on('pointermove.planManualResizeActive', move)
        .on('pointerup.planManualResizeActive pointercancel.planManualResizeActive', finish);
    });
  }

  function configureResizableCompatibility($task) {
    try {
      if ($task.resizable('instance')) {
        $task.resizable('destroy');
      }
    } catch (_error) {}

    $task.resizable({
      handles: 's',
      minHeight: MIN_HEIGHT,
      autoHide: false,
      start: function () {
        const $current = $(this);
        $current.data('planCompatibilityOriginalHeight', $current.outerHeight());
      },
      resize: function (_event, ui) {
        const $current = $(this);
        const top = Number.parseFloat($current.css('top')) || 0;
        const maximum = Math.max(MIN_HEIGHT, $current.parent().innerHeight() - top);
        const height = Math.max(MIN_HEIGHT, Math.min(snap(ui.size.height), maximum));
        ui.size.height = height;
        $current.css('height', height);
        updateTime($current);
      },
      stop: function (_event, ui) {
        const $current = $(this);
        const top = Number.parseFloat($current.css('top')) || 0;
        const maximum = Math.max(MIN_HEIGHT, $current.parent().innerHeight() - top);
        const height = Math.max(MIN_HEIGHT, Math.min(snap(ui.size.height), maximum));
        if (overlaps($current, top, height, $current.parent())) {
          $current.css('height', $current.data('planCompatibilityOriginalHeight'));
        } else {
          $current.css('height', height);
        }
        updateTime($current);
      }
    });

    bindPointerResize($task);
    $task.attr('data-plan-manual-resize-version', VERSION);
  }

  function openStudyEditor($task) {
    $task.addClass('plan-study-editor-pinned plan-study-editing');
    $task.find('.plan-study-compact').hide();
    $task.find('.task-chapter, .task-extra').each(function () {
      const $select = $(this);
      if ($select.hasClass('select2-hidden-accessible')) {
        $select.next('.select2-container').css('display', 'block');
      } else {
        $select.show();
      }
    });
  }

  function bindPersistentStudyEditor() {
    $(document)
      .off('click.planPersistentStudyEditor', '.plan-study-edit')
      .on('click.planPersistentStudyEditor', '.plan-study-edit', function (event) {
        event.preventDefault();
        event.stopPropagation();
        openStudyEditor($(this).closest('.calendar-task'));
      })
      .off('.planPersistentStudyEditorSelection', '.task-chapter, .task-extra')
      .on(
        'change.planPersistentStudyEditorSelection select2:select.planPersistentStudyEditorSelection',
        '.task-chapter, .task-extra',
        function () {
          const $task = $(this).closest('.calendar-task');
          const chapter = String($task.find('.task-chapter').val() || '').trim();
          const tests = String($task.find('.task-extra').val() || '').trim();
          if (chapter && tests) {
            $task.removeClass('plan-study-editor-pinned');
          }
        }
      );
  }

  function synchronize() {
    $('.calendar .calendar-task').each(function () {
      const $task = $(this);
      if (
        $task.attr('data-plan-manual-resize-version') !== VERSION ||
        !$task.children('.plan-resize-handle').length
      ) {
        configureResizableCompatibility($task);
      } else {
        bindPointerResize($task);
      }

      if ($task.hasClass('plan-study-editor-pinned')) {
        openStudyEditor($task);
      }
    });
  }

  function initialize() {
    const previousInit = window.initCalendarTask;
    if (typeof previousInit === 'function' && !previousInit.planManualResizeWrapped) {
      const wrappedInit = function ($task) {
        const result = previousInit($task);
        window.setTimeout(function () {
          configureResizableCompatibility($($task));
        }, 0);
        return result;
      };
      wrappedInit.planManualResizeWrapped = true;
      window.initCalendarTask = wrappedInit;
    }

    bindPersistentStudyEditor();

    const calendar = document.querySelector('.calendar');
    if (calendar) {
      new MutationObserver(function () {
        window.requestAnimationFrame(synchronize);
      }).observe(calendar, { childList: true, subtree: true });
    }

    synchronize();
    window.setInterval(synchronize, 400);
    window.dispatchEvent(new CustomEvent('plan:manual-resize-ready'));
  }

  $(initialize);
})(window, document, window.jQuery);

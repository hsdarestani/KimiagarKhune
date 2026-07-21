(function (window, document, $) {
  'use strict';

  if (!$ || !$.ui || !window.moment) {
    console.error('Plan interactions require jQuery UI and Moment.js.');
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

  function clampTop(value, height, containerHeight) {
    const maximum = Math.max(0, Number(containerHeight || 0) - Number(height || 0));
    return Math.max(0, Math.min(snap(value), maximum));
  }

  function safeInstance($element, widgetName) {
    try {
      return $element[widgetName]('instance') || null;
    } catch (_error) {
      return $element.data('ui-' + widgetName) || $element.data('ui' + widgetName.charAt(0).toUpperCase() + widgetName.slice(1)) || null;
    }
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
    let result = false;
    $container.children('.calendar-task:visible').not($task).each(function () {
      const $other = $(this);
      const otherTop = Number.parseFloat($other.css('top')) || 0;
      const otherBottom = otherTop + $other.outerHeight();
      if (!(bottom <= otherTop || top >= otherBottom)) {
        result = true;
        return false;
      }
    });
    return result;
  }

  function removeLegacyCompactControls($task) {
    $task.find('.chapter-display, .tests-display, .edit-btn').remove();
  }

  function select2Container($select) {
    return $select.next('.select2-container');
  }

  function setupCompactStudyControls($task) {
    if (!$task.hasClass('extended-task')) {
      return;
    }

    removeLegacyCompactControls($task);
    const $chapter = $task.find('.task-chapter').first();
    const $tests = $task.find('.task-extra').first();
    const $info = $task.find('.task-info').first();
    if (!$chapter.length || !$tests.length || !$info.length) {
      return;
    }

    let $compact = $info.children('.plan-study-compact');
    if (!$compact.length) {
      $compact = $(
        '<div class="plan-study-compact" aria-live="polite">' +
          '<span class="plan-study-chip plan-chapter-chip"></span>' +
          '<span class="plan-study-chip plan-tests-chip"></span>' +
          '<button type="button" class="plan-study-edit" title="ویرایش فصل و تعداد تست" aria-label="ویرایش فصل و تعداد تست">' +
            '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M4 16.5V20h3.5L18.2 9.3l-3.5-3.5L4 16.5Zm16.7-9.9a1 1 0 0 0 0-1.4l-1.9-1.9a1 1 0 0 0-1.4 0l-1.5 1.5 3.5 3.5 1.3-1.7Z"/></svg>' +
          '</button>' +
        '</div>'
      );
      $info.prepend($compact);
    }

    const $chapterChip = $compact.find('.plan-chapter-chip');
    const $testsChip = $compact.find('.plan-tests-chip');
    const $edit = $compact.find('.plan-study-edit');

    function showEditor() {
      $task.addClass('plan-study-editing');
      $compact.hide();
      if ($chapter.hasClass('select2-hidden-accessible')) {
        select2Container($chapter).css('display', 'block');
      } else {
        $chapter.show();
      }
      if ($tests.hasClass('select2-hidden-accessible')) {
        select2Container($tests).css('display', 'block');
      } else {
        $tests.show();
      }
    }

    function showCompact() {
      const chapterValue = String($chapter.val() || '').trim();
      const testsValue = String($tests.val() || '').trim();
      if (!chapterValue || !testsValue) {
        showEditor();
        return;
      }

      const chapterText = String($chapter.find('option:selected').text() || 'فصل انتخاب‌شده').trim();
      $chapterChip.text(chapterText);
      $testsChip.text(testsValue + ' تست');
      $task.removeClass('plan-study-editing');
      $chapter.hide();
      $tests.hide();
      select2Container($chapter).hide();
      select2Container($tests).hide();
      $compact.css('display', 'flex');
    }

    $edit.off('.planInteraction').on('click.planInteraction', function (event) {
      event.preventDefault();
      event.stopPropagation();
      showEditor();
    });

    $chapter.add($tests)
      .off('.planInteractionCompact')
      .on('change.planInteractionCompact select2:select.planInteractionCompact', function () {
        window.setTimeout(showCompact, 0);
      });

    window.setTimeout(showCompact, 0);
  }

  function ensureResizeHandle($task) {
    let $handle = $task.children('.plan-resize-handle');
    if (!$handle.length) {
      $handle = $('<div class="plan-resize-handle" title="برای تغییر زمان بکشید"><span></span></div>');
      $task.append($handle);
    }
    return $handle;
  }

  function destroyInteractionWidgets($task) {
    const draggable = safeInstance($task, 'draggable');
    const resizable = safeInstance($task, 'resizable');
    if (draggable) {
      try { $task.draggable('destroy'); } catch (_error) {}
    }
    if (resizable) {
      try { $task.resizable('destroy'); } catch (_error) {}
    }
  }

  function initializeTask($task) {
    if (!$task || !$task.length || !$task.hasClass('calendar-task')) {
      return;
    }
    if ($task.data('planInteractionInitializing')) {
      return;
    }

    $task.data('planInteractionInitializing', true);
    destroyInteractionWidgets($task);
    ensureResizeHandle($task);
    setupCompactStudyControls($task);

    $task.draggable({
      helper: function () {
        return $(this)
          .clone(false)
          .removeAttr('id')
          .removeClass('ui-draggable ui-draggable-handle ui-resizable')
          .addClass('plan-drag-ghost')
          .css({
            width: $(this).outerWidth(),
            height: $(this).outerHeight(),
            margin: 0,
            zIndex: 20000
          });
      },
      appendTo: 'body',
      scroll: true,
      refreshPositions: true,
      revert: 'invalid',
      revertDuration: 140,
      distance: 3,
      cancel: 'button, input, textarea, select, option, .select2-container, .plan-resize-handle, .plan-study-compact',
      start: function (event, ui) {
        const $current = $(this);
        const offset = $current.offset();
        const originalParent = $current.parent();
        const originalTop = Number.parseFloat($current.css('top')) || 0;

        $current.data('planOriginalParent', originalParent);
        $current.data('planOriginalTop', originalTop);
        $current.data('runtimeOriginalParent', originalParent);
        $current.data('runtimeOriginalTop', originalTop);
        $current.data('planGrabOffsetY', Math.max(0, event.pageY - offset.top));
        $current.data('planDropAccepted', false);
        $current.addClass('plan-dragging-source');
        ui.helper.find('.select2-container, .plan-study-edit').remove();
      },
      stop: function () {
        const $current = $(this);
        $current.removeClass('plan-dragging-source');
        $current.removeData('planGrabOffsetY');
        $current.removeData('planDropAccepted');
        updateTime($current);
      }
    });

    $task.resizable({
      handles: { s: '.plan-resize-handle' },
      minHeight: MIN_HEIGHT,
      autoHide: false,
      start: function () {
        const $current = $(this);
        $current.data('planOriginalHeight', $current.outerHeight());
        $current.addClass('plan-resizing');
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
          $current.css('height', $current.data('planOriginalHeight'));
        } else {
          $current.css('height', height);
        }
        $current.removeClass('plan-resizing');
        updateTime($current);
      }
    });

    $task.attr('data-plan-interaction-version', VERSION);
    $task.removeData('planInteractionInitializing');
    updateTime($task);
  }

  function sourceDuration($source) {
    if ($source.hasClass('calendar-task')) {
      return Math.max(MIN_HEIGHT, $source.outerHeight()) / PIXELS_PER_MINUTE;
    }
    return Math.max(
      GRID_MINUTES,
      Number($source.attr('data-duration-minutes')) ||
      Number(($source.data() || {}).duration_minutes) ||
      90
    );
  }

  function desiredDropTop(event, ui, $target) {
    const $source = $(ui.draggable);
    const height = sourceDuration($source) * PIXELS_PER_MINUTE;
    const targetOffset = $target.offset();
    const grabOffset = $source.hasClass('calendar-task')
      ? Number($source.data('planGrabOffsetY')) || 0
      : 0;
    const pointerY = Number(event.pageY) ||
      (ui.offset ? Number(ui.offset.top) + grabOffset : targetOffset.top);
    return clampTop(pointerY - targetOffset.top - grabOffset, height, $target.innerHeight());
  }

  function wrapDroppable($container) {
    const instance = safeInstance($container, 'droppable');
    if (!instance || !instance.options) {
      return;
    }

    const currentDrop = instance.options.drop;
    if (!currentDrop || currentDrop.planRealInteraction) {
      return;
    }

    const wrapped = function (event, ui) {
      const $target = $(this);
      const $source = ui && ui.draggable ? $(ui.draggable) : $();
      if (!$source.length || window.readOnlyMode || !(window.planRuntimeState && window.planRuntimeState.loaded)) {
        return false;
      }

      if ($target.closest('.day-column').hasClass('disabled-day')) {
        return false;
      }

      const top = desiredDropTop(event, ui, $target);
      const before = new Set($target.children('.calendar-task').toArray());

      if ($source.hasClass('other-plan-task')) {
        if (typeof window.planSecondaryBuildOtherPlanTask === 'function') {
          const $created = window.planSecondaryBuildOtherPlanTask($source, $target, top);
          if ($created && $created.length) {
            initializeTask($created);
            return true;
          }
        }
        return false;
      }

      const patchedUi = $.extend({}, ui, {
        draggable: $source,
        offset: $.extend({}, ui.offset || {}, {
          top: $target.offset().top + top
        })
      });

      const result = currentDrop.call(this, event, patchedUi);
      $source.data('planDropAccepted', true).removeClass('plan-dragging-source');

      window.setTimeout(function () {
        $target.children('.calendar-task').each(function () {
          if (!before.has(this) || this === $source[0]) {
            initializeTask($(this));
          }
        });
      }, 0);
      return result;
    };

    wrapped.planRealInteraction = true;
    wrapped.planRealOriginal = currentDrop;
    instance.options.drop = wrapped;
    instance.options.tolerance = 'pointer';
    instance.options.hoverClass = 'plan-drop-target';
    instance.options.activeClass = 'plan-drop-active';
  }

  function synchronize() {
    $('.calendar .task-container').each(function () {
      wrapDroppable($(this));
    });
    $('.calendar .calendar-task').each(function () {
      const $task = $(this);
      if ($task.attr('data-plan-interaction-version') !== VERSION || !safeInstance($task, 'draggable') || !safeInstance($task, 'resizable')) {
        initializeTask($task);
      } else {
        setupCompactStudyControls($task);
      }
    });
  }

  function initialize() {
    window.initCalendarTask = initializeTask;
    window.setupEditableSelects = function ($task) {
      setupCompactStudyControls($($task));
    };

    const calendar = document.querySelector('.calendar');
    if (calendar) {
      new MutationObserver(function () {
        window.requestAnimationFrame(synchronize);
      }).observe(calendar, { childList: true, subtree: true });
    }

    $(document)
      .off('mousedown.planInteraction', '.calendar-task')
      .on('mousedown.planInteraction', '.calendar-task', function () {
        const $task = $(this);
        if (
          $task.attr('data-plan-interaction-version') !== VERSION ||
          !safeInstance($task, 'draggable') ||
          !safeInstance($task, 'resizable')
        ) {
          initializeTask($task);
        }
      });

    synchronize();
    window.setInterval(synchronize, 500);
    window.dispatchEvent(new CustomEvent('plan:interactions-ready'));
  }

  $(initialize);
})(window, document, window.jQuery);

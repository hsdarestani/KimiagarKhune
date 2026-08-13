(function (window, document, $) {
  'use strict';

  if (!$) {
    return;
  }

  const VERSION = '2026.08.13.3';
  const nativeSetInterval = window.setInterval.bind(window);
  let dropdownFrame = 0;

  // plan-interactions historically started a full-calendar synchronize pass every
  // 500ms. Dynamic task creation is already covered by MutationObserver, so the
  // polling loop only burns CPU and becomes noticeable on busy weeks. Block just
  // that one interval while the ready callbacks are bootstrapping, then restore
  // the browser API immediately afterwards.
  window.setInterval = function (handler, delay) {
    if (
      Number(delay) === 500 &&
      typeof handler === 'function' &&
      handler.name === 'synchronize'
    ) {
      return 0;
    }
    return nativeSetInterval.apply(window, arguments);
  };

  function visibleChapterDropdown() {
    return $('.select2-dropdown.plan-chapter-dropdown:visible').last();
  }

  function chapterDropdownWrapper($dropdown) {
    if (!$dropdown || !$dropdown.length) {
      return $();
    }
    return $dropdown.parents('.select2-container.select2-container--open').first();
  }

  function setImportant(element, property, value) {
    if (element && element.style) {
      element.style.setProperty(property, value, 'important');
    }
  }

  function viewportBounds() {
    const visual = window.visualViewport;
    const left = visual ? Number(visual.offsetLeft || 0) : 0;
    const top = visual ? Number(visual.offsetTop || 0) : 0;
    const width = visual
      ? Number(visual.width || document.documentElement.clientWidth || window.innerWidth || 0)
      : Math.max(document.documentElement.clientWidth || 0, window.innerWidth || 0);
    const height = visual
      ? Number(visual.height || document.documentElement.clientHeight || window.innerHeight || 0)
      : Math.max(document.documentElement.clientHeight || 0, window.innerHeight || 0);
    return {
      left: left,
      top: top,
      width: width,
      height: height,
      right: left + width,
      bottom: top + height
    };
  }

  function constrainChapterDropdown() {
    const $dropdown = visibleChapterDropdown();
    if (!$dropdown.length) {
      return;
    }

    const edge = 10;
    const viewport = viewportBounds();
    const maxWidth = Math.max(180, viewport.width - edge * 2);
    const preferredWidth = Math.min(390, maxWidth);
    const preferredMinWidth = Math.min(260, maxWidth);
    const $wrapper = chapterDropdownWrapper($dropdown);
    const $positioned = $wrapper.length ? $wrapper : $dropdown;

    if ($wrapper.length) {
      $wrapper.addClass('plan-chapter-dropdown-wrapper');
      setImportant($wrapper[0], 'width', preferredWidth + 'px');
      setImportant($wrapper[0], 'min-width', preferredMinWidth + 'px');
      setImportant($wrapper[0], 'max-width', maxWidth + 'px');
      setImportant($wrapper[0], 'box-sizing', 'border-box');
      setImportant($dropdown[0], 'width', '100%');
      setImportant($dropdown[0], 'min-width', '100%');
      setImportant($dropdown[0], 'max-width', '100%');
    } else {
      setImportant($dropdown[0], 'width', preferredWidth + 'px');
      setImportant($dropdown[0], 'min-width', preferredMinWidth + 'px');
      setImportant($dropdown[0], 'max-width', maxWidth + 'px');
    }

    // Keep the result list short enough to fit even on a small laptop window.
    const $options = $dropdown.find('.select2-results__options').first();
    if ($options.length) {
      const dropdownHeight = $dropdown.outerHeight() || 0;
      const optionsHeight = $options.outerHeight() || 0;
      const nonResultsHeight = Math.max(52, dropdownHeight - optionsHeight);
      const maxOptionsHeight = Math.max(
        110,
        Math.min(320, viewport.height - edge * 2 - nonResultsHeight)
      );
      setImportant($options[0], 'max-height', maxOptionsHeight + 'px');
      setImportant($options[0], 'overflow-y', 'auto');
    }

    // Select2 may position RTL dropdowns with `right` instead of `left`. Work in
    // document coordinates and explicitly own left/top so the correction always
    // wins, regardless of scroll position or directionality.
    const rect = $positioned[0].getBoundingClientRect();
    let deltaX = 0;
    let deltaY = 0;

    if (rect.left < viewport.left + edge) {
      deltaX = viewport.left + edge - rect.left;
    } else if (rect.right > viewport.right - edge) {
      deltaX = viewport.right - edge - rect.right;
    }

    if (rect.top < viewport.top + edge) {
      deltaY = viewport.top + edge - rect.top;
    } else if (rect.bottom > viewport.bottom - edge) {
      deltaY = viewport.bottom - edge - rect.bottom;
    }

    if (deltaX || deltaY) {
      const offset = $positioned.offset() || { left: 0, top: 0 };
      if (deltaX) {
        setImportant($positioned[0], 'right', 'auto');
        setImportant($positioned[0], 'left', offset.left + deltaX + 'px');
      }
      if (deltaY) {
        setImportant($positioned[0], 'top', offset.top + deltaY + 'px');
      }
    }
  }

  function queueDropdownConstraint() {
    if (dropdownFrame) {
      return;
    }
    dropdownFrame = window.requestAnimationFrame(function () {
      dropdownFrame = 0;
      constrainChapterDropdown();
    });
  }

  function cleanupDetachedTask($task) {
    $task.find('select.select2-hidden-accessible').each(function () {
      try { $(this).select2('destroy'); } catch (_error) {}
    });
    if ($task.hasClass('ui-draggable')) {
      try { $task.draggable('destroy'); } catch (_error) {}
    }
    if ($task.hasClass('ui-resizable')) {
      try { $task.resizable('destroy'); } catch (_error) {}
    }
    $task.remove();
  }

  function bindFastRemove() {
    $(document)
      .off('click.planRuntime', '.remove-btn')
      .off('click.planStabilityRemove', '.remove-btn')
      .on('click.planStabilityRemove', '.remove-btn', function (event) {
        event.preventDefault();
        event.stopPropagation();
        const $task = $(this).closest('.calendar-task');
        if (!$task.length) {
          return;
        }

        // Detach first so the UI responds immediately and teardown mutations do
        // not wake every calendar MutationObserver. Cleanup runs off the hot path.
        $task.detach();
        const cleanup = function () { cleanupDetachedTask($task); };
        if (typeof window.requestIdleCallback === 'function') {
          window.requestIdleCallback(cleanup, { timeout: 120 });
        } else {
          window.setTimeout(cleanup, 0);
        }
      });
  }

  function initialize() {
    window.setInterval = nativeSetInterval;
    bindFastRemove();

    $(document)
      .off('select2:open.planStabilityDropdown', '.task-chapter')
      .on('select2:open.planStabilityDropdown', '.task-chapter', function () {
        queueDropdownConstraint();
        window.setTimeout(queueDropdownConstraint, 0);
        window.setTimeout(queueDropdownConstraint, 40);
      });

    window.addEventListener('resize', queueDropdownConstraint, { passive: true });
    window.addEventListener('scroll', queueDropdownConstraint, { passive: true, capture: true });
    if (window.visualViewport) {
      window.visualViewport.addEventListener('resize', queueDropdownConstraint, { passive: true });
      window.visualViewport.addEventListener('scroll', queueDropdownConstraint, { passive: true });
    }

    document.body.setAttribute('data-plan-stability-version', VERSION);
    window.planStabilityFixes = {
      version: VERSION,
      constrainChapterDropdown: constrainChapterDropdown
    };
  }

  $(initialize);
})(window, document, window.jQuery);

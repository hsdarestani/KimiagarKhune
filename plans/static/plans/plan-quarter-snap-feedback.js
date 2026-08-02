(function (window, document, $) {
  'use strict';

  if (!$ || !$.ui) {
    return;
  }

  const BASE_MINUTES = 6 * 60;
  const PIXELS_PER_MINUTE = 35 / 60;
  const GRID_MINUTES = 15;
  const GRID_PIXELS = GRID_MINUTES * PIXELS_PER_MINUTE;
  const VERSION = '2026.08.02.1';
  let synchronizeQueued = false;

  function pad(value) {
    return String(value).padStart(2, '0');
  }

  function formatClock(totalMinutes) {
    let value = Math.round(totalMinutes) % (24 * 60);
    if (value < 0) {
      value += 24 * 60;
    }
    return pad(Math.floor(value / 60)) + ':' + pad(value % 60);
  }

  function snap(value) {
    return Math.round(Number(value || 0) / GRID_PIXELS) * GRID_PIXELS;
  }

  function ensureFeedback() {
    let $feedback = $('.plan-quarter-feedback').first();
    if (!$feedback.length) {
      $feedback = $(
        '<div class="plan-quarter-feedback" aria-hidden="true">' +
          '<strong class="plan-quarter-feedback-time"></strong>' +
          '<span>حرکت پله‌ای ۱۵ دقیقه</span>' +
        '</div>'
      ).appendTo('body');
    }

    let $line = $('.plan-quarter-guide-line').first();
    if (!$line.length) {
      $line = $('<div class="plan-quarter-guide-line" aria-hidden="true"></div>').appendTo('body');
    }
    return { feedback: $feedback, line: $line };
  }

  function visibleContainers() {
    return $('.calendar .task-container').filter(function () {
      const rect = this.getBoundingClientRect();
      return rect.width > 0 && rect.height > 0;
    }).toArray();
  }

  function targetContainer(clientX) {
    const containers = visibleContainers();
    let closest = null;
    let closestDistance = Number.POSITIVE_INFINITY;

    containers.forEach(function (container) {
      const rect = container.getBoundingClientRect();
      if (clientX >= rect.left && clientX <= rect.right) {
        closest = container;
        closestDistance = 0;
        return;
      }
      const distance = Math.min(
        Math.abs(clientX - rect.left),
        Math.abs(clientX - rect.right)
      );
      if (distance < closestDistance) {
        closest = container;
        closestDistance = distance;
      }
    });
    return closest;
  }

  function updateFeedback(event, $task) {
    const clientX = Number.isFinite(event.clientX)
      ? event.clientX
      : Number(event.pageX || 0) - window.scrollX;
    const clientY = Number.isFinite(event.clientY)
      ? event.clientY
      : Number(event.pageY || 0) - window.scrollY;
    const container = targetContainer(clientX);
    if (!container) {
      return;
    }

    const rect = container.getBoundingClientRect();
    const height = Math.max(GRID_PIXELS, $task.outerHeight());
    const grabOffset = Math.max(0, Number($task.data('planGrabOffsetY')) || 0);
    const maximum = Math.max(0, rect.height - height);
    const top = Math.max(0, Math.min(snap(clientY - rect.top - grabOffset), maximum));
    const start = BASE_MINUTES + Math.round(top / PIXELS_PER_MINUTE);
    const duration = Math.max(GRID_MINUTES, Math.round(height / PIXELS_PER_MINUTE));
    const widgets = ensureFeedback();

    widgets.feedback
      .addClass('is-visible')
      .css({
        left: Math.min(window.innerWidth - 178, Math.max(8, clientX + 14)) + 'px',
        top: Math.max(8, clientY - 54) + 'px'
      })
      .find('.plan-quarter-feedback-time')
      .text(formatClock(start) + ' تا ' + formatClock(start + duration));

    widgets.line
      .addClass('is-visible')
      .css({
        left: rect.left + 'px',
        top: rect.top + top + 'px',
        width: rect.width + 'px'
      });
  }

  function hideFeedback() {
    $('.plan-quarter-feedback, .plan-quarter-guide-line').removeClass('is-visible');
  }

  function draggableInstance($task) {
    try {
      return $task.draggable('instance') || null;
    } catch (_error) {
      return $task.data('ui-draggable') || null;
    }
  }

  function patchTask(task) {
    const $task = $(task);
    const instance = draggableInstance($task);
    if (!instance || !instance.options) {
      return;
    }
    if ($task.attr('data-plan-quarter-snap-version') === VERSION) {
      return;
    }

    const options = instance.options;
    const previousStart = options.start;
    const previousDrag = options.drag;
    const previousStop = options.stop;

    options.grid = [1, GRID_PIXELS];
    options.start = function (event, ui) {
      const result = typeof previousStart === 'function'
        ? previousStart.apply(this, arguments)
        : undefined;
      $(this).addClass('plan-quarter-snapping');
      updateFeedback(event, $(this));
      return result;
    };
    options.drag = function (event, ui) {
      const result = typeof previousDrag === 'function'
        ? previousDrag.apply(this, arguments)
        : undefined;
      updateFeedback(event, $(this));
      return result;
    };
    options.stop = function (event, ui) {
      try {
        return typeof previousStop === 'function'
          ? previousStop.apply(this, arguments)
          : undefined;
      } finally {
        $(this).removeClass('plan-quarter-snapping');
        hideFeedback();
      }
    };

    $task.attr('data-plan-quarter-snap-version', VERSION);
  }

  function synchronize() {
    synchronizeQueued = false;
    $('.calendar .calendar-task').each(function () {
      patchTask(this);
    });
    if (document.body) {
      document.body.setAttribute('data-plan-quarter-snap-version', VERSION);
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
    if (typeof previous !== 'function' || previous.planQuarterSnapWrapped) {
      return;
    }

    const wrapped = function (task) {
      const result = previous.apply(this, arguments);
      const element = task && task.jquery ? task[0] : task;
      if (element) {
        window.requestAnimationFrame(function () {
          patchTask(element);
        });
      }
      return result;
    };
    wrapped.planQuarterSnapWrapped = true;
    wrapped.planQuarterSnapOriginal = previous;
    window.initCalendarTask = wrapped;
  }

  function initialize() {
    ensureFeedback();
    wrapTaskInitializer();
    synchronize();

    const calendar = document.querySelector('.calendar');
    if (calendar) {
      new MutationObserver(queueSynchronize).observe(calendar, {
        childList: true,
        subtree: true
      });
    }

    window.addEventListener('plan:interactions-ready', function () {
      wrapTaskInitializer();
      queueSynchronize();
    });
    window.addEventListener('blur', hideFeedback);
    document.addEventListener('mouseup', hideFeedback, true);
    document.addEventListener('pointerup', hideFeedback, true);

    window.planQuarterSnapFeedback = {
      version: VERSION,
      synchronize: synchronize,
      gridMinutes: GRID_MINUTES
    };
  }

  $(initialize);
})(window, document, window.jQuery);

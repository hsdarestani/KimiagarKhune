(function (window, document, $) {
  'use strict';

  if (!$) {
    return;
  }

  const START_HOUR = 6;
  const END_HOUR = 24;
  const HOURS = END_HOUR - START_HOUR;
  const HOUR_HEIGHT = 35;
  const QUARTER_HEIGHT = HOUR_HEIGHT / 4;
  const GRID_HEIGHT = HOURS * HOUR_HEIGHT;
  const HEADER_HEIGHT = 58;
  const VERSION = '2026.07.22.2';
  let synchronizeQueued = false;

  function pad(value) {
    return String(value).padStart(2, '0');
  }

  function ensureDayHeaders() {
    $('.calendar .day-column').each(function () {
      const $column = $(this);
      let $header = $column.children('.plan-day-header').first();
      if (!$header.length) {
        $header = $('<div class="plan-day-header"></div>');
        const $heading = $column.children('h4').first();
        const $labels = $column.children('label');
        const $options = $('<div class="plan-day-options"></div>');
        if ($heading.length) {
          $header.append($heading);
        }
        $options.append($labels);
        $header.append($options);
        $column.prepend($header);
      }
    });
  }

  function layoutTimeline() {
    const $timeline = $('.calendar-container > .timeline').first();
    if (!$timeline.length) {
      return;
    }

    let $slots = $timeline.children('.time-slot');
    const expectedSlots = HOURS + 1;
    if ($slots.length !== expectedSlots) {
      const fragment = document.createDocumentFragment();
      for (let index = 0; index < expectedSlots; index += 1) {
        const slot = document.createElement('div');
        slot.className = 'time-slot';
        fragment.appendChild(slot);
      }
      $timeline.empty().append(fragment);
      $slots = $timeline.children('.time-slot');
    }

    $slots.each(function (index) {
      const label = pad((START_HOUR + index) % 24) + ':00';
      const minute = String(index * 60);
      const top = index * HOUR_HEIGHT + 'px';
      if (this.textContent !== label) {
        this.textContent = label;
      }
      if (this.getAttribute('data-plan-minute') !== minute) {
        this.setAttribute('data-plan-minute', minute);
      }
      if (this.style.top !== top) {
        this.style.top = top;
      }
    });
  }

  function applyGeometryVariables() {
    const root = document.documentElement;
    root.style.setProperty('--plan-hour-height', HOUR_HEIGHT + 'px');
    root.style.setProperty('--plan-quarter-height', QUARTER_HEIGHT + 'px');
    root.style.setProperty('--plan-grid-hours', String(HOURS));
    root.style.setProperty('--plan-grid-height', GRID_HEIGHT + 'px');
    root.style.setProperty('--plan-day-header-height', HEADER_HEIGHT + 'px');
  }

  function normalizeTaskGeometry() {
    $('.calendar .task-container').each(function () {
      const height = GRID_HEIGHT + 'px';
      if (this.style.height !== height) {
        this.style.height = height;
      }
      if (this.style.minHeight !== height) {
        this.style.minHeight = height;
      }
      if (this.style.maxHeight !== height) {
        this.style.maxHeight = height;
      }
    });

    $('.calendar .calendar-task').each(function () {
      const $task = $(this);
      const top = Number.parseFloat($task.css('top')) || 0;
      const height = Number.parseFloat($task.css('height')) || QUARTER_HEIGHT;
      const clampedTop = Math.max(
        0,
        Math.min(top, GRID_HEIGHT - Math.max(QUARTER_HEIGHT, height))
      );
      if (Math.abs(clampedTop - top) > 0.1) {
        $task.css('top', clampedTop + 'px');
        if (typeof window.updateTimeLabel === 'function') {
          window.updateTimeLabel($task);
        }
      }
    });
  }

  function synchronize() {
    synchronizeQueued = false;
    applyGeometryVariables();
    ensureDayHeaders();
    layoutTimeline();
    normalizeTaskGeometry();
    if (document.body) {
      document.body.setAttribute('data-plan-time-grid-version', VERSION);
    }
  }

  function queueSynchronize() {
    if (synchronizeQueued) {
      return;
    }
    synchronizeQueued = true;
    window.requestAnimationFrame(synchronize);
  }

  function topForClock(hours, minutes) {
    const total = Number(hours) * 60 + Number(minutes || 0) - START_HOUR * 60;
    return Math.max(0, Math.min(total, HOURS * 60)) * HOUR_HEIGHT / 60;
  }

  function clockForTop(top) {
    const total = START_HOUR * 60 + Math.round(Number(top || 0) * 60 / HOUR_HEIGHT);
    return {
      hour: Math.floor(total / 60) % 24,
      minute: total % 60
    };
  }

  function geometrySnapshot() {
    const container = document.querySelector('.calendar .task-container');
    const timeline = document.querySelector('.calendar-container > .timeline');
    const six = timeline && timeline.querySelector('.time-slot[data-plan-minute="0"]');
    const seven = timeline && timeline.querySelector('.time-slot[data-plan-minute="60"]');
    if (!container || !timeline || !six || !seven) {
      return null;
    }
    const containerRect = container.getBoundingClientRect();
    const sixRect = six.getBoundingClientRect();
    const sevenRect = seven.getBoundingClientRect();
    return {
      gridTop: containerRect.top,
      gridHeight: containerRect.height,
      sixCenter: sixRect.top + sixRect.height / 2,
      sevenCenter: sevenRect.top + sevenRect.height / 2,
      hourDistance:
        sevenRect.top + sevenRect.height / 2 -
        (sixRect.top + sixRect.height / 2)
    };
  }

  window.planTimeGrid = {
    version: VERSION,
    startHour: START_HOUR,
    endHour: END_HOUR,
    hourHeight: HOUR_HEIGHT,
    quarterHeight: QUARTER_HEIGHT,
    gridHeight: GRID_HEIGHT,
    topForClock: topForClock,
    clockForTop: clockForTop,
    synchronize: synchronize,
    geometrySnapshot: geometrySnapshot
  };

  function initialize() {
    synchronize();

    const calendar = document.querySelector('.calendar');
    if (calendar) {
      new MutationObserver(queueSynchronize).observe(calendar, {
        childList: true,
        subtree: true
      });
    }

    window.addEventListener('resize', queueSynchronize);
    window.addEventListener('plan:interactions-ready', queueSynchronize);
    window.addEventListener('plan:drag-surface-ready', queueSynchronize);
    window.dispatchEvent(new CustomEvent('plan:time-grid-ready'));
  }

  $(initialize);
})(window, document, window.jQuery);

(function (window, document, $) {
  'use strict';

  if (!$) {
    return;
  }

  const VERSION = '2026.08.18.1';
  const PIXELS_PER_MINUTE = 35 / 60;
  const BASE_MINUTES = 6 * 60;
  let recurringRequest = null;

  function normalizeText(value) {
    return String(value || '')
      .trim()
      .replace(/[\u200c\u200e\u200f\s]+/g, '')
      .replace(/[يى]/g, 'ی')
      .replace(/ك/g, 'ک');
  }

  function normalizeDay(value) {
    const normalized = normalizeText(value);
    const days = ['شنبه', 'یک‌شنبه', 'دوشنبه', 'سه‌شنبه', 'چهارشنبه', 'پنج‌شنبه', 'جمعه'];
    return days.find(function (day) {
      return normalizeText(day) === normalized;
    }) || null;
  }

  function parseClock(value) {
    if (!value) {
      return null;
    }
    const raw = String(value);
    if (raw.indexOf('T') >= 0 && window.moment) {
      const parsed = window.moment.parseZone(raw);
      if (parsed.isValid()) {
        return parsed.hour() * 60 + parsed.minute();
      }
    }
    const match = raw.match(/(\d{1,2}):(\d{2})/);
    if (!match) {
      return null;
    }
    return Number(match[1]) * 60 + Number(match[2]);
  }

  function clockFromTask($task) {
    const top = Number.parseFloat($task.css('top')) || 0;
    const height = Number.parseFloat($task.css('height')) || $task.outerHeight() || 0;
    const start = BASE_MINUTES + Math.round(top / PIXELS_PER_MINUTE);
    const duration = Math.max(15, Math.round(height / PIXELS_PER_MINUTE));
    return {
      start: start % (24 * 60),
      end: (start + duration) % (24 * 60)
    };
  }

  function taskTitle($task) {
    const $title = $task.find('.task-title').first();
    if ($title.is('input, textarea')) {
      return String($title.val() || '').trim();
    }
    return String($title.text() || '').trim();
  }

  function synchronizeTitleElement(element) {
    if (!element || element.nodeType !== 1) {
      return;
    }
    if (element.matches('input.task-title')) {
      element.setAttribute('value', element.value || '');
    } else if (element.matches('textarea.task-title')) {
      element.textContent = element.value || '';
    }
  }

  function synchronizeTitlesForExport() {
    document.querySelectorAll('.calendar-task .task-title').forEach(synchronizeTitleElement);
    if (document.body) {
      document.body.setAttribute('data-plan-export-title-sync-version', VERSION);
    }
  }

  function sameRecurringEvent($task, event) {
    if (($task.attr('data-box-type') || '') !== 'ایونت') {
      return false;
    }
    if (normalizeText(taskTitle($task)) !== normalizeText(event.name)) {
      return false;
    }

    const taskClock = clockFromTask($task);
    const eventStart = parseClock(event.start_time);
    const eventEnd = parseClock(event.end_time);
    if (eventStart === null || eventEnd === null) {
      return false;
    }

    return Math.abs(taskClock.start - eventStart) <= 1 && Math.abs(taskClock.end - eventEnd) <= 1;
  }

  function findDayContainer(dayName) {
    const canonical = normalizeDay(dayName);
    if (!canonical) {
      return $();
    }
    return $('.calendar .day-column').filter(function () {
      return normalizeDay($(this).attr('data-day')) === canonical;
    }).find('.task-container').first();
  }

  function recurringEventAlreadyVisible(event) {
    const $container = findDayContainer(event.day_of_week);
    if (!$container.length) {
      return false;
    }
    let found = false;
    $container.children('.calendar-task').each(function () {
      if (sameRecurringEvent($(this), event)) {
        found = true;
        return false;
      }
    });
    return found;
  }

  function appendRecurringEvent(event) {
    if (!event || !event.name || recurringEventAlreadyVisible(event)) {
      return false;
    }

    const $container = findDayContainer(event.day_of_week);
    if (!$container.length) {
      return false;
    }

    const start = parseClock(event.start_time);
    const end = parseClock(event.end_time);
    if (start === null || end === null) {
      return false;
    }
    let duration = end - start;
    if (duration <= 0) {
      duration += 24 * 60;
    }
    duration = Math.max(15, duration);

    const top = typeof window.calculateTop === 'function'
      ? window.calculateTop(event.start_time)
      : Math.max(0, start - BASE_MINUTES) * PIXELS_PER_MINUTE;
    const height = typeof window.calculateHeight === 'function'
      ? window.calculateHeight(event.start_time, event.end_time)
      : duration * PIXELS_PER_MINUTE;

    const $task = $('<div class="calendar-task event-task"></div>')
      .attr('data-box-type', 'ایونت')
      .attr('data-duration-minutes', duration)
      .attr('data-recurring-default', 'true')
      .css({
        top: top + 'px',
        height: Math.max(15 * PIXELS_PER_MINUTE, height) + 'px',
        left: '5%'
      });

    if (event.default_event_id) {
      $task.attr('data-default-event-id', event.default_event_id);
    }

    $task.append('<button type="button" class="remove-btn" title="حذف">✖</button>');
    $task.append('<button type="button" class="tick-btn" title="ایجاد تکلیف از ایونت">افزودن تکلیف</button>');
    $task.append(
      $('<input type="text" class="task-title task-inp editable">')
        .val(event.name)
        .attr('value', event.name)
    );
    $task.append('<div class="time-label"></div>');

    $container.append($task);
    if (typeof window.initCalendarTask === 'function') {
      window.initCalendarTask($task);
    }
    if (typeof window.updateTimeLabel === 'function') {
      window.updateTimeLabel($task);
    }
    return true;
  }

  function mergeRecurringEvents(events) {
    let added = 0;
    (Array.isArray(events) ? events : []).forEach(function (event) {
      if (appendRecurringEvent(event)) {
        added += 1;
      }
    });
    if (document.body) {
      document.body.setAttribute('data-plan-recurring-defaults-version', VERSION);
    }
    return added;
  }

  function reloadRecurringEvents() {
    const state = window.planRuntimeState || {};
    const studentId = state.studentId || $('#student-select').val();
    if (!studentId || !state.loaded) {
      return Promise.resolve(0);
    }

    if (recurringRequest && typeof recurringRequest.abort === 'function') {
      recurringRequest.abort();
    }

    return new Promise(function (resolve) {
      recurringRequest = $.ajax({
        url: '/get_default_events/',
        method: 'GET',
        dataType: 'json',
        data: { student_id: studentId }
      })
        .done(function (events) {
          resolve(mergeRecurringEvents(events));
        })
        .fail(function (xhr, status) {
          if (status !== 'abort') {
            console.warn('Could not reload recurring Plan events.', xhr && xhr.responseText);
          }
          resolve(0);
        })
        .always(function () {
          recurringRequest = null;
        });
    });
  }

  function bindExportTitleSync() {
    ['download-week-output', 'download-all-pdf'].forEach(function (id) {
      const element = document.getElementById(id);
      if (element && !element.dataset.planTitleSyncBound) {
        element.dataset.planTitleSyncBound = 'true';
        element.addEventListener('click', synchronizeTitlesForExport, true);
      }
    });

    $(document)
      .off('input.planTitleSync change.planTitleSync', '.calendar-task .task-title')
      .on('input.planTitleSync change.planTitleSync', '.calendar-task .task-title', function () {
        synchronizeTitleElement(this);
      });
  }

  function bindRecurringReload() {
    $(document)
      .off('ajaxComplete.planRecurringDefaults')
      .on('ajaxComplete.planRecurringDefaults', function (_event, xhr, settings) {
        const url = String((settings && settings.url) || '');
        if (url.indexOf('/get-weekly-report-details/') === -1) {
          return;
        }

        const response = (xhr && xhr.responseJSON) || null;
        // The canonical runtime already loads recurring defaults for a completely
        // empty week. We only need to repair the historical gap: a saved report
        // with one or more tasks used to suppress every recurring class/event.
        if (!response || !Array.isArray(response.tasks) || !response.tasks.length) {
          return;
        }
        window.setTimeout(reloadRecurringEvents, 0);
      });
  }

  function initialize() {
    bindExportTitleSync();
    bindRecurringReload();
    synchronizeTitlesForExport();

    window.planPersistenceFixes = {
      version: VERSION,
      synchronizeTitlesForExport: synchronizeTitlesForExport,
      mergeRecurringEvents: mergeRecurringEvents,
      reloadRecurringEvents: reloadRecurringEvents
    };

    if (document.body) {
      document.body.setAttribute('data-plan-persistence-fixes-version', VERSION);
    }
    window.dispatchEvent(new CustomEvent('plan:persistence-fixes-ready'));
  }

  $(initialize);
})(window, document, window.jQuery);

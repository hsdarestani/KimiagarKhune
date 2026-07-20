(function (window, document, $) {
  'use strict';

  if (!$ || !$.ui || !window.moment) {
    console.error('Plan runtime requires jQuery, jQuery UI and Moment.js.');
    return;
  }

  const BASE_HOUR = 6;
  const MINUTES_PER_DAY_VIEW = 18 * 60;
  const PIXELS_PER_HOUR = 35;
  const PIXELS_PER_MINUTE = PIXELS_PER_HOUR / 60;
  const GRID_MINUTES = 15;
  const GRID_PIXELS = GRID_MINUTES * PIXELS_PER_MINUTE;
  const DEFAULT_DURATION = 90;
  const CANONICAL_DAYS = [
    'شنبه',
    'یک‌شنبه',
    'دوشنبه',
    'سه‌شنبه',
    'چهارشنبه',
    'پنج‌شنبه',
    'جمعه'
  ];
  const JS_DAY_TO_PERSIAN = {
    6: 'شنبه',
    0: 'یک‌شنبه',
    1: 'دوشنبه',
    2: 'سه‌شنبه',
    3: 'چهارشنبه',
    4: 'پنج‌شنبه',
    5: 'جمعه'
  };
  const EXAM_FALLBACK = [
    { name: 'آزمون آزمایشی', duration_minutes: 210 },
    { name: 'تحلیل آزمون', duration_minutes: 240 },
    { name: 'پیش آزمون و تحلیل آن', duration_minutes: 360 },
    { name: 'مرور و آمادگی آزمون', duration_minutes: 240 }
  ];

  const state = {
    loaded: false,
    loading: false,
    saving: false,
    reportId: null,
    studentId: null,
    start: null,
    end: null,
    examTemplates: EXAM_FALLBACK.slice(),
    eventTemplates: [],
    currentMajorCode: window.currentMajorCode || ''
  };

  window.planRuntimeState = state;

  function dayKey(value) {
    return String(value || '')
      .trim()
      .replace(/[\u200c\u200e\u200f\s]/g, '')
      .replace(/[يى]/g, 'ی')
      .replace(/ك/g, 'ک');
  }

  function normalizeDay(value) {
    const key = dayKey(value);
    return CANONICAL_DAYS.find(function (day) {
      return dayKey(day) === key;
    }) || null;
  }

  function englishDigits(value) {
    const source = String(value || '');
    const persian = '۰۱۲۳۴۵۶۷۸۹';
    const arabic = '٠١٢٣٤٥٦٧٨٩';
    return source.replace(/[۰-۹٠-٩]/g, function (digit) {
      const persianIndex = persian.indexOf(digit);
      if (persianIndex >= 0) {
        return String(persianIndex);
      }
      return String(arabic.indexOf(digit));
    });
  }

  function pad(value) {
    return String(value).padStart(2, '0');
  }

  function formatClock(totalMinutes) {
    let normalized = Math.round(totalMinutes) % (24 * 60);
    if (normalized < 0) {
      normalized += 24 * 60;
    }
    return pad(Math.floor(normalized / 60)) + ':' + pad(normalized % 60);
  }

  function parseClock(value) {
    if (!value) {
      return null;
    }
    const raw = String(value);
    if (raw.indexOf('T') >= 0) {
      const parsed = moment.parseZone(raw);
      if (!parsed.isValid()) {
        return null;
      }
      return parsed.hour() * 60 + parsed.minute();
    }
    const parts = raw.split(':');
    if (parts.length < 2) {
      return null;
    }
    const hours = Number(parts[0]);
    const minutes = Number(parts[1]);
    if (!Number.isFinite(hours) || !Number.isFinite(minutes)) {
      return null;
    }
    return hours * 60 + minutes;
  }

  function viewMinute(clockMinutes) {
    let result = clockMinutes - BASE_HOUR * 60;
    if (result < 0) {
      result += 24 * 60;
    }
    return result;
  }

  function timeToTop(value) {
    const clock = parseClock(value);
    if (clock === null) {
      return 0;
    }
    return Math.max(0, Math.min(viewMinute(clock), MINUTES_PER_DAY_VIEW)) * PIXELS_PER_MINUTE;
  }

  function durationBetween(startValue, endValue, explicitDuration) {
    const explicit = Number(explicitDuration);
    if (Number.isFinite(explicit) && explicit > 0) {
      return explicit;
    }
    const start = parseClock(startValue);
    const end = parseClock(endValue);
    if (start === null || end === null) {
      return DEFAULT_DURATION;
    }
    let duration = end - start;
    if (duration <= 0) {
      duration += 24 * 60;
    }
    return Math.max(GRID_MINUTES, Math.min(duration, MINUTES_PER_DAY_VIEW));
  }

  function snapPixels(value) {
    return Math.round(Number(value || 0) / GRID_PIXELS) * GRID_PIXELS;
  }

  function clampTop(value, height, containerHeight) {
    const maximum = Math.max(0, containerHeight - height);
    return Math.max(0, Math.min(snapPixels(value), maximum));
  }

  function taskTitle($task) {
    const $title = $task.find('.task-title').first();
    if ($title.is('input, textarea')) {
      return String($title.val() || '').trim();
    }
    return String($title.text() || '').trim();
  }

  function updateTimeLabel($task) {
    const top = Number.parseFloat($task.css('top')) || 0;
    const height = Number.parseFloat($task.css('height')) || GRID_PIXELS;
    const start = BASE_HOUR * 60 + Math.round(top / PIXELS_PER_MINUTE);
    const end = start + Math.round(height / PIXELS_PER_MINUTE);
    $task.find('.time-label').first().text(formatClock(start) + ' - ' + formatClock(end));
  }

  function hasOverlap($task, top, height, $container) {
    const candidateTop = Number.isFinite(top) ? top : (Number.parseFloat($task.css('top')) || 0);
    const candidateHeight = Number.isFinite(height) ? height : $task.outerHeight();
    const candidateBottom = candidateTop + candidateHeight;
    let overlap = false;

    ($container || $task.parent()).find('.calendar-task').not($task).each(function () {
      const $other = $(this);
      if (!$other.is(':visible')) {
        return;
      }
      const otherTop = Number.parseFloat($other.css('top')) || 0;
      const otherBottom = otherTop + $other.outerHeight();
      if (!(candidateBottom <= otherTop || candidateTop >= otherBottom)) {
        overlap = true;
        return false;
      }
    });
    return overlap;
  }

  function destroyTaskWidgets($task) {
    $task.find('select.select2-hidden-accessible').each(function () {
      try {
        $(this).select2('destroy');
      } catch (error) {
        console.warn('Could not destroy Select2 instance.', error);
      }
    });
    if ($task.hasClass('ui-draggable')) {
      $task.draggable('destroy');
    }
    if ($task.hasClass('ui-resizable')) {
      $task.resizable('destroy');
    }
  }

  function initCalendarTask($task) {
    if (!$task || !$task.length) {
      return;
    }

    if ($task.hasClass('ui-draggable')) {
      $task.draggable('destroy');
    }
    if ($task.hasClass('ui-resizable')) {
      $task.resizable('destroy');
    }

    $task.draggable({
      grid: [GRID_PIXELS, GRID_PIXELS],
      scroll: false,
      cancel: 'button, input, select, textarea, .select2-container',
      start: function () {
        const $current = $(this);
        $current.data('runtimeOriginalParent', $current.parent());
        $current.data('runtimeOriginalTop', Number.parseFloat($current.css('top')) || 0);
        $current.data('runtimeDropped', false);
      },
      drag: function (event, ui) {
        const $current = $(this);
        const containerHeight = $current.parent().innerHeight();
        ui.position.top = clampTop(ui.position.top, $current.outerHeight(), containerHeight);
        $current.css('top', ui.position.top);
        updateTimeLabel($current);
      },
      stop: function (event, ui) {
        const $current = $(this);
        if ($current.data('runtimeDropped')) {
          $current.removeData('runtimeDropped');
          return;
        }
        const $container = $current.parent();
        const top = clampTop(ui.position.top, $current.outerHeight(), $container.innerHeight());
        if (hasOverlap($current, top, $current.outerHeight(), $container)) {
          $current.css('top', $current.data('runtimeOriginalTop'));
        } else {
          $current.css('top', top);
        }
        updateTimeLabel($current);
      }
    }).resizable({
      handles: 's',
      grid: [GRID_PIXELS, GRID_PIXELS],
      minHeight: GRID_PIXELS,
      start: function () {
        const $current = $(this);
        $current.data('runtimeOriginalHeight', $current.outerHeight());
        const top = Number.parseFloat($current.css('top')) || 0;
        $current.resizable('option', 'maxHeight', Math.max(GRID_PIXELS, $current.parent().innerHeight() - top));
      },
      resize: function (event, ui) {
        ui.size.height = Math.max(GRID_PIXELS, snapPixels(ui.size.height));
        $(this).css('height', ui.size.height);
        updateTimeLabel($(this));
      },
      stop: function (event, ui) {
        const $current = $(this);
        const height = Math.max(GRID_PIXELS, snapPixels(ui.size.height));
        if (hasOverlap($current, Number.parseFloat($current.css('top')) || 0, height, $current.parent())) {
          $current.css('height', $current.data('runtimeOriginalHeight'));
        } else {
          $current.css('height', height);
        }
        updateTimeLabel($current);
      }
    });

    updateTimeLabel($task);
  }

  window.calculateTop = timeToTop;
  window.calculateHeight = function (startValue, endValue) {
    return durationBetween(startValue, endValue) * PIXELS_PER_MINUTE;
  };
  window.updateTimeLabel = updateTimeLabel;
  window.checkOverlap = function ($task) {
    return hasOverlap($task);
  };
  window.initCalendarTask = initCalendarTask;

  function createButton(className, label, title) {
    return $('<button type="button"></button>')
      .addClass(className)
      .attr('title', title || label)
      .text(label);
  }

  function addExamPattern($task, title) {
    if (!/آزمون|تحلیل آزمون/.test(title || '')) {
      return;
    }
    const patterns = ['exam-pattern-1', 'exam-pattern-2', 'exam-pattern-3'];
    const index = Math.abs(String(title).split('').reduce(function (total, character) {
      return total + character.charCodeAt(0);
    }, 0)) % patterns.length;
    $task.addClass(patterns[index]);
  }

  function addTestOptions($select, selected) {
    $select.append($('<option></option>').attr('value', '').text('-'));
    for (let value = 5; value <= 100; value += 5) {
      $select.append($('<option></option>').attr('value', value).text(value));
    }
    if (selected) {
      $select.val(String(selected));
    }
  }

  function initStudyControls($task, task) {
    const $chapter = $task.find('.task-chapter');
    const $extra = $task.find('.task-extra');
    const lessonId = $task.attr('data-lesson-id');
    const grade = $task.attr('data-grade');

    if (task.chapter_id && task.chapter_text) {
      $chapter.append(new Option(task.chapter_text, task.chapter_id, true, true));
    }
    addTestOptions($extra, task.optional_tests_count || task.extra || 0);

    if ($.fn.select2) {
      $chapter.select2({
        placeholder: 'شماره فصل',
        dropdownParent: $task,
        width: '100%',
        theme: 'bootstrap-5',
        allowClear: true,
        ajax: {
          url: '/get-chapters/',
          dataType: 'json',
          delay: 200,
          data: function (params) {
            return {
              lesson_id: lessonId,
              grade: grade,
              major_code: state.currentMajorCode,
              q: params.term || ''
            };
          },
          processResults: function (data) {
            return { results: Array.isArray(data) ? data : [] };
          }
        }
      });
      $extra.select2({
        placeholder: 'تعداد تست',
        dropdownParent: $task,
        width: '100%',
        theme: 'bootstrap-5',
        minimumResultsForSearch: Infinity
      });
    }
  }

  function buildCalendarTask(task) {
    const type = String(task.box_type || 'مطالعه');
    const title = String(task.title || task.lesson_name || type).trim();
    const duration = Math.max(GRID_MINUTES, Number(task.duration_minutes) || DEFAULT_DURATION);
    const $task = $('<div class="calendar-task"></div>')
      .attr('data-box-type', type)
      .attr('data-duration-minutes', duration)
      .css({
        top: Number(task.top || 0) + 'px',
        height: duration * PIXELS_PER_MINUTE + 'px',
        left: '5%'
      });

    if (task.lesson_id) {
      $task.attr('data-lesson-id', task.lesson_id);
    }
    if (task.lesson_name) {
      $task.attr('data-lesson-name', task.lesson_name);
    }
    if (task.grade) {
      $task.attr('data-grade', task.grade);
    }
    if (task.lesson_type) {
      $task.attr('data-lesson-type', task.lesson_type);
    }

    $task.append(createButton('remove-btn', '✖', 'حذف'));

    if (type === 'مطالعه') {
      $task.addClass('extended-task');
      $task.append(createButton('repeat-btn', 'تکرار', 'تکرار در روزهای دیگر'));
      $task.append($('<div class="task-title"></div>').text(title));
      const $info = $('<div class="task-info"></div>').css({
        display: 'flex',
        flexDirection: 'row',
        alignItems: 'center',
        maxWidth: '80%'
      });
      $info.append($('<select class="task-chapter p-1 text-sm leading-tight"></select>'));
      $info.append($('<select class="task-extra p-1 text-sm leading-tight"></select>'));
      $info.append($('<div class="hidden extra-info"></div>').text('تعداد تست: ' + (task.optional_tests_count || 0)));
      $info.append($('<div class="time-label"></div>'));
      $task.append($info);
      initStudyControls($task, task);
    } else {
      if (type === 'ایونت') {
        $task.addClass('event-task');
        $task.append(createButton('tick-btn', 'افزودن تکلیف', 'ایجاد تکلیف از ایونت'));
      } else if (type === 'شناور') {
        $task.addClass('floating');
      } else if (type === 'تکلیف') {
        $task.addClass('assignment-task');
      }
      $task.append(
        $('<input type="text" class="task-title task-inp editable">').val(title)
      );
      $task.append($('<div class="time-label"></div>'));
      addExamPattern($task, title);
    }

    if (task.lesson_name && window.subjectColors && window.subjectColors[task.lesson_name]) {
      $task.css('background-color', window.subjectColors[task.lesson_name]);
    }

    initCalendarTask($task);
    return $task;
  }

  function taskDataFromElement($task) {
    const top = Number.parseFloat($task.css('top')) || 0;
    const height = $task.outerHeight();
    const startMinutes = BASE_HOUR * 60 + Math.round(top / PIXELS_PER_MINUTE);
    const duration = Math.max(GRID_MINUTES, Math.round(height / PIXELS_PER_MINUTE));
    return {
      title: taskTitle($task),
      start: formatClock(startMinutes) + ':00',
      end: formatClock(startMinutes + duration) + ':00',
      box_type: $task.attr('data-box-type') || 'مطالعه',
      lesson_id: $task.attr('data-lesson-id') || null,
      lesson_type: $task.attr('data-lesson-type') || '',
      grade: $task.attr('data-grade') || null,
      chapter_id: $task.find('.task-chapter').val() || null,
      chapter_text: $task.find('.task-chapter option:selected').text() || '',
      optional_tests_count: Number($task.find('.task-extra').val()) || 0,
      duration_minutes: duration,
      top: top
    };
  }

  function initializePaletteDraggable($items) {
    $items.each(function () {
      const $item = $(this);
      if ($item.hasClass('ui-draggable')) {
        $item.draggable('destroy');
      }
      $item.draggable({
        helper: function () {
          return $(this).clone().css({ width: '120px' }).appendTo('body');
        },
        appendTo: 'body',
        cursorAt: { top: 0, left: 60 },
        revert: 'invalid',
        zIndex: 10000,
        start: function (event, ui) {
          ui.helper.css('width', '120px');
        }
      });
    });
  }

  function renderLessons(response) {
    state.currentMajorCode = response.major_code || '';
    window.currentMajorCode = state.currentMajorCode;

    const groups = [
      ['#specialized-task-list', response.specialized_lessons || [], 'تخصصی'],
      ['#general-task-list', response.general_lessons || [], 'عمومی']
    ];
    groups.forEach(function (group) {
      const $list = $(group[0]).empty();
      group[1].forEach(function (lesson) {
        $list.append(
          $('<div class="task plan-lesson-palette"></div>')
            .attr('data-lesson-id', lesson.id)
            .attr('data-lesson-name', lesson.name)
            .attr('data-grade', lesson.grade_id)
            .attr('data-lesson-type', group[2])
            .text(lesson.name + ' ' + lesson.grade)
        );
      });
    });
    initializePaletteDraggable($('.subjects-box .plan-lesson-palette'));
    $('.grade-filter').trigger('change');
  }

  function renderEventPalette(response) {
    if (response && Array.isArray(response.event_boxes) && response.event_boxes.length) {
      state.eventTemplates = response.event_boxes;
      const $list = $('.events-box .task-list').empty();
      response.event_boxes.forEach(function (box) {
        const $item = $('<div class="task plan-event-palette"></div>')
          .text(box.name)
          .attr('data-box-type', box.box_type)
          .attr('data-kind', box.kind)
          .attr('data-duration-minutes', box.duration_minutes || DEFAULT_DURATION);
        if (box.kind === 'floating') {
          $item.addClass('floating-box');
        }
        $list.append($item);
      });
    }
    if (response && Array.isArray(response.exam_boxes) && response.exam_boxes.length) {
      state.examTemplates = response.exam_boxes;
    }
    initializePaletteDraggable($('.events-box .task'));
  }

  function bindExamPalette() {
    $('#examWeekCheckbox').off('change').on('change.planRuntime', function () {
      const $list = $(this).closest('.events-box').find('.task-list');
      $list.find('.exam-task').remove();
      if (!this.checked) {
        return;
      }
      state.examTemplates.forEach(function (box) {
        $list.append(
          $('<div class="task exam-task"></div>')
            .text(box.name || box.title)
            .attr('data-duration-minutes', box.duration_minutes || Number(box.duration) * 60 || DEFAULT_DURATION)
        );
      });
      initializePaletteDraggable($list.find('.exam-task'));
    });
  }

  function restoreOriginalPosition($task) {
    const $originalParent = $task.data('runtimeOriginalParent');
    if ($originalParent && $originalParent.length) {
      $task.appendTo($originalParent);
    }
    $task.css({ top: $task.data('runtimeOriginalTop') || 0, left: '5%' });
    updateTimeLabel($task);
  }

  function initializeDroppables() {
    $('.task-container').each(function () {
      const $container = $(this);
      if ($container.hasClass('ui-droppable')) {
        $container.droppable('destroy');
      }
      $container.droppable({
        accept: '.task, .calendar-task, .other-plan-task',
        tolerance: 'pointer',
        drop: function (event, ui) {
          if (window.readOnlyMode || !state.loaded) {
            return;
          }
          const $target = $(this);
          const $day = $target.closest('.day-column');
          if ($day.hasClass('disabled-day')) {
            if (ui.draggable.hasClass('calendar-task')) {
              restoreOriginalPosition(ui.draggable);
            }
            return;
          }

          const $source = ui.draggable;
          const targetOffset = $target.offset();
          const helperTop = ui.offset ? ui.offset.top : event.pageY;
          const desiredTop = clampTop(
            helperTop - targetOffset.top,
            $source.hasClass('calendar-task') ? $source.outerHeight() : DEFAULT_DURATION * PIXELS_PER_MINUTE,
            $target.innerHeight()
          );

          if ($source.hasClass('calendar-task')) {
            const height = $source.outerHeight();
            if (hasOverlap($source, desiredTop, height, $target)) {
              restoreOriginalPosition($source);
              $source.data('runtimeDropped', true);
              return;
            }
            $source.appendTo($target).css({ top: desiredTop, left: '5%' });
            $source.data('runtimeDropped', true);
            updateTimeLabel($source);
            return;
          }

          let task;
          let consumeSource = false;
          const sourceTitle = String($source.text() || '').trim();

          if ($source.hasClass('exam-task')) {
            task = {
              title: sourceTitle,
              box_type: 'ایونت',
              duration_minutes: Number($source.attr('data-duration-minutes')) || DEFAULT_DURATION,
              top: desiredTop
            };
            consumeSource = true;
          } else if ($source.hasClass('floating-box') || $source.attr('data-kind') === 'floating') {
            task = {
              title: sourceTitle || 'باکس شناور',
              box_type: 'شناور',
              duration_minutes: Number($source.attr('data-duration-minutes')) || DEFAULT_DURATION,
              top: desiredTop
            };
          } else if ($source.closest('.assignments-box').length) {
            task = {
              title: sourceTitle,
              box_type: 'تکلیف',
              duration_minutes: DEFAULT_DURATION,
              top: desiredTop
            };
            consumeSource = true;
          } else if ($source.closest('.events-box').length) {
            task = {
              title: sourceTitle === 'ایونت' ? '' : sourceTitle,
              box_type: 'ایونت',
              duration_minutes: Number($source.attr('data-duration-minutes')) || DEFAULT_DURATION,
              top: desiredTop
            };
          } else {
            task = {
              title: sourceTitle,
              box_type: 'مطالعه',
              lesson_id: $source.attr('data-lesson-id'),
              lesson_name: $source.attr('data-lesson-name'),
              lesson_type: $source.attr('data-lesson-type') || ($source.closest('#specialized-task-list').length ? 'تخصصی' : 'عمومی'),
              grade: $source.attr('data-grade'),
              duration_minutes: DEFAULT_DURATION,
              top: desiredTop
            };
          }

          const $newTask = buildCalendarTask(task);
          const newHeight = $newTask.outerHeight();
          const correctedTop = clampTop(desiredTop, newHeight, $target.innerHeight());
          $newTask.css('top', correctedTop);
          if (hasOverlap($newTask, correctedTop, newHeight, $target)) {
            destroyTaskWidgets($newTask);
            $newTask.remove();
            return;
          }
          $target.append($newTask);
          initCalendarTask($newTask);
          if (consumeSource) {
            $source.remove();
          }
        }
      });
    });
  }

  function resetCalendar() {
    $('.day-column').each(function () {
      const $day = $(this);
      $day.removeClass('disabled-day');
      $day.find('.disable-day-checkbox, .remove-events-checkbox').prop('checked', false);
      $day.removeData('runtimeCachedTasks runtimeCachedEvents cachedTasks cachedEvents');
      $day.find('.task-container').empty();
    });
    $('#important-events').val('');
  }

  function reorderCalendar(start) {
    const columns = {};
    $('.calendar .day-column').each(function () {
      const canonical = normalizeDay($(this).attr('data-day'));
      if (canonical) {
        columns[canonical] = $(this);
      }
    });

    const $calendar = $('.calendar').empty();
    for (let index = 0; index < 7; index += 1) {
      const date = start.clone().add(index, 'days');
      const dayName = JS_DAY_TO_PERSIAN[date.day()];
      const $column = columns[dayName];
      if (!$column) {
        continue;
      }
      $column.attr('data-day', dayName).attr('data-date', date.format('YYYY-MM-DD'));
      $column.find('h4').first().text(dayName + ' - ' + date.format('jD jMMMM'));
      $calendar.append($column);
    }
  }

  function renderTask(task) {
    const dayName = normalizeDay(task.day_of_week);
    if (!dayName) {
      return;
    }
    const $container = $('.day-column').filter(function () {
      return normalizeDay($(this).attr('data-day')) === dayName;
    }).find('.task-container');
    if (!$container.length) {
      return;
    }

    const top = timeToTop(task.start_time || task.start);
    const duration = durationBetween(task.start_time || task.start, task.end_time || task.end, task.duration_minutes);
    const $task = buildCalendarTask(Object.assign({}, task, { top: top, duration_minutes: duration }));
    const correctedTop = clampTop(top, $task.outerHeight(), $container.innerHeight());
    $task.css('top', correctedTop);
    $container.append($task);
    initCalendarTask($task);
  }

  function applyDisabledDays(days) {
    (days || []).forEach(function (day) {
      const canonical = normalizeDay(day);
      if (!canonical) {
        return;
      }
      const $column = $('.day-column').filter(function () {
        return normalizeDay($(this).attr('data-day')) === canonical;
      });
      $column.find('.disable-day-checkbox').prop('checked', true).trigger('change');
    });
  }

  function ajaxJson(options) {
    return new Promise(function (resolve, reject) {
      $.ajax(options).done(resolve).fail(function (xhr, status, error) {
        const response = xhr.responseJSON || {};
        reject(new Error(response.message || response.detail || error || status || 'خطای ارتباط با سرور'));
      });
    });
  }

  async function loadLessons(studentId) {
    const response = await ajaxJson({
      url: '/get-lessons-for-student/',
      method: 'GET',
      dataType: 'json',
      data: { student_id: studentId }
    });
    renderLessons(response);
  }

  async function loadWeek() {
    if (state.loading) {
      return;
    }
    const rawDate = englishDigits($('#weekSelector').val());
    const studentId = $('#student-select').val();
    if (!rawDate || !studentId) {
      window.alert('لطفاً تاریخ و دانش‌آموز را انتخاب کنید.');
      return;
    }

    const selected = moment(rawDate, 'jYYYY-jMM-jDD', true);
    if (!selected.isValid()) {
      window.alert('تاریخ انتخاب‌شده معتبر نیست.');
      return;
    }

    state.loading = true;
    $('#loadWeek').prop('disabled', true).text('در حال بارگذاری...');
    try {
      const check = await ajaxJson({
        url: '/check-weekly-report/',
        method: 'GET',
        dataType: 'json',
        data: {
          selected_date: selected.format('YYYY-MM-DD'),
          student_id: studentId
        }
      });

      if (check.exists === 'future') {
        window.alert('یک برنامه آینده از تاریخ ' + check.week_start + ' وجود دارد.');
        return;
      }

      const start = check.exists === 'current'
        ? moment(check.week_start, 'YYYY-MM-DD')
        : selected.clone().startOf('day');
      const end = check.exists === 'current'
        ? moment(check.week_end, 'YYYY-MM-DD')
        : start.clone().add(6, 'days');

      state.studentId = String(studentId);
      state.start = start.clone();
      state.end = end.clone();
      state.reportId = check.report_id || null;
      state.loaded = true;
      window.readOnlyMode = false;

      resetCalendar();
      reorderCalendar(start);
      initializeDroppables();
      await loadLessons(studentId);

      const report = await ajaxJson({
        url: '/get-weekly-report-details/',
        method: 'GET',
        dataType: 'json',
        data: {
          week_start: start.format('YYYY-MM-DD'),
          student_id: studentId
        }
      });

      state.reportId = report.report_id || null;
      $('#important-events').val(report.important_events || '');
      (report.tasks || []).forEach(renderTask);
      applyDisabledDays(report.disabled_days || []);

      if (!report.tasks || !report.tasks.length) {
        const defaults = await ajaxJson({
          url: '/get_default_events/',
          method: 'GET',
          dataType: 'json',
          data: { student_id: studentId }
        });
        (defaults || []).forEach(function (event) {
          renderTask(Object.assign({}, event, {
            title: event.name,
            box_type: 'ایونت',
            duration_minutes: durationBetween(event.start_time, event.end_time)
          }));
        });
      }

      initializeDroppables();
      $('#pageOverlay').remove();
      $('.save-btn').prop('disabled', false).text('ذخیره');
    } catch (error) {
      console.error(error);
      state.loaded = false;
      window.alert(error.message || 'بارگذاری برنامه انجام نشد.');
    } finally {
      state.loading = false;
      $('#loadWeek').prop('disabled', false).text('بارگذاری هفته');
    }
  }

  function collectPlanPayload() {
    if (!state.loaded || !state.start || !state.end || !state.studentId) {
      throw new Error('ابتدا هفته و دانش‌آموز را بارگذاری کنید.');
    }
    const days = [];
    $('.calendar .day-column').each(function () {
      const $column = $(this);
      const dayName = normalizeDay($column.attr('data-day'));
      if (!dayName) {
        return;
      }
      const tasks = [];
      $column.find('.task-container > .calendar-task').each(function () {
        tasks.push(taskDataFromElement($(this)));
      });
      days.push({
        day: dayName,
        disabled: $column.hasClass('disabled-day') || $column.find('.disable-day-checkbox').is(':checked'),
        tasks: tasks
      });
    });
    return {
      student_id: state.studentId,
      week_start: state.start.format('YYYY-MM-DD'),
      week_end: state.end.format('YYYY-MM-DD'),
      important_events: $('#important-events').val() || '',
      days: days
    };
  }

  function csrfToken() {
    const cookie = document.cookie.split(';').map(function (part) {
      return part.trim();
    }).find(function (part) {
      return part.indexOf('csrftoken=') === 0;
    });
    if (cookie) {
      return decodeURIComponent(cookie.substring('csrftoken='.length));
    }
    return $('input[name="csrfmiddlewaretoken"]').first().val() || '';
  }

  async function saveWeek() {
    if (state.saving) {
      return;
    }
    let payload;
    try {
      payload = collectPlanPayload();
    } catch (error) {
      window.alert(error.message);
      return;
    }

    state.saving = true;
    $('.save-btn').prop('disabled', true).text('در حال ذخیره...');
    try {
      const response = await ajaxJson({
        url: '/save-weekly-report/',
        method: 'POST',
        dataType: 'json',
        contentType: 'application/json; charset=utf-8',
        headers: { 'X-CSRFToken': csrfToken() },
        data: JSON.stringify(payload)
      });
      state.reportId = response.report_id || state.reportId;
      window.alert('برنامه با موفقیت ذخیره شد.');
    } catch (error) {
      console.error(error);
      window.alert(error.message || 'ذخیره برنامه انجام نشد.');
    } finally {
      state.saving = false;
      $('.save-btn').prop('disabled', false).text('ذخیره');
    }
  }

  function bindCalendarActions() {
    $(document)
      .off('click', '.remove-btn')
      .on('click.planRuntime', '.remove-btn', function (event) {
        event.preventDefault();
        event.stopPropagation();
        const $task = $(this).closest('.calendar-task');
        destroyTaskWidgets($task);
        $task.remove();
      })
      .off('click', '.tick-btn')
      .on('click.planRuntime', '.tick-btn', function (event) {
        event.preventDefault();
        event.stopPropagation();
        const title = taskTitle($(this).closest('.calendar-task'));
        if (!title) {
          window.alert('ابتدا عنوان ایونت را وارد کنید.');
          return;
        }
        const $assignment = $('<div class="task plan-assignment-palette"></div>')
          .text('آمادگی و تکلیف ' + title);
        $('.assignments-box .task-list').append($assignment);
        initializePaletteDraggable($assignment);
      })
      .off('click', '.repeat-btn')
      .on('click.planRuntime', '.repeat-btn', function (event) {
        event.preventDefault();
        event.stopPropagation();
        const $source = $(this).closest('.calendar-task');
        const data = taskDataFromElement($source);
        const top = Number.parseFloat($source.css('top')) || 0;
        const height = $source.outerHeight();
        $('.day-column').each(function () {
          const $column = $(this);
          const $target = $column.find('.task-container');
          if ($target[0] === $source.parent()[0] || $column.hasClass('disabled-day')) {
            return;
          }
          if (hasOverlap($(), top, height, $target)) {
            return;
          }
          const $clone = buildCalendarTask(Object.assign({}, data, { top: top }));
          $clone.find('.repeat-btn').remove();
          $target.append($clone);
          initCalendarTask($clone);
        });
      })
      .off('change', '.disable-day-checkbox')
      .on('change.planRuntime', '.disable-day-checkbox', function () {
        const $column = $(this).closest('.day-column');
        const $container = $column.find('.task-container');
        if (this.checked) {
          $column.data('runtimeCachedTasks', $container.children().detach());
          $column.addClass('disabled-day');
        } else {
          $column.removeClass('disabled-day');
          const tasks = $column.data('runtimeCachedTasks');
          if (tasks && tasks.length) {
            $container.append(tasks);
            tasks.each(function () {
              initCalendarTask($(this));
            });
          }
          $column.removeData('runtimeCachedTasks');
        }
      })
      .off('change', '.remove-events-checkbox')
      .on('change.planRuntime', '.remove-events-checkbox', function () {
        const $column = $(this).closest('.day-column');
        const $container = $column.find('.task-container');
        if (this.checked) {
          $column.data(
            'runtimeCachedEvents',
            $container.find('.calendar-task[data-box-type="ایونت"]').detach()
          );
        } else {
          const events = $column.data('runtimeCachedEvents');
          if (events && events.length) {
            $container.append(events);
            events.each(function () {
              initCalendarTask($(this));
            });
          }
          $column.removeData('runtimeCachedEvents');
        }
      })
      .off('change.planRuntime', '.task-extra')
      .on('change.planRuntime', '.task-extra', function () {
        $(this).siblings('.extra-info').text('تعداد تست: ' + ($(this).val() || 0));
      });
  }

  function removeLegacyCoreHandlers() {
    $('#loadWeek').off('click').on('click.planRuntime', function (event) {
      event.preventDefault();
      loadWeek();
    });
    $('.save-btn').off('click').on('click.planRuntime', function (event) {
      event.preventDefault();
      saveWeek();
    });
    $('#examWeekCheckbox').off('change');
    bindExamPalette();
    bindCalendarActions();
  }

  async function initialize() {
    removeLegacyCoreHandlers();
    initializePaletteDraggable($('.subjects-box .task, .events-box .task, .assignments-box .task'));
    initializeDroppables();

    try {
      const palette = await ajaxJson({
        url: '/get_default_boxes/',
        method: 'GET',
        dataType: 'json'
      });
      renderEventPalette(palette);
      bindExamPalette();
    } catch (error) {
      console.warn('Default palette API unavailable; using template palette.', error);
    }

    window.dispatchEvent(new CustomEvent('plan:runtime-ready'));
  }

  $(initialize);
})(window, document, window.jQuery);

(function (window, document, $) {
  'use strict';

  if (!$ || !$.ui) {
    return;
  }

  const PIXELS_PER_MINUTE = 35 / 60;
  const GRID_PIXELS = 8.75;
  const DEFAULT_DURATION = 90;

  function snap(value) {
    return Math.round(Number(value || 0) / GRID_PIXELS) * GRID_PIXELS;
  }

  function addTestOptions($select, selectedValue) {
    $select.append($('<option></option>').attr('value', '').text('-'));
    for (let value = 5; value <= 100; value += 5) {
      $select.append($('<option></option>').attr('value', value).text(value));
    }
    if (selectedValue) {
      $select.val(String(selectedValue));
    }
  }

  function overlaps($container, top, height) {
    const bottom = top + height;
    let result = false;
    $container.children('.calendar-task:visible').each(function () {
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

  function initChapterSelect($task, taskData) {
    const $chapter = $task.find('.task-chapter');
    if (taskData.chapter_id && taskData.chapter_text) {
      $chapter.append(
        new Option(
          taskData.chapter_text,
          taskData.chapter_id,
          true,
          true
        )
      );
    }

    if (!$.fn.select2) {
      return;
    }

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
            lesson_id: taskData.lesson_id,
            grade: taskData.grade_id || taskData.grade,
            major_code: window.currentMajorCode || '',
            q: params.term || ''
          };
        },
        processResults: function (data) {
          return { results: Array.isArray(data) ? data : [] };
        }
      }
    });
  }

  function initTestSelect($task, taskData) {
    const $extra = $task.find('.task-extra');
    addTestOptions($extra, taskData.optional_tests_count || 0);
    if ($.fn.select2) {
      $extra.select2({
        placeholder: 'تعداد تست',
        dropdownParent: $task,
        width: '100%',
        theme: 'bootstrap-5',
        minimumResultsForSearch: Infinity
      });
    }
  }

  function buildOtherPlanTask($source, $container, dropTop) {
    const taskData = $source.data() || {};
    const lessonId = taskData.lesson_id || $source.attr('data-lesson-id');
    if (!lessonId) {
      window.alert('اطلاعات درس این باکس کامل نیست.');
      return;
    }

    const lessonName = String(
      taskData.lesson_name || $source.attr('data-lesson-name') || 'مطالعه'
    ).trim();
    const duration = Math.max(
      15,
      Number(taskData.duration_minutes) || DEFAULT_DURATION
    );
    const height = duration * PIXELS_PER_MINUTE;
    const maximumTop = Math.max(0, $container.innerHeight() - height);
    const top = Math.max(0, Math.min(snap(dropTop), maximumTop));

    if (overlaps($container, top, height)) {
      window.alert('این بازه زمانی با یک باکس دیگر تداخل دارد.');
      return;
    }

    const $task = $('<div class="calendar-task extended-task"></div>')
      .attr('data-box-type', 'مطالعه')
      .attr('data-lesson-id', lessonId)
      .attr('data-lesson-name', lessonName)
      .attr(
        'data-lesson-type',
        taskData.lesson_type || $source.attr('data-lesson-type') || 'عمومی'
      )
      .attr(
        'data-grade',
        taskData.grade_id || taskData.grade || $source.attr('data-grade') || ''
      )
      .css({
        top: top + 'px',
        height: height + 'px',
        left: '5%'
      });

    $task.append(
      $('<button type="button" class="remove-btn" title="حذف">✖</button>')
    );
    $task.append(
      $('<button type="button" class="repeat-btn" title="تکرار شونده">تکرار</button>')
    );
    $task.append($('<div class="task-title"></div>').text(lessonName));

    const $info = $('<div class="task-info"></div>').css({
      display: 'flex',
      flexDirection: 'row',
      alignItems: 'center',
      maxWidth: '80%'
    });
    $info.append(
      $('<select class="task-chapter p-1 text-sm leading-tight"></select>')
    );
    $info.append(
      $('<select class="task-extra p-1 text-sm leading-tight"></select>')
    );
    $info.append(
      $('<div class="hidden extra-info"></div>').text(
        'تعداد تست: ' + (taskData.optional_tests_count || 0)
      )
    );
    $info.append($('<div class="time-label"></div>'));
    $task.append($info);

    if (window.subjectColors && window.subjectColors[lessonName]) {
      $task.css('background-color', window.subjectColors[lessonName]);
    }

    $container.append($task);
    initChapterSelect($task, taskData);
    initTestSelect($task, taskData);

    if (typeof window.initCalendarTask === 'function') {
      window.initCalendarTask($task);
    }
    if (typeof window.updateTimeLabel === 'function') {
      window.updateTimeLabel($task);
    }
    if (typeof window.setupEditableSelects === 'function') {
      window.setupEditableSelects($task, 1);
    }
  }

  function droppableInstance($container) {
    // jQuery UI temporarily removes the widget instance while the core runtime
    // rebuilds a week. Reading the widget through `.droppable('option', ...)`
    // during that tiny window throws an uncaught error even when the CSS class
    // has not yet been removed. Read the instance directly instead.
    return (
      $container.data('ui-droppable') ||
      $container.data('uiDroppable') ||
      null
    );
  }

  function wrapDroppable($container) {
    const instance = droppableInstance($container);
    if (!instance || !instance.options) {
      return;
    }

    const currentDrop = instance.options.drop;
    if (!currentDrop || currentDrop.planSecondaryWrapped) {
      return;
    }

    const wrapped = function (event, ui) {
      const $source = ui && ui.draggable ? $(ui.draggable) : $();
      if (!$source.hasClass('other-plan-task')) {
        return currentDrop.call(this, event, ui);
      }

      const $target = $(this);
      const $day = $target.closest('.day-column');
      if ($day.hasClass('disabled-day')) {
        return;
      }
      const offset = $target.offset();
      const sourceTop = ui.offset ? ui.offset.top : event.pageY;
      buildOtherPlanTask($source, $target, sourceTop - offset.top);
    };
    wrapped.planSecondaryWrapped = true;
    wrapped.planSecondaryOriginal = currentDrop;
    instance.options.drop = wrapped;
  }

  function synchronizeDroppables() {
    $('.task-container').each(function () {
      wrapDroppable($(this));
    });
  }

  function exposeOtherPlanData() {
    $('#otherStudentTasks .other-plan-task').each(function () {
      const $task = $(this);
      const data = $task.data() || {};
      if (data.lesson_id) $task.attr('data-lesson-id', data.lesson_id);
      if (data.lesson_name) $task.attr('data-lesson-name', data.lesson_name);
      if (data.lesson_type) $task.attr('data-lesson-type', data.lesson_type);
      if (data.grade_id || data.grade) {
        $task.attr('data-grade', data.grade_id || data.grade);
      }
      if (data.duration_minutes) {
        $task.attr('data-duration-minutes', data.duration_minutes);
      }
    });
  }

  function initialize() {
    // Remove the legacy delegated drop handler. The wrapped jQuery UI callback
    // below is the only owner of drops from the other-student tab, preventing
    // duplicate calendar boxes.
    $(document).off('drop', '.task-container');

    const observer = new MutationObserver(function () {
      exposeOtherPlanData();
      synchronizeDroppables();
    });
    const otherTasks = document.getElementById('otherStudentTasks');
    if (otherTasks) {
      observer.observe(otherTasks, { childList: true, subtree: true });
    }

    synchronizeDroppables();
    exposeOtherPlanData();
    window.setInterval(synchronizeDroppables, 250);
    window.dispatchEvent(new CustomEvent('plan:secondary-ready'));
  }

  $(initialize);
})(window, document, window.jQuery);

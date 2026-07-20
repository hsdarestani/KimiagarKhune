(function ($) {
  'use strict';

  if (!$) {
    return;
  }

  const fallbackExamBoxes = [
    { name: 'آزمون آزمایشی', duration_minutes: 210 },
    { name: 'تحلیل آزمون', duration_minutes: 240 },
    { name: 'پیش آزمون و تحلیل آن', duration_minutes: 360 },
    { name: 'مرور و آمادگی آزمون', duration_minutes: 240 }
  ];

  function makePaletteItemsDraggable($items) {
    $items.draggable({
      helper: function () {
        return $(this).clone().css({ width: '100px' });
      },
      revert: 'invalid',
      zIndex: 100,
      cursorAt: { top: 0, left: 50 },
      start: function (event, ui) {
        ui.helper.css('width', '100px');
        $(this).data('originalElement', $(this));
      }
    });
  }

  function renderEventPalette(eventBoxes) {
    const $taskList = $('.events-box .task-list');
    if (!$taskList.length || !eventBoxes.length) {
      return;
    }

    $taskList.empty();
    eventBoxes.forEach(function (box) {
      const $item = $('<div class="task"></div>')
        .text(box.name)
        .attr('data-box-template-id', box.id)
        .attr('data-duration-minutes', box.duration_minutes || 90);

      if (box.kind === 'floating') {
        $item.addClass('floating-box');
      }
      $taskList.append($item);
    });
    makePaletteItemsDraggable($taskList.find('.task'));
  }

  function bindExamWeekPalette(examBoxes) {
    const boxes = examBoxes.length ? examBoxes : fallbackExamBoxes;
    const $checkbox = $('#examWeekCheckbox');
    if (!$checkbox.length) {
      return;
    }

    // Replace the old hard-coded handler with the database-backed palette.
    $checkbox.off('change');
    $checkbox.on('change.planDefaults', function () {
      const $taskList = $(this).closest('.events-box').find('.task-list');
      $taskList.find('.exam-task').remove();

      if (!this.checked) {
        return;
      }

      boxes.forEach(function (box) {
        const $item = $('<div class="task exam-task"></div>')
          .text(box.name)
          .attr('data-box-template-id', box.id || '')
          .attr('data-duration-minutes', box.duration_minutes || 90);
        $taskList.append($item);
        makePaletteItemsDraggable($item);
      });
    });
  }

  function initializeLoadedDefaultEvents() {
    $('.task-container .calendar-task').each(function () {
      const $task = $(this);
      if ($task.attr('data-box-type')) {
        return;
      }

      $task
        .attr('data-box-type', 'ایونت')
        .addClass('event-task');

      if (typeof window.initCalendarTask === 'function') {
        window.initCalendarTask($task);
      }
      if (typeof window.updateTimeLabel === 'function') {
        window.updateTimeLabel($task);
      }
    });
  }

  $(function () {
    $.getJSON('/get_default_boxes/')
      .done(function (response) {
        renderEventPalette(response.event_boxes || []);
        bindExamWeekPalette(response.exam_boxes || []);
      })
      .fail(function () {
        bindExamWeekPalette(fallbackExamBoxes);
      });
  });

  // The legacy page creates default-event DOM nodes after this AJAX request.
  // Add the missing type and drag/resize behaviour without rewriting the page.
  $(document).ajaxComplete(function (event, xhr, settings) {
    if (!settings.url || settings.url.indexOf('/get_default_events/') === -1) {
      return;
    }
    window.setTimeout(initializeLoadedDefaultEvents, 0);
  });
})(window.jQuery);

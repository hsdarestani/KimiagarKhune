(function (window, document, $) {
  'use strict';
  if (!$) return;

  var DAYS = ['دهم', 'یازدهم', 'دوازدهم'];
  var MAX_ITEMS = 12;

  function itemsFor($task) {
    try {
      var items = JSON.parse($task.attr('data-study-items') || '[]');
      return Array.isArray(items) ? items : [];
    } catch (_error) {
      return [];
    }
  }

  function gradeName(id) {
    var $label = $('.grade-filter[value="' + String(id || '') + '"]').first().closest('label');
    var text = $label.text().trim();
    return DAYS.find(function (day) { return text.indexOf(day) >= 0; }) || text || '';
  }

  function lessonOptions() {
    var seen = {};
    return $('.subjects-box .task[data-lesson-id]').map(function () {
      var $lesson = $(this);
      var id = String($lesson.attr('data-lesson-id') || '');
      if (!id || seen[id]) return null;
      seen[id] = true;
      return {
        lesson_id: id,
        lesson_name: $lesson.attr('data-lesson-name') || $lesson.text().trim(),
        grade_id: $lesson.attr('data-grade') || '',
        grade: gradeName($lesson.attr('data-grade'))
      };
    }).get();
  }

  function taskCaption($task) {
    var mode = $task.attr('data-study-mode') === 'test' ? 'test' : 'study';
    var count = Number($task.find('select.task-extra').first().val()) || 0;
    var chapter = $task.find('select.task-chapter option:selected').first().text().trim();
    if (/^(شماره فصل|-)$/.test(chapter)) chapter = '';
    var names = [];
    if (chapter) names.push(chapter);
    itemsFor($task).forEach(function (item) {
      names.push((item.lesson_name || '') +
        (item.grade ? ' ' + item.grade : '') +
        (item.chapter_text ? ' / ' + item.chapter_text : ''));
    });
    var target = names.length ? names.join('، ') : 'فصل موردنظر';
    if (mode === 'test') {
      return count + ' تست تستی ' + target;
    }
    return 'خواندن ' + target + (count ? ' + ' + count + ' تست آموزشی' : '');
  }

  function updateControls($task) {
    var mode = $task.attr('data-study-mode') === 'test' ? 'test' : 'study';
    $task.find('.plan-mode-toggle').text(mode === 'test' ? 'تست تستی ✓' : 'مطالعه + تست');
    $task.find('.plan-multi-edit').text('درس / فصل بیشتر' +
      (itemsFor($task).length ? ' (' + itemsFor($task).length + ')' : ''));
    $task.find('.plan-study-caption').text(taskCaption($task));
  }

  function decorate($task) {
    if (!$task.length || $task.attr('data-box-type') !== 'مطالعه') return;
    if (!$task.attr('data-study-mode')) $task.attr('data-study-mode', 'study');
    if (!$task.attr('data-study-items')) $task.attr('data-study-items', '[]');
    if (!$task.children('.plan-study-tools').length) {
      var $tools = $('<div class="plan-study-tools"></div>');
      $tools.append($('<button type="button" class="plan-mode-toggle"></button>'));
      $tools.append($('<button type="button" class="plan-multi-edit"></button>'));
      $tools.append($('<div class="plan-study-caption"></div>'));
      $task.append($tools);
    }
    updateControls($task);
  }

  function decorateAll() {
    $('.calendar .calendar-task[data-box-type="مطالعه"]').each(function () {
      decorate($(this));
    });
  }

  function loadChapters($row, lesson, current) {
    var $chapter = $row.find('.plan-multi-chapter');
    $chapter.empty().append($('<option value="">بدون فصل مشخص</option>'));
    if (!lesson) return;
    $chapter.prop('disabled', true);
    $.ajax({
      url: '/get-chapters/',
      dataType: 'json',
      data: {
        lesson_id: lesson.lesson_id,
        grade: lesson.grade_id,
        major_code: window.currentMajorCode || ''
      }
    }).done(function (chapters) {
      (Array.isArray(chapters) ? chapters : []).forEach(function (chapter) {
        $chapter.append($('<option></option>').val(String(chapter.id)).text(chapter.text));
      });
      if (current && current.chapter_id) {
        if (!$chapter.find('option[value="' + String(current.chapter_id) + '"]').length) {
          $chapter.append($('<option></option>')
            .val(String(current.chapter_id)).text(current.chapter_text || String(current.chapter_id)));
        }
        $chapter.val(String(current.chapter_id));
      }
    }).fail(function () {
      if (current && current.chapter_id) {
        $chapter.append($('<option></option>')
          .val(String(current.chapter_id)).text(current.chapter_text || 'فصل انتخاب‌شده'));
        $chapter.val(String(current.chapter_id));
      }
      $row.find('.plan-multi-error').text('بارگذاری فصل‌ها ممکن نشد؛ دوباره تلاش کنید.');
    }).always(function () {
      $chapter.prop('disabled', false);
    });
  }

  function addRow($list, selected, options) {
    if ($list.children('.plan-multi-row').length >= MAX_ITEMS) return;
    var $row = $('<div class="plan-multi-row"></div>');
    var $lesson = $('<select class="plan-multi-lesson" aria-label="انتخاب درس"></select>')
      .append('<option value="">انتخاب درس</option>');
    options.forEach(function (entry) {
      $lesson.append($('<option></option>').val(entry.lesson_id)
        .text(entry.lesson_name + ' ' + entry.grade));
    });
    $row.append($lesson);
    $row.append('<select class="plan-multi-chapter" aria-label="انتخاب فصل"><option value="">بدون فصل مشخص</option></select>');
    $row.append('<button type="button" class="plan-multi-remove" aria-label="حذف درس">×</button>');
    $row.append('<small class="plan-multi-error"></small>');
    $list.append($row);
    $row.find('.plan-multi-remove').on('click', function () { $row.remove(); });
    $lesson.on('change', function () {
      $row.find('.plan-multi-error').empty();
      loadChapters($row, options.find(function (entry) {
        return entry.lesson_id === $lesson.val();
      }), null);
    });
    if (selected && selected.lesson_id) {
      $lesson.val(String(selected.lesson_id));
      loadChapters($row, options.find(function (entry) {
        return entry.lesson_id === $lesson.val();
      }), selected);
    }
  }

  function showEditor($task) {
    $('.plan-multi-backdrop').remove();
    var options = lessonOptions();
    if (!options.length) {
      window.alert('اول فهرست درس‌های دانش‌آموز را بارگذاری کنید.');
      return;
    }
    var $backdrop = $('<div class="plan-multi-backdrop" role="presentation"></div>');
    var $panel = $('<div class="plan-multi-panel" role="dialog" aria-modal="true" aria-label="چند درس یا فصل"></div>');
    $panel.append('<h3>چند درس یا فصل در یک باکس</h3>');
    $panel.append('<p>درس‌های اضافه را انتخاب کنید. زمان و تعداد تست برای کل این باکس مشترک است.</p>');
    var $list = $('<div class="plan-multi-list"></div>');
    $panel.append($list);
    var $actions = $('<div class="plan-multi-actions"></div>');
    var $add = $('<button type="button">+ افزودن درس یا فصل</button>');
    var $cancel = $('<button type="button">انصراف</button>');
    var $save = $('<button type="button" class="plan-multi-save">ثبت انتخاب‌ها</button>');
    $actions.append($add, $cancel, $save);
    $panel.append($actions);
    $backdrop.append($panel);
    $('body').append($backdrop);
    itemsFor($task).forEach(function (item) { addRow($list, item, options); });
    if (!$list.children().length) addRow($list, null, options);
    $add.on('click', function () { addRow($list, null, options); });
    function close() {
      $backdrop.remove();
      $(document).off('keydown.planMultiEditor');
    }
    $cancel.on('click', close);
    $backdrop.on('click', function (event) {
      if (event.target === $backdrop[0]) close();
    });
    $(document).on('keydown.planMultiEditor', function (event) {
      if (event.key === 'Escape') close();
    });
    $save.on('click', function () {
      var items = [];
      var invalid = false;
      $list.children('.plan-multi-row').each(function () {
        var $row = $(this);
        var id = String($row.find('.plan-multi-lesson').val() || '');
        if (!id) { invalid = true; return; }
        var entry = options.find(function (opt) { return opt.lesson_id === id; });
        if (!entry || $row.find('.plan-multi-chapter').prop('disabled')) {
          invalid = true; return;
        }
        var $chapter = $row.find('.plan-multi-chapter');
        var chapterId = $chapter.val() || null;
        items.push({
          lesson_id: entry.lesson_id,
          lesson_name: entry.lesson_name,
          grade: entry.grade,
          grade_id: entry.grade_id,
          chapter_id: chapterId,
          chapter_text: chapterId ? $chapter.find('option:selected').text() : ''
        });
      });
      if (invalid) {
        $panel.find('p').text('لطفاً درس هر ردیف را انتخاب کنید و منتظر بارگذاری فصل‌ها بمانید.');
        return;
      }
      $task.attr('data-study-items', JSON.stringify(items));
      updateControls($task);
      close();
    });
  }

  $(document).on('click.planStudyTools', '.calendar .calendar-task[data-box-type="مطالعه"]', function (event) {
    if ($(event.target).closest('button,select,input,textarea,.select2-container,.plan-study-tools').length) return;
    $('.calendar-task').not(this).removeClass('plan-study-tools-open');
    $(this).toggleClass('plan-study-tools-open');
  }).on('click.planStudyToolsOutside', function (event) {
    if (!$(event.target).closest('.calendar-task,.plan-multi-panel').length) {
      $('.calendar-task').removeClass('plan-study-tools-open');
    }
  });

  $(document)
    .on('click', '.calendar .plan-mode-toggle', function (event) {
      event.preventDefault();
      event.stopPropagation();
      var $task = $(this).closest('.calendar-task');
      $task.attr('data-study-mode', $task.attr('data-study-mode') === 'test' ? 'study' : 'test');
      updateControls($task);
    })
    .on('click', '.calendar .plan-multi-edit', function (event) {
      event.preventDefault();
      event.stopPropagation();
      showEditor($(this).closest('.calendar-task'));
    })
    .on('change', '.calendar .task-chapter, .calendar .task-extra', function () {
      updateControls($(this).closest('.calendar-task'));
    });

  $(function () {
    decorateAll();
    var calendar = document.querySelector('.calendar');
    if (calendar) {
      new MutationObserver(function (changes) {
        changes.forEach(function (change) {
          change.addedNodes.forEach(function (node) {
            if (node.nodeType !== 1) return;
            var $node = $(node);
            if ($node.hasClass('calendar-task')) decorate($node);
            $node.find('.calendar-task').each(function () { decorate($(this)); });
          });
        });
      }).observe(calendar, {childList: true, subtree: true});
    }
    window.planStudyOptions = {itemsFor: itemsFor, taskCaption: taskCaption, decorate: decorate};
  });
})(window, document, window.jQuery);

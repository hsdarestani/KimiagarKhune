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
    var mode = ['test', 'review'].includes($task.attr('data-study-mode')) ? $task.attr('data-study-mode') : 'study';
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
    if (mode === 'review') return 'مرور ' + target + (count ? ' + ' + count + ' تست مروری' : '');
    if (mode === 'test') {
      return (count ? count + ' ' : '') + 'تست تستی ' + target;
    }
    return 'خواندن ' + target + (count ? ' + ' + count + ' تست آموزشی' : '');
  }

  function updateControls($task) {
    var mode = ['test', 'review'].includes($task.attr('data-study-mode')) ? $task.attr('data-study-mode') : 'study';
    $task.find('.plan-mode-choice').each(function () {
      var selected = $(this).attr('data-mode') === mode;
      $(this).attr('aria-pressed', String(selected)).toggleClass('is-selected', selected);
    });
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
      $tools.append('<strong class="plan-mode-label">نوع فعالیت · میانبر روی باکس انتخاب‌شده</strong>');
      $tools.append('<button type="button" class="plan-mode-choice" data-mode="study">مطالعه + تست آموزشی <kbd>E</kbd></button>');
      $tools.append('<button type="button" class="plan-mode-choice" data-mode="test">فقط تست <kbd>S</kbd></button>');
      $tools.append('<button type="button" class="plan-mode-choice" data-mode="review">مرور <kbd>D</kbd></button>');
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
        student_id: (window.planRuntimeState || {}).studentId || $('#student-select').val(),
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

  async function showEditor($task) {
    $('.plan-multi-backdrop').remove();
    var studentId = String((window.planRuntimeState || {}).studentId || $('#student-select').val() || '');
    var options;
    try {
      var catalog = await $.getJSON('/get-lessons-for-student/', {student_id:studentId});
      if (studentId !== String((window.planRuntimeState || {}).studentId || $('#student-select').val() || '')) return;
      options = (catalog.specialized_lessons || []).concat(catalog.general_lessons || []).map(function (lesson) {
        return {lesson_id:String(lesson.id), lesson_name:lesson.name, grade_id:lesson.grade_id, grade:lesson.grade};
      });
    } catch (_error) {
      window.alert('بارگذاری فهرست کامل درس‌ها انجام نشد؛ دوباره تلاش کنید.');
      return;
    }
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

  function syncUsedSources() {
    var used = {};
    $('.calendar .calendar-task[data-source-detail-id]').each(function () {
      var id = String($(this).attr('data-source-detail-id') || '');
      if (id) used[id] = true;
    });
    $('#otherStudentTasks .other-plan-task').each(function () {
      var $source = $(this);
      var id = String($source.data('source_detail_id') ||
        $source.attr('data-source-detail-id') || '');
      var taken = !!(id && used[id]);
      $source.toggleClass('plan-used-other-task', taken).toggle(!taken);
    });
  }

  function setMode($task, mode) {
    if (window.readOnlyMode || !$task.length) return;
    $task.attr('data-study-mode', ['test', 'review'].includes(mode) ? mode : 'study');
    updateControls($task);
  }
  $(document).on('pointerdown.planStudySelection', '.calendar .calendar-task[data-box-type="مطالعه"]', function () {
    $('.calendar-task').not(this).removeClass('plan-study-selected');
    $(this).addClass('plan-study-selected');
  }).on('keydown.planStudyShortcuts', function (event) {
    var original = event.originalEvent || event;
    if (original.isComposing || event.ctrlKey || event.metaKey || event.altKey || event.shiftKey || original.repeat) return;
    if ($(event.target).closest('input,textarea,select,[contenteditable]:not([contenteditable="false"]),[role="textbox"],.select2-container').length) return;
    if ($('.plan-multi-backdrop').length || window.readOnlyMode) return;
    var modes = {KeyE:'study', KeyS:'test', KeyD:'review'};
    var mode = modes[original.code] || ({e:'study', s:'test', d:'review'})[String(event.key || '').toLowerCase()];
    var $selected = $('.calendar .calendar-task.plan-study-selected[data-box-type="مطالعه"]').first();
    if (!mode || !$selected.length) return;
    event.preventDefault();
    setMode($selected, mode);
    $selected.addClass('plan-study-tools-open');
  });

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
    .on('click', '.calendar .plan-mode-choice', function (event) {
      event.preventDefault();
      event.stopPropagation();
      var $task = $(this).closest('.calendar-task');
      setMode($task, $(this).attr('data-mode'));
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
    syncUsedSources();
    var otherList = document.getElementById('otherStudentTasks');
    if (otherList) {
      new MutationObserver(syncUsedSources).observe(otherList, {childList: true});
    }
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
        syncUsedSources();
      }).observe(calendar, {childList: true, subtree: true});
    }
    window.planStudyOptions = {itemsFor: itemsFor, taskCaption: taskCaption, decorate: decorate, syncUsedSources: syncUsedSources, refresh: updateControls};
  });
})(window, document, window.jQuery);

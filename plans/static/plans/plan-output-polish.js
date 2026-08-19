(function (window, document, $) {
  'use strict';

  if (!$) {
    return;
  }

  const VERSION = '2026.08.19.1';
  const EXPORT_HIDE_SELECTOR = [
    '.calendar-task .select2-container',
    '.calendar-task .ui-resizable-handle',
    '.calendar-task .plan-resize-handle',
    '.calendar-task select.task-chapter',
    '.calendar-task select.task-extra'
  ].join(',');

  function normalizeText(value) {
    return String(value || '')
      .trim()
      .replace(/[\u200c\u200e\u200f\s]+/g, '')
      .replace(/[يى]/g, 'ی')
      .replace(/ك/g, 'ک');
  }

  function selectedStudentName() {
    return String($('#student-select option:selected').text() || '')
      .replace(/\s+/g, ' ')
      .trim();
  }

  function safeFileStem(value) {
    const cleaned = String(value || '')
      .replace(/[\\/:*?"<>|]+/g, '-')
      .replace(/\s+/g, ' ')
      .replace(/[. ]+$/g, '')
      .trim();
    return cleaned || 'دانش‌آموز';
  }

  function studentPdfFileName(suffix) {
    const student = safeFileStem(selectedStudentName());
    const tail = String(suffix || '').trim();
    return tail ? student + '-' + tail + '.pdf' : student + '.pdf';
  }

  function escapeHtml(value) {
    return String(value || '')
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;')
      .replace(/'/g, '&#039;');
  }

  function rewritePdfMarkup(markup, filename, title) {
    if (typeof markup !== 'string') {
      return markup;
    }
    const fileLiteral = JSON.stringify(filename);
    let rewritten = markup.replace(
      /pdf\.save\((?:'[^']*'|"[^"]*")\);/,
      'pdf.save(' + fileLiteral + ');'
    );
    if (title) {
      rewritten = rewritten.replace(
        /<title>(?:خروجی هفته|خلاصه هفته)<\/title>/,
        '<title>' + escapeHtml(title) + '</title>'
      );
    }
    return rewritten;
  }

  function interceptNextPopupPdf(filename, title) {
    const originalOpen = window.open;
    if (typeof originalOpen !== 'function') {
      return function () {};
    }

    let restored = false;
    function restore() {
      if (restored) {
        return;
      }
      restored = true;
      if (window.open === wrappedOpen) {
        window.open = originalOpen;
      }
    }

    function wrappedOpen() {
      const popup = originalOpen.apply(window, arguments);
      if (!popup || !popup.document || typeof popup.document.write !== 'function') {
        return popup;
      }

      const originalWrite = popup.document.write.bind(popup.document);
      popup.document.write = function (markup) {
        return originalWrite(rewritePdfMarkup(markup, filename, title));
      };
      return popup;
    }

    window.open = wrappedOpen;
    window.setTimeout(restore, 0);
    return restore;
  }

  function taskTitle($task) {
    const $title = $task.find('.task-title').first();
    if ($title.is('input, textarea')) {
      return String($title.val() || '').trim();
    }
    return String($title.text() || '').trim();
  }

  function paletteLessonForTask($task) {
    const lessonId = String($task.attr('data-lesson-id') || '').trim();
    if (!lessonId) {
      return $();
    }
    return $('.subjects-box .task[data-lesson-id]').filter(function () {
      return String($(this).attr('data-lesson-id') || '') === lessonId;
    }).first();
  }

  function repairStudyTaskColor($task, preferredColor) {
    if (!$task || !$task.length || ($task.attr('data-box-type') || '') !== 'مطالعه') {
      return false;
    }

    const $palette = paletteLessonForTask($task);
    let lessonName = String($task.attr('data-lesson-name') || '').trim();
    if (!lessonName && $palette.length) {
      lessonName = String($palette.attr('data-lesson-name') || '').trim();
      if (lessonName) {
        $task.attr('data-lesson-name', lessonName);
      }
    }

    let color = String(preferredColor || '').trim();
    if (!color && lessonName && window.subjectColors && window.subjectColors[lessonName]) {
      color = window.subjectColors[lessonName];
    }
    if (!color && $palette.length && $palette[0]) {
      color = window.getComputedStyle($palette[0]).backgroundColor || '';
    }
    if (!color || color === 'rgba(0, 0, 0, 0)' || color === 'transparent') {
      return false;
    }

    $task.css('background-color', color);
    $task.attr('data-plan-study-color', color);
    return true;
  }

  function repairAllStudyTaskColors() {
    $('.calendar .calendar-task[data-box-type="مطالعه"]').each(function () {
      repairStudyTaskColor($(this));
    });
  }

  function preserveRepeatedStudyColor(button) {
    const $source = $(button).closest('.calendar-task');
    if (!$source.length || ($source.attr('data-box-type') || '') !== 'مطالعه') {
      return;
    }

    const lessonId = String($source.attr('data-lesson-id') || '').trim();
    const sourceColor = window.getComputedStyle($source[0]).backgroundColor || '';
    const sourceTitle = normalizeText(taskTitle($source));

    $('.calendar .calendar-task[data-box-type="مطالعه"]').each(function () {
      const $candidate = $(this);
      const sameLessonId = lessonId && String($candidate.attr('data-lesson-id') || '') === lessonId;
      const sameTitle = !lessonId && sourceTitle && normalizeText(taskTitle($candidate)) === sourceTitle;
      if (sameLessonId || sameTitle || this === $source[0]) {
        repairStudyTaskColor($candidate, sourceColor);
      }
    });
  }

  function styleAssignmentTitle($title) {
    $title
      .attr('data-plan-assignment-title', 'true')
      .css({
        width: 'calc(100% - 8px)',
        maxWidth: 'calc(100% - 8px)',
        height: 'calc(100% - 20px)',
        minHeight: '26px',
        margin: '2px 4px 0',
        padding: '2px 4px',
        border: '0',
        borderRadius: '5px',
        background: 'rgba(255,255,255,.30)',
        color: '#172033',
        fontSize: '9px',
        fontWeight: '800',
        lineHeight: '1.25',
        textAlign: 'right',
        whiteSpace: 'pre-wrap',
        overflowWrap: 'anywhere',
        wordBreak: 'break-word',
        resize: 'none',
        overflow: 'hidden',
        boxSizing: 'border-box'
      });
  }

  function upgradeAssignmentTask($task) {
    if (!$task || !$task.length) {
      return false;
    }
    const type = String($task.attr('data-box-type') || '');
    if (type !== 'تکلیف') {
      return false;
    }
    $task.addClass('assignment-task');

    let $title = $task.find('.task-title').first();
    if (!$title.length) {
      return false;
    }

    if ($title.is('input')) {
      const value = String($title.val() || '');
      const className = $title.attr('class') || 'task-title task-inp editable';
      const placeholder = $title.attr('placeholder') || 'عنوان تکلیف';
      const $textarea = $('<textarea rows="2"></textarea>')
        .attr('class', className)
        .attr('placeholder', placeholder)
        .attr('aria-label', 'عنوان تکلیف')
        .val(value)
        .text(value);
      $title.replaceWith($textarea);
      $title = $textarea;
    }

    styleAssignmentTitle($title);
    return true;
  }

  function upgradeAssignmentTitles(root) {
    const $root = root ? $(root) : $(document);
    let changed = 0;
    $root.find('.calendar-task[data-box-type="تکلیف"], .calendar-task.assignment-task').each(function () {
      if (upgradeAssignmentTask($(this))) {
        changed += 1;
      }
    });
    return changed;
  }

  function selectedChapterText($task) {
    const $select = $task.find('select.task-chapter').first();
    let value = String($select.find('option:selected').text() || '').trim();
    if (!value || value === '-' || /شماره فصل/.test(value)) {
      value = String($task.find('.chapter-display').first().text() || '').trim();
    }
    if (!value || value === '-' || /شماره فصل/.test(value)) {
      value = String($task.find('.select2-selection__rendered').first().attr('title') || '').trim();
    }
    return value && value !== '-' && !/شماره فصل/.test(value) ? value : '';
  }

  function selectedTestsText($task) {
    const raw = String($task.find('select.task-extra').first().val() || '').trim();
    if (raw && raw !== '0') {
      return raw + ' تست';
    }
    const display = String($task.find('.tests-display').first().text() || '').trim();
    return display && display !== '-' ? display : '';
  }

  function addExportStudyMirrors() {
    $('.calendar .calendar-task[data-box-type="مطالعه"]').each(function () {
      const $task = $(this);
      $task.children('.plan-export-study-meta').remove();
      const chapter = selectedChapterText($task);
      const tests = selectedTestsText($task);
      if (!chapter && !tests) {
        return;
      }
      const parts = [];
      if (chapter) {
        parts.push(chapter);
      }
      if (tests) {
        parts.push(tests);
      }
      const $meta = $('<div class="plan-export-study-meta"></div>')
        .text(parts.join(' | '))
        .css({
          position: 'absolute',
          right: '5px',
          left: '5px',
          bottom: '12px',
          overflow: 'hidden',
          color: '#263238',
          fontSize: '7px',
          fontWeight: '700',
          lineHeight: '1.2',
          textAlign: 'right',
          whiteSpace: 'normal'
        });
      $task.append($meta);
    });
  }

  function prepareExportUi() {
    const savedStyles = [];
    document.querySelectorAll(EXPORT_HIDE_SELECTOR).forEach(function (element) {
      savedStyles.push([element, element.getAttribute('style')]);
      element.style.setProperty('display', 'none', 'important');
      element.setAttribute('data-plan-export-hidden', 'true');
    });

    addExportStudyMirrors();
    upgradeAssignmentTitles(document);
    if (window.planPersistenceFixes && typeof window.planPersistenceFixes.synchronizeTitlesForExport === 'function') {
      window.planPersistenceFixes.synchronizeTitlesForExport();
    }

    if (document.body) {
      document.body.setAttribute('data-plan-export-polish-version', VERSION);
    }

    return function cleanupExportUi() {
      savedStyles.forEach(function (entry) {
        const element = entry[0];
        const style = entry[1];
        element.removeAttribute('data-plan-export-hidden');
        if (style === null) {
          element.removeAttribute('style');
        } else {
          element.setAttribute('style', style);
        }
      });
      $('.calendar .plan-export-study-meta').remove();
    };
  }

  function bindPdfExport(id, suffix) {
    const element = document.getElementById(id);
    if (!element || element.dataset.planOutputPolishBound) {
      return;
    }
    element.dataset.planOutputPolishBound = 'true';
    element.addEventListener('click', function () {
      const student = selectedStudentName();
      const cleanup = prepareExportUi();
      interceptNextPopupPdf(studentPdfFileName(suffix), student);
      window.setTimeout(cleanup, 0);
    }, true);
  }

  function bindRepeatColorRepair() {
    $(document)
      .off('click.planOutputPolishRepeat', '.repeat-btn')
      .on('click.planOutputPolishRepeat', '.repeat-btn', function () {
        // The canonical runtime registered its delegated handler before this file,
        // so its clones already exist by the time this handler runs.
        preserveRepeatedStudyColor(this);
      });
  }

  function observeCalendar() {
    const calendar = document.querySelector('.calendar');
    if (!calendar || calendar.dataset.planOutputPolishObserved) {
      return;
    }
    calendar.dataset.planOutputPolishObserved = 'true';
    const observer = new MutationObserver(function (mutations) {
      mutations.forEach(function (mutation) {
        mutation.addedNodes.forEach(function (node) {
          if (!node || node.nodeType !== 1) {
            return;
          }
          const $node = $(node);
          if ($node.hasClass('calendar-task')) {
            upgradeAssignmentTask($node);
            repairStudyTaskColor($node);
          }
          upgradeAssignmentTitles(node);
          $node.find('.calendar-task[data-box-type="مطالعه"]').each(function () {
            repairStudyTaskColor($(this));
          });
        });
      });
    });
    observer.observe(calendar, { childList: true, subtree: true });
  }

  function initialize() {
    upgradeAssignmentTitles(document);
    repairAllStudyTaskColors();
    bindRepeatColorRepair();
    bindPdfExport('download-week-output', '');
    bindPdfExport('download-week-summary', 'خلاصه');
    observeCalendar();

    window.planOutputPolish = {
      version: VERSION,
      studentPdfFileName: studentPdfFileName,
      rewritePdfMarkup: rewritePdfMarkup,
      prepareExportUi: prepareExportUi,
      upgradeAssignmentTitles: upgradeAssignmentTitles,
      repairStudyTaskColor: repairStudyTaskColor,
      preserveRepeatedStudyColor: preserveRepeatedStudyColor
    };

    if (document.body) {
      document.body.setAttribute('data-plan-output-polish-version', VERSION);
    }
    window.dispatchEvent(new CustomEvent('plan:output-polish-ready'));
  }

  $(initialize);
})(window, document, window.jQuery);

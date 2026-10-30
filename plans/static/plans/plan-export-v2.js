(function (window, document, $) {
  'use strict';
  if (!$) return;

  var DAY_NAMES = ['یک‌شنبه','دوشنبه','سه‌شنبه','چهارشنبه','پنج‌شنبه','جمعه','شنبه'];
  var PIXELS_PER_MINUTE = 35 / 60;
  var PER_DAY = 5;
  var DAYS_PER_PAGE = 4;

  function normalize(value) {
    return String(value || '').replace(/[\u200c\u200e\u200f\s]/g, '')
      .replace(/[يى]/g, 'ی').replace(/ك/g, 'ک');
  }
  function persianDigits(value) {
    return String(value).replace(/\d/g, function (d) { return '۰۱۲۳۴۵۶۷۸۹'[Number(d)]; });
  }
  function escapeHtml(value) {
    return String(value == null ? '' : value)
      .replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;')
      .replace(/"/g,'&quot;').replace(/'/g,'&#39;');
  }
  function selectedStart() {
    var state = window.planRuntimeState || {};
    if (state.loaded && state.start && state.start.isValid && state.start.isValid()) {
      return state.start.clone();
    }
    return null;
  }
  function studentName() {
    return String($('#student-select option:selected').text() || '').trim() || 'دانش‌آموز';
  }
  function dateText(start) {
    return persianDigits(start.format('jD jMMMM jYYYY'));
  }
  function fileName(start, suffix) {
    var name = studentName().replace(/[\\/:*?"<>|]+/g,'')
      .trim().replace(/\s+/g,'-');
    var stamp = persianDigits(start.format('jD-jMMMM-jYYYY')).replace(/\s+/g,'-');
    return name + '-' + stamp + (suffix ? '-' + suffix : '') + '.pdf';
  }
  function gradeName($task) {
    var lessonId = String($task.attr('data-lesson-id') || '');
    var $source = $('.subjects-box [data-lesson-id]').filter(function () {
      return String($(this).attr('data-lesson-id') || '') === lessonId;
    }).first();
    if ($source.length) {
      var title = $source.text().trim();
      var match = title.match(/(دهم|یازدهم|دوازدهم)/);
      if (match) return match[1];
    }
    var gradeId = String($task.attr('data-grade') || '');
    var label = $('.grade-filter[value="' + gradeId + '"]').first().closest('label').text().trim();
    return (label.match(/(دهم|یازدهم|دوازدهم)/) || [,''])[1];
  }
  function clock(minutes) {
    var h = Math.floor(minutes / 60) % 24;
    var m = Math.round(minutes % 60);
    return persianDigits(String(h).padStart(2,'0') + ':' + String(m).padStart(2,'0'));
  }
  function chapterName(text) {
    var cleaned = String(text || '').trim();
    if (!cleaned || /^(شماره فصل|-)$/.test(cleaned)) return '';
    cleaned = cleaned.replace(/^[۰-۹٠-٩0-9]+\s*[-.)ـ]\s*/, '');
    return cleaned.indexOf('فصل') === 0 ? cleaned : 'فصل ' + cleaned;
  }
  function studyItems($task) {
    try {
      var items = JSON.parse($task.attr('data-study-items') || '[]');
      return Array.isArray(items) ? items : [];
    } catch (_error) { return []; }
  }
  function taskTitle($task) {
    var $title = $task.find('.task-title').first();
    return String($title.is('input,textarea') ? $title.val() : $title.text()).trim();
  }
  function taskInfo(element) {
    var $task = $(element);
    var type = $task.attr('data-box-type') || '';
    var title = taskTitle($task);
    var top = parseFloat($task.css('top')) || 0;
    var height = $task.outerHeight() || 0;
    var from = 360 + Math.round(top / PIXELS_PER_MINUTE);
    var duration = Math.max(15, Math.round(height / PIXELS_PER_MINUTE));
    var tests = Number($task.find('select.task-extra').first().val()) || 0;
    var main = $task.attr('data-lesson-name') || title;
    var grade = gradeName($task);
    var nameWithGrade = main + (grade && main.indexOf(grade) < 0 ? ' ' + grade : '');
    var primaryChapter = chapterName($task.find('select.task-chapter option:selected').first().text());
    var topics = primaryChapter ? [primaryChapter] : [];
    var additional = studyItems($task);
    additional.forEach(function (item) {
      var lesson = (item.lesson_name || '') + (item.grade ? ' ' + item.grade : '');
      topics.push(lesson + (item.chapter_text ? ' / ' + chapterName(item.chapter_text) : ''));
    });
    if (!topics.length) topics.push(nameWithGrade);
    var target = topics.join(' و ');
    var mode = $task.attr('data-study-mode') === 'test' ? 'test' : 'study';
    var description = '';
    if (type === 'مطالعه') {
      description = mode === 'test'
        ? persianDigits(tests) + ' تست تستی ' + target
        : 'خواندن ' + target + (tests ? ' + ' + persianDigits(tests) + ' تست آموزشی' : '');
    } else {
      description = title;
    }
    return {
      title: type === 'مطالعه' ? nameWithGrade : (title || type),
      description: description, type: type,
      start: clock(from), end: clock(from + duration),
      duration: duration, tests: tests,
      category: type === 'مطالعه'
        ? [nameWithGrade].concat(additional.map(function (item) {
          return (item.lesson_name || '') + (item.grade ? ' ' + item.grade : '');
        })).join(' + ')
        : type
    };
  }
  function collect(start) {
    var $columns = $('.calendar-wrapper .day-column');
    var byName = {};
    $columns.each(function () {
      byName[normalize($(this).attr('data-day'))] = this;
    });
    var result = [];
    for (var i = 0; i < 7; i++) {
      var date = start.clone().add(i, 'days');
      var day = DAY_NAMES[date.day()];
      var column = byName[normalize(day)];
      var tasks = column ? $(column).find('.task-container > .calendar-task')
        .map(function () { return taskInfo(this); }).get() : [];
      tasks.sort(function (a,b) { return a.start.localeCompare(b.start, 'fa'); });
      result.push({ day: day, date: dateText(date), tasks: tasks });
    }
    return result;
  }
  function page(title, inner, index, count, start) {
    var html = '<section class="plan-pdf-page">' +
      '<header class="plan-pdf-header"><div class="plan-pdf-logo">KIMIAGARKHUNE</div>' +
      '<h1>' + escapeHtml(title) + '</h1></header>' +
      '<div class="plan-pdf-meta"><span>دانش‌آموز: <b>' + escapeHtml(studentName()) + '</b></span>' +
      '<span>شروع برنامه: ' + escapeHtml(dateText(start)) + '</span>' +
      '<span>صفحه ' + persianDigits(index) + ' از ' + persianDigits(count) + '</span></div>' +
      inner + '<div class="plan-pdf-footer">کیمیاگرخونه | برنامه‌ریزی درسی</div></section>';
    return html;
  }
  function dayCards(days) {
    return '<div class="plan-pdf-days">' + days.map(function (day) {
      var cards = day.tasks.length ? day.tasks.map(function (task) {
        return '<article class="plan-pdf-task"><span class="clock">' +
          escapeHtml(task.start + ' تا ' + task.end) + '</span>' +
          '<b>' + escapeHtml(task.title) + '</b>' +
          '<em>' + escapeHtml(task.description) + '</em></article>';
      }).join('') : '<p class="plan-pdf-empty">برنامه‌ای ثبت نشده</p>';
      return '<div class="plan-pdf-day"><div class="plan-pdf-day-head">' +
        escapeHtml(day.day) + '<small>' + escapeHtml(day.date) + '</small></div>' +
        cards + '</div>';
    }).join('') + '</div>';
  }
  function estimatedCardHeight(task) {
    // Split busy days instead of shrinking text or drawing a task over the next card.
    var titleLines = Math.max(1, Math.ceil(String(task.title || '').length / 27));
    var descriptionLines = Math.max(1, Math.ceil(String(task.description || '').length / 35));
    return 32 + titleLines * 19 + descriptionLines * 16 + 15;
  }
  function schedulePages(days, start) {
    var chunks = [];
    days.forEach(function (day) {
      var tasks = day.tasks.slice();
      if (!tasks.length) {
        chunks.push(day);
        return;
      }
      while (tasks.length) {
        var part = [];
        var height = 0;
        while (tasks.length && part.length < PER_DAY) {
          var size = estimatedCardHeight(tasks[0]);
          if (part.length && height + size > 510) break;
          part.push(tasks.shift());
          height += size;
        }
        chunks.push({day: day.day, date: day.date, tasks: part});
      }
    });
    var groups = [];
    while (chunks.length) groups.push(chunks.splice(0,DAYS_PER_PAGE));
    return groups.map(function (group,index) {
      return page('برنامه هفتگی', dayCards(group), index+1, groups.length, start);
    });
  }
  function aggregate(days) {
    var result = {};
    days.forEach(function (day, i) {
      day.tasks.forEach(function (task) {
        if (task.type !== 'مطالعه') return;
        var key = task.category;
        if (!result[key]) {
          result[key] = {title:key, days:Array.from({length:7}, function () {
            return {tests:0,minutes:0};
          }), tests:0, minutes:0};
        }
        result[key].days[i].tests += task.tests;
        result[key].days[i].minutes += task.duration;
        result[key].tests += task.tests;
        result[key].minutes += task.duration;
      });
    });
    return Object.keys(result).sort(function (a,b) { return a.localeCompare(b,'fa'); })
      .map(function (key) { return result[key]; });
  }
  function summaryTable(entries, days) {
    var heads = ['درس / پایه'].concat(days.map(function (day) { return day.day; }))
      .concat(['کل تست', 'کل زمان']);
    var html = '<table class="plan-pdf-table"><thead><tr>' +
      heads.map(function (heading) { return '<th>' + escapeHtml(heading) + '</th>'; }).join('') +
      '</tr></thead><tbody>';
    entries.forEach(function (entry) {
      html += '<tr><td><b>' + escapeHtml(entry.title) + '</b></td>';
      entry.days.forEach(function (item) {
        html += '<td>' + (item.minutes || item.tests
          ? persianDigits(item.tests) + ' تست / ' + persianDigits(item.minutes) + ' د'
          : '—') + '</td>';
      });
      html += '<td>' + persianDigits(entry.tests) + '</td><td>' +
        persianDigits(entry.minutes) + ' دقیقه</td></tr>';
    });
    return html + '</tbody></table>';
  }
  function summaryPages(days, start) {
    var rows = aggregate(days);
    var allTests = rows.reduce(function (sum,row) { return sum + row.tests; }, 0);
    var allMinutes = rows.reduce(function (sum,row) { return sum + row.minutes; }, 0);
    var groups = [];
    while (rows.length) groups.push(rows.splice(0, 8));
    if (!groups.length) groups.push([]);
    return groups.map(function (group,index) {
      var kpis = '<div class="plan-pdf-kpis">' +
        '<div class="plan-pdf-kpi">کل زمان مطالعه<strong>' + persianDigits(allMinutes) + ' دقیقه</strong></div>' +
        '<div class="plan-pdf-kpi">مجموع تست‌های برنامه<strong>' + persianDigits(allTests) + ' تست</strong></div>' +
        '<div class="plan-pdf-kpi">تعداد درس‌ها / ترکیب‌ها<strong>' + persianDigits(groups.reduce(function (sum,g) { return sum+g.length; },0)) + '</strong></div></div>';
      return page('برنامه‌ریزی به سبک حجمی', (index === 0 ? kpis : '<div style="height:14px"></div>') +
        summaryTable(group,days), index+1,groups.length,start);
    });
  }
  function matrixPages(days,start) {
    var heads = ['درس / مبحث'].concat(days.map(function (day) { return day.day; }));
    var html = '<p style="font-size:14px;color:#668293">فضای خالی برای ثبت پیشرفت و گزارش انجام برنامه</p>' +
      '<table class="plan-pdf-table"><thead><tr>' + heads.map(function (h) {
        return '<th>' + escapeHtml(h) + '</th>';
      }).join('') + '</tr></thead><tbody>';
    for (var row=0; row<10; row++) {
      html += '<tr><td style="height:45px"></td>';
      for(var c=0;c<7;c++) html += '<td></td>';
      html += '</tr>';
    }
    html += '</tbody></table>';
    return [page('ماتریس ثبت عملکرد',html,1,1,start)];
  }
  async function download(kind, button) {
    var start = selectedStart();
    if (!start) {
      window.alert('ابتدا هفته و دانش‌آموز را بارگذاری کنید.');
      return;
    }
    if (typeof window.html2canvas !== 'function' || !window.jspdf || !window.jspdf.jsPDF) {
      window.alert('ابزار خروجی PDF بارگذاری نشده است. صفحه را مجدداً باز کنید.');
      return;
    }
    var days = collect(start);
    var pages = [];
    if (kind === 'week' || kind === 'all') pages = pages.concat(schedulePages(days,start));
    if (kind === 'summary' || kind === 'all') pages = pages.concat(summaryPages(days,start));
    if (kind === 'matrix' || kind === 'all') pages = pages.concat(matrixPages(days,start));
    var suffix = kind === 'summary' ? 'حجمی' : kind === 'matrix' ? 'ماتریس' :
      kind === 'all' ? 'گزارش-کامل' : '';
    var oldText = button.textContent;
    button.disabled = true;
    button.textContent = 'در حال آماده‌سازی PDF...';
    var $capture = $('<div class="plan-pdf-capture" aria-hidden="true"></div>').appendTo('body');
    var pdf = new window.jspdf.jsPDF({orientation:'landscape',unit:'mm',format:'a4',compress:true});
    try {
      for (var i=0; i<pages.length; i++) {
        var $page = $(pages[i]).appendTo($capture);
        await document.fonts.ready;
        var canvas = await window.html2canvas($page[0], {
          scale: 1.6, useCORS: true, backgroundColor: '#ffffff',
          width: 1122, height: 794, windowWidth: 1122, windowHeight: 794,
          logging: false
        });
        if (i) pdf.addPage();
        pdf.addImage(canvas.toDataURL('image/jpeg',.88), 'JPEG', 0, 0, 297, 210);
        $page.remove();
      }
      pdf.save(fileName(start, suffix));
    } catch (error) {
      console.error('Plan PDF export failed:',error);
      window.alert('ساخت PDF ناموفق بود؛ لطفاً دوباره تلاش کنید.');
    } finally {
      $capture.remove();
      button.disabled = false;
      button.textContent = oldText;
    }
  }
  function bind() {
    var buttons = {
      'download-week-output':'week',
      'download-week-summary':'summary',
      'download-empty-matrix':'matrix',
      'download-all-pdf':'all'
    };
    Object.keys(buttons).forEach(function (id) {
      var old = document.getElementById(id);
      if (!old || !old.parentNode) return;
      // Replace legacy screenshot/popup handlers instead of stacking export listeners.
      var fresh = old.cloneNode(true);
      fresh.removeAttribute('data-plan-output-polish-bound');
      fresh.parentNode.replaceChild(fresh,old);
      fresh.addEventListener('click', function (event) {
        event.preventDefault();
        event.stopImmediatePropagation();
        download(buttons[id],fresh);
      });
    });
  }
  $(bind);
  window.planPdfV2 = {
    collect:collect, aggregate:aggregate, schedulePages:schedulePages,
    summaryPages:summaryPages, fileName:fileName, taskInfo:taskInfo
  };
})(window, document, window.jQuery);

(function (window, document, $) {
  'use strict';

  if (!$) {
    return;
  }

  const VERSION = '2026.08.31.1';

  function englishDigits(value) {
    const persian = '۰۱۲۳۴۵۶۷۸۹';
    const arabic = '٠١٢٣٤٥٦٧٨٩';
    return String(value || '').replace(/[۰-۹٠-٩]/g, function (digit) {
      const persianIndex = persian.indexOf(digit);
      return String(persianIndex >= 0 ? persianIndex : arabic.indexOf(digit));
    });
  }

  function selectedStudentStem() {
    const selected = String($('#student-select option:selected').text() || '').trim();
    const cleaned = selected
      .replace(/[\\/:*?"<>|]+/g, '-')
      .replace(/\s+/g, '')
      .replace(/[. ]+$/g, '')
      .trim();
    return cleaned || 'دانش‌آموز';
  }

  function selectedWeekStamp() {
    const state = window.planRuntimeState || {};
    if (state.start && typeof state.start.format === 'function') {
      const stamp = englishDigits(state.start.format('YYYYMMDD'));
      if (/^\d{8}$/.test(stamp)) {
        return stamp;
      }
    }

    const rawDate = englishDigits($('#weekSelector').val());
    if (rawDate && window.moment) {
      const parsed = window.moment(rawDate, 'jYYYY-jMM-jDD', true);
      if (parsed.isValid()) {
        const stamp = englishDigits(parsed.format('YYYYMMDD'));
        if (/^\d{8}$/.test(stamp)) {
          return stamp;
        }
      }
    }
    return '';
  }

  function studentPdfFileName(suffix) {
    const base = selectedStudentStem() + selectedWeekStamp();
    const tail = String(suffix || '').trim();
    return tail ? base + '-' + tail + '.pdf' : base + '.pdf';
  }

  function rewritePopupPdfName(markup) {
    if (typeof markup !== 'string' || markup.indexOf('pdf.save') === -1) {
      return markup;
    }
    const isSummary = /خلاصه/.test(markup);
    const filename = studentPdfFileName(isSummary ? 'خلاصه' : '');
    return markup.replace(
      /pdf\.save\((?:'[^']*'|"[^"]*")\);/,
      'pdf.save(' + JSON.stringify(filename) + ');'
    );
  }

  function installPopupInterceptor() {
    if (window.__planFilenameOpenInterceptorInstalled || typeof window.open !== 'function') {
      return;
    }
    window.__planFilenameOpenInterceptorInstalled = true;

    const originalOpen = window.open;
    window.open = function () {
      const popup = originalOpen.apply(window, arguments);
      if (!popup || !popup.document || typeof popup.document.write !== 'function') {
        return popup;
      }
      const originalWrite = popup.document.write.bind(popup.document);
      popup.document.write = function (markup) {
        return originalWrite(rewritePopupPdfName(markup));
      };
      return popup;
    };
  }

  function initialize() {
    installPopupInterceptor();

    // Keep the public helper consistent with the actual downloaded filename.
    // plan-output-polish keeps a private closure for its click handler; the
    // popup interceptor above applies this final filename after that handler.
    if (window.planOutputPolish) {
      window.planOutputPolish.studentPdfFileName = studentPdfFileName;
    }

    window.planFilenameFix = {
      version: VERSION,
      studentPdfFileName: studentPdfFileName,
      selectedWeekStamp: selectedWeekStamp,
      rewritePopupPdfName: rewritePopupPdfName
    };

    if (document.body) {
      document.body.setAttribute('data-plan-filename-fix-version', VERSION);
    }
    window.dispatchEvent(new CustomEvent('plan:filename-fix-ready'));
  }

  $(initialize);
})(window, document, window.jQuery);

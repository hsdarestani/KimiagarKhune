(function (window, document, $) {
  'use strict';

  if (!$) {
    return;
  }

  const VERSION = '2026.07.22.1';

  function placeStartNotice() {
    const $overlay = $('#pageOverlay').first();
    const $calendarWrapper = $('.calendar-wrapper').first();

    if (!$overlay.length || !$calendarWrapper.length) {
      return;
    }

    if ($overlay.attr('data-plan-start-state-version') === VERSION) {
      return;
    }

    $calendarWrapper.css('position', 'relative');
    $overlay
      .removeAttr('style')
      .addClass('plan-start-notice')
      .attr({
        'data-plan-start-state-version': VERSION,
        role: 'status',
        'aria-live': 'polite'
      })
      .empty()
      .append(
        $('<div class="plan-start-notice-card"></div>').html(
          'ابتدا <strong>دانش‌آموز</strong> و <strong>تاریخ شروع هفته</strong> را انتخاب کنید، سپس روی «بارگذاری هفته» بزنید.'
        )
      )
      .appendTo($calendarWrapper);
  }

  function initialize() {
    placeStartNotice();

    const observer = new MutationObserver(function () {
      placeStartNotice();
    });

    observer.observe(document.body, {
      childList: true,
      subtree: true
    });

    window.setTimeout(function () {
      observer.disconnect();
    }, 5000);
  }

  $(initialize);
})(window, document, window.jQuery);

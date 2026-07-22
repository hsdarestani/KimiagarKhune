(function (window, document, $) {
  'use strict';

  if (!$) {
    return;
  }

  const VERSION = '2026.07.22.1';
  const MOBILE_QUERY = window.matchMedia('(max-width: 760px)');

  function calendarIcon() {
    return (
      '<svg viewBox="0 0 24 24" aria-hidden="true">' +
        '<path d="M7 3v3M17 3v3M4.5 9h15M5 5h14a2 2 0 0 1 2 2v12a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V7a2 2 0 0 1 2-2Z"/>' +
        '<path d="m8 14 2 2 5-5"/>' +
      '</svg>'
    );
  }

  function booksIcon() {
    return (
      '<svg viewBox="0 0 24 24" aria-hidden="true">' +
        '<path d="M4 5.5A2.5 2.5 0 0 1 6.5 3H11v16H6.5A2.5 2.5 0 0 0 4 21.5v-16Z"/>' +
        '<path d="M20 5.5A2.5 2.5 0 0 0 17.5 3H13v16h4.5a2.5 2.5 0 0 1 2.5 2.5v-16Z"/>' +
      '</svg>'
    );
  }

  function closeIcon() {
    return (
      '<svg viewBox="0 0 24 24" aria-hidden="true">' +
        '<path d="m6 6 12 12M18 6 6 18"/>' +
      '</svg>'
    );
  }

  function ensurePageHeading() {
    const $header = $('.top-header').first();
    if (!$header.length || $header.children('.plan-page-heading').length) {
      return;
    }

    const $heading = $(
      '<div class="plan-page-heading">' +
        '<div class="plan-page-heading-main">' +
          '<span class="plan-page-mark">' + calendarIcon() + '</span>' +
          '<div>' +
            '<h1 class="plan-page-title">برنامه‌ریز هفتگی</h1>' +
            '<p class="plan-page-subtitle">مدیریت یکپارچه درس‌ها، تکالیف، رویدادها و زمان مطالعه</p>' +
          '</div>' +
        '</div>' +
        '<span class="plan-page-badge">تقویم هوشمند</span>' +
      '</div>'
    );
    $header.prepend($heading);
  }

  function ensurePaletteRow() {
    const $assignments = $('.assignments-box').first();
    const $events = $('.events-box').first();
    if (!$assignments.length || !$events.length || $assignments.closest('.plan-palette-row').length) {
      return;
    }

    const $row = $('<section class="plan-palette-row" aria-label="ابزارهای برنامه‌ریزی"></section>');
    const $anchor = $assignments.add($events).first();
    $anchor.before($row);
    $row.append($assignments, $events);
  }

  function setDrawerState(open) {
    const isOpen = Boolean(open && MOBILE_QUERY.matches);
    const $body = $('body');
    $body.toggleClass('plan-subjects-open', isOpen);
    $('.plan-subjects-toggle').attr('aria-expanded', String(isOpen));
    $('.subjects-box').attr('aria-hidden', String(MOBILE_QUERY.matches && !isOpen));

    if (isOpen) {
      window.setTimeout(function () {
        $('.plan-subjects-close').trigger('focus');
      }, 240);
    }
  }

  function ensureResponsiveControls() {
    const $subjects = $('.subjects-box').first();
    if (!$subjects.length) {
      return;
    }

    $subjects.attr({
      id: $subjects.attr('id') || 'plan-subjects-panel',
      role: 'complementary',
      'aria-label': 'فهرست دروس'
    });

    if (!$subjects.children('.plan-subjects-close').length) {
      $subjects.prepend(
        $('<button type="button" class="plan-subjects-close" aria-label="بستن فهرست دروس"></button>')
          .html(closeIcon())
      );
    }

    if (!$('.plan-subjects-toggle').length) {
      $('body').append(
        $('<button type="button" class="plan-subjects-toggle" aria-controls="' + $subjects.attr('id') + '" aria-expanded="false"></button>')
          .html(booksIcon() + '<span>انتخاب درس</span>')
      );
    }

    if (!$('.plan-mobile-backdrop').length) {
      $('body').append('<div class="plan-mobile-backdrop" aria-hidden="true"></div>');
    }
  }

  function bindResponsiveControls() {
    $(document)
      .off('click.planModernOpen', '.plan-subjects-toggle')
      .on('click.planModernOpen', '.plan-subjects-toggle', function () {
        setDrawerState(true);
      })
      .off('click.planModernClose', '.plan-subjects-close, .plan-mobile-backdrop')
      .on('click.planModernClose', '.plan-subjects-close, .plan-mobile-backdrop', function () {
        setDrawerState(false);
      })
      .off('keydown.planModernUi')
      .on('keydown.planModernUi', function (event) {
        if (event.key === 'Escape' && $('body').hasClass('plan-subjects-open')) {
          setDrawerState(false);
          $('.plan-subjects-toggle').trigger('focus');
        }
      });

    const onQueryChange = function (event) {
      if (!event.matches) {
        setDrawerState(false);
        $('.subjects-box').attr('aria-hidden', 'false');
      } else {
        $('.subjects-box').attr('aria-hidden', 'true');
      }
    };

    if (typeof MOBILE_QUERY.addEventListener === 'function') {
      MOBILE_QUERY.addEventListener('change', onQueryChange);
    } else if (typeof MOBILE_QUERY.addListener === 'function') {
      MOBILE_QUERY.addListener(onQueryChange);
    }
  }

  function markScrollableWorkspace() {
    const $wrapper = $('.calendar-wrapper').first();
    if (!$wrapper.length) {
      return;
    }
    $wrapper.attr({
      role: 'region',
      'aria-label': 'تقویم هفتگی؛ در نمایشگر کوچک به‌صورت افقی پیمایش می‌شود',
      tabindex: '0'
    });
  }

  function initialize() {
    const $body = $('body');
    if ($body.attr('data-plan-modern-ui-version') === VERSION) {
      return;
    }

    $body
      .addClass('plan-ui-modern')
      .attr('data-plan-modern-ui-version', VERSION);

    ensurePageHeading();
    ensurePaletteRow();
    ensureResponsiveControls();
    bindResponsiveControls();
    markScrollableWorkspace();
    setDrawerState(false);

    window.planModernUi = {
      version: VERSION,
      openSubjects: function () { setDrawerState(true); },
      closeSubjects: function () { setDrawerState(false); }
    };

    window.dispatchEvent(new CustomEvent('plan:modern-ui-ready'));
  }

  $(initialize);
})(window, document, window.jQuery);

(function (window, document, $) {
  'use strict';

  if (!$ || !$.ui) {
    return;
  }

  const ACTIVE_BODY_CLASS = 'plan-calendar-drag-active';
  const ACTIVE_SOURCE_CLASS = 'plan-active-drag-source';

  function beginDrag(element) {
    const $source = $(element);
    $('body').addClass(ACTIVE_BODY_CLASS);
    $source.addClass(ACTIVE_SOURCE_CLASS);
  }

  function endDrag(element) {
    if (element) {
      $(element).removeClass(ACTIVE_SOURCE_CLASS);
    }
    $('.' + ACTIVE_SOURCE_CLASS).removeClass(ACTIVE_SOURCE_CLASS);
    $('body').removeClass(ACTIVE_BODY_CLASS);
  }

  function initialize() {
    $(document)
      .off('dragstart.planDragSurface', '.calendar-task, .task, .other-plan-task')
      .on('dragstart.planDragSurface', '.calendar-task, .task, .other-plan-task', function () {
        beginDrag(this);
      })
      .off('dragstop.planDragSurface', '.calendar-task, .task, .other-plan-task')
      .on('dragstop.planDragSurface', '.calendar-task, .task, .other-plan-task', function () {
        endDrag(this);
      })
      .off('mouseup.planDragSurface pointerup.planDragSurface pointercancel.planDragSurface touchend.planDragSurface')
      .on(
        'mouseup.planDragSurface pointerup.planDragSurface pointercancel.planDragSurface touchend.planDragSurface',
        function () {
          window.setTimeout(function () {
            endDrag();
          }, 0);
        }
      );

    window.addEventListener('blur', function () {
      endDrag();
    });

    window.dispatchEvent(new CustomEvent('plan:drag-surface-ready'));
  }

  $(initialize);
})(window, document, window.jQuery);

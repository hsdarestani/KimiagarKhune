(function (window, document, $) {
  'use strict';

  if (!$ || !$.ui) {
    return;
  }

  const ACTIVE_BODY_CLASS = 'plan-calendar-drag-active';
  const ACTIVE_SOURCE_CLASS = 'plan-active-drag-source';
  const DRAGGABLE_SELECTOR = '.calendar-task, .task, .other-plan-task';
  const CANCEL_SELECTOR = [
    'button',
    'input',
    'textarea',
    'select',
    'option',
    '.select2-container',
    '.plan-resize-handle',
    '.plan-study-compact'
  ].join(', ');

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

  function canBegin(event) {
    const original = event.originalEvent || event;
    if (original.button !== undefined && original.button !== 0) {
      return false;
    }
    return !$(event.target).closest(CANCEL_SELECTOR).length;
  }

  function initialize() {
    $(document)
      .off('pointerdown.planDragSurface mousedown.planDragSurface touchstart.planDragSurface', DRAGGABLE_SELECTOR)
      .on(
        'pointerdown.planDragSurface mousedown.planDragSurface touchstart.planDragSurface',
        DRAGGABLE_SELECTOR,
        function (event) {
          if (canBegin(event)) {
            beginDrag(this);
          }
        }
      )
      .off('dragstart.planDragSurface', DRAGGABLE_SELECTOR)
      .on('dragstart.planDragSurface', DRAGGABLE_SELECTOR, function () {
        beginDrag(this);
      })
      .off('dragstop.planDragSurface', DRAGGABLE_SELECTOR)
      .on('dragstop.planDragSurface', DRAGGABLE_SELECTOR, function () {
        endDrag(this);
      })
      .off('mouseup.planDragSurface pointerup.planDragSurface pointercancel.planDragSurface touchend.planDragSurface touchcancel.planDragSurface')
      .on(
        'mouseup.planDragSurface pointerup.planDragSurface pointercancel.planDragSurface touchend.planDragSurface touchcancel.planDragSurface',
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

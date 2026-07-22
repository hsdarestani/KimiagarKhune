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
    if (!element) {
      return;
    }
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

  function eventElement(event) {
    const target = event && event.target;
    if (!target) {
      return null;
    }
    if (target.nodeType === 1) {
      return target;
    }
    return target.parentElement || null;
  }

  function sourceForEvent(event) {
    const target = eventElement(event);
    if (!target) {
      return null;
    }
    if (target.closest(CANCEL_SELECTOR)) {
      return null;
    }
    return target.closest(DRAGGABLE_SELECTOR);
  }

  function canBegin(event) {
    if (event.button !== undefined && event.button !== 0) {
      return false;
    }
    return Boolean(sourceForEvent(event));
  }

  function captureStart(event) {
    if (!canBegin(event)) {
      return;
    }
    beginDrag(sourceForEvent(event));
  }

  function captureEnd() {
    window.setTimeout(function () {
      endDrag();
    }, 0);
  }

  function bindCaptureListeners() {
    if (window.__planDragSurfaceCaptureBound) {
      return;
    }
    window.__planDragSurfaceCaptureBound = true;

    ['pointerdown', 'mousedown', 'touchstart'].forEach(function (eventName) {
      document.addEventListener(eventName, captureStart, true);
    });
    ['pointerup', 'mouseup', 'pointercancel', 'touchend', 'touchcancel'].forEach(function (eventName) {
      document.addEventListener(eventName, captureEnd, true);
    });
  }

  function draggableInstance($element) {
    try {
      return $element.draggable('instance') || null;
    } catch (_error) {
      return $element.data('ui-draggable') || $element.data('uiDraggable') || null;
    }
  }

  function wrapDraggable($element) {
    const instance = draggableInstance($element);
    if (!instance || !instance.options) {
      return;
    }

    const currentStart = instance.options.start;
    if (currentStart && currentStart.planDragSurfaceWrapped) {
      return;
    }
    const currentStop = instance.options.stop;

    const wrappedStart = function (event, ui) {
      beginDrag(this);
      if (typeof currentStart === 'function') {
        return currentStart.call(this, event, ui);
      }
      return undefined;
    };
    wrappedStart.planDragSurfaceWrapped = true;
    wrappedStart.planDragSurfaceOriginal = currentStart;

    const wrappedStop = function (event, ui) {
      try {
        if (typeof currentStop === 'function') {
          return currentStop.call(this, event, ui);
        }
        return undefined;
      } finally {
        endDrag(this);
      }
    };
    wrappedStop.planDragSurfaceWrapped = true;
    wrappedStop.planDragSurfaceOriginal = currentStop;

    instance.options.start = wrappedStart;
    instance.options.stop = wrappedStop;
  }

  function synchronize() {
    $(DRAGGABLE_SELECTOR).each(function () {
      wrapDraggable($(this));
    });
  }

  function initialize() {
    bindCaptureListeners();

    const calendar = document.querySelector('.calendar');
    if (calendar) {
      new MutationObserver(function () {
        window.requestAnimationFrame(synchronize);
      }).observe(calendar, { childList: true, subtree: true });
    }

    window.addEventListener('blur', function () {
      endDrag();
    });

    synchronize();
    window.setInterval(synchronize, 250);
    window.dispatchEvent(new CustomEvent('plan:drag-surface-ready'));
  }

  $(initialize);
})(window, document, window.jQuery);

(function (window, document, $) {
  'use strict';

  if (!$) {
    return;
  }

  const PIXELS_PER_MINUTE = 35 / 60;
  const GRID_PIXELS = 8.75;
  const DEFAULT_DURATION_MINUTES = 90;
  const VERSION = '2026.07.22.1';

  function finite(value) {
    const number = Number.parseFloat(value);
    return Number.isFinite(number) ? number : null;
  }

  function snap(value) {
    return Math.round(Number(value || 0) / GRID_PIXELS) * GRID_PIXELS;
  }

  function inlineNumber(element, property) {
    if (!element) {
      return null;
    }
    return finite(element.style[property]);
  }

  function renderedNumber($task, property) {
    return finite($task.css(property));
  }

  function currentTop($task) {
    const element = $task[0];
    const inline = inlineNumber(element, 'top');
    if (inline !== null) {
      return inline;
    }
    const rendered = renderedNumber($task, 'top');
    return rendered !== null ? rendered : 0;
  }

  function currentHeight($task) {
    const element = $task[0];
    const inline = inlineNumber(element, 'height');
    if (inline !== null && inline > 0) {
      return inline;
    }
    const duration = finite($task.attr('data-duration-minutes'));
    if (duration !== null && duration > 0) {
      return duration * PIXELS_PER_MINUTE;
    }
    const rendered = renderedNumber($task, 'height');
    if (rendered !== null && rendered > 0) {
      return rendered;
    }
    return DEFAULT_DURATION_MINUTES * PIXELS_PER_MINUTE;
  }

  function setAbsoluteGeometry($task, top, height) {
    const element = $task[0];
    if (!element) {
      return;
    }

    const safeTop = Math.max(0, snap(top));
    const safeHeight = Math.max(GRID_PIXELS, snap(height));

    element.style.setProperty('position', 'absolute', 'important');
    element.style.setProperty('display', 'block', 'important');
    element.style.setProperty('margin', '0', 'important');
    element.style.setProperty('top', safeTop + 'px');
    element.style.setProperty('height', safeHeight + 'px');
    element.style.setProperty('box-sizing', 'border-box', 'important');

    $task
      .attr('data-plan-top-px', String(safeTop))
      .attr('data-plan-height-px', String(safeHeight))
      .attr('data-duration-minutes', String(Math.round(safeHeight / PIXELS_PER_MINUTE)))
      .attr('data-plan-task-geometry-version', VERSION);

    if (typeof window.updateTimeLabel === 'function') {
      window.updateTimeLabel($task);
    }
  }

  function adoptCurrentGeometry(task) {
    const $task = $(task);
    if (!$task.length || !$task.hasClass('calendar-task')) {
      return;
    }
    setAbsoluteGeometry($task, currentTop($task), currentHeight($task));
  }

  function restoreStoredGeometry(task) {
    const $task = $(task);
    if (!$task.length || !$task.hasClass('calendar-task')) {
      return;
    }
    const top = finite($task.attr('data-plan-top-px'));
    const height = finite($task.attr('data-plan-height-px'));
    setAbsoluteGeometry(
      $task,
      top !== null ? top : currentTop($task),
      height !== null ? height : currentHeight($task)
    );
  }

  function wrapTaskInitializer() {
    const previous = window.initCalendarTask;
    if (typeof previous !== 'function' || previous.planTaskGeometryWrapped) {
      return;
    }

    const wrapped = function (task) {
      const $task = $(task);

      // A newly-created task is often initialized while it is still detached.
      // Prime an inline absolute position first so jQuery UI cannot convert it
      // to position:relative and put sibling tasks back into normal document flow.
      adoptCurrentGeometry($task);
      const result = previous.apply(this, arguments);
      adoptCurrentGeometry($task);
      return result;
    };

    wrapped.planTaskGeometryWrapped = true;
    wrapped.planTaskGeometryOriginal = previous;
    window.initCalendarTask = wrapped;
  }

  function handleAddedNode(node) {
    if (!node || node.nodeType !== 1) {
      return;
    }
    if (node.matches && node.matches('.calendar-task')) {
      adoptCurrentGeometry(node);
    }
    if (node.querySelectorAll) {
      node.querySelectorAll('.calendar-task').forEach(adoptCurrentGeometry);
    }
  }

  function observeCalendar() {
    const calendar = document.querySelector('.calendar');
    if (!calendar) {
      return;
    }

    new MutationObserver(function (mutations) {
      mutations.forEach(function (mutation) {
        mutation.addedNodes.forEach(handleAddedNode);
      });
    }).observe(calendar, {
      childList: true,
      subtree: true
    });
  }

  function bindInteractionCommits() {
    $(document)
      .off('.planTaskGeometry')
      .on(
        'dragstart.planTaskGeometry resizestart.planTaskGeometry',
        '.calendar-task',
        function () {
          adoptCurrentGeometry(this);
          $(this).attr('data-plan-geometry-active', 'true');
        }
      )
      .on(
        'dragstop.planTaskGeometry resizestop.planTaskGeometry',
        '.calendar-task',
        function () {
          const task = this;
          window.requestAnimationFrame(function () {
            adoptCurrentGeometry(task);
            $(task).removeAttr('data-plan-geometry-active');
          });
        }
      )
      .on('drop.planTaskGeometry', '.task-container', function () {
        const container = this;
        window.requestAnimationFrame(function () {
          $(container).children('.calendar-task').each(function () {
            adoptCurrentGeometry(this);
          });
        });
      });
  }

  function initialize() {
    wrapTaskInitializer();
    bindInteractionCommits();
    $('.calendar .calendar-task').each(function () {
      adoptCurrentGeometry(this);
    });
    observeCalendar();

    window.planTaskGeometry = {
      version: VERSION,
      adopt: adoptCurrentGeometry,
      restore: restoreStoredGeometry,
      snapshot: function (task) {
        const $task = $(task);
        return {
          position: $task.css('position'),
          top: currentTop($task),
          height: currentHeight($task),
          storedTop: finite($task.attr('data-plan-top-px')),
          storedHeight: finite($task.attr('data-plan-height-px'))
        };
      }
    };

    document.body.setAttribute('data-plan-task-geometry-version', VERSION);
    window.dispatchEvent(new CustomEvent('plan:task-geometry-ready'));
  }

  $(initialize);
})(window, document, window.jQuery);

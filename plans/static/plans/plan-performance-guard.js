(function (window, document) {
  'use strict';

  if (window.__planPerformanceGuardInstalled) {
    return;
  }
  window.__planPerformanceGuardInstalled = true;

  const VERSION = '2026.08.14.1';
  const blockedDelays = new Set([250, 350, 400, 500]);
  const nativeSetInterval = window.setInterval.bind(window);
  const NativeMutationObserver = window.MutationObserver;
  let suppressedTimerId = -1;

  const stats = {
    blockedIntervals: 0,
    filteredMutationBatches: 0
  };

  function isLegacyPlanSynchronizer(handler, delay) {
    return (
      typeof handler === 'function' &&
      handler.name === 'synchronize' &&
      blockedDelays.has(Number(delay))
    );
  }

  // Several compatibility layers used to rescan every calendar task every
  // 250/350/400/500ms. Their MutationObservers and input hooks already keep new
  // tasks patched, so these loops only add continuous CPU/layout pressure.
  window.setInterval = function (handler, delay) {
    if (isLegacyPlanSynchronizer(handler, delay)) {
      stats.blockedIntervals += 1;
      return suppressedTimerId--;
    }
    return nativeSetInterval.apply(window, arguments);
  };

  function elementTouchesCalendarStructure(node) {
    if (!node || node.nodeType !== 1) {
      return false;
    }
    if (
      node.matches &&
      node.matches('.calendar-task, .task-container, .day-column')
    ) {
      return true;
    }
    return Boolean(
      node.querySelector &&
      node.querySelector('.calendar-task, .task-container')
    );
  }

  function mutationTouchesCalendarStructure(mutation) {
    const nodes = [];
    mutation.addedNodes.forEach(function (node) { nodes.push(node); });
    mutation.removedNodes.forEach(function (node) { nodes.push(node); });
    return nodes.some(elementTouchesCalendarStructure);
  }

  // Calendar observers only need structural task/day changes. Select2 updates
  // its internal DOM heavily while a chapter is selected; letting every one of
  // those mutations wake all interaction layers creates the multi-second stall
  // seen before dropping the next lesson.
  if (typeof NativeMutationObserver === 'function') {
    function PlanMutationObserver(callback) {
      let filterCalendarMutations = false;
      const observer = new NativeMutationObserver(function (mutations, nativeObserver) {
        if (!filterCalendarMutations) {
          callback(mutations, nativeObserver);
          return;
        }

        const filtered = mutations.filter(mutationTouchesCalendarStructure);
        if (!filtered.length) {
          stats.filteredMutationBatches += 1;
          return;
        }
        callback(filtered, nativeObserver);
      });

      const nativeObserve = observer.observe.bind(observer);
      observer.observe = function (target, options) {
        filterCalendarMutations = Boolean(
          target &&
          target.nodeType === 1 &&
          target.matches &&
          target.matches('.calendar') &&
          options &&
          options.childList &&
          options.subtree
        );
        return nativeObserve(target, options);
      };
      return observer;
    }

    PlanMutationObserver.prototype = NativeMutationObserver.prototype;
    window.MutationObserver = PlanMutationObserver;
  }

  if (document.body) {
    document.body.setAttribute('data-plan-performance-guard-version', VERSION);
  }

  window.planPerformanceGuard = {
    version: VERSION,
    stats: stats,
    nativeSetInterval: nativeSetInterval
  };
})(window, document);

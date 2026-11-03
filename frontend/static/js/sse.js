/* ============================================================================
 * sse.js —— 实时事件流封装（Server-Sent Events）
 * Realtime event stream helper (Server-Sent Events).
 * 用法 / Usage:
 *   var stream = ROS.connectStream({
 *     onEvent: function (name, data) { ... },
 *     onReconnect: function () { ... },
 *   });
 *   stream.close();
 * ========================================================================== */

(function (global) {
  "use strict";

  window.ROS = window.ROS || {};

  // 监听的事件名 / Event names to listen for
  var EVENT_NAMES = [
    "order.created",
    "order.status_changed",
    "order.item_status_changed",
    "heartbeat",
  ];

  /**
   * 连接实时事件流
   * Connect to the realtime event stream.
   * @param {{onEvent?: Function, onReconnect?: Function, url?: string}} [options]
   *        回调选项 / callback options
   * @returns {{close: Function}} 控制句柄 / control handle
   */
  ROS.connectStream = function (options) {
    options = options || {};
    var onEvent = options.onEvent || function () {};
    var onReconnect = options.onReconnect || function () {};
    var url = options.url || "/api/orders/stream";

    var source = new EventSource(url);
    var openedOnce = false;

    source.onopen = function () {
      if (openedOnce) {
        // 非首次连接成功视为重连 / A non-first open is treated as a reconnect
        onReconnect();
      }
      openedOnce = true;
    };

    EVENT_NAMES.forEach(function (name) {
      source.addEventListener(name, function (event) {
        var data = null;
        if (event.data) {
          try {
            data = JSON.parse(event.data);
          } catch (err) {
            data = event.data;
          }
        }
        onEvent(name, data);
      });
    });

    // 连接错误时由 EventSource 自动重连，这里仅吞掉错误避免刷屏
    // EventSource auto-reconnects; swallow the error to avoid noisy logs.
    source.onerror = function () {};

    return {
      /**
       * 关闭事件流连接
       * Close the event stream connection.
       */
      close: function () {
        source.close();
      },
    };
  };
})(window);

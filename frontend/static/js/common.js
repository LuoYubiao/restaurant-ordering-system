/* ============================================================================
 * common.js —— 通用工具与文案
 * Common utilities and texts.
 * 依赖 / Depends on: api.js（提供 window.ROS 基础对象）
 * ========================================================================== */

(function (global) {
  "use strict";

  window.ROS = window.ROS || {};

  // 与后端保持一致的状态文案 / Status texts consistent with the backend
  ROS.ORDER_STATUS_TEXT = {
    pending: "待接单",
    cooking: "制作中",
    completed: "已出餐",
    settled: "已结账",
    cancelled: "已取消",
  };

  ROS.DINING_TYPE_TEXT = {
    dine_in: "堂食",
    takeaway: "打包",
  };

  ROS.ITEM_STATUS_TEXT = {
    pending: "待出餐",
    completed: "已出餐",
  };

  // 状态到徽标样式类的映射 / Mapping from status to badge style class
  ROS.STATUS_BADGE_CLASS = {
    pending: "badge-pending",
    cooking: "badge-cooking",
    completed: "badge-completed",
    settled: "badge-settled",
    cancelled: "badge-cancelled",
  };

  /**
   * 格式化金额（元，两位小数）
   * Format a money string (yuan, two decimals).
   * @param {string|number} value 金额 / amount
   * @returns {string} 如 "12.50" / e.g. "12.50"
   */
  ROS.formatMoney = function (value) {
    if (value === null || value === undefined || value === "") {
      return "0.00";
    }
    var num = Number(value);
    if (isNaN(num)) {
      return String(value);
    }
    return num.toFixed(2);
  };

  /**
   * 格式化时间（YYYY-MM-DD HH:mm）
   * Format a time value as YYYY-MM-DD HH:mm.
   * @param {string} iso ISO 时间字符串 / ISO time string
   * @returns {string} 格式化结果 / formatted result
   */
  ROS.formatTime = function (iso) {
    if (!iso) {
      return "";
    }
    var date = new Date(iso);
    if (isNaN(date.getTime())) {
      return String(iso);
    }
    function pad(n) {
      return n < 10 ? "0" + n : String(n);
    }
    return (
      date.getFullYear() +
      "-" +
      pad(date.getMonth() + 1) +
      "-" +
      pad(date.getDate()) +
      " " +
      pad(date.getHours()) +
      ":" +
      pad(date.getMinutes())
    );
  };

  /**
   * 返回状态对应的徽标样式类
   * Return the badge style class for a status.
   * @param {string} status 状态 / status
   * @returns {string} 样式类名 / style class name
   */
  ROS.statusBadgeClass = function (status) {
    return ROS.STATUS_BADGE_CLASS[status] || "badge";
  };

  /**
   * 右上角轻提示
   * Show a toast at the top-right corner.
   * @param {string} message 提示文本 / message text
   * @param {string} [type] 类型：success / error / warning / type
   */
  ROS.toast = function (message, type) {
    var el = document.createElement("div");
    el.className = "toast" + (type ? " " + type : "");
    el.textContent = message;
    document.body.appendChild(el);
    // 下一帧加类触发过渡 / Add the class on the next frame to animate
    requestAnimationFrame(function () {
      el.classList.add("show");
    });
    setTimeout(function () {
      el.classList.remove("show");
      setTimeout(function () {
        if (el.parentNode) {
          el.parentNode.removeChild(el);
        }
      }, 250);
    }, 2200);
  };

  /**
   * 播放一声提示音（WebAudio 合成，供厨房页使用）
   * Play a short beep using WebAudio (for the kitchen page).
   * @param {number} [frequency] 频率（赫兹）/ frequency in Hz
   */
  ROS.beep = function (frequency) {
    try {
      var AudioCtx = global.AudioContext || global.webkitAudioContext;
      if (!AudioCtx) {
        return;
      }
      var ctx = new AudioCtx();
      var osc = ctx.createOscillator();
      var gain = ctx.createGain();
      osc.type = "sine";
      osc.frequency.value = frequency || 880;
      gain.gain.value = 0.15;
      osc.connect(gain);
      gain.connect(ctx.destination);
      osc.start();
      osc.stop(ctx.currentTime + 0.18);
      osc.onended = function () {
        ctx.close();
      };
    } catch (err) {
      // 忽略音频失败 / Ignore audio failures
    }
  };
})(window);

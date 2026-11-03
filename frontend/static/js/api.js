/* ============================================================================
 * api.js —— 前端统一请求封装
 * Unified frontend HTTP helper.
 * 挂载到全局 window.ROS：ROS.get / post / put / patch / del
 * Mounted on the global window.ROS: ROS.get / post / put / patch / del
 * ========================================================================== */

(function (global) {
  "use strict";

  window.ROS = window.ROS || {};

  /**
   * 构建带查询参数的完整地址
   * Build the full URL with query parameters.
   * @param {string} path 接口路径 / API path
   * @param {object} [params] 查询参数 / query params
   * @returns {string} 完整地址 / full URL
   */
  function buildUrl(path, params) {
    var url = path;
    if (params) {
      var search = new URLSearchParams();
      Object.keys(params).forEach(function (key) {
        var value = params[key];
        if (value !== undefined && value !== null) {
          search.append(key, value);
        }
      });
      var qs = search.toString();
      if (qs) {
        url += (url.indexOf("?") >= 0 ? "&" : "?") + qs;
      }
    }
    return url;
  }

  /**
   * 统一处理响应：成功返回 JSON，失败抛出带 message 的错误
   * Handle a response: resolve JSON on success, reject with an Error on failure.
   * @param {Response} response 原生响应对象 / native response
   * @returns {Promise<any>} 解析结果 / parsed payload
   */
  function handle(response) {
    return response
      .json()
      .catch(function () {
        return null;
      })
      .then(function (body) {
        if (!response.ok) {
          var message =
            (body && body.detail) || "请求失败 (" + response.status + ")";
          var error = new Error(
            typeof message === "string" ? message : JSON.stringify(message)
          );
          error.status = response.status;
          error.body = body;
          throw error;
        }
        return body;
      });
  }

  /**
   * 发送 JSON 请求
   * Send a JSON request.
   * @param {string} method HTTP 方法 / HTTP method
   * @param {string} path 接口路径 / API path
   * @param {object} [body] 请求体 / request body
   * @param {object} [params] 查询参数 / query params
   * @returns {Promise<any>} 响应数据 / response payload
   */
  function request(method, path, body, params) {
    var options = {
      method: method,
      headers: { "Content-Type": "application/json" },
    };
    if (body !== undefined && body !== null) {
      options.body = JSON.stringify(body);
    }
    return fetch(buildUrl(path, params), options).then(handle);
  }

  ROS.get = function (path, params) {
    return request("GET", path, null, params);
  };
  ROS.post = function (path, body) {
    return request("POST", path, body);
  };
  ROS.put = function (path, body) {
    return request("PUT", path, body);
  };
  ROS.patch = function (path, body) {
    return request("PATCH", path, body);
  };
  ROS.del = function (path) {
    return request("DELETE", path);
  };
})(window);

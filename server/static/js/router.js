/**
 * 简易 Hash 路由器（支持参数路由）
 */
const Router = (() => {
  // 注册的路由：{ 'dashboard': handler, 'contracts': handler, ... }
  const routes = {};
  let currentPath = '';
  let listeners = [];

  /** 注册路由 */
  function register(name, handler) {
    routes[name] = handler;
  }

  /** 获取当前路径（不含 #/） */
  function getCurrentPath() {
    return location.hash.replace('#/', '').replace('#', '') || 'dashboard';
  }

  /** 解析路径，返回 { route, params } */
  function _resolve(path) {
    // 精确匹配
    if (routes[path]) {
      return { route: path, params: {} };
    }
    // 参数匹配：contracts/123 → contracts, { id: '123' }
    const parts = path.split('/');
    if (parts.length >= 2) {
      const baseRoute = parts[0];
      if (routes[baseRoute]) {
        return { route: baseRoute, params: { id: parts.slice(1).join('/') } };
      }
    }
    return { route: 'dashboard', params: {} };
  }

  /** 导航到指定路径 */
  function navigate(path) {
    if (location.hash !== '#/' + path) {
      location.hash = '#/' + path;
    } else {
      _handleRouteChange();
    }
  }

  /** 添加路由变化监听器 */
  function onChange(fn) {
    listeners.push(fn);
  }

  /** 获取当前路由名（不含参数） */
  function getCurrent() {
    return _resolve(getCurrentPath()).route;
  }

  /** 处理路由变化 */
  function _handleRouteChange() {
    const path = getCurrentPath();
    if (path === currentPath) return;
    currentPath = path;

    const { route, params } = _resolve(path);
    const handler = routes[route];
    if (handler) {
      handler(params);
    }
    listeners.forEach(fn => fn(route, params));
  }

  /** 初始化路由 */
  function init() {
    window.addEventListener('hashchange', _handleRouteChange);
    if (!location.hash) {
      location.hash = '#/dashboard';
    } else {
      _handleRouteChange();
    }
  }

  return { register, getCurrent, navigate, onChange, init };
})();

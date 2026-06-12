/**
 * 简易 Hash 路由器
 */
const Router = (() => {
  const routes = {};
  let currentRoute = '';
  let listeners = [];

  /** 注册路由 */
  function register(name, handler) {
    routes[name] = handler;
  }

  /** 获取当前路由名 */
  function getCurrent() {
    const hash = location.hash.replace('#/', '').replace('#', '') || 'dashboard';
    return routes[hash] ? hash : 'dashboard';
  }

  /** 导航到指定路由 */
  function navigate(name) {
    if (location.hash !== '#/' + name) {
      location.hash = '#/' + name;
    } else {
      // hash 相同但需要触发渲染
      _handleRouteChange();
    }
  }

  /** 添加路由变化监听器 */
  function onChange(fn) {
    listeners.push(fn);
  }

  /** 处理路由变化 */
  function _handleRouteChange() {
    const route = getCurrent();
    if (route === currentRoute) return;
    currentRoute = route;
    const handler = routes[route];
    if (handler) {
      handler();
    }
    // 通知监听器
    listeners.forEach(fn => fn(route));
  }

  /** 初始化路由 */
  function init() {
    window.addEventListener('hashchange', _handleRouteChange);
    // 初始路由
    if (!location.hash) {
      location.hash = '#/dashboard';
    } else {
      _handleRouteChange();
    }
  }

  return { register, getCurrent, navigate, onChange, init };
})();

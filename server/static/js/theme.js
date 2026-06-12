/**
 * 主题切换模块（亮色 / 暗色）
 */
const Theme = (() => {
  const STORAGE_KEY = 'clause-light-theme';

  /** 获取当前主题 */
  function get() {
    return document.documentElement.getAttribute('data-theme') || 'light';
  }

  /** 设置主题 */
  function set(theme) {
    document.documentElement.setAttribute('data-theme', theme);
    localStorage.setItem(STORAGE_KEY, theme);
  }

  /** 切换主题 */
  function toggle() {
    const next = get() === 'light' ? 'dark' : 'light';
    set(next);
    return next;
  }

  /** 初始化：从 localStorage 恢复 */
  function init() {
    const saved = localStorage.getItem(STORAGE_KEY);
    if (saved === 'dark' || saved === 'light') {
      set(saved);
    }
    // 跟随系统偏好（如果没有保存过）
    if (!saved && window.matchMedia && window.matchMedia('(prefers-color-scheme: dark)').matches) {
      set('dark');
    }
  }

  return { get, set, toggle, init };
})();

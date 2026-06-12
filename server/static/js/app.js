/**
 * 主应用 — 路由 + 主题 + 初始化
 */
const App = (() => {
  const pages = {
    dashboard: DashboardPage,
    contracts: ContractsPage,
    knowledge: KnowledgePage,
    sync: SyncPage,
    settings: SettingsPage,
  };

  let currentRoute = 'dashboard';

  /** 渲染指定页面 */
  async function renderPage(route) {
    currentRoute = route;
    const page = pages[route];
    if (!page) return;

    const app = document.getElementById('app');

    // 渲染侧边栏
    const sidebarHtml = Components.Sidebar(route);

    // 渲染页面内容（每个页面自己包含 header + body）
    let contentHtml = '';
    try {
      contentHtml = await page.render();
    } catch (e) {
      console.error('页面渲染错误:', e);
      contentHtml = `<div class="empty-state">加载失败，请刷新页面</div>`;
    }

    app.innerHTML = `
      ${sidebarHtml}
      <div class="main-content">
        ${contentHtml}
      </div>`;

    // 绑定侧边栏导航事件
    app.querySelectorAll('.sidebar-nav-item').forEach(item => {
      item.addEventListener('click', () => {
        const page = item.getAttribute('data-page');
        if (page) Router.navigate(page);
      });
    });

    // 滚动到顶部
    const contentBody = app.querySelector('.content-body');
    if (contentBody) contentBody.scrollTop = 0;
  }

  /** 渲染当前页面（用于状态更新时重新渲染） */
  function renderCurrentPage() {
    renderPage(currentRoute);
  }

  /** 切换主题 */
  function toggleTheme() {
    Theme.toggle();
    // 重新渲染当前页面以更新主题图标
    renderPage(currentRoute);
  }

  /** 初始化 */
  function init() {
    // 初始化主题
    Theme.init();

    // 注册路由
    Router.register('dashboard', () => renderPage('dashboard'));
    Router.register('contracts', () => renderPage('contracts'));
    Router.register('knowledge', () => renderPage('knowledge'));
    Router.register('sync', () => renderPage('sync'));
    Router.register('settings', () => renderPage('settings'));

    // 路由变化时更新侧边栏高亮
    Router.onChange(route => {
      currentRoute = route;
      document.querySelectorAll('.sidebar-nav-item').forEach(item => {
        const page = item.getAttribute('data-page');
        item.classList.toggle('active', page === route);
      });
    });

    // 初始化路由
    Router.init();
  }

  return { init, renderPage, renderCurrentPage, toggleTheme };
})();

// 启动应用
document.addEventListener('DOMContentLoaded', App.init);

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
    contractDetail: ContractDetailPage,
  };

  let currentRoute = 'dashboard';
  let currentParams = {};

  /** 渲染指定页面 */
  async function renderPage(route, params = {}) {
    currentRoute = route;
    currentParams = params;
    const page = pages[route];
    if (!page) return;

    const app = document.getElementById('app');

    // 渲染侧边栏（合同详情页也高亮"合同管理"）
    const sidebarRoute = route === 'contractDetail' ? 'contracts' : route;
    const sidebarHtml = Components.Sidebar(sidebarRoute);

    // 渲染页面内容
    let contentHtml = '';
    try {
      contentHtml = await page.render(params);
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
    renderPage(currentRoute, currentParams);
  }

  /** 切换主题 */
  function toggleTheme() {
    Theme.toggle();
    renderPage(currentRoute, currentParams);
  }

  /** 初始化 */
  function init() {
    Theme.init();

    // 注册路由（handler 接收 params）
    Router.register('dashboard', (params) => renderPage('dashboard', params));
    Router.register('contracts', (params) => renderPage('contracts', params));
    Router.register('contractDetail', (params) => renderPage('contractDetail', params));
    Router.register('knowledge', (params) => renderPage('knowledge', params));
    Router.register('sync', (params) => renderPage('sync', params));
    Router.register('settings', (params) => renderPage('settings', params));

    // 路由变化时更新侧边栏高亮
    Router.onChange(route => {
      currentRoute = route;
      const sidebarRoute = route === 'contractDetail' ? 'contracts' : route;
      document.querySelectorAll('.sidebar-nav-item').forEach(item => {
        const page = item.getAttribute('data-page');
        item.classList.toggle('active', page === sidebarRoute);
      });
    });

    Router.init();
  }

  return { init, renderPage, renderCurrentPage, toggleTheme };
})();

document.addEventListener('DOMContentLoaded', App.init);

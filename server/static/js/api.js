/**
 * API 调用封装 + Mock 数据
 * 当后端未就绪时使用 mock 数据，后端就绪后切换为真实 API 调用
 */

// ============================================
// Mock 数据
// ============================================

const MOCK_CONTRACTS = [
  { id: '1', title: '房屋租赁合同', type: '租赁合同', typeEn: 'rental', score: 42, riskLevel: 'red', redCount: 5, yellowCount: 3, greenCount: 2, createdAt: '2026-06-10', status: 'analyzed', model: 'deepseek-chat' },
  { id: '2', title: '劳动合同（三年期）', type: '劳动合同', typeEn: 'labor', score: 68, riskLevel: 'yellow', redCount: 2, yellowCount: 4, greenCount: 6, createdAt: '2026-06-09', status: 'analyzed', model: 'deepseek-chat' },
  { id: '3', title: '装修工程施工合同', type: '装修合同', typeEn: 'renovation', score: 35, riskLevel: 'red', redCount: 7, yellowCount: 2, greenCount: 1, createdAt: '2026-06-08', status: 'analyzed', model: 'qwen2.5:32b' },
  { id: '4', title: '软件开发外包合同', type: '外包合同', typeEn: 'outsourcing', score: 81, riskLevel: 'green', redCount: 0, yellowCount: 3, greenCount: 9, createdAt: '2026-06-07', status: 'analyzed', model: 'deepseek-chat' },
  { id: '5', title: '借款合同（个人）', type: '借款合同', typeEn: 'loan', score: 55, riskLevel: 'yellow', redCount: 3, yellowCount: 2, greenCount: 4, createdAt: '2026-06-06', status: 'analyzed', model: 'deepseek-chat' },
  { id: '6', title: '物业服务合同', type: '服务合同', typeEn: 'service', score: 73, riskLevel: 'green', redCount: 1, yellowCount: 2, greenCount: 8, createdAt: '2026-06-05', status: 'analyzed', model: 'qwen2.5:32b' },
];

const MOCK_RULES = [
  { id: '1', category: '通用', text: '滞纳金或违约金超过合同金额20%的条款应标记为高风险', confidence: 0.95, source: 'manual', usageCount: 45, active: true },
  { id: '2', category: '通用', text: '单方面解除权不对等的条款应标记为高风险', confidence: 0.92, source: 'manual', usageCount: 38, active: true },
  { id: '3', category: '租赁', text: '押金超过两个月租金的租赁合同应标记为高风险', confidence: 0.88, source: 'manual', usageCount: 22, active: true },
  { id: '4', category: '劳动', text: '竞业限制补偿金低于月工资30%的条款应标记为高风险', confidence: 0.91, source: 'auto_learned', usageCount: 15, active: true },
  { id: '5', category: '装修', text: '装修合同未约定验收标准的应标记为中风险', confidence: 0.85, source: 'user_feedback', usageCount: 8, active: true },
  { id: '6', category: '通用', text: '管辖法院约定为对方所在地法院的条款应标记为中风险', confidence: 0.78, source: 'auto_learned', usageCount: 12, active: true },
  { id: '7', category: '外包', text: '知识产权归属不明确的外包合同应标记为高风险', confidence: 0.90, source: 'manual', usageCount: 18, active: true },
  { id: '8', category: '劳动', text: '加班条款未明确加班费计算标准的应标记为中风险', confidence: 0.87, source: 'user_feedback', usageCount: 10, active: true },
];

const MOCK_SYNC_LOG = [
  { id: '1', type: 'WebDAV', direction: 'push', status: 'success', details: '同步完成，上传 3 个文件', time: '2026-06-12 08:30' },
  { id: '2', type: 'WebDAV', direction: 'pull', status: 'success', details: '同步完成，下载 2 个文件', time: '2026-06-11 20:15' },
  { id: '3', type: 'Git', direction: 'push', status: 'failed', details: '连接超时，无法访问远程仓库', time: '2026-06-11 14:00' },
  { id: '4', type: 'WebDAV', direction: 'push', status: 'success', details: '同步完成，上传 1 个文件', time: '2026-06-10 09:00' },
];

const MOCK_DEVICES = [
  { id: '1', name: 'iPhone 15 Pro', type: 'mobile', status: 'online', lastSeen: '刚刚', ip: '192.168.1.105' },
  { id: '2', name: 'iPad Air', type: 'tablet', status: 'offline', lastSeen: '2 小时前', ip: '192.168.1.108' },
];

const MOCK_STATS = {
  totalContracts: 6,
  thisMonth: 4,
  totalRules: 8,
  avgScore: 59,
  totalDevices: 1,
  pendingReview: 2,
  totalLaws: 70,
  avgConfidence: 0.88,
  redCount: 18,
  yellowCount: 16,
  greenCount: 30,
};

const MOCK_LAWS = [
  { id: '1', name: '中华人民共和国民法典', articles: 42, tags: ['合同', '租赁', '借款', '服务'] },
  { id: '2', name: '中华人民共和国劳动合同法', articles: 28, tags: ['劳动', '竞业限制', '加班'] },
];

const MOCK_PENDING_RULES = [
  { id: 'p1', text: '服务期限超过五年的合同应增加中期评估条款', source: 'auto_learned', confidence: 0.72 },
  { id: 'p2', text: '合同中未约定不可抗力条款的应标记为中风险', source: 'auto_learned', confidence: 0.68 },
];

// ============================================
// API 封装
// ============================================

const API = (() => {
  // 是否使用 mock 数据（后端未就绪时为 true）
  const USE_MOCK = false;

  /** 通用 fetch 封装 */
  async function _fetch(url, options = {}) {
    try {
      // 如果是 FormData，不设置 Content-Type，让浏览器自动设置 multipart/form-data
      const isFormData = options.body instanceof FormData;
      const defaultHeaders = isFormData ? {} : { 'Content-Type': 'application/json' };
      const headers = { ...defaultHeaders, ...options.headers };

      const res = await fetch(url, {
        ...options,
        headers,
      });
      if (!res.ok) {
        const err = await res.json().catch(() => ({ detail: res.statusText }));
        throw new Error(err.detail || `请求失败 (${res.status})`);
      }
      return await res.json();
    } catch (e) {
      if (e.name === 'TypeError' && e.message.includes('fetch')) {
        // 网络错误，后端未启动
        console.warn('API 不可用，使用 mock 数据:', url);
        return null;
      }
      throw e;
    }
  }

  /** 合同相关 API */
  const contracts = {
    async list(params = {}) {
      if (USE_MOCK) {
        let data = [...MOCK_CONTRACTS];
        if (params.search) {
          const q = params.search.toLowerCase();
          data = data.filter(c => c.title.toLowerCase().includes(q) || c.type.toLowerCase().includes(q));
        }
        if (params.type) {
          data = data.filter(c => c.typeEn === params.type);
        }
        if (params.risk) {
          data = data.filter(c => c.riskLevel === params.risk);
        }
        return data;
      }
      const qs = new URLSearchParams(params).toString();
      return _fetch(`/api/contracts?${qs}`);
    },
    async get(id) {
      if (USE_MOCK) return MOCK_CONTRACTS.find(c => c.id === id) || null;
      return _fetch(`/api/contracts/${id}`);
    },
    async analyze(file) {
      if (USE_MOCK) return { success: true, message: '分析完成（mock）' };
      const form = new FormData();
      form.append('file', file);
      // 不设置 Content-Type，让浏览器自动设置 multipart/form-data boundary
      return _fetch('/api/contracts/analyze', { method: 'POST', body: form, headers: {} });
    },
  };

  /** 知识库相关 API */
  const knowledge = {
    async rules(params = {}) {
      if (USE_MOCK) {
        let data = [...MOCK_RULES];
        if (params.search) {
          const q = params.search.toLowerCase();
          data = data.filter(r => r.text.toLowerCase().includes(q));
        }
        if (params.category) {
          data = data.filter(r => r.category === params.category);
        }
        return data;
      }
      const qs = new URLSearchParams(params).toString();
      return _fetch(`/api/knowledge/rules?${qs}`);
    },
    async createRule(rule) {
      if (USE_MOCK) return { success: true, id: String(Date.now()) };
      return _fetch('/api/knowledge/rules', { method: 'POST', body: JSON.stringify(rule) });
    },
    async updateRule(id, data) {
      if (USE_MOCK) return { success: true };
      return _fetch(`/api/knowledge/rules/${id}`, { method: 'PUT', body: JSON.stringify(data) });
    },
    async deleteRule(id) {
      if (USE_MOCK) return { success: true };
      return _fetch(`/api/knowledge/rules/${id}`, { method: 'DELETE' });
    },
    async stats() {
      if (USE_MOCK) return MOCK_STATS;
      return _fetch('/api/knowledge/stats');
    },
    async pending() {
      if (USE_MOCK) return MOCK_PENDING_RULES;
      return _fetch('/api/knowledge/pending');
    },
    async laws() {
      if (USE_MOCK) return MOCK_LAWS;
      return _fetch('/api/knowledge/laws');
    },
  };

  /** 同步相关 API */
  const sync = {
    async config() {
      if (USE_MOCK) return { webdav: { enabled: true, url: 'https://dav.example.com', username: 'user', path: '/clause-light/' }, git: { enabled: false }, s3: { enabled: false } };
      return _fetch('/api/sync/config');
    },
    async updateConfig(data) {
      if (USE_MOCK) return { success: true };
      return _fetch('/api/sync/config', { method: 'PUT', body: JSON.stringify(data) });
    },
    async push() {
      if (USE_MOCK) return { success: true, message: '上传完成（mock）' };
      return _fetch('/api/sync/push', { method: 'POST' });
    },
    async pull() {
      if (USE_MOCK) return { success: true, message: '下载完成（mock）' };
      return _fetch('/api/sync/pull', { method: 'POST' });
    },
    async log() {
      if (USE_MOCK) return MOCK_SYNC_LOG;
      return _fetch('/api/sync/log');
    },
  };

  /** 模型管理 API */
  const models = {
    async status() {
      return _fetch('/api/models/status');
    },
  };

  /** 设置相关 API */
  const settings = {
    async llm() {
      if (USE_MOCK) return { remote: { enabled: true, provider: 'deepseek', baseUrl: 'https://api.deepseek.com', apiKey: '', models: { classify: 'deepseek-chat', analyze: 'deepseek-chat', explain: 'deepseek-chat' } }, local: { enabled: false, endpoint: 'http://localhost:11434', models: { classify: 'qwen2.5:32b', analyze: 'qwen2.5:32b', explain: 'qwen2.5:32b' } } };
      return _fetch('/api/settings/llm');
    },
    async updateLLM(data) {
      if (USE_MOCK) return { success: true };
      return _fetch('/api/settings/llm', { method: 'PUT', body: JSON.stringify(data) });
    },
    async testLLM() {
      if (USE_MOCK) return { success: true, latency_ms: 120, model: 'deepseek-chat', provider: 'deepseek' };
      return _fetch('/api/settings/llm/test', { method: 'POST' });
    },
    async testLLMLocal() {
      if (USE_MOCK) return { success: true, latency_ms: 50, models: ['qwen2.5:7b', 'qwen2.5:32b'], endpoint: 'http://localhost:11434' };
      return _fetch('/api/settings/llm/test-local', { method: 'POST' });
    },
    async devices() {
      if (USE_MOCK) return MOCK_DEVICES;
      return _fetch('/api/devices');
    },
  };

  return { contracts, knowledge, sync, models, settings };
})();

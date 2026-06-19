/**
 * API 调用封装
 * 所有 API 调用通过此模块统一管理，后端未启动时会抛出错误
 */

// ============================================
// API 封装
// ============================================

const API = (() => {

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
        console.warn('API 不可用:', url);
        throw new Error('后端服务未启动，请先启动服务');
      }
      throw e;
    }
  }

  /** 合同相关 API */
  const contracts = {
    async list(params = {}) {
      const qs = new URLSearchParams(params).toString();
      return _fetch(`/api/contracts?${qs}`);
    },
    async get(id) {
      return _fetch(`/api/contracts/${id}`);
    },
    async analyze(file) {
      const form = new FormData();
      form.append('file', file);
      // 不设置 Content-Type，让浏览器自动设置 multipart/form-data boundary
      return _fetch('/api/contracts/analyze', { method: 'POST', body: form, headers: {} });
    },
    /**
     * 流式分析合同（SSE），返回 { onProgress, onResult, onError, done }
     * @param {File} file - 要上传的文件
     * @param {object} callbacks - { onProgress(step, total, message, substep), onResult(data), onError(message) }
     */
    analyzeStream(file, callbacks = {}) {
      const form = new FormData();
      form.append('file', file);
      const ctrl = new AbortController();

      fetch('/api/contracts/analyze', {
        method: 'POST',
        body: form,
        signal: ctrl.signal,
      }).then(async res => {
        if (!res.ok) {
          const err = await res.json().catch(() => ({ detail: res.statusText }));
          throw new Error(err.detail || `请求失败 (${res.status})`);
        }
        const reader = res.body.getReader();
        const decoder = new TextDecoder();
        let buffer = '';

        while (true) {
          const { done, value } = await reader.read();
          if (done) break;
          buffer += decoder.decode(value, { stream: true });

          // 按行解析 SSE 事件
          const lines = buffer.split('\n');
          buffer = lines.pop(); // 保留未完成的行
          for (const line of lines) {
            if (line.startsWith('data: ')) {
              try {
                const data = JSON.parse(line.slice(6));
                if (data.type === 'progress' && callbacks.onProgress) {
                  callbacks.onProgress(data.step, data.total, data.message, data.substep);
                } else if (data.type === 'result' && callbacks.onResult) {
                  callbacks.onResult(data);
                } else if (data.type === 'error' && callbacks.onError) {
                  callbacks.onError(data.message);
                }
              } catch (e) {
                console.warn('SSE 解析失败:', line);
              }
            }
          }
        }
      }).catch(err => {
        if (err.name !== 'AbortError' && callbacks.onError) {
          callbacks.onError(err.message);
        }
      });

      return { abort: () => ctrl.abort() };
    },
    async feedback(contractId, clauseAnalysisId, feedback) {
      const form = new URLSearchParams({ clause_analysis_id: clauseAnalysisId, feedback });
      return _fetch(`/api/contracts/${contractId}/feedback`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
        body: form,
      });
    },
    async delete(id) {
      if (USE_MOCK) return { success: true };
      return _fetch(`/api/contracts/${id}`, { method: 'DELETE' });
    },
  };

  /** 知识库相关 API */
  const knowledge = {
    async rules(params = {}) {
      const qs = new URLSearchParams(params).toString();
      return _fetch(`/api/knowledge/rules?${qs}`);
    },
    async createRule(rule) {
      return _fetch('/api/knowledge/rules', { method: 'POST', body: JSON.stringify(rule) });
    },
    async updateRule(id, data) {
      return _fetch(`/api/knowledge/rules/${id}`, { method: 'PUT', body: JSON.stringify(data) });
    },
    async deleteRule(id) {
      return _fetch(`/api/knowledge/rules/${id}`, { method: 'DELETE' });
    },
    async stats() {
      return _fetch('/api/knowledge/stats');
    },
    async pending() {
      return _fetch('/api/knowledge/pending');
    },
    async laws() {
      return _fetch('/api/knowledge/laws');
    },
    async approveRule(id) {
      return _fetch(`/api/knowledge/pending/${id}/approve`, { method: 'POST' });
    },
    async rejectRule(id) {
      return _fetch(`/api/knowledge/pending/${id}/reject`, { method: 'POST' });
    },
  };

  /** 同步相关 API */
  const sync = {
    async config() {
      return _fetch('/api/sync/config');
    },
    async updateConfig(data) {
      return _fetch('/api/sync/config', { method: 'PUT', body: JSON.stringify(data) });
    },
    async push() {
      return _fetch('/api/sync/push', { method: 'POST' });
    },
    async pull() {
      return _fetch('/api/sync/pull', { method: 'POST' });
    },
    async log() {
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
      return _fetch('/api/settings/llm');
    },
    async updateLLM(data) {
      return _fetch('/api/settings/llm', { method: 'PUT', body: JSON.stringify(data) });
    },
    async testLLM() {
      return _fetch('/api/settings/llm/test', { method: 'POST' });
    },
    async testLLMLocal() {
      return _fetch('/api/settings/llm/test-local', { method: 'POST' });
    },
    async devices() {
      return _fetch('/api/connection/devices');
    },
  };

  // ── 连接管理 API ──
  const connection = {
    async info() {
      return _fetch('/api/connection/info');
    },
    qrUrl() {
      // 直接返回 URL，用于 <img src>
      return '/api/connection/qr?' + Date.now();
    },
    async health() {
      return _fetch('/api/connection/health');
    },
    async devices() {
      return _fetch('/api/connection/devices');
    },
  };

  return { contracts, knowledge, sync, models, settings, connection };
})();

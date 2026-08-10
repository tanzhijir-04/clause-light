import type {
  ContractListItem,
  ContractDetail,
  AnalyzeResponse,
  FeedbackResponse,
  KnowledgeRule,
  KnowledgeLaw,
  KnowledgeStats,
} from '../types/api';

let _baseUrl = '';

export const setBaseUrl = (url: string) => {
  _baseUrl = url;
};

const getBaseUrl = () => _baseUrl;

// 合同列表
export const getContracts = async (params?: {
  search?: string;
  type?: string;
  risk?: string;
}): Promise<ContractListItem[]> => {
  const base = getBaseUrl();
  const query = new URLSearchParams();
  if (params?.search) query.set('search', params.search);
  if (params?.type) query.set('type', params.type);
  if (params?.risk) query.set('risk', params.risk);

  const qs = query.toString();
  const response = await fetch(`${base}/api/contracts/${qs ? `?${qs}` : ''}`);
  if (!response.ok) throw new Error('获取合同列表失败');
  return response.json();
};

// 合同详情
export const getContract = async (id: string): Promise<ContractDetail> => {
  const base = getBaseUrl();
  const response = await fetch(`${base}/api/contracts/${id}`);
  if (!response.ok) throw new Error('获取合同详情失败');
  return response.json();
};

// 上传并分析合同
export const analyzeContract = async (
  fileUri: string,
  contractType: string = ''
): Promise<AnalyzeResponse> => {
  const base = getBaseUrl();
  const formData = new FormData();

  // 获取文件名和 MIME（按扩展名推断，兼容办公文档）
  const filename = fileUri.split('/').pop() || 'contract.pdf';
  const lower = filename.toLowerCase();
  const mimeByExt: Record<string, string> = {
    pdf: 'application/pdf',
    png: 'image/png',
    jpg: 'image/jpeg',
    jpeg: 'image/jpeg',
    bmp: 'image/bmp',
    tiff: 'image/tiff',
    tif: 'image/tiff',
    webp: 'image/webp',
    doc: 'application/msword',
    docx: 'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
    xls: 'application/vnd.ms-excel',
    xlsx: 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
    ppt: 'application/vnd.ms-powerpoint',
    pptx: 'application/vnd.openxmlformats-officedocument.presentationml.presentation',
    rtf: 'application/rtf',
    csv: 'text/csv',
    epub: 'application/epub+zip',
    odt: 'application/vnd.oasis.opendocument.text',
    ods: 'application/vnd.oasis.opendocument.spreadsheet',
    odp: 'application/vnd.oasis.opendocument.presentation',
  };
  const ext = lower.includes('.') ? lower.split('.').pop() || '' : '';
  const type = mimeByExt[ext] || 'application/octet-stream';

  formData.append('file', {
    uri: fileUri,
    name: filename,
    type,
  } as any);

  if (contractType) {
    formData.append('contract_type', contractType);
  }

  const response = await fetch(`${base}/api/contracts/analyze`, {
    method: 'POST',
    body: formData,
    headers: {
      'Content-Type': 'multipart/form-data',
    },
  });

  if (!response.ok) throw new Error('分析合同失败');
  return response.json();
};

// 提交反馈
export const submitFeedback = async (
  contractId: string,
  clauseAnalysisId: string,
  feedback: 'correct' | 'incorrect'
): Promise<FeedbackResponse> => {
  const base = getBaseUrl();
  const formData = new FormData();
  formData.append('clause_analysis_id', clauseAnalysisId);
  formData.append('feedback', feedback);

  const response = await fetch(`${base}/api/contracts/${contractId}/feedback`, {
    method: 'POST',
    body: formData,
  });

  if (!response.ok) throw new Error('提交反馈失败');
  return response.json();
};

// 知识库规则列表
export const getKnowledgeRules = async (params?: {
  search?: string;
  category?: string;
}): Promise<KnowledgeRule[]> => {
  const base = getBaseUrl();
  const query = new URLSearchParams();
  if (params?.search) query.set('search', params.search);
  if (params?.category) query.set('category', params.category);

  const qs = query.toString();
  const response = await fetch(`${base}/api/knowledge/rules${qs ? `?${qs}` : ''}`);
  if (!response.ok) throw new Error('获取规则列表失败');
  return response.json();
};

// 知识库法规列表
export const getKnowledgeLaws = async (): Promise<KnowledgeLaw[]> => {
  const base = getBaseUrl();
  const response = await fetch(`${base}/api/knowledge/laws`);
  if (!response.ok) throw new Error('获取法规列表失败');
  return response.json();
};

// 知识库统计
export const getKnowledgeStats = async (): Promise<KnowledgeStats> => {
  const base = getBaseUrl();
  const response = await fetch(`${base}/api/knowledge/stats`);
  if (!response.ok) throw new Error('获取统计信息失败');
  return response.json();
};

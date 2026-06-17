// 合同列表项（GET /api/contracts/ 返回）
export interface ContractListItem {
  id: string;
  title: string;
  type: string;       // 中文类型名
  typeEn: string;     // 英文类型名
  score: number;      // 0-100
  riskLevel: 'red' | 'yellow' | 'green';
  redCount: number;
  yellowCount: number;
  greenCount: number;
  createdAt: string;  // YYYY-MM-DD
  status: 'analyzed' | 'pending';
  model: string;
}

// 合同详情（GET /api/contracts/{id} 返回）
export interface ContractDetail extends ContractListItem {
  summary: string;
  recommendation: string;  // 'sign' | 'negotiate_first' | 'reject'
  fullText: string;
  clauses: ClauseData[];
}

// 条款分析数据（后端字段名，非 mock 的 number/title/content）
export interface ClauseData {
  id: string;
  clauseNumber: string;
  clauseTitle: string;
  clauseContent: string;
  riskLevel: 'red' | 'yellow' | 'green';
  riskType: string;
  riskSummary: string;
  plainExplanation: string;
  legalBasis: string;
  severityScore: number;  // 1-10
  suggestedClause: string;
  canNegotiate: boolean;
  userFeedback: 'correct' | 'incorrect' | null;
}

// 知识库规则（后端字段名：text 而非 ruleText）
export interface KnowledgeRule {
  id: string;
  category: string;
  text: string;
  confidence: number;
  source: string;
  usageCount: number;
  active: boolean;
}

// 知识库法规
export interface KnowledgeLaw {
  id: string;
  lawName: string;
  articleNumber: string;
  content: string;
  effectiveDate: string;
  tags: string[];
}

// 上传分析响应
export interface AnalyzeResponse {
  success: boolean;
  contractId: string;
  score: number;
  riskLevel: string;
  error?: string;
}

// 反馈响应
export interface FeedbackResponse {
  success: boolean;
}

// 知识库统计（字段名与后端 knowledge.py get_stats() 一致）
export interface KnowledgeStats {
  totalRules: number;
  totalLaws: number;
  avgConfidence: number;
  pendingReview: number;
  totalContracts: number;
  thisMonth: number;
  avgScore: number;
  redCount: number;
  yellowCount: number;
  greenCount: number;
}

// WebSocket 消息类型
export type WSMessage =
  | { type: 'progress'; step: number; total: number; message: string }
  | { type: 'result'; data: WSResultData }
  | { type: 'pong' };

export interface WSResultData {
  contractId: string;
  score: number;
  riskLevel: string;
  summary: string;
  redCount: number;
  yellowCount: number;
  greenCount: number;
  clauses: Partial<ClauseData>[];
}

// 合同类型映射
export const TYPE_EN_MAP: Record<string, string> = {
  '租赁合同': 'rental',
  '劳动合同': 'labor',
  '装修合同': 'renovation',
  '外包合同': 'outsourcing',
  '借款合同': 'loan',
  '服务合同': 'service',
  '采购合同': 'procurement',
  '合作协议': 'cooperation',
  '其他': 'other',
};

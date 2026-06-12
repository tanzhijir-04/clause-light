/* Mock data for 合同红绿灯 Desktop prototype */
const MOCK_CONTRACTS = [
  { id: '1', title: '房屋租赁合同', type: '租赁合同', typeEn: 'rental', score: 42, riskLevel: 'red', redCount: 5, yellowCount: 3, greenCount: 2, createdAt: '2026-06-10', status: 'analyzed', model: 'deepseek-chat' },
  { id: '2', title: '劳动合同（三年期）', type: '劳动合同', typeEn: 'labor', score: 68, riskLevel: 'yellow', redCount: 2, yellowCount: 4, greenCount: 6, createdAt: '2026-06-09', status: 'analyzed', model: 'deepseek-chat' },
  { id: '3', title: '装修工程施工合同', type: '装修合同', typeEn: 'renovation', score: 35, riskLevel: 'red', redCount: 7, yellowCount: 2, greenCount: 1, createdAt: '2026-06-08', status: 'analyzed', model: 'qwen2.5:32b' },
  { id: '4', title: '软件开发外包合同', type: '外包合同', typeEn: 'outsourcing', score: 81, riskLevel: 'green', redCount: 0, yellowCount: 3, greenCount: 9, createdAt: '2026-06-07', status: 'analyzed', model: 'deepseek-chat' },
  { id: '5', title: '借款合同（个人）', type: '借款合同', typeEn: 'loan', score: 55, riskLevel: 'yellow', redCount: 3, yellowCount: 2, greenCount: 4, createdAt: '2026-06-06', status: 'analyzed', model: 'deepseek-chat' },
  { id: '6', title: '物业服务合同', type: '服务合同', typeEn: 'service', score: 73, riskLevel: 'green', redCount: 1, yellowCount: 2, greenCount: 8, createdAt: '2026-06-05', status: 'analyzed', model: 'qwen2.5:32b' },
];

const MOCK_CLAUSES = [
  { num: '第三条', title: '租金及支付方式', content: '乙方应在每月5日前支付当月租金人民币8500元整，逾期每日加收5%滞纳金。', risk: 'red', summary: '滞纳金比例过高', explanation: '每天收5%的滞纳金，一个月就是150%，远超法律保护的上限。', suggestion: '修改为逾期每日加收万分之三的滞纳金（约年化10.95%），这是法律通常认可的合理范围。', canNegotiate: true },
  { num: '第五条', title: '押金条款', content: '乙方需一次性支付三个月押金共计25500元，退租时需提前30天通知，否则押金不予退还。', risk: 'red', summary: '押金过高且退还条件苛刻', explanation: '三个月押金已经偏高，而且不提前30天通知就完全不退，这对租客非常不公平。', suggestion: '押金改为一个月租金，退租时提前15天通知即可退还押金。', canNegotiate: true },
  { num: '第七条', title: '合同解除', content: '甲方有权在提前7天书面通知的情况下单方面解除本合同，乙方无权要求赔偿。', risk: 'red', summary: '房东可随时解约且不赔偿', explanation: '房东只要提前7天通知就能赶你走，还不用赔你任何损失，这完全不对等。', suggestion: '增加甲方违约赔偿条款：甲方提前解约需支付两个月租金作为违约金。', canNegotiate: true },
  { num: '第九条', title: '维修责任', content: '房屋内所有设施的维修费用由乙方承担，包括但不限于水管、电路、门窗等。', risk: 'yellow', summary: '维修责任全部转嫁给租客', explanation: '正常情况下，房屋结构性问题和设备自然老化应该由房东负责维修。', suggestion: '明确区分：因乙方使用不当造成的损坏由乙方维修，自然老化和结构问题由甲方负责。', canNegotiate: true },
  { num: '第十一条', title: '转租条款', content: '未经甲方书面同意，乙方不得将房屋全部或部分转租给第三方。', risk: 'green', summary: '转租需房东同意', explanation: '这条本身是合理的，房东有权知道谁住在他/她的房子里。', suggestion: '无需修改，属于标准条款。', canNegotiate: false },
  { num: '第十三条', title: '争议解决', content: '因本合同引起的争议，双方应友好协商解决，协商不成的，提交合同签订地人民法院诉讼解决。', risk: 'green', summary: '争议通过诉讼解决', explanation: '通过法院解决纠纷是合理合法的方式，虽然时间长但是公正。', suggestion: '无需修改，属于标准条款。', canNegotiate: false },
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
};
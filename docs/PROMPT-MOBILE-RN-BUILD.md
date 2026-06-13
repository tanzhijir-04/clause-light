# 手机端 React Native 构建提示词

## 任务

从零实现合同红绿灯手机端 React Native 应用。`mobile/` 目录当前为空，需要创建完整的移动端应用。

设计原型位于 `designs/clause-light-mobile/`（React + Babel），仅用于视觉和交互参考。实际实现使用 **React Native + Expo**。

---

## 技术选型

| 层 | 技术 | 理由 |
|----|------|------|
| 框架 | **React Native (Expo)** | 跨平台、快速开发、丰富的内置 API |
| 导航 | **React Navigation 6** | React Native 标准导航方案 |
| 状态管理 | **React Context + useReducer** | 轻量，无需 Redux |
| 本地存储 | **@react-native-async-storage/async-storage** | 简单键值存储 |
| 相机 | **expo-camera** | 拍照功能 |
| 文件选择 | **expo-document-picker** | 选择 PDF/图片 |
| 文件系统 | **expo-file-system** | 读取文件内容 |
| HTTP | **fetch**（内置） | API 调用 |
| WebSocket | **内置 WebSocket** | 实时通信 |
| 图标 | **@expo/vector-icons（Ionicons）** | 内置图标库 |
| 动画 | **React Native Animated** | 内置动画 API |

---

## 项目约束

| 约束 | 说明 |
|------|------|
| 框架 | React Native (Expo managed workflow) |
| 语言 | TypeScript |
| UI 文本 | 全部使用中文 |
| 字体 | 系统字体（iOS: SF Pro, Android: Roboto） |
| 主题 | 支持亮色/暗色（默认跟随系统） |
| 触控 | 所有可点击元素最小高度 44px |
| 存储 | AsyncStorage（键值对存储） |
| 后端 | FastAPI 服务，提供 REST API + WebSocket |
| 离线 | 基础功能离线可用（历史记录本地缓存） |

---

## 目标目录结构

```
mobile/
├── app.json                 # Expo 配置
├── App.tsx                  # 入口组件
├── package.json
├── tsconfig.json
├── babel.config.js
├── src/
│   ├── navigation/
│   │   └── AppNavigator.tsx      # 导航配置（Tab + Stack）
│   ├── screens/
│   │   ├── HomeScreen.tsx         # 首页
│   │   ├── AnalysisScreen.tsx     # 分析中
│   │   ├── ResultScreen.tsx       # 分析结果
│   │   ├── HistoryScreen.tsx      # 历史记录
│   │   ├── KnowledgeScreen.tsx    # 知识库
│   │   └── SettingsScreen.tsx     # 设置
│   ├── components/
│   │   ├── RiskBadge.tsx          # 风险徽章
│   │   ├── ScoreDisplay.tsx       # 评分显示
│   │   ├── ContractCard.tsx       # 合同卡片
│   │   ├── ClauseCard.tsx         # 条款卡片
│   │   ├── ConnectionBar.tsx      # 连接状态条
│   │   ├── SearchInput.tsx        # 搜索框
│   │   ├── FilterChips.tsx        # 筛选 Chips
│   │   ├── FilterTabs.tsx         # 筛选 Tab
│   │   ├── EmptyState.tsx         # 空状态
│   │   ├── Toast.tsx              # Toast 提示
│   │   └── Dialog.tsx             # 确认对话框
│   ├── context/
│   │   ├── ThemeContext.tsx        # 主题上下文
│   │   └── ConnectionContext.tsx   # 连接上下文
│   ├── services/
│   │   ├── api.ts                 # HTTP API 封装
│   │   ├── websocket.ts           # WebSocket 通信
│   │   └── storage.ts             # AsyncStorage 封装
│   ├── theme/
│   │   ├── colors.ts              # 颜色定义（亮色/暗色）
│   │   ├── spacing.ts             # 间距定义
│   │   └── typography.ts          # 字体定义
│   ├── types/
│   │   └── index.ts               # TypeScript 类型定义
│   └── utils/
│       ├── helpers.ts             # 工具函数
│       └── constants.ts           # 常量定义
```

---

## 后端 API 参考

### 合同相关

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/contracts/` | 合同列表（支持 `search`, `type`, `risk` 查询参数） |
| GET | `/api/contracts/{id}` | 合同详情 + 分析结果 + 条款列表 |
| POST | `/api/contracts/analyze` | 上传并分析合同（multipart form: `file` + `contract_type`） |
| POST | `/api/contracts/{id}/feedback` | 提交反馈（form: `clause_analysis_id`, `feedback`=correct/incorrect） |

### 知识库

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/knowledge/rules` | 规则列表（支持 `search`, `category` 查询参数） |
| GET | `/api/knowledge/stats` | 知识库统计（返回规则数、法规数） |
| GET | `/api/knowledge/laws` | 法规列表 |

### WebSocket

| 路径 | 说明 |
|------|------|
| `ws://{host}:{port}/ws/client` | 手机端实时通信 |

**WebSocket 消息格式：**

客户端发送：
```json
// 文本合同分析
{ "type": "analyze", "text": "合同全文...", "contractType": "租赁合同" }

// 心跳
{ "type": "ping" }
```

服务端响应：
```json
// 进度
{ "type": "progress", "step": 1, "total": 5, "message": "正在识别文字..." }

// 结果
{
  "type": "result",
  "data": {
    "contractId": "xxx",
    "score": 35,
    "riskLevel": "red",
    "summary": "...",
    "redCount": 3, "yellowCount": 2, "greenCount": 5,
    "clauses": [
      {
        "id": "cl001",
        "title": "租金及支付方式",
        "content": "...",
        "riskLevel": "red",
        "riskType": "违约金过高",
        "riskSummary": "滞纳金按日5%计算",
        "plainExplanation": "逾期一天就要多付..."
      }
    ]
  }
}
```

### 文件上传分析（HTTP 方式）

`POST /api/contracts/analyze` 接收 multipart form-data：
- `file`：文件（PDF/图片，最大 20MB）
- `contract_type`：合同类型（可选，默认"其他"）

返回：
```json
{ "success": true, "contractId": "xxx", "score": 35, "riskLevel": "red" }
```

---

## 数据模型

### 合同（Contract）

```typescript
interface Contract {
  id: string;
  title: string;
  type: string;           // 中文类型名
  typeEn: string;         // 英文类型名
  score: number;          // 0-100
  riskLevel: 'red' | 'yellow' | 'green';
  redCount: number;
  yellowCount: number;
  greenCount: number;
  createdAt: string;      // YYYY-MM-DD
  status: 'analyzed' | 'pending';
  model: string;
  summary: string;
  recommendation: 'sign' | 'negotiate_first' | 'reject';
  fullText: string;       // OCR 原文
  clauses: ClauseAnalysis[];
}
```

### 条款分析（ClauseAnalysis）

```typescript
interface ClauseAnalysis {
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
```

### 知识库规则

```typescript
interface KnowledgeRule {
  id: string;
  category: string;       // 通用 | 租赁 | 劳动 | 装修 | 外包
  text: string;
  confidence: number;     // 0.0-1.0
  source: 'manual' | 'auto_learned';
  usageCount: number;
}
```

### 合同类型映射

```typescript
const TYPE_EN_MAP: Record<string, string> = {
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
```

---

## 设计系统

### 颜色（亮色主题）

```typescript
export const lightColors = {
  // 背景
  background: '#ffffff',
  surface: '#ffffff',
  surfaceHover: '#f7f7f5',
  muted: '#f1f1ef',
  input: '#ffffff',

  // 文字
  text: '#1a1a1a',
  textSecondary: '#6b6b6b',
  textTertiary: '#9b9b9b',
  textInverse: '#ffffff',

  // 边框
  border: '#e8e8e5',
  borderSubtle: '#f0f0ee',

  // 强调色
  accent: '#2383e2',
  accentSubtle: '#e8f0fe',

  // 风险色
  riskRed: '#e53e3e',
  riskRedBg: '#fff5f5',
  riskRedBorder: '#fed7d7',
  riskRedText: '#c53030',

  riskYellow: '#d69e2e',
  riskYellowBg: '#fffff0',
  riskYellowBorder: '#fefcbf',
  riskYellowText: '#b7791f',

  riskGreen: '#38a169',
  riskGreenBg: '#f0fff4',
  riskGreenBorder: '#c6f6d5',
  riskGreenText: '#276749',

  // 阴影
  shadow: 'rgba(0,0,0,0.06)',
  shadowMedium: 'rgba(0,0,0,0.08)',
};
```

### 颜色（暗色主题）

```typescript
export const darkColors = {
  // 背景
  background: '#191919',
  surface: '#232323',
  surfaceHover: '#2a2a2a',
  muted: '#2a2a2a',
  input: '#282828',

  // 文字
  text: '#ebebeb',
  textSecondary: '#999999',
  textTertiary: '#666666',
  textInverse: '#ffffff',

  // 边框
  border: '#333333',
  borderSubtle: '#2a2a2a',

  // 强调色
  accent: '#529cca',
  accentSubtle: '#1a2a35',

  // 风险色
  riskRed: '#fc8181',
  riskRedBg: '#2d1b1b',
  riskRedBorder: '#5c2626',
  riskRedText: '#feb2b2',

  riskYellow: '#f6e05e',
  riskYellowBg: '#2d2b1b',
  riskYellowBorder: '#5c5626',
  riskYellowText: '#faf089',

  riskGreen: '#68d391',
  riskGreenBg: '#1b2d1f',
  riskGreenBorder: '#265c33',
  riskGreenText: '#9ae6b4',

  // 阴影
  shadow: 'rgba(0,0,0,0.2)',
  shadowMedium: 'rgba(0,0,0,0.3)',
};
```

### 间距

```typescript
export const spacing = {
  xs: 4,
  sm: 8,
  md: 12,
  lg: 16,
  xl: 20,
  xxl: 24,
  xxxl: 32,
  huge: 40,
};
```

### 圆角

```typescript
export const borderRadius = {
  sm: 6,
  md: 8,
  lg: 12,
  xl: 16,
  full: 9999,
};
```

### 字体大小

```typescript
export const fontSize = {
  xs: 11,
  sm: 13,
  base: 15,
  md: 16,
  lg: 18,
  xl: 22,
  xxl: 28,
  display: 48,
};
```

---

## 页面规格

### 0. 全局布局

**导航结构：**
```typescript
// AppNavigator.tsx
// 底部 Tab 导航：首页 | 历史 | 知识库 | 设置
// Stack 导航嵌套：分析中、结果页在 Tab 之外

const Tab = createBottomTabNavigator();
const Stack = createStackNavigator();

function HomeStack() {
  return (
    <Stack.Navigator screenOptions={{ headerShown: false }}>
      <Stack.Screen name="HomeMain" component={HomeScreen} />
      <Stack.Screen name="Analysis" component={AnalysisScreen} />
      <Stack.Screen name="Result" component={ResultScreen} />
    </Stack.Navigator>
  );
}

function MainTabs() {
  return (
    <Tab.Navigator screenOptions={{ headerShown: false }}>
      <Tab.Screen name="Home" component={HomeStack} />
      <Tab.Screen name="History" component={HistoryScreen} />
      <Tab.Screen name="Knowledge" component={KnowledgeScreen} />
      <Tab.Screen name="Settings" component={SettingsScreen} />
    </Tab.Navigator>
  );
}
```

**Tab 栏样式：**
- 高度：56px + 底部安全区
- 背景：半透明 + 模糊（iOS `blurRadius`，Android 半透明）
- 选中态：accent 色图标 + 文字
- 未选中：textTertiary
- 图标：Ionicons，22px
- 文字：10px

**页面容器：**
```typescript
// 每个页面用 SafeAreaView + ScrollView
<SafeAreaView style={styles.container}>
  <ScrollView contentContainerStyle={styles.content}>
    {/* 页面内容 */}
  </ScrollView>
</SafeAreaView>
```

---

### 1. 首页（HomeScreen）

**功能：** 拍照/选择文件上传合同、显示连接状态、最近分析列表

**布局：**
- 顶部标题栏：标题「合同红绿灯」+ 主题切换按钮
- 上传区：两个并排大按钮（高度 120px，圆角 16px）
  - 「拍照上传」：绿色渐变背景，白色相机图标 + 文字
  - 「选择文件」：浅灰色背景，灰色文件夹图标 + 文字
- 连接状态条：全宽圆角条，高度 40px，三种状态
- 「最近分析」标题 + 最近 5 条合同卡片
- 空状态

**文件上传流程：**
1. 用户点击按钮 → `expo-document-picker` 或 `expo-camera`
2. 调用 `POST /api/contracts/analyze`（multipart form-data）
3. 显示 loading 状态（ActivityIndicator）
4. 成功 → 跳转结果页
5. 失败 → Toast 提示

**实现要点：**
```typescript
// 拍照
import * as ImagePicker from 'expo-image-picker';

const takePhoto = async () => {
  const result = await ImagePicker.launchCameraAsync({
    mediaTypes: ['images'],
    quality: 0.8,
  });
  if (!result.canceled) {
    uploadAndAnalyze(result.assets[0].uri);
  }
};

// 选择文件
import * as DocumentPicker from 'expo-document-picker';

const pickFile = async () => {
  const result = await DocumentPicker.getDocumentAsync({
    type: ['image/*', 'application/pdf'],
  });
  if (!result.canceled) {
    uploadAndAnalyze(result.assets[0].uri);
  }
};
```

---

### 2. 分析中页（AnalysisScreen）

**功能：** 显示分析进度和实时结果

**布局：**
- 顶部标题栏：返回按钮 + 标题「分析中」
- 进度区（居中）：
  - 当前步骤文字 + ActivityIndicator
  - 步骤进度条：5 个圆点 + 连线
  - 步骤标签：OCR → 拆解 → 分析 → 建议 → 评分
  - 总体进度条 + 百分比
- 实时结果区：逐条滑入的分析卡片
- 完成后：绿色横幅「✅ 分析完成，点击查看结果」

**进度回调（WebSocket）：**
```typescript
// 使用 useEffect 监听 WebSocket 消息
useEffect(() => {
  const ws = new WebSocket(`ws://${host}:${port}/ws/client`);

  ws.onmessage = (event) => {
    const msg = JSON.parse(event.data);
    if (msg.type === 'progress') {
      setCurrentStep(msg.step);
      setProgress(Math.round((msg.step / msg.total) * 100));
      setMessage(msg.message);
    } else if (msg.type === 'result') {
      setResult(msg.data);
      setIsComplete(true);
    }
  };

  return () => ws.close();
}, []);
```

**动画：**
```typescript
// 使用 Animated API 实现卡片滑入
const translateY = useRef(new Animated.Value(20)).current;

useEffect(() => {
  Animated.spring(translateY, {
    toValue: 0,
    useNativeDriver: true,
  }).start();
}, [clause]);
```

---

### 3. 分析结果页（ResultScreen）

**功能：** 展示完整分析结果

**布局：**
- 顶部标题栏：返回按钮 + 标题「分析结果」
- 总览卡片：
  - 大号评分数字（48px，颜色跟随分数）
  - 「综合评分」文字
  - 风险分布：🔴 3 🟡 2 🟢 5 + 分布条
  - 建议文字
- 条款筛选 Tab：全部(N) | 红(N) | 黄(N) | 绿(N)
- 条款卡片列表：
  - 左侧 4px 风险色条
  - 顶部：条款编号 + 风险徽章
  - 问题摘要
  - 💡 大白话区块
  - 📝 修改建议（可折叠）
  - ⚖️ 法律依据（可折叠）
  - 👍 准确 / 👎 不准确 反馈按钮
- 底部操作栏：分享报告 + 重新分析

**评分颜色：**
```typescript
const getScoreColor = (score: number) => {
  if (score >= 70) return colors.riskGreen;
  if (score >= 50) return colors.riskYellow;
  return colors.riskRed;
};
```

**分享功能：**
```typescript
import * as Sharing from 'expo-sharing';

const handleShare = async () => {
  if (await Sharing.isAvailableAsync()) {
    await Sharing.shareAsync(
      `合同分析报告：${contract.title}，评分 ${contract.score}`
    );
  }
};
```

---

### 4. 历史记录页（HistoryScreen）

**功能：** 展示所有过往分析记录

**布局：**
- 顶部标题栏：标题「历史记录」
- 搜索框
- 筛选 Chips：全部 | 🔴高风险 | 🟡中风险 | 🟢低风险
- 按月份分组：月份标题 + 记录卡片
- 空状态

**数据来源：**
```typescript
// 从 AsyncStorage 获取缓存的分析记录
const loadHistory = async () => {
  const data = await AsyncStorage.getItem('analyses');
  if (data) {
    setContracts(JSON.parse(data));
  }
};
```

---

### 5. 知识库页（KnowledgeScreen）

**功能：** 查看规则库和法规库（只读）

**布局：**
- 顶部标题栏：标题「知识库」
- 统计概览条：「N 条规则 | M 部法规」
- Tab 栏：规则库 | 法规库
- 规则卡片列表
- 法规列表

**数据来源：**
```typescript
// 从 API 获取规则
const loadRules = async () => {
  const response = await fetch(`${baseUrl}/api/knowledge/rules`);
  const data = await response.json();
  setRules(data);
};
```

---

### 6. 设置页（SettingsScreen）

**功能：** 管理连接和基本配置

**布局：**
- 顶部标题栏：标题「设置」
- 服务器连接组：
  - 连接方式 Segmented Control：局域网直连 | 云端 API
  - 局域网直连：IP 地址输入 + 端口输入 + 测试连接按钮
  - 云端 API：API 地址输入 + API Key 输入
- 外观组：主题 Segmented Control：自动 | 亮色 | 暗色
- 数据管理组：清除本地缓存 + 导出分析记录
- 关于组：版本号 + 项目名称

**连接测试：**
```typescript
const testConnection = async (host: string, port: string) => {
  try {
    const response = await fetch(
      `http://${host}:${port}/api/contracts/`,
      { signal: AbortSignal.timeout(3000) }
    );
    return response.ok;
  } catch {
    return false;
  }
};
```

**主题切换：**
```typescript
import { useColorScheme } from 'react-native';

const colorScheme = useColorScheme(); // 'light' | 'dark'

// 根据主题选择颜色
const colors = colorScheme === 'dark' ? darkColors : lightColors;
```

---

## JS 模块详细规格

### `src/services/api.ts` — HTTP API 封装

```typescript
import AsyncStorage from '@react-native-async-storage/async-storage';

// 获取基础 URL
const getBaseUrl = async (): Promise<string> => {
  const host = await AsyncStorage.getItem('serverHost') || '192.168.1.100';
  const port = await AsyncStorage.getItem('serverPort') || '8080';
  return `http://${host}:${port}`;
};

// 合同列表
export const listContracts = async (params?: {
  search?: string;
  type?: string;
  risk?: string;
}) => {
  const baseUrl = await getBaseUrl();
  const query = new URLSearchParams(params).toString();
  const response = await fetch(`${baseUrl}/api/contracts/?${query}`);
  return response.json();
};

// 合同详情
export const getContract = async (id: string) => {
  const baseUrl = await getBaseUrl();
  const response = await fetch(`${baseUrl}/api/contracts/${id}`);
  return response.json();
};

// 上传并分析合同
export const uploadAndAnalyze = async (
  fileUri: string,
  contractType: string = ''
) => {
  const baseUrl = await getBaseUrl();
  const formData = new FormData();

  // 获取文件名和类型
  const filename = fileUri.split('/').pop() || 'contract.pdf';
  const type = filename.endsWith('.pdf')
    ? 'application/pdf'
    : 'image/jpeg';

  formData.append('file', {
    uri: fileUri,
    name: filename,
    type,
  } as any);

  if (contractType) {
    formData.append('contract_type', contractType);
  }

  const response = await fetch(`${baseUrl}/api/contracts/analyze`, {
    method: 'POST',
    body: formData,
    headers: {
      'Content-Type': 'multipart/form-data',
    },
  });

  return response.json();
};

// 提交反馈
export const submitFeedback = async (
  contractId: string,
  clauseAnalysisId: string,
  feedback: 'correct' | 'incorrect'
) => {
  const baseUrl = await getBaseUrl();
  const formData = new FormData();
  formData.append('clause_analysis_id', clauseAnalysisId);
  formData.append('feedback', feedback);

  const response = await fetch(
    `${baseUrl}/api/contracts/${contractId}/feedback`,
    { method: 'POST', body: formData }
  );

  return response.json();
};

// 知识库规则
export const listRules = async (params?: {
  search?: string;
  category?: string;
}) => {
  const baseUrl = await getBaseUrl();
  const query = new URLSearchParams(params).toString();
  const response = await fetch(`${baseUrl}/api/knowledge/rules?${query}`);
  return response.json();
};

// 知识库统计
export const getKnowledgeStats = async () => {
  const baseUrl = await getBaseUrl();
  const response = await fetch(`${baseUrl}/api/knowledge/stats`);
  return response.json();
};

// 法规列表
export const listLaws = async () => {
  const baseUrl = await getBaseUrl();
  const response = await fetch(`${baseUrl}/api/knowledge/laws`);
  return response.json();
};
```

### `src/services/websocket.ts` — WebSocket 通信

```typescript
export type WSMessage =
  | { type: 'progress'; step: number; total: number; message: string }
  | { type: 'result'; data: Contract }
  | { type: 'pong' };

export class ClauseWebSocket {
  private ws: WebSocket | null = null;
  private heartbeatInterval: NodeJS.Timeout | null = null;

  constructor(
    private host: string,
    private port: string
  ) {}

  connect(
    onMessage: (msg: WSMessage) => void,
    onError: (error: Event) => void
  ) {
    this.ws = new WebSocket(`ws://${this.host}:${this.port}/ws/client`);

    this.ws.onmessage = (event) => {
      const msg = JSON.parse(event.data) as WSMessage;
      onMessage(msg);
    };

    this.ws.onerror = onError;

    // 心跳
    this.heartbeatInterval = setInterval(() => {
      if (this.ws?.readyState === WebSocket.OPEN) {
        this.ws.send(JSON.stringify({ type: 'ping' }));
      }
    }, 30000);
  }

  sendAnalyze(text: string, contractType: string = '') {
    if (this.ws?.readyState === WebSocket.OPEN) {
      this.ws.send(JSON.stringify({
        type: 'analyze',
        text,
        contractType,
      }));
    }
  }

  disconnect() {
    if (this.heartbeatInterval) {
      clearInterval(this.heartbeatInterval);
    }
    this.ws?.close();
  }
}
```

### `src/services/storage.ts` — AsyncStorage 封装

```typescript
import AsyncStorage from '@react-native-async-storage/async-storage';

const ANALYSES_KEY = 'analyses';
const SETTINGS_KEY = 'settings';

// 分析记录
export const saveAnalysis = async (analysis: Contract) => {
  const existing = await getAnalyses();
  const updated = [analysis, ...existing.filter(a => a.id !== analysis.id)];
  // 只保留最近 20 条
  await AsyncStorage.setItem(
    ANALYSES_KEY,
    JSON.stringify(updated.slice(0, 20))
  );
};

export const getAnalyses = async (): Promise<Contract[]> => {
  const data = await AsyncStorage.getItem(ANALYSES_KEY);
  return data ? JSON.parse(data) : [];
};

export const getAnalysis = async (id: string): Promise<Contract | null> => {
  const analyses = await getAnalyses();
  return analyses.find(a => a.id === id) || null;
};

export const deleteAnalysis = async (id: string) => {
  const existing = await getAnalyses();
  await AsyncStorage.setItem(
    ANALYSES_KEY,
    JSON.stringify(existing.filter(a => a.id !== id))
  );
};

export const clearAnalyses = async () => {
  await AsyncStorage.removeItem(ANALYSES_KEY);
};

// 设置
export const getSetting = async (key: string): Promise<string | null> => {
  return AsyncStorage.getItem(key);
};

export const setSetting = async (key: string, value: string) => {
  await AsyncStorage.setItem(key, value);
};

export const getAllSettings = async () => {
  const keys = ['theme', 'serverHost', 'serverPort', 'connectionType'];
  const values = await AsyncStorage.multiGet(keys);
  return Object.fromEntries(values);
};
```

### `src/theme/colors.ts` — 主题颜色

```typescript
import { useColorScheme } from 'react-native';

const lightColors = {
  background: '#ffffff',
  surface: '#ffffff',
  surfaceHover: '#f7f7f5',
  muted: '#f1f1ef',
  input: '#ffffff',
  text: '#1a1a1a',
  textSecondary: '#6b6b6b',
  textTertiary: '#9b9b9b',
  textInverse: '#ffffff',
  border: '#e8e8e5',
  borderSubtle: '#f0f0ee',
  accent: '#2383e2',
  accentSubtle: '#e8f0fe',
  riskRed: '#e53e3e',
  riskRedBg: '#fff5f5',
  riskRedBorder: '#fed7d7',
  riskRedText: '#c53030',
  riskYellow: '#d69e2e',
  riskYellowBg: '#fffff0',
  riskYellowBorder: '#fefcbf',
  riskYellowText: '#b7791f',
  riskGreen: '#38a169',
  riskGreenBg: '#f0fff4',
  riskGreenBorder: '#c6f6d5',
  riskGreenText: '#276749',
};

const darkColors = {
  background: '#191919',
  surface: '#232323',
  surfaceHover: '#2a2a2a',
  muted: '#2a2a2a',
  input: '#282828',
  text: '#ebebeb',
  textSecondary: '#999999',
  textTertiary: '#666666',
  textInverse: '#ffffff',
  border: '#333333',
  borderSubtle: '#2a2a2a',
  accent: '#529cca',
  accentSubtle: '#1a2a35',
  riskRed: '#fc8181',
  riskRedBg: '#2d1b1b',
  riskRedBorder: '#5c2626',
  riskRedText: '#feb2b2',
  riskYellow: '#f6e05e',
  riskYellowBg: '#2d2b1b',
  riskYellowBorder: '#5c5626',
  riskYellowText: '#faf089',
  riskGreen: '#68d391',
  riskGreenBg: '#1b2d1f',
  riskGreenBorder: '#265c33',
  riskGreenText: '#9ae6b4',
};

export type Colors = typeof lightColors;

export const useColors = (): Colors => {
  const colorScheme = useColorScheme();
  return colorScheme === 'dark' ? darkColors : lightColors;
};
```

### `src/components/ClauseCard.tsx` — 条款卡片

```typescript
import React, { useState } from 'react';
import {
  View,
  Text,
  TouchableOpacity,
  StyleSheet,
} from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import { useColors } from '../theme/colors';
import { spacing, borderRadius, fontSize } from '../theme/spacing';
import { ClauseAnalysis } from '../types';
import RiskBadge from './RiskBadge';

interface Props {
  clause: ClauseAnalysis;
  onFeedback?: (feedback: 'correct' | 'incorrect') => void;
}

export default function ClauseCard({ clause, onFeedback }: Props) {
  const colors = useColors();
  const [showSuggestion, setShowSuggestion] = useState(false);
  const [showLegal, setShowLegal] = useState(false);
  const [feedback, setFeedback] = useState<'correct' | 'incorrect' | null>(null);

  const styles = createStyles(colors);

  const handleFeedback = (type: 'correct' | 'incorrect') => {
    setFeedback(feedback === type ? null : type);
    onFeedback?.(type);
  };

  return (
    <View style={styles.card}>
      {/* 左侧风险色条 */}
      <View
        style={[
          styles.riskBar,
          { backgroundColor: colors[`risk${clause.riskLevel.charAt(0).toUpperCase() + clause.riskLevel.slice(1)}` as keyof typeof colors] },
        ]}
      />

      <View style={styles.content}>
        {/* 头部 */}
        <View style={styles.header}>
          <Text style={styles.title}>
            {clause.clauseNumber} {clause.clauseTitle}
          </Text>
          <RiskBadge level={clause.riskLevel} />
        </View>

        {/* 问题摘要 */}
        {clause.riskSummary ? (
          <Text style={styles.summary}>{clause.riskSummary}</Text>
        ) : null}

        {/* 大白话 */}
        {clause.plainExplanation ? (
          <View style={styles.explainBox}>
            <Text style={styles.explainLabel}>💡 大白话</Text>
            <Text style={styles.explainText}>{clause.plainExplanation}</Text>
          </View>
        ) : null}

        {/* 修改建议 */}
        {clause.suggestedClause ? (
          <>
            <TouchableOpacity
              style={styles.expandButton}
              onPress={() => setShowSuggestion(!showSuggestion)}
            >
              <Text style={styles.expandButtonText}>📝 修改建议</Text>
              <Ionicons
                name={showSuggestion ? 'chevron-down' : 'chevron-forward'}
                size={16}
                color={colors.accent}
              />
            </TouchableOpacity>
            {showSuggestion ? (
              <View style={styles.suggestionBox}>
                <Text style={styles.suggestionText}>{clause.suggestedClause}</Text>
              </View>
            ) : null}
          </>
        ) : null}

        {/* 法律依据 */}
        {clause.legalBasis ? (
          <>
            <TouchableOpacity
              style={styles.expandButton}
              onPress={() => setShowLegal(!showLegal)}
            >
              <Text style={styles.expandButtonText}>⚖️ 法律依据</Text>
              <Ionicons
                name={showLegal ? 'chevron-down' : 'chevron-forward'}
                size={16}
                color={colors.accent}
              />
            </TouchableOpacity>
            {showLegal ? (
              <View style={styles.legalBox}>
                <Text style={styles.legalText}>{clause.legalBasis}</Text>
              </View>
            ) : null}
          </>
        ) : null}

        {/* 反馈按钮 */}
        <View style={styles.feedbackRow}>
          <TouchableOpacity
            style={[
              styles.feedbackButton,
              feedback === 'correct' && styles.feedbackButtonActive,
            ]}
            onPress={() => handleFeedback('correct')}
          >
            <Ionicons
              name="thumbs-up"
              size={14}
              color={feedback === 'correct' ? colors.accent : colors.textSecondary}
            />
            <Text
              style={[
                styles.feedbackText,
                feedback === 'correct' && styles.feedbackTextActive,
              ]}
            >
              准确
            </Text>
          </TouchableOpacity>

          <TouchableOpacity
            style={[
              styles.feedbackButton,
              feedback === 'incorrect' && styles.feedbackButtonActive,
            ]}
            onPress={() => handleFeedback('incorrect')}
          >
            <Ionicons
              name="thumbs-down"
              size={14}
              color={feedback === 'incorrect' ? colors.accent : colors.textSecondary}
            />
            <Text
              style={[
                styles.feedbackText,
                feedback === 'incorrect' && styles.feedbackTextActive,
              ]}
            >
              不准确
            </Text>
          </TouchableOpacity>
        </View>
      </View>
    </View>
  );
}

const createStyles = (colors: Colors) =>
  StyleSheet.create({
    card: {
      flexDirection: 'row',
      backgroundColor: colors.surface,
      borderRadius: borderRadius.lg,
      borderWidth: 1,
      borderColor: colors.borderSubtle,
      marginBottom: spacing.md,
      overflow: 'hidden',
    },
    riskBar: {
      width: 4,
    },
    content: {
      flex: 1,
      padding: spacing.lg,
    },
    header: {
      flexDirection: 'row',
      alignItems: 'center',
      gap: spacing.sm,
      marginBottom: spacing.md,
    },
    title: {
      flex: 1,
      fontSize: fontSize.base,
      fontWeight: '700',
      color: colors.text,
    },
    summary: {
      fontSize: fontSize.sm,
      color: colors.textSecondary,
      marginBottom: spacing.md,
      lineHeight: 20,
    },
    explainBox: {
      backgroundColor: colors.riskYellowBg,
      borderWidth: 1,
      borderColor: colors.riskYellowBorder,
      borderRadius: borderRadius.md,
      padding: spacing.md,
      marginBottom: spacing.md,
    },
    explainLabel: {
      fontWeight: '600',
      marginBottom: 2,
      color: colors.text,
    },
    explainText: {
      fontSize: fontSize.sm,
      color: colors.text,
      lineHeight: 22,
    },
    expandButton: {
      flexDirection: 'row',
      alignItems: 'center',
      gap: spacing.sm,
      paddingVertical: spacing.md,
      borderTopWidth: 1,
      borderTopColor: colors.borderSubtle,
    },
    expandButtonText: {
      flex: 1,
      fontSize: fontSize.sm,
      fontWeight: '500',
      color: colors.accent,
    },
    suggestionBox: {
      backgroundColor: colors.accentSubtle,
      borderRadius: borderRadius.md,
      padding: spacing.md,
      marginBottom: spacing.md,
    },
    suggestionText: {
      fontSize: fontSize.sm,
      color: colors.text,
      lineHeight: 22,
    },
    legalBox: {
      padding: spacing.md,
    },
    legalText: {
      fontSize: fontSize.sm,
      color: colors.textTertiary,
      fontStyle: 'italic',
      lineHeight: 22,
    },
    feedbackRow: {
      flexDirection: 'row',
      gap: spacing.sm,
      paddingTop: spacing.md,
      borderTopWidth: 1,
      borderTopColor: colors.borderSubtle,
    },
    feedbackButton: {
      flexDirection: 'row',
      alignItems: 'center',
      gap: 4,
      paddingHorizontal: spacing.md,
      paddingVertical: spacing.sm,
      borderRadius: borderRadius.full,
      borderWidth: 1,
      borderColor: colors.border,
      backgroundColor: colors.surface,
    },
    feedbackButtonActive: {
      backgroundColor: colors.accentSubtle,
      borderColor: colors.accent,
    },
    feedbackText: {
      fontSize: fontSize.xs,
      fontWeight: '500',
      color: colors.textSecondary,
    },
    feedbackTextActive: {
      color: colors.accent,
    },
  });
```

---

## 实现顺序

### Phase 1：项目初始化

1. 使用 `npx create-expo-app mobile --template blank-typescript` 初始化项目
2. 安装依赖：
   ```bash
   npx expo install @react-navigation/native @react-navigation/bottom-tabs @react-navigation/stack
   npx expo install react-native-screens react-native-safe-area-context
   npx expo install @react-native-async-storage/async-storage
   npx expo install expo-camera expo-document-picker expo-file-system expo-sharing
   npx expo install @expo/vector-icons
   ```
3. 创建 `src/` 目录结构
4. 配置 TypeScript

### Phase 2：基础框架

5. 创建 `src/theme/colors.ts` + `spacing.ts` + `typography.ts`
6. 创建 `src/context/ThemeContext.tsx`
7. 创建 `src/services/api.ts` + `storage.ts`
8. 创建 `src/types/index.ts`
9. 创建 `src/navigation/AppNavigator.tsx`
10. 创建 `App.tsx` 入口
11. 验证：空壳页面能正常切换 Tab

### Phase 3：首页 + 上传

12. 实现 `src/screens/HomeScreen.tsx`
13. 实现文件选择和拍照功能
14. 实现文件上传 API 调用
15. 实现连接状态检测和显示
16. 实现最近分析列表

### Phase 4：结果页

17. 实现 `src/screens/ResultScreen.tsx`
18. 实现总览卡片 + 条款筛选
19. 实现条款卡片组件
20. 实现折叠展开功能
21. 实现反馈按钮

### Phase 5：分析中页

22. 实现 `src/screens/AnalysisScreen.tsx`
23. 实现步骤进度条
24. 实现实时结果动画
25. 实现 WebSocket 连接

### Phase 6：其他页面

26. 实现 `src/screens/HistoryScreen.tsx`
27. 实现 `src/screens/KnowledgeScreen.tsx`
28. 实现 `src/screens/SettingsScreen.tsx`

### Phase 7：完善

29. 完善错误处理和 loading 状态
30. 优化性能（FlatList、useMemo、useCallback）
31. 测试和调试

---

## 关键实现细节

### 文件上传

```typescript
import * as DocumentPicker from 'expo-document-picker';

export const pickAndUpload = async () => {
  const result = await DocumentPicker.getDocumentAsync({
    type: ['image/*', 'application/pdf'],
  });

  if (result.canceled) return null;

  const file = result.assets[0];
  return uploadAndAnalyze(file.uri);
};
```

### 搜索防抖

```typescript
import { useCallback, useRef } from 'react';

export const useDebounce = <T extends (...args: any[]) => void>(
  callback: T,
  delay: number = 300
) => {
  const timerRef = useRef<NodeJS.Timeout>();

  return useCallback(
    (...args: Parameters<T>) => {
      if (timerRef.current) {
        clearTimeout(timerRef.current);
      }
      timerRef.current = setTimeout(() => callback(...args), delay);
    },
    [callback, delay]
  );
};
```

### 性能优化

```typescript
// 使用 FlatList 替代 ScrollView + map
<FlatList
  data={contracts}
  keyExtractor={(item) => item.id}
  renderItem={({ item }) => <ContractCard contract={item} />}
  contentContainerStyle={styles.list}
/>

// 使用 useMemo 缓存计算结果
const filteredClauses = useMemo(() => {
  if (filter === 'all') return clauses;
  return clauses.filter(c => c.riskLevel === filter);
}, [clauses, filter]);

// 使用 useCallback 缓存回调
const handleFeedback = useCallback((clauseId: string, feedback: string) => {
  submitFeedback(contractId, clauseId, feedback);
}, [contractId]);
```

---

## 验收标准

### 基础功能
- [ ] 5 个页面（首页/分析中/结果/历史/设置）+ 知识库页均可正常切换
- [ ] 底部 Tab 导航栏固定在底部
- [ ] 亮色/暗色主题切换正常
- [ ] 拍照上传和文件选择按钮功能正常
- [ ] 连接状态条显示正确状态

### 分析流程
- [ ] 文件上传 → 分析 → 结果展示的完整流程
- [ ] 分析进度页步骤进度条和实时结果正确显示
- [ ] 结果页总览卡片评分和风险分布正确
- [ ] 条款卡片可折叠展开修改建议和法律依据
- [ ] 反馈按钮可点击并调用后端 API

### 数据
- [ ] 历史记录从后端 API 获取并缓存到 AsyncStorage
- [ ] 历史记录按月份分组，搜索和筛选可用
- [ ] 知识库页规则列表从后端 API 获取
- [ ] 设置页连接配置可编辑并持久化

### 体验
- [ ] 所有触控区域 >= 44px
- [ ] 刘海屏 safe-area 适配
- [ ] 所有文本为中文
- [ ] 暗色主题下所有颜色正确
- [ ] 按钮点击有视觉反馈
- [ ] Toast 3 秒自动消失
- [ ] 搜索输入防抖 300ms
- [ ] 文件上传有 loading 状态
- [ ] 分析超时有错误提示

### 性能
- [ ] FlatList 用于长列表
- [ ] useMemo/useCallback 优化重渲染
- [ ] 图片使用缓存
- [ ] 启动时间 < 2 秒

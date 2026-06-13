import React, { useState, useEffect, useRef } from 'react';
import {
  View,
  Text,
  ScrollView,
  ActivityIndicator,
  StyleSheet,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { useThemeContext } from '../contexts/ThemeContext';
import { useConnectionContext } from '../contexts/ConnectionContext';
import { useToastContext } from '../contexts/ToastContext';
import { spacing, fontSize } from '../theme';
import TopBar from '../components/TopBar';
import StepProgress from '../components/StepProgress';
import MiniClauseCard from '../components/MiniClauseCard';
import Dialog from '../components/Dialog';
import { analyzeContract } from '../services/api';
import { ClauseWebSocket } from '../services/websocket';
import { addToHistory } from '../services/storage';
import type { ClauseData, WSMessage } from '../types/api';
import type { AnalysisScreenProps } from '../types/navigation';

const ANALYSIS_STEPS = [
  { key: 'ocr', label: 'OCR' },
  { key: 'split', label: '拆解' },
  { key: 'analyze', label: '分析' },
  { key: 'suggest', label: '建议' },
  { key: 'score', label: '评分' },
];

export default function AnalysisScreen({ navigation, route }: AnalysisScreenProps) {
  const { filePath, fileName, contractType } = route.params;
  const { colors } = useThemeContext();
  const { wsUrl, status } = useConnectionContext();
  const { showToast } = useToastContext();

  const [currentStep, setCurrentStep] = useState(0);
  const [progress, setProgress] = useState(0);
  const [message, setMessage] = useState('准备中...');
  const [isComplete, setIsComplete] = useState(false);
  const [clauses, setClauses] = useState<Partial<ClauseData>[]>([]);
  const [contractId, setContractId] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [showLeaveDialog, setShowLeaveDialog] = useState(false);
  const [isAnalyzing, setIsAnalyzing] = useState(false);

  const wsRef = useRef<ClauseWebSocket | null>(null);

  useEffect(() => {
    startAnalysis();
    return () => {
      wsRef.current?.disconnect();
    };
  }, []);

  const startAnalysis = async () => {
    setIsAnalyzing(true);
    setError(null);

    // 如果已连接且有 WebSocket URL，尝试实时进度
    if (status === 'connected' && wsUrl) {
      startWebSocketAnalysis();
    } else {
      startHttpAnalysis();
    }
  };

  const startWebSocketAnalysis = () => {
    const ws = new ClauseWebSocket(wsUrl);
    wsRef.current = ws;

    ws.connect(
      (msg: WSMessage) => {
        if (msg.type === 'progress') {
          setCurrentStep(msg.step);
          setProgress(Math.round((msg.step / msg.total) * 100));
          setMessage(msg.message);
        } else if (msg.type === 'result') {
          setContractId(msg.data.contractId);
          setClauses(msg.data.clauses);
          setProgress(100);
          setIsComplete(true);
          setIsAnalyzing(false);
          saveToHistory(msg.data);
        }
      },
      () => {
        // WebSocket 失败，降级到 HTTP
        startHttpAnalysis();
      }
    );
  };

  const startHttpAnalysis = async () => {
    try {
      setMessage('正在上传并分析合同...');
      setProgress(10);

      const result = await analyzeContract(filePath, contractType || '');

      if (result.success) {
        setContractId(result.contractId);
        setProgress(100);
        setIsComplete(true);
        setIsAnalyzing(false);

        saveToHistory({
          contractId: result.contractId,
          score: result.score,
          riskLevel: result.riskLevel as any,
        });
      } else {
        setError(result.error || '分析失败');
        setIsAnalyzing(false);
      }
    } catch (err) {
      setError('网络错误，请检查连接');
      setIsAnalyzing(false);
    }
  };

  const saveToHistory = async (data: any) => {
    try {
      await addToHistory({
        id: data.contractId,
        title: fileName || '未命名合同',
        type: contractType || '其他',
        typeEn: 'other',
        score: data.score || 0,
        riskLevel: data.riskLevel || 'green',
        redCount: data.redCount || 0,
        yellowCount: data.yellowCount || 0,
        greenCount: data.greenCount || 0,
        createdAt: new Date().toISOString().split('T')[0],
        status: 'analyzed',
        model: '',
      });
    } catch {}
  };

  const handleBack = () => {
    if (isAnalyzing) {
      setShowLeaveDialog(true);
    } else {
      navigation.goBack();
    }
  };

  const handleConfirmLeave = () => {
    wsRef.current?.disconnect();
    navigation.goBack();
  };

  const handleViewResult = () => {
    if (contractId) {
      navigation.replace('Result', { contractId });
    }
  };

  return (
    <SafeAreaView style={[styles.container, { backgroundColor: colors.background }]} edges={['top']}>
      <TopBar title="分析中" showBack onBack={handleBack} />

      <ScrollView contentContainerStyle={styles.content}>
        {/* 步骤进度 */}
        <View style={styles.progressSection}>
          <StepProgress steps={ANALYSIS_STEPS} currentStep={currentStep} progress={progress} />

          {!isComplete && !error && (
            <View style={styles.loadingSection}>
              <ActivityIndicator size="large" color={colors.accent} />
              <Text style={[styles.message, { color: colors.textSecondary }]}>{message}</Text>
            </View>
          )}

          {error && (
            <View style={[styles.errorCard, { backgroundColor: colors.riskRedBg, borderColor: colors.riskRedBorder }]}>
              <Text style={[styles.errorText, { color: colors.riskRedText }]}>{error}</Text>
            </View>
          )}

          {isComplete && (
            <View style={[styles.completeBanner, { backgroundColor: colors.riskGreenBg, borderColor: colors.riskGreenBorder }]}>
              <Text style={[styles.completeText, { color: colors.riskGreenText }]}>
                ✅ 分析完成，点击查看结果
              </Text>
            </View>
          )}
        </View>

        {/* 实时结果 */}
        {clauses.length > 0 && (
          <View style={styles.resultsSection}>
            <Text style={[styles.resultsTitle, { color: colors.text }]}>实时结果</Text>
            {clauses.map((clause, index) => (
              <MiniClauseCard key={clause.id || index} clause={clause} />
            ))}
          </View>
        )}

        {/* 完成按钮 */}
        {isComplete && contractId && (
          <View style={styles.actionSection}>
            <Text
              style={[styles.viewResultButton, { color: colors.accent }]}
              onPress={handleViewResult}
            >
              查看完整报告 →
            </Text>
          </View>
        )}
      </ScrollView>

      <Dialog
        visible={showLeaveDialog}
        title="离开分析？"
        text="分析正在进行中，离开将丢失当前进度。"
        onConfirm={handleConfirmLeave}
        onCancel={() => setShowLeaveDialog(false)}
        confirmText="离开"
      />
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
  },
  content: {
    padding: spacing.lg,
    gap: spacing.xl,
  },
  progressSection: {
    alignItems: 'center',
  },
  loadingSection: {
    alignItems: 'center',
    gap: spacing.md,
    marginTop: spacing.xl,
  },
  message: {
    fontSize: fontSize.sm,
  },
  errorCard: {
    borderWidth: 1,
    borderRadius: 12,
    padding: spacing.lg,
    marginTop: spacing.lg,
    alignItems: 'center',
  },
  errorText: {
    fontSize: fontSize.sm,
    fontWeight: '500',
  },
  completeBanner: {
    borderWidth: 1,
    borderRadius: 12,
    padding: spacing.lg,
    marginTop: spacing.lg,
    alignItems: 'center',
  },
  completeText: {
    fontSize: fontSize.sm,
    fontWeight: '600',
  },
  resultsSection: {
    gap: spacing.sm,
  },
  resultsTitle: {
    fontSize: fontSize.md,
    fontWeight: '600',
    marginBottom: spacing.xs,
  },
  actionSection: {
    alignItems: 'center',
    paddingVertical: spacing.xl,
  },
  viewResultButton: {
    fontSize: fontSize.md,
    fontWeight: '600',
  },
});

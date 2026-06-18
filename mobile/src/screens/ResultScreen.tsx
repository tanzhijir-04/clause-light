import React, { useState, useEffect, useMemo } from 'react';
import {
  View,
  Text,
  ScrollView,
  TouchableOpacity,
  Share,
  StyleSheet,
  ActivityIndicator,
} from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import { useThemeContext } from '../contexts/ThemeContext';
import { useToastContext } from '../contexts/ToastContext';
import { spacing, fontSize } from '../theme';
import TopBar from '../components/TopBar';
import OverviewCard from '../components/OverviewCard';
import FilterTabs from '../components/FilterTabs';
import ClauseCard from '../components/ClauseCard';
import EmptyState from '../components/EmptyState';
import { getContract, submitFeedback } from '../services/api';
import type { ContractDetail, ClauseData } from '../types/api';
import type { ResultScreenProps } from '../types/navigation';

const FILTER_TABS = [
  { key: 'all', label: '全部' },
  { key: 'red', label: '🔴' },
  { key: 'yellow', label: '🟡' },
  { key: 'green', label: '🟢' },
];

export default function ResultScreen({ navigation, route }: ResultScreenProps) {
  const { contractId } = route.params;
  const { colors } = useThemeContext();
  const { showToast } = useToastContext();

  const [contract, setContract] = useState<ContractDetail | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [filter, setFilter] = useState('all');

  useEffect(() => {
    loadContract();
  }, [contractId]);

  const loadContract = async () => {
    try {
      setLoading(true);
      const data = await getContract(contractId);
      setContract(data);
    } catch (err) {
      setError('加载失败');
    } finally {
      setLoading(false);
    }
  };

  // 筛选条款
  const filteredClauses = useMemo(() => {
    if (!contract?.clauses) return [];
    if (filter === 'all') return contract.clauses;
    return contract.clauses.filter((c) => c.riskLevel === filter);
  }, [contract?.clauses, filter]);

  // 统计各风险等级数量
  const counts = useMemo(() => {
    if (!contract?.clauses) return { all: 0, red: 0, yellow: 0, green: 0 };
    return {
      all: contract.clauses.length,
      red: contract.clauses.filter((c) => c.riskLevel === 'red').length,
      yellow: contract.clauses.filter((c) => c.riskLevel === 'yellow').length,
      green: contract.clauses.filter((c) => c.riskLevel === 'green').length,
    };
  }, [contract?.clauses]);

  // 反馈
  const handleFeedback = async (clauseId: string, feedback: 'correct' | 'incorrect') => {
    try {
      await submitFeedback(contractId, clauseId, feedback);
      // 更新本地状态
      if (contract) {
        setContract({
          ...contract,
          clauses: contract.clauses.map((c) =>
            c.id === clauseId ? { ...c, userFeedback: feedback } : c
          ),
        });
      }
    } catch {
      showToast('提交反馈失败');
    }
  };

  // 分享
  const handleShare = async () => {
    if (!contract) return;
    try {
      await Share.share({
        message: `合同分析报告：${contract.title}\n评分：${contract.score}\n风险等级：${contract.riskLevel}`,
      });
    } catch {}
  };

  if (loading) {
    return (
      <View style={[styles.container, { backgroundColor: colors.background }]}>
        <TopBar title="分析结果" showBack onBack={() => navigation.goBack()} />
        <View style={styles.loadingContainer}>
          <ActivityIndicator size="large" color={colors.accent} />
        </View>
      </View>
    );
  }

  if (error || !contract) {
    return (
      <View style={[styles.container, { backgroundColor: colors.background }]}>
        <TopBar title="分析结果" showBack onBack={() => navigation.goBack()} />
        <EmptyState text={error || '加载失败'} />
      </View>
    );
  }

  const tabsWithCounts = FILTER_TABS.map((tab) => ({
    ...tab,
    count: counts[tab.key as keyof typeof counts],
  }));

  return (
    <View style={[styles.container, { backgroundColor: colors.background }]}>
      <TopBar title="分析结果" showBack onBack={() => navigation.goBack()} />

      <ScrollView contentContainerStyle={styles.content}>
        {/* 总览卡片 */}
        <OverviewCard
          score={contract.score}
          redCount={contract.redCount}
          yellowCount={contract.yellowCount}
          greenCount={contract.greenCount}
          summary={contract.summary}
        />

        {/* 条款筛选 */}
        <View style={styles.filterSection}>
          <FilterTabs tabs={tabsWithCounts} active={filter} onSelect={setFilter} />
        </View>

        {/* 条款列表 */}
        <View style={styles.clausesSection}>
          {filteredClauses.length === 0 ? (
            <EmptyState text="暂无该风险等级的条款" />
          ) : (
            filteredClauses.map((clause) => (
              <ClauseCard
                key={clause.id}
                clause={clause}
                onFeedback={handleFeedback}
              />
            ))
          )}
        </View>
      </ScrollView>

      {/* 底部操作栏 */}
      <View style={[styles.bottomBar, { backgroundColor: colors.surface, borderTopColor: colors.border }]}>
        <TouchableOpacity
          style={[styles.bottomButton, styles.shareButton, { backgroundColor: colors.accent }]}
          onPress={handleShare}
          activeOpacity={0.7}
        >
          <Ionicons name="share-social" size={18} color={colors.textInverse} />
          <Text style={[styles.bottomButtonText, { color: colors.textInverse }]}>分享报告</Text>
        </TouchableOpacity>

        <TouchableOpacity
          style={[styles.bottomButton, styles.reanalyzeButton, { backgroundColor: colors.muted }]}
          onPress={() => navigation.goBack()}
          activeOpacity={0.7}
        >
          <Ionicons name="refresh" size={18} color={colors.text} />
          <Text style={[styles.bottomButtonText, { color: colors.text }]}>重新分析</Text>
        </TouchableOpacity>
      </View>
    </View>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
  },
  loadingContainer: {
    flex: 1,
    alignItems: 'center',
    justifyContent: 'center',
  },
  content: {
    padding: spacing.lg,
    gap: spacing.lg,
    paddingBottom: 100,
  },
  filterSection: {
    gap: spacing.sm,
  },
  clausesSection: {
    gap: spacing.sm,
  },
  bottomBar: {
    position: 'absolute',
    bottom: 0,
    left: 0,
    right: 0,
    flexDirection: 'row',
    padding: spacing.lg,
    gap: spacing.sm,
    borderTopWidth: 1,
  },
  bottomButton: {
    flex: 1,
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    height: 48,
    borderRadius: 12,
    gap: spacing.sm,
  },
  shareButton: {},
  reanalyzeButton: {},
  bottomButtonText: {
    fontSize: fontSize.sm,
    fontWeight: '600',
  },
});

import React, { useState, useEffect, useMemo } from 'react';
import {
  View,
  Text,
  ScrollView,
  TouchableOpacity,
  StyleSheet,
  ActivityIndicator,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { Ionicons } from '@expo/vector-icons';
import { useThemeContext } from '../contexts/ThemeContext';
import { spacing, borderRadius, fontSize } from '../theme';
import TopBar from '../components/TopBar';
import SearchInput from '../components/SearchInput';
import FilterChips from '../components/FilterChips';
import FilterTabs from '../components/FilterTabs';
import EmptyState from '../components/EmptyState';
import { getKnowledgeRules, getKnowledgeLaws, getKnowledgeStats } from '../services/api';
import type { KnowledgeRule, KnowledgeLaw, KnowledgeStats } from '../types/api';
import type { KnowledgeScreenProps } from '../types/navigation';

const CATEGORY_FILTERS = [
  { key: 'all', label: '全部' },
  { key: '通用', label: '通用' },
  { key: '租赁', label: '租赁' },
  { key: '劳动', label: '劳动' },
  { key: '装修', label: '装修' },
  { key: '外包', label: '外包' },
];

const TABS = [
  { key: 'rules', label: '规则库' },
  { key: 'laws', label: '法规库' },
];

export default function KnowledgeScreen({ navigation }: KnowledgeScreenProps) {
  const { colors } = useThemeContext();

  const [activeTab, setActiveTab] = useState('rules');
  const [rules, setRules] = useState<KnowledgeRule[]>([]);
  const [laws, setLaws] = useState<KnowledgeLaw[]>([]);
  const [stats, setStats] = useState<KnowledgeStats | null>(null);
  const [loading, setLoading] = useState(true);
  const [ruleSearch, setRuleSearch] = useState('');
  const [categoryFilter, setCategoryFilter] = useState('all');
  const [expandedRule, setExpandedRule] = useState<string | null>(null);

  useEffect(() => {
    loadData();
  }, []);

  const loadData = async () => {
    try {
      setLoading(true);
      const [rulesData, lawsData, statsData] = await Promise.allSettled([
        getKnowledgeRules(),
        getKnowledgeLaws(),
        getKnowledgeStats(),
      ]);

      if (rulesData.status === 'fulfilled') setRules(rulesData.value);
      if (lawsData.status === 'fulfilled') setLaws(lawsData.value);
      if (statsData.status === 'fulfilled') setStats(statsData.value);
    } catch {} finally {
      setLoading(false);
    }
  };

  // 筛选规则
  const filteredRules = useMemo(() => {
    let result = rules;

    if (ruleSearch) {
      const query = ruleSearch.toLowerCase();
      result = result.filter((r) => r.text.toLowerCase().includes(query));
    }

    if (categoryFilter !== 'all') {
      result = result.filter((r) => r.category === categoryFilter);
    }

    return result;
  }, [rules, ruleSearch, categoryFilter]);

  if (loading) {
    return (
      <SafeAreaView style={[styles.container, { backgroundColor: colors.background }]} edges={['top']}>
        <TopBar title="知识库" />
        <View style={styles.loadingContainer}>
          <ActivityIndicator size="large" color={colors.accent} />
        </View>
      </SafeAreaView>
    );
  }

  return (
    <SafeAreaView style={[styles.container, { backgroundColor: colors.background }]} edges={['top']}>
      <TopBar title="知识库" />

      <ScrollView contentContainerStyle={styles.content}>
        {/* 统计概览 */}
        {stats && (
          <View style={[styles.statsBar, { backgroundColor: colors.muted }]}>
            <Text style={[styles.statsText, { color: colors.textSecondary }]}>
              {stats.totalRules} 条规则 | {stats.totalLaws} 部法规
            </Text>
          </View>
        )}

        {/* Tab 切换 */}
        <FilterTabs tabs={TABS} active={activeTab} onSelect={setActiveTab} />

        {/* 规则库 */}
        {activeTab === 'rules' && (
          <View style={styles.tabContent}>
            <SearchInput
              value={ruleSearch}
              onChangeText={setRuleSearch}
              placeholder="搜索规则..."
            />
            <FilterChips items={CATEGORY_FILTERS} active={categoryFilter} onSelect={setCategoryFilter} />

            {filteredRules.length === 0 ? (
              <EmptyState text="暂无匹配的规则" />
            ) : (
              filteredRules.map((rule) => (
                <TouchableOpacity
                  key={rule.id}
                  style={[styles.ruleCard, { backgroundColor: colors.surface, borderColor: colors.borderSubtle }]}
                  onPress={() => setExpandedRule(expandedRule === rule.id ? null : rule.id)}
                  activeOpacity={0.7}
                >
                  <View style={styles.ruleHeader}>
                    <View style={[styles.categoryBadge, { backgroundColor: colors.accentSubtle }]}>
                      <Text style={[styles.categoryText, { color: colors.accent }]}>{rule.category}</Text>
                    </View>
                    <Text style={[styles.confidenceText, { color: colors.textTertiary }]}>
                      置信度 {(rule.confidence * 100).toFixed(0)}%
                    </Text>
                  </View>

                  <Text
                    style={[styles.ruleText, { color: colors.text }]}
                    numberOfLines={expandedRule === rule.id ? undefined : 3}
                  >
                    {rule.text}
                  </Text>

                  <View style={styles.ruleFooter}>
                    <Text style={[styles.ruleSource, { color: colors.textTertiary }]}>
                      来源：{rule.source === 'manual' ? '手动' : '自动学习'}
                    </Text>
                    <Text style={[styles.ruleUsage, { color: colors.textTertiary }]}>
                      使用 {rule.usageCount} 次
                    </Text>
                  </View>
                </TouchableOpacity>
              ))
            )}
          </View>
        )}

        {/* 法规库 */}
        {activeTab === 'laws' && (
          <View style={styles.tabContent}>
            {laws.length === 0 ? (
              <EmptyState text="暂无法规数据" />
            ) : (
              laws.map((law) => (
                <View
                  key={law.id}
                  style={[styles.lawCard, { backgroundColor: colors.surface, borderColor: colors.borderSubtle }]}
                >
                  <View style={styles.lawHeader}>
                    <Text style={[styles.lawName, { color: colors.text }]}>{law.lawName}</Text>
                    <Text style={[styles.articleCount, { color: colors.textTertiary }]}>
                      {law.articleNumber}
                    </Text>
                  </View>

                  <Text style={[styles.lawContent, { color: colors.textSecondary }]} numberOfLines={3}>
                    {law.content}
                  </Text>

                  {law.tags && law.tags.length > 0 && (
                    <View style={styles.tagsRow}>
                      {law.tags.slice(0, 3).map((tag, i) => (
                        <View key={i} style={[styles.tag, { backgroundColor: colors.muted }]}>
                          <Text style={[styles.tagText, { color: colors.textSecondary }]}>{tag}</Text>
                        </View>
                      ))}
                    </View>
                  )}
                </View>
              ))
            )}
          </View>
        )}
      </ScrollView>
    </SafeAreaView>
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
    gap: spacing.md,
  },
  statsBar: {
    alignItems: 'center',
    paddingVertical: spacing.sm,
    borderRadius: borderRadius.md,
  },
  statsText: {
    fontSize: fontSize.sm,
    fontWeight: '500',
  },
  tabContent: {
    gap: spacing.sm,
  },
  ruleCard: {
    borderWidth: 1,
    borderRadius: borderRadius.lg,
    padding: spacing.lg,
  },
  ruleHeader: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    marginBottom: spacing.sm,
  },
  categoryBadge: {
    paddingHorizontal: spacing.sm,
    paddingVertical: 2,
    borderRadius: borderRadius.sm,
  },
  categoryText: {
    fontSize: fontSize.xs,
    fontWeight: '600',
  },
  confidenceText: {
    fontSize: fontSize.xs,
  },
  ruleText: {
    fontSize: fontSize.sm,
    lineHeight: 22,
    marginBottom: spacing.sm,
  },
  ruleFooter: {
    flexDirection: 'row',
    justifyContent: 'space-between',
  },
  ruleSource: {
    fontSize: fontSize.xs,
  },
  ruleUsage: {
    fontSize: fontSize.xs,
  },
  lawCard: {
    borderWidth: 1,
    borderRadius: borderRadius.lg,
    padding: spacing.lg,
  },
  lawHeader: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    marginBottom: spacing.sm,
  },
  lawName: {
    fontSize: fontSize.base,
    fontWeight: '600',
    flex: 1,
  },
  articleCount: {
    fontSize: fontSize.xs,
  },
  lawContent: {
    fontSize: fontSize.sm,
    lineHeight: 22,
    marginBottom: spacing.sm,
  },
  tagsRow: {
    flexDirection: 'row',
    gap: spacing.xs,
  },
  tag: {
    paddingHorizontal: spacing.sm,
    paddingVertical: 2,
    borderRadius: borderRadius.sm,
  },
  tagText: {
    fontSize: fontSize.xs,
  },
});

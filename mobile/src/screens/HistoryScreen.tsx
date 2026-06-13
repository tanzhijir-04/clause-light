import React, { useState, useEffect, useMemo } from 'react';
import { View, Text, SectionList, StyleSheet } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { useThemeContext } from '../contexts/ThemeContext';
import { spacing, fontSize } from '../theme';
import TopBar from '../components/TopBar';
import SearchInput from '../components/SearchInput';
import FilterChips from '../components/FilterChips';
import ContractCard from '../components/ContractCard';
import EmptyState from '../components/EmptyState';
import { getHistory } from '../services/storage';
import { groupByMonth } from '../utils/formatDate';
import type { ContractListItem } from '../types/api';
import type { HistoryScreenProps } from '../types/navigation';

const RISK_FILTERS = [
  { key: 'all', label: '全部' },
  { key: 'red', label: '高风险', dot: 'red' as const },
  { key: 'yellow', label: '中风险', dot: 'yellow' as const },
  { key: 'green', label: '低风险', dot: 'green' as const },
];

export default function HistoryScreen({ navigation }: HistoryScreenProps) {
  const { colors } = useThemeContext();
  const [contracts, setContracts] = useState<ContractListItem[]>([]);
  const [search, setSearch] = useState('');
  const [riskFilter, setRiskFilter] = useState('all');

  useEffect(() => {
    loadHistory();
  }, []);

  const loadHistory = async () => {
    try {
      const history = await getHistory();
      setContracts(history);
    } catch {}
  };

  // 筛选和搜索
  const filteredContracts = useMemo(() => {
    let result = contracts;

    // 搜索过滤
    if (search) {
      const query = search.toLowerCase();
      result = result.filter(
        (c) =>
          c.title.toLowerCase().includes(query) ||
          c.type.toLowerCase().includes(query)
      );
    }

    // 风险过滤
    if (riskFilter !== 'all') {
      result = result.filter((c) => c.riskLevel === riskFilter);
    }

    return result;
  }, [contracts, search, riskFilter]);

  // 按月分组
  const sections = useMemo(() => {
    return groupByMonth(filteredContracts).map((group) => ({
      title: group.month,
      data: group.data,
    }));
  }, [filteredContracts]);

  return (
    <SafeAreaView style={[styles.container, { backgroundColor: colors.background }]} edges={['top']}>
      <TopBar title="历史记录" />

      <View style={styles.content}>
        {/* 搜索框 */}
        <SearchInput
          value={search}
          onChangeText={setSearch}
          placeholder="搜索合同..."
        />

        {/* 风险筛选 */}
        <FilterChips items={RISK_FILTERS} active={riskFilter} onSelect={setRiskFilter} />

        {/* 列表 */}
        <SectionList
          sections={sections}
          keyExtractor={(item) => item.id}
          renderItem={({ item }) => (
            <ContractCard
              contract={item}
              onPress={() => navigation.navigate('HomeTab', {
                screen: 'Home',
                params: { screen: 'Result', params: { contractId: item.id } },
              } as any)}
            />
          )}
          renderSectionHeader={({ section }) => (
            <Text style={[styles.monthHeader, { color: colors.textSecondary }]}>
              {section.title}
            </Text>
          )}
          ListEmptyComponent={
            <EmptyState
              icon="time-outline"
              text={search || riskFilter !== 'all' ? '没有匹配的记录' : '暂无历史记录'}
            />
          }
          contentContainerStyle={styles.listContent}
          stickySectionHeadersEnabled={false}
        />
      </View>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
  },
  content: {
    flex: 1,
    padding: spacing.lg,
    gap: spacing.sm,
  },
  monthHeader: {
    fontSize: fontSize.sm,
    fontWeight: '600',
    marginTop: spacing.md,
    marginBottom: spacing.sm,
  },
  listContent: {
    paddingBottom: spacing.xxl,
  },
});

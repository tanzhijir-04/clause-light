import React from 'react';
import { View, Text, TouchableOpacity, StyleSheet } from 'react-native';
import { useThemeContext } from '../contexts/ThemeContext';
import { spacing, borderRadius, fontSize } from '../theme';
import RiskBadge from './RiskBadge';
import type { ContractListItem } from '../types/api';

interface Props {
  contract: ContractListItem;
  onPress: () => void;
}

const RISK_DOT_COLORS = {
  red: '#e53e3e',
  yellow: '#d69e2e',
  green: '#38a169',
};

export default function ContractCard({ contract, onPress }: Props) {
  const { colors } = useThemeContext();

  const riskBarColor =
    contract.riskLevel === 'red' ? colors.riskRed :
    contract.riskLevel === 'yellow' ? colors.riskYellow :
    colors.riskGreen;

  return (
    <TouchableOpacity
      style={[styles.card, { backgroundColor: colors.surface, borderColor: colors.borderSubtle }]}
      onPress={onPress}
      activeOpacity={0.7}
    >
      {/* 左侧风险色条 */}
      <View style={[styles.riskBar, { backgroundColor: riskBarColor }]} />

      <View style={styles.content}>
        {/* 顶部：标题 + 评分 */}
        <View style={styles.header}>
          <Text style={[styles.title, { color: colors.text }]} numberOfLines={1}>
            {contract.title}
          </Text>
          <Text style={[styles.score, { color: riskBarColor }]}>
            {contract.score}
          </Text>
        </View>

        {/* 底部：类型 + 风险点 + 日期 */}
        <View style={styles.footer}>
          <View style={[styles.typeBadge, { backgroundColor: colors.muted }]}>
            <Text style={[styles.typeText, { color: colors.textSecondary }]}>
              {contract.type}
            </Text>
          </View>

          <View style={styles.dots}>
            {contract.redCount > 0 && (
              <View style={[styles.dot, { backgroundColor: RISK_DOT_COLORS.red }]} />
            )}
            {contract.yellowCount > 0 && (
              <View style={[styles.dot, { backgroundColor: RISK_DOT_COLORS.yellow }]} />
            )}
            {contract.greenCount > 0 && (
              <View style={[styles.dot, { backgroundColor: RISK_DOT_COLORS.green }]} />
            )}
          </View>

          <Text style={[styles.date, { color: colors.textTertiary }]}>
            {contract.createdAt}
          </Text>
        </View>
      </View>
    </TouchableOpacity>
  );
}

const styles = StyleSheet.create({
  card: {
    flexDirection: 'row',
    borderRadius: borderRadius.lg,
    borderWidth: 1,
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
    justifyContent: 'space-between',
    marginBottom: spacing.sm,
  },
  title: {
    flex: 1,
    fontSize: fontSize.base,
    fontWeight: '600',
    marginRight: spacing.sm,
  },
  score: {
    fontSize: fontSize.xl,
    fontWeight: '700',
  },
  footer: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: spacing.sm,
  },
  typeBadge: {
    paddingHorizontal: spacing.sm,
    paddingVertical: 2,
    borderRadius: borderRadius.sm,
  },
  typeText: {
    fontSize: fontSize.xs,
    fontWeight: '500',
  },
  dots: {
    flexDirection: 'row',
    gap: 4,
  },
  dot: {
    width: 6,
    height: 6,
    borderRadius: 3,
  },
  date: {
    fontSize: fontSize.xs,
    marginLeft: 'auto',
  },
});

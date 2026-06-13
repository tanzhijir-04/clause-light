import React from 'react';
import { View, Text, StyleSheet } from 'react-native';
import { useThemeContext } from '../contexts/ThemeContext';
import { spacing, borderRadius, fontSize } from '../theme';
import RiskBadge from './RiskBadge';
import type { ClauseData } from '../types/api';

interface Props {
  clause: Partial<ClauseData>;
}

export default function MiniClauseCard({ clause }: Props) {
  const { colors } = useThemeContext();

  const riskBarColor =
    clause.riskLevel === 'red' ? colors.riskRed :
    clause.riskLevel === 'yellow' ? colors.riskYellow :
    colors.riskGreen;

  return (
    <View style={[styles.card, { backgroundColor: colors.surface, borderColor: colors.borderSubtle }]}>
      <View style={[styles.riskBar, { backgroundColor: riskBarColor }]} />
      <View style={styles.content}>
        <View style={styles.header}>
          <Text style={[styles.title, { color: colors.text }]} numberOfLines={1}>
            {clause.clauseNumber} {clause.clauseTitle}
          </Text>
          {clause.riskLevel && <RiskBadge level={clause.riskLevel} />}
        </View>
        {clause.riskSummary ? (
          <Text style={[styles.summary, { color: colors.textSecondary }]} numberOfLines={2}>
            {clause.riskSummary}
          </Text>
        ) : null}
      </View>
    </View>
  );
}

const styles = StyleSheet.create({
  card: {
    flexDirection: 'row',
    borderRadius: borderRadius.md,
    borderWidth: 1,
    overflow: 'hidden',
    marginBottom: spacing.sm,
  },
  riskBar: {
    width: 4,
  },
  content: {
    flex: 1,
    padding: spacing.md,
  },
  header: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: spacing.sm,
    marginBottom: spacing.xs,
  },
  title: {
    flex: 1,
    fontSize: fontSize.sm,
    fontWeight: '600',
  },
  summary: {
    fontSize: fontSize.xs,
    lineHeight: 18,
  },
});

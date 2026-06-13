import React from 'react';
import { View, Text, StyleSheet } from 'react-native';
import { useThemeContext } from '../contexts/ThemeContext';
import { spacing, borderRadius, fontSize } from '../theme';
import ScoreDisplay from './ScoreDisplay';
import { getRiskAdvice } from '../utils/riskAdvice';

interface Props {
  score: number;
  redCount: number;
  yellowCount: number;
  greenCount: number;
  summary?: string;
}

export default function OverviewCard({ score, redCount, yellowCount, greenCount, summary }: Props) {
  const { colors } = useThemeContext();
  const total = redCount + yellowCount + greenCount;

  return (
    <View style={[styles.card, { backgroundColor: colors.surface, borderColor: colors.borderSubtle }]}>
      {/* 评分 */}
      <View style={styles.scoreSection}>
        <ScoreDisplay score={score} size="lg" />
        <Text style={[styles.scoreLabel, { color: colors.textSecondary }]}>综合评分</Text>
      </View>

      {/* 风险分布 */}
      <View style={styles.distributionSection}>
        <View style={styles.distributionRow}>
          <Text style={[styles.distributionItem, { color: colors.riskRedText }]}>🔴 {redCount}</Text>
          <Text style={[styles.distributionItem, { color: colors.riskYellowText }]}>🟡 {yellowCount}</Text>
          <Text style={[styles.distributionItem, { color: colors.riskGreenText }]}>🟢 {greenCount}</Text>
        </View>

        {/* 分布条 */}
        <View style={[styles.distributionBar, { backgroundColor: colors.muted }]}>
          {total > 0 && redCount > 0 && (
            <View style={[styles.barSegment, { flex: redCount, backgroundColor: colors.riskRed }]} />
          )}
          {total > 0 && yellowCount > 0 && (
            <View style={[styles.barSegment, { flex: yellowCount, backgroundColor: colors.riskYellow }]} />
          )}
          {total > 0 && greenCount > 0 && (
            <View style={[styles.barSegment, { flex: greenCount, backgroundColor: colors.riskGreen }]} />
          )}
        </View>
      </View>

      {/* 建议 */}
      <Text style={[styles.advice, { color: colors.textSecondary }]}>
        {getRiskAdvice(score)}
      </Text>

      {/* 摘要 */}
      {summary ? (
        <Text style={[styles.summary, { color: colors.text }]} numberOfLines={3}>
          {summary}
        </Text>
      ) : null}
    </View>
  );
}

const styles = StyleSheet.create({
  card: {
    borderRadius: borderRadius.xl,
    borderWidth: 1,
    padding: spacing.xxl,
    alignItems: 'center',
  },
  scoreSection: {
    alignItems: 'center',
    marginBottom: spacing.lg,
  },
  scoreLabel: {
    fontSize: fontSize.sm,
    marginTop: spacing.xs,
  },
  distributionSection: {
    width: '100%',
    marginBottom: spacing.lg,
  },
  distributionRow: {
    flexDirection: 'row',
    justifyContent: 'center',
    gap: spacing.xl,
    marginBottom: spacing.sm,
  },
  distributionItem: {
    fontSize: fontSize.sm,
    fontWeight: '600',
  },
  distributionBar: {
    flexDirection: 'row',
    height: 8,
    borderRadius: 4,
    overflow: 'hidden',
  },
  barSegment: {
    height: '100%',
  },
  advice: {
    fontSize: fontSize.sm,
    textAlign: 'center',
    marginBottom: spacing.sm,
  },
  summary: {
    fontSize: fontSize.sm,
    lineHeight: 22,
    textAlign: 'center',
  },
});

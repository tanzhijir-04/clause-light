import React, { useState } from 'react';
import { View, Text, TouchableOpacity, LayoutAnimation, UIManager, Platform, StyleSheet } from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import { useThemeContext } from '../contexts/ThemeContext';
import { spacing, borderRadius, fontSize } from '../theme';
import RiskBadge from './RiskBadge';
import type { ClauseData } from '../types/api';

// Android 需要启用 LayoutAnimation
if (Platform.OS === 'android') {
  UIManager.setLayoutAnimationEnabledExperimental?.(true);
}

interface Props {
  clause: ClauseData;
  onFeedback?: (clauseId: string, feedback: 'correct' | 'incorrect') => void;
}

export default function ClauseCard({ clause, onFeedback }: Props) {
  const { colors } = useThemeContext();
  const [showSuggestion, setShowSuggestion] = useState(false);
  const [showLegal, setShowLegal] = useState(false);
  const [feedback, setFeedback] = useState<'correct' | 'incorrect' | null>(clause.userFeedback);

  const riskBarColor =
    clause.riskLevel === 'red' ? colors.riskRed :
    clause.riskLevel === 'yellow' ? colors.riskYellow :
    colors.riskGreen;

  const handleFeedback = (type: 'correct' | 'incorrect') => {
    const newFeedback = feedback === type ? null : type;
    setFeedback(newFeedback);
    onFeedback?.(clause.id, type);
  };

  const toggleSuggestion = () => {
    LayoutAnimation.configureNext(LayoutAnimation.Presets.easeInEaseOut);
    setShowSuggestion(!showSuggestion);
  };

  const toggleLegal = () => {
    LayoutAnimation.configureNext(LayoutAnimation.Presets.easeInEaseOut);
    setShowLegal(!showLegal);
  };

  return (
    <View style={[styles.card, { backgroundColor: colors.surface, borderColor: colors.borderSubtle }]}>
      {/* 左侧风险色条 */}
      <View style={[styles.riskBar, { backgroundColor: riskBarColor }]} />

      <View style={styles.content}>
        {/* 头部 */}
        <View style={styles.header}>
          <Text style={[styles.title, { color: colors.text }]} numberOfLines={1}>
            {clause.clauseNumber} {clause.clauseTitle}
          </Text>
          <RiskBadge level={clause.riskLevel} />
        </View>

        {/* 问题摘要 */}
        {clause.riskSummary ? (
          <Text style={[styles.summary, { color: colors.textSecondary }]}>{clause.riskSummary}</Text>
        ) : null}

        {/* 大白话 */}
        {clause.plainExplanation ? (
          <View style={[styles.explainBox, { backgroundColor: colors.riskYellowBg, borderColor: colors.riskYellowBorder }]}>
            <Text style={[styles.explainLabel, { color: colors.text }]}>💡 大白话</Text>
            <Text style={[styles.explainText, { color: colors.text }]}>{clause.plainExplanation}</Text>
          </View>
        ) : null}

        {/* 修改建议 */}
        {clause.suggestedClause ? (
          <>
            <TouchableOpacity style={[styles.expandButton, { borderTopColor: colors.borderSubtle }]} onPress={toggleSuggestion}>
              <Text style={[styles.expandButtonText, { color: colors.accent }]}>📝 修改建议</Text>
              <Ionicons
                name={showSuggestion ? 'chevron-down' : 'chevron-forward'}
                size={16}
                color={colors.accent}
              />
            </TouchableOpacity>
            {showSuggestion ? (
              <View style={[styles.suggestionBox, { backgroundColor: colors.accentSubtle }]}>
                <Text style={[styles.suggestionText, { color: colors.text }]}>{clause.suggestedClause}</Text>
              </View>
            ) : null}
          </>
        ) : null}

        {/* 法律依据 */}
        {clause.legalBasis ? (
          <>
            <TouchableOpacity style={[styles.expandButton, { borderTopColor: colors.borderSubtle }]} onPress={toggleLegal}>
              <Text style={[styles.expandButtonText, { color: colors.accent }]}>⚖️ 法律依据</Text>
              <Ionicons
                name={showLegal ? 'chevron-down' : 'chevron-forward'}
                size={16}
                color={colors.accent}
              />
            </TouchableOpacity>
            {showLegal ? (
              <View style={styles.legalBox}>
                <Text style={[styles.legalText, { color: colors.textTertiary }]}>{clause.legalBasis}</Text>
              </View>
            ) : null}
          </>
        ) : null}

        {/* 反馈按钮 */}
        <View style={[styles.feedbackRow, { borderTopColor: colors.borderSubtle }]}>
          <TouchableOpacity
            style={[
              styles.feedbackButton,
              { borderColor: colors.border, backgroundColor: colors.surface },
              feedback === 'correct' && { backgroundColor: colors.accentSubtle, borderColor: colors.accent },
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
                { color: colors.textSecondary },
                feedback === 'correct' && { color: colors.accent },
              ]}
            >
              准确
            </Text>
          </TouchableOpacity>

          <TouchableOpacity
            style={[
              styles.feedbackButton,
              { borderColor: colors.border, backgroundColor: colors.surface },
              feedback === 'incorrect' && { backgroundColor: colors.accentSubtle, borderColor: colors.accent },
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
                { color: colors.textSecondary },
                feedback === 'incorrect' && { color: colors.accent },
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

const styles = StyleSheet.create({
  card: {
    flexDirection: 'row',
    borderRadius: borderRadius.lg,
    borderWidth: 1,
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
  },
  summary: {
    fontSize: fontSize.sm,
    marginBottom: spacing.md,
    lineHeight: 20,
  },
  explainBox: {
    borderWidth: 1,
    borderRadius: borderRadius.md,
    padding: spacing.md,
    marginBottom: spacing.md,
  },
  explainLabel: {
    fontWeight: '600',
    marginBottom: 2,
  },
  explainText: {
    fontSize: fontSize.sm,
    lineHeight: 22,
  },
  expandButton: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: spacing.sm,
    paddingVertical: spacing.md,
    borderTopWidth: 1,
  },
  expandButtonText: {
    flex: 1,
    fontSize: fontSize.sm,
    fontWeight: '500',
  },
  suggestionBox: {
    borderRadius: borderRadius.md,
    padding: spacing.md,
    marginBottom: spacing.md,
  },
  suggestionText: {
    fontSize: fontSize.sm,
    lineHeight: 22,
  },
  legalBox: {
    padding: spacing.md,
  },
  legalText: {
    fontSize: fontSize.sm,
    fontStyle: 'italic',
    lineHeight: 22,
  },
  feedbackRow: {
    flexDirection: 'row',
    gap: spacing.sm,
    paddingTop: spacing.md,
    borderTopWidth: 1,
  },
  feedbackButton: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 4,
    paddingHorizontal: spacing.md,
    paddingVertical: spacing.sm,
    borderRadius: borderRadius.full,
    borderWidth: 1,
  },
  feedbackText: {
    fontSize: fontSize.xs,
    fontWeight: '500',
  },
});

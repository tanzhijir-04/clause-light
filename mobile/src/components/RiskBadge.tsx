import React from 'react';
import { View, Text, StyleSheet } from 'react-native';
import { useThemeContext } from '../contexts/ThemeContext';
import { borderRadius, fontSize } from '../theme';

interface Props {
  level: 'red' | 'yellow' | 'green';
  label?: string;
}

const LEVEL_LABELS = {
  red: '高风险',
  yellow: '中风险',
  green: '低风险',
};

export default function RiskBadge({ level, label }: Props) {
  const { colors } = useThemeContext();

  const bgColor =
    level === 'red' ? colors.riskRedBg :
    level === 'yellow' ? colors.riskYellowBg :
    colors.riskGreenBg;

  const textColor =
    level === 'red' ? colors.riskRedText :
    level === 'yellow' ? colors.riskYellowText :
    colors.riskGreenText;

  const borderColor =
    level === 'red' ? colors.riskRedBorder :
    level === 'yellow' ? colors.riskYellowBorder :
    colors.riskGreenBorder;

  return (
    <View style={[styles.badge, { backgroundColor: bgColor, borderColor }]}>
      <Text style={[styles.text, { color: textColor }]}>
        {label || LEVEL_LABELS[level]}
      </Text>
    </View>
  );
}

const styles = StyleSheet.create({
  badge: {
    paddingHorizontal: 8,
    paddingVertical: 2,
    borderRadius: borderRadius.full,
    borderWidth: 1,
  },
  text: {
    fontSize: fontSize.xs,
    fontWeight: '600',
  },
});

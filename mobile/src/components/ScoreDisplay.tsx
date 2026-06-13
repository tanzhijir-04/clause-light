import React from 'react';
import { Text, StyleSheet } from 'react-native';
import { useThemeContext } from '../contexts/ThemeContext';
import { getScoreColor } from '../utils/scoreColor';
import { fontSize, fontWeight } from '../theme';

interface Props {
  score: number;
  size?: 'md' | 'lg';
}

export default function ScoreDisplay({ score, size = 'md' }: Props) {
  const { colors } = useThemeContext();
  const color = getScoreColor(score, colors);

  return (
    <Text
      style={[
        styles.score,
        size === 'lg' ? styles.lg : styles.md,
        { color },
      ]}
    >
      {score}
    </Text>
  );
}

const styles = StyleSheet.create({
  score: {
    fontWeight: fontWeight.bold,
  },
  md: {
    fontSize: fontSize.xl,
  },
  lg: {
    fontSize: fontSize.display,
  },
});

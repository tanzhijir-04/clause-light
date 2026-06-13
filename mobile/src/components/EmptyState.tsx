import React from 'react';
import { View, Text, TouchableOpacity, StyleSheet } from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import { useThemeContext } from '../contexts/ThemeContext';
import { spacing, fontSize } from '../theme';

interface Props {
  icon?: keyof typeof Ionicons.glyphMap;
  text: string;
  buttonText?: string;
  onAction?: () => void;
}

export default function EmptyState({ icon, text, buttonText, onAction }: Props) {
  const { colors } = useThemeContext();

  return (
    <View style={styles.container}>
      <Ionicons
        name={icon || 'document-text-outline'}
        size={48}
        color={colors.textTertiary}
      />
      <Text style={[styles.text, { color: colors.textSecondary }]}>{text}</Text>
      {buttonText && onAction && (
        <TouchableOpacity
          style={[styles.button, { backgroundColor: colors.accent }]}
          onPress={onAction}
          activeOpacity={0.7}
        >
          <Text style={[styles.buttonText, { color: colors.textInverse }]}>
            {buttonText}
          </Text>
        </TouchableOpacity>
      )}
    </View>
  );
}

const styles = StyleSheet.create({
  container: {
    alignItems: 'center',
    justifyContent: 'center',
    paddingVertical: spacing.huge,
    gap: spacing.md,
  },
  text: {
    fontSize: fontSize.sm,
    textAlign: 'center',
  },
  button: {
    paddingHorizontal: spacing.xl,
    paddingVertical: spacing.sm,
    borderRadius: 8,
    marginTop: spacing.sm,
  },
  buttonText: {
    fontSize: fontSize.sm,
    fontWeight: '600',
  },
});

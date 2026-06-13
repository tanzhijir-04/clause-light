import React from 'react';
import { ScrollView, TouchableOpacity, Text, View, StyleSheet } from 'react-native';
import { useThemeContext } from '../contexts/ThemeContext';
import { spacing, borderRadius, fontSize } from '../theme';

interface FilterItem {
  key: string;
  label: string;
  dot?: 'red' | 'yellow' | 'green';
}

interface Props {
  items: FilterItem[];
  active: string;
  onSelect: (key: string) => void;
}

const DOT_COLORS = {
  red: '#e53e3e',
  yellow: '#d69e2e',
  green: '#38a169',
};

export default function FilterChips({ items, active, onSelect }: Props) {
  const { colors } = useThemeContext();

  return (
    <ScrollView
      horizontal
      showsHorizontalScrollIndicator={false}
      contentContainerStyle={styles.container}
    >
      {items.map((item) => {
        const isActive = item.key === active;
        return (
          <TouchableOpacity
            key={item.key}
            style={[
              styles.chip,
              {
                backgroundColor: isActive ? colors.accent : colors.muted,
                borderColor: isActive ? colors.accent : colors.border,
              },
            ]}
            onPress={() => onSelect(item.key)}
            activeOpacity={0.7}
          >
            {item.dot && (
              <View
                style={[
                  styles.dot,
                  { backgroundColor: DOT_COLORS[item.dot] },
                ]}
              />
            )}
            <Text
              style={[
                styles.label,
                { color: isActive ? colors.textInverse : colors.text },
              ]}
            >
              {item.label}
            </Text>
          </TouchableOpacity>
        );
      })}
    </ScrollView>
  );
}

const styles = StyleSheet.create({
  container: {
    gap: spacing.sm,
    paddingVertical: spacing.xs,
  },
  chip: {
    flexDirection: 'row',
    alignItems: 'center',
    height: 32,
    paddingHorizontal: spacing.md,
    borderRadius: borderRadius.full,
    borderWidth: 1,
    gap: spacing.xs,
  },
  dot: {
    width: 6,
    height: 6,
    borderRadius: 3,
  },
  label: {
    fontSize: fontSize.sm,
    fontWeight: '500',
  },
});

import React from 'react';
import { View, Text, TouchableOpacity, StyleSheet } from 'react-native';
import { useThemeContext } from '../contexts/ThemeContext';
import { borderRadius, fontSize, spacing } from '../theme';

interface Tab {
  key: string;
  label: string;
  count?: number;
}

interface Props {
  tabs: Tab[];
  active: string;
  onSelect: (key: string) => void;
}

export default function FilterTabs({ tabs, active, onSelect }: Props) {
  const { colors } = useThemeContext();

  return (
    <View style={[styles.container, { backgroundColor: colors.muted }]}>
      {tabs.map((tab) => {
        const isActive = tab.key === active;
        return (
          <TouchableOpacity
            key={tab.key}
            style={[
              styles.tab,
              isActive && { backgroundColor: colors.surface },
              isActive && styles.activeTab,
            ]}
            onPress={() => onSelect(tab.key)}
            activeOpacity={0.7}
          >
            <Text
              style={[
                styles.label,
                { color: isActive ? colors.text : colors.textSecondary },
              ]}
            >
              {tab.label}
              {tab.count !== undefined ? `(${tab.count})` : ''}
            </Text>
          </TouchableOpacity>
        );
      })}
    </View>
  );
}

const styles = StyleSheet.create({
  container: {
    flexDirection: 'row',
    borderRadius: borderRadius.md,
    padding: 2,
  },
  tab: {
    flex: 1,
    alignItems: 'center',
    justifyContent: 'center',
    height: 36,
    borderRadius: borderRadius.sm - 2,
  },
  activeTab: {
    shadowColor: '#000',
    shadowOffset: { width: 0, height: 1 },
    shadowOpacity: 0.08,
    shadowRadius: 2,
    elevation: 2,
  },
  label: {
    fontSize: fontSize.sm,
    fontWeight: '500',
  },
});

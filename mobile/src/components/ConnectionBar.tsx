import React from 'react';
import { View, Text, TouchableOpacity, StyleSheet } from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import { useThemeContext } from '../contexts/ThemeContext';
import { spacing, borderRadius, fontSize } from '../theme';
import type { ConnectionStatus } from '../contexts/ConnectionContext';

interface Props {
  status: ConnectionStatus;
  serverName?: string;
  onPress?: () => void;
}

const STATUS_CONFIG: Record<ConnectionStatus, { icon: keyof typeof Ionicons.glyphMap; label: string; bgColor: string; textColor: string }> = {
  connected: {
    icon: 'checkmark-circle',
    label: '已连接',
    bgColor: '#f0fff4',
    textColor: '#276749',
  },
  cloud: {
    icon: 'cloud',
    label: '云端模式',
    bgColor: '#e8f0fe',
    textColor: '#1a4a7a',
  },
  offline: {
    icon: 'cloud-offline',
    label: '离线模式',
    bgColor: '#fff5f5',
    textColor: '#c53030',
  },
};

export default function ConnectionBar({ status, serverName, onPress }: Props) {
  const { colors } = useThemeContext();
  const config = STATUS_CONFIG[status];

  const bgColor = status === 'connected'
    ? colors.riskGreenBg
    : status === 'cloud'
    ? colors.accentSubtle
    : colors.riskRedBg;

  const textColor = status === 'connected'
    ? colors.riskGreenText
    : status === 'cloud'
    ? colors.accent
    : colors.riskRedText;

  return (
    <TouchableOpacity
      style={[styles.bar, { backgroundColor: bgColor }]}
      onPress={onPress}
      activeOpacity={0.7}
    >
      <Ionicons name={config.icon} size={16} color={textColor} />
      <Text style={[styles.label, { color: textColor }]}>
        {status === 'connected' && serverName ? `${serverName} · ` : ''}
        {config.label}
      </Text>
      <Ionicons name="chevron-forward" size={14} color={textColor} />
    </TouchableOpacity>
  );
}

const styles = StyleSheet.create({
  bar: {
    flexDirection: 'row',
    alignItems: 'center',
    height: 40,
    borderRadius: borderRadius.lg,
    paddingHorizontal: spacing.md,
    gap: spacing.sm,
  },
  label: {
    flex: 1,
    fontSize: fontSize.sm,
    fontWeight: '500',
  },
});

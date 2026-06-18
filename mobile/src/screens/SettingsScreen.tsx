import React, { useState } from 'react';
import {
  View,
  Text,
  ScrollView,
  TextInput,
  TouchableOpacity,
  StyleSheet,
  ActivityIndicator,
} from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import { useThemeContext } from '../contexts/ThemeContext';
import { useConnectionContext, type ConnectionMode } from '../contexts/ConnectionContext';
import { useToastContext } from '../contexts/ToastContext';
import { spacing, borderRadius, fontSize } from '../theme';
import TopBar from '../components/TopBar';
import FilterTabs from '../components/FilterTabs';
import Dialog from '../components/Dialog';
import { clearAll, clearHistory } from '../services/storage';
import type { SettingsScreenProps } from '../types/navigation';
import type { ThemeMode } from '../types/theme';

const CONNECTION_TABS = [
  { key: 'lan', label: '局域网直连' },
  { key: 'scan', label: '扫描连接' },
  { key: 'cloud', label: '云端 API' },
];

const THEME_TABS = [
  { key: 'auto', label: '自动' },
  { key: 'light', label: '亮色' },
  { key: 'dark', label: '暗色' },
];

export default function SettingsScreen({ navigation }: SettingsScreenProps) {
  const { colors, themeMode, setThemeMode } = useThemeContext();
  const { config, status, setMode, setLanConfig, setCloudConfig, testConnection } = useConnectionContext();
  const { showToast } = useToastContext();

  const [ip, setIp] = useState(config.serverIp);
  const [port, setPort] = useState(config.port);
  const [cloudUrl, setCloudUrl] = useState(config.cloudUrl);
  const [apiKey, setApiKey] = useState(config.apiKey);
  const [testing, setTesting] = useState(false);
  const [showClearDialog, setShowClearDialog] = useState(false);

  const handleTestConnection = async () => {
    setTesting(true);
    try {
      // 先保存配置
      setLanConfig(ip, port);
      const success = await testConnection();
      showToast(success ? '连接成功' : '连接失败');
    } finally {
      setTesting(false);
    }
  };

  const handleClearCache = async () => {
    try {
      await clearAll();
      showToast('缓存已清除');
    } catch {
      showToast('清除失败');
    }
    setShowClearDialog(false);
  };

  const handleExport = () => {
    showToast('功能开发中...');
  };

  return (
    <View style={[styles.container, { backgroundColor: colors.background }]}>
      <TopBar title="设置" />

      <ScrollView contentContainerStyle={styles.content}>
        {/* 服务器连接 */}
        <View style={styles.section}>
          <Text style={[styles.sectionTitle, { color: colors.textSecondary }]}>服务器连接</Text>

          <FilterTabs
            tabs={CONNECTION_TABS}
            active={config.mode}
            onSelect={(mode) => setMode(mode as ConnectionMode)}
          />

          {/* LAN 配置 */}
          {config.mode === 'lan' && (
            <View style={styles.configGroup}>
              <View style={[styles.inputRow, { backgroundColor: colors.input, borderColor: colors.border }]}>
                <Text style={[styles.inputLabel, { color: colors.textTertiary }]}>IP</Text>
                <TextInput
                  style={[styles.input, { color: colors.text }]}
                  value={ip}
                  onChangeText={setIp}
                  placeholder="192.168.1.100"
                  placeholderTextColor={colors.textTertiary}
                  keyboardType="numeric"
                />
              </View>

              <View style={[styles.inputRow, { backgroundColor: colors.input, borderColor: colors.border }]}>
                <Text style={[styles.inputLabel, { color: colors.textTertiary }]}>端口</Text>
                <TextInput
                  style={[styles.input, { color: colors.text }]}
                  value={port}
                  onChangeText={setPort}
                  placeholder="8080"
                  placeholderTextColor={colors.textTertiary}
                  keyboardType="numeric"
                />
              </View>

              <TouchableOpacity
                style={[styles.testButton, { backgroundColor: colors.accent }]}
                onPress={handleTestConnection}
                disabled={testing}
                activeOpacity={0.7}
              >
                {testing ? (
                  <ActivityIndicator size="small" color={colors.textInverse} />
                ) : (
                  <>
                    <Ionicons name="flash" size={18} color={colors.textInverse} />
                    <Text style={[styles.testButtonText, { color: colors.textInverse }]}>
                      测试连接
                    </Text>
                  </>
                )}
              </TouchableOpacity>

              {/* 连接状态 */}
              <View style={styles.statusRow}>
                <View
                  style={[
                    styles.statusDot,
                    { backgroundColor: status === 'connected' ? colors.riskGreen : colors.riskRed },
                  ]}
                />
                <Text style={[styles.statusText, { color: colors.textSecondary }]}>
                  {status === 'connected' ? '已连接' : '未连接'}
                </Text>
              </View>
            </View>
          )}

          {/* 扫描连接 */}
          {config.mode === 'scan' && (
            <View style={styles.configGroup}>
              <View style={[styles.scanPlaceholder, { backgroundColor: colors.muted, borderColor: colors.border }]}>
                <Ionicons name="scan" size={48} color={colors.textTertiary} />
                <Text style={[styles.scanText, { color: colors.textSecondary }]}>
                  请在电脑端显示二维码后扫描
                </Text>
              </View>
            </View>
          )}

          {/* 云端 API */}
          {config.mode === 'cloud' && (
            <View style={styles.configGroup}>
              <View style={[styles.inputRow, { backgroundColor: colors.input, borderColor: colors.border }]}>
                <Text style={[styles.inputLabel, { color: colors.textTertiary }]}>URL</Text>
                <TextInput
                  style={[styles.input, { color: colors.text }]}
                  value={cloudUrl}
                  onChangeText={setCloudUrl}
                  placeholder="https://api.example.com"
                  placeholderTextColor={colors.textTertiary}
                  autoCapitalize="none"
                />
              </View>

              <View style={[styles.inputRow, { backgroundColor: colors.input, borderColor: colors.border }]}>
                <Text style={[styles.inputLabel, { color: colors.textTertiary }]}>Key</Text>
                <TextInput
                  style={[styles.input, { color: colors.text }]}
                  value={apiKey}
                  onChangeText={setApiKey}
                  placeholder="API Key"
                  placeholderTextColor={colors.textTertiary}
                  secureTextEntry
                  autoCapitalize="none"
                />
              </View>
            </View>
          )}
        </View>

        {/* 外观 */}
        <View style={styles.section}>
          <Text style={[styles.sectionTitle, { color: colors.textSecondary }]}>外观</Text>
          <FilterTabs tabs={THEME_TABS} active={themeMode} onSelect={(mode) => setThemeMode(mode as ThemeMode)} />
        </View>

        {/* 数据管理 */}
        <View style={styles.section}>
          <Text style={[styles.sectionTitle, { color: colors.textSecondary }]}>数据管理</Text>

          <TouchableOpacity
            style={[styles.menuItem, { backgroundColor: colors.surface, borderColor: colors.borderSubtle }]}
            onPress={() => setShowClearDialog(true)}
            activeOpacity={0.7}
          >
            <Ionicons name="trash-outline" size={20} color={colors.riskRed} />
            <Text style={[styles.menuText, { color: colors.riskRed }]}>清除本地缓存</Text>
            <Ionicons name="chevron-forward" size={16} color={colors.textTertiary} />
          </TouchableOpacity>

          <TouchableOpacity
            style={[styles.menuItem, { backgroundColor: colors.surface, borderColor: colors.borderSubtle }]}
            onPress={handleExport}
            activeOpacity={0.7}
          >
            <Ionicons name="download-outline" size={20} color={colors.accent} />
            <Text style={[styles.menuText, { color: colors.text }]}>导出分析记录</Text>
            <Ionicons name="chevron-forward" size={16} color={colors.textTertiary} />
          </TouchableOpacity>
        </View>

        {/* 关于 */}
        <View style={styles.section}>
          <Text style={[styles.sectionTitle, { color: colors.textSecondary }]}>关于</Text>

          <View style={[styles.aboutCard, { backgroundColor: colors.surface, borderColor: colors.borderSubtle }]}>
            <Text style={[styles.appName, { color: colors.text }]}>合同红绿灯</Text>
            <Text style={[styles.version, { color: colors.textTertiary }]}>版本 0.1.0</Text>
            <Text style={[styles.copyright, { color: colors.textTertiary }]}>
              开源合同风险审查工具
            </Text>
          </View>
        </View>
      </ScrollView>

      <Dialog
        visible={showClearDialog}
        title="清除缓存"
        text="确定要清除所有本地缓存吗？这将删除所有历史记录和设置。"
        onConfirm={handleClearCache}
        onCancel={() => setShowClearDialog(false)}
        confirmText="清除"
      />
    </View>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
  },
  content: {
    padding: spacing.lg,
    gap: spacing.xl,
  },
  section: {
    gap: spacing.sm,
  },
  sectionTitle: {
    fontSize: fontSize.sm,
    fontWeight: '600',
    textTransform: 'uppercase',
    letterSpacing: 0.5,
  },
  configGroup: {
    gap: spacing.sm,
  },
  inputRow: {
    flexDirection: 'row',
    alignItems: 'center',
    borderWidth: 1,
    borderRadius: borderRadius.md,
    paddingHorizontal: spacing.md,
    height: 44,
  },
  inputLabel: {
    fontSize: fontSize.sm,
    width: 40,
  },
  input: {
    flex: 1,
    fontSize: fontSize.sm,
    padding: 0,
  },
  testButton: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    height: 44,
    borderRadius: borderRadius.md,
    gap: spacing.sm,
  },
  testButtonText: {
    fontSize: fontSize.sm,
    fontWeight: '600',
  },
  statusRow: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: spacing.sm,
  },
  statusDot: {
    width: 8,
    height: 8,
    borderRadius: 4,
  },
  statusText: {
    fontSize: fontSize.sm,
  },
  scanPlaceholder: {
    borderWidth: 1,
    borderStyle: 'dashed',
    borderRadius: borderRadius.lg,
    padding: spacing.xxl,
    alignItems: 'center',
    gap: spacing.md,
  },
  scanText: {
    fontSize: fontSize.sm,
  },
  menuItem: {
    flexDirection: 'row',
    alignItems: 'center',
    borderWidth: 1,
    borderRadius: borderRadius.md,
    paddingHorizontal: spacing.lg,
    height: 52,
    gap: spacing.md,
  },
  menuText: {
    flex: 1,
    fontSize: fontSize.sm,
  },
  aboutCard: {
    borderWidth: 1,
    borderRadius: borderRadius.lg,
    padding: spacing.xl,
    alignItems: 'center',
    gap: spacing.xs,
  },
  appName: {
    fontSize: fontSize.lg,
    fontWeight: '700',
  },
  version: {
    fontSize: fontSize.sm,
  },
  copyright: {
    fontSize: fontSize.xs,
  },
});

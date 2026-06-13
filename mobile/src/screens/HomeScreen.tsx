import React, { useState, useEffect, useCallback } from 'react';
import {
  View,
  Text,
  ScrollView,
  TouchableOpacity,
  StyleSheet,
  ActivityIndicator,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { Ionicons } from '@expo/vector-icons';
import * as ImagePicker from 'expo-image-picker';
import * as DocumentPicker from 'expo-document-picker';
import { useThemeContext } from '../contexts/ThemeContext';
import { useConnectionContext } from '../contexts/ConnectionContext';
import { useToastContext } from '../contexts/ToastContext';
import { spacing, borderRadius, fontSize } from '../theme';
import TopBar from '../components/TopBar';
import ConnectionBar from '../components/ConnectionBar';
import ContractCard from '../components/ContractCard';
import EmptyState from '../components/EmptyState';
import { getHistory } from '../services/storage';
import type { ContractListItem } from '../types/api';
import type { HomeScreenProps } from '../types/navigation';

export default function HomeScreen({ navigation }: HomeScreenProps) {
  const { colors, isDark, setThemeMode, themeMode } = useThemeContext();
  const { status } = useConnectionContext();
  const { showToast } = useToastContext();
  const [recentContracts, setRecentContracts] = useState<ContractListItem[]>([]);
  const [loading, setLoading] = useState(false);

  // 加载最近分析记录
  useEffect(() => {
    loadHistory();
  }, []);

  const loadHistory = async () => {
    try {
      const history = await getHistory();
      setRecentContracts(history.slice(0, 5));
    } catch {}
  };

  // 拍照上传
  const handleCamera = async () => {
    const { status } = await ImagePicker.requestCameraPermissionsAsync();
    if (status !== 'granted') {
      showToast('需要相机权限才能拍照');
      return;
    }

    const result = await ImagePicker.launchCameraAsync({
      mediaTypes: ['images'],
      quality: 0.8,
    });

    if (!result.canceled) {
      navigation.navigate('Analysis', {
        filePath: result.assets[0].uri,
        fileName: '拍照上传',
      });
    }
  };

  // 选择文件
  const handleFilePick = async () => {
    const result = await DocumentPicker.getDocumentAsync({
      type: ['image/*', 'application/pdf'],
    });

    if (!result.canceled) {
      navigation.navigate('Analysis', {
        filePath: result.assets[0].uri,
        fileName: result.assets[0].name,
      });
    }
  };

  // 切换主题
  const toggleTheme = () => {
    const next = isDark ? 'light' : 'dark';
    setThemeMode(next);
  };

  // 跳转到设置页
  const goToSettings = () => {
    // 通过 tab 导航跳转
    navigation.navigate('SettingsTab' as any);
  };

  return (
    <SafeAreaView style={[styles.container, { backgroundColor: colors.background }]} edges={['top']}>
      <TopBar
        title="合同红绿灯"
        rightAction={
          <TouchableOpacity onPress={toggleTheme}>
            <Ionicons
              name={isDark ? 'sunny' : 'moon'}
              size={22}
              color={colors.text}
            />
          </TouchableOpacity>
        }
      />

      <ScrollView contentContainerStyle={styles.content}>
        {/* 上传区 */}
        <View style={styles.uploadSection}>
          <TouchableOpacity
            style={[styles.uploadButton, styles.uploadCamera]}
            onPress={handleCamera}
            activeOpacity={0.7}
          >
            <Ionicons name="camera" size={32} color="#ffffff" />
            <Text style={styles.uploadButtonText}>拍照上传</Text>
          </TouchableOpacity>

          <TouchableOpacity
            style={[styles.uploadButton, styles.uploadFile, { backgroundColor: colors.muted }]}
            onPress={handleFilePick}
            activeOpacity={0.7}
          >
            <Ionicons name="folder-open" size={32} color={colors.textSecondary} />
            <Text style={[styles.uploadButtonText, { color: colors.textSecondary }]}>
              选择文件
            </Text>
          </TouchableOpacity>
        </View>

        {/* 连接状态 */}
        <View style={styles.section}>
          <ConnectionBar status={status} onPress={goToSettings} />
        </View>

        {/* 最近分析 */}
        <View style={styles.section}>
          <Text style={[styles.sectionTitle, { color: colors.text }]}>最近分析</Text>

          {recentContracts.length === 0 ? (
            <EmptyState
              icon="document-text-outline"
              text="暂无分析记录，上传合同开始分析"
            />
          ) : (
            recentContracts.map((contract) => (
              <ContractCard
                key={contract.id}
                contract={contract}
                onPress={() => navigation.navigate('Result', { contractId: contract.id })}
              />
            ))
          )}
        </View>
      </ScrollView>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
  },
  content: {
    padding: spacing.lg,
    gap: spacing.lg,
  },
  uploadSection: {
    flexDirection: 'row',
    gap: spacing.md,
  },
  uploadButton: {
    flex: 1,
    height: 120,
    borderRadius: borderRadius.xl,
    alignItems: 'center',
    justifyContent: 'center',
    gap: spacing.sm,
  },
  uploadCamera: {
    backgroundColor: '#38a169',
  },
  uploadFile: {},
  uploadButtonText: {
    color: '#ffffff',
    fontSize: fontSize.sm,
    fontWeight: '600',
  },
  section: {
    gap: spacing.sm,
  },
  sectionTitle: {
    fontSize: fontSize.md,
    fontWeight: '600',
    marginBottom: spacing.xs,
  },
});

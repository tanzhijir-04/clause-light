import React from 'react';
import { createBottomTabNavigator } from '@react-navigation/bottom-tabs';
import { Ionicons } from '@expo/vector-icons';
import { useSafeAreaInsets } from 'react-native-safe-area-context';
import HomeStack from './HomeStack';
import HistoryScreen from '../screens/HistoryScreen';
import KnowledgeScreen from '../screens/KnowledgeScreen';
import SettingsScreen from '../screens/SettingsScreen';
import { useThemeContext } from '../contexts/ThemeContext';
import type { RootTabParamList } from '../types/navigation';

const Tab = createBottomTabNavigator<RootTabParamList>();

const TAB_ICONS: Record<keyof RootTabParamList, { focused: keyof typeof Ionicons.glyphMap; unfocused: keyof typeof Ionicons.glyphMap }> = {
  HomeTab: { focused: 'home', unfocused: 'home-outline' },
  HistoryTab: { focused: 'time', unfocused: 'time-outline' },
  KnowledgeTab: { focused: 'book', unfocused: 'book-outline' },
  SettingsTab: { focused: 'settings', unfocused: 'settings-outline' },
};

const TAB_LABELS: Record<keyof RootTabParamList, string> = {
  HomeTab: '首页',
  HistoryTab: '历史',
  KnowledgeTab: '知识库',
  SettingsTab: '设置',
};

export default function RootNavigator() {
  const { colors } = useThemeContext();
  const insets = useSafeAreaInsets();

  return (
    <Tab.Navigator
      screenOptions={({ route }) => ({
        headerShown: false,
        tabBarIcon: ({ focused, color, size }) => {
          const icons = TAB_ICONS[route.name];
          return (
            <Ionicons
              name={focused ? icons.focused : icons.unfocused}
              size={22}
              color={color}
            />
          );
        },
        tabBarLabel: TAB_LABELS[route.name],
        tabBarActiveTintColor: colors.accent,
        tabBarInactiveTintColor: colors.textTertiary,
        tabBarStyle: {
          backgroundColor: colors.surface,
          borderTopColor: colors.border,
          height: 56 + insets.bottom,
          paddingBottom: insets.bottom,
          paddingTop: 8,
        },
        tabBarLabelStyle: {
          fontSize: 10,
          fontWeight: '500',
        },
      })}
    >
      <Tab.Screen name="HomeTab" component={HomeStack} />
      <Tab.Screen name="HistoryTab" component={HistoryScreen} />
      <Tab.Screen name="KnowledgeTab" component={KnowledgeScreen} />
      <Tab.Screen name="SettingsTab" component={SettingsScreen} />
    </Tab.Navigator>
  );
}

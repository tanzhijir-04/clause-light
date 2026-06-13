import type { NativeStackScreenProps } from '@react-navigation/native-stack';
import type { BottomTabScreenProps } from '@react-navigation/bottom-tabs';
import type { CompositeScreenProps, NavigatorScreenParams } from '@react-navigation/native';

// 底部 Tab 参数
export type RootTabParamList = {
  HomeTab: undefined;
  HistoryTab: undefined;
  KnowledgeTab: undefined;
  SettingsTab: undefined;
};

// 首页 Stack 参数
export type HomeStackParamList = {
  Home: undefined;
  Analysis: { filePath: string; fileName: string; contractType?: string };
  Result: { contractId: string };
};

// 各页面 Props 类型
export type HomeScreenProps = CompositeScreenProps<
  NativeStackScreenProps<HomeStackParamList, 'Home'>,
  BottomTabScreenProps<RootTabParamList>
>;

export type AnalysisScreenProps = NativeStackScreenProps<HomeStackParamList, 'Analysis'>;

export type ResultScreenProps = CompositeScreenProps<
  NativeStackScreenProps<HomeStackParamList, 'Result'>,
  BottomTabScreenProps<RootTabParamList>
>;

export type HistoryScreenProps = BottomTabScreenProps<RootTabParamList, 'HistoryTab'>;
export type KnowledgeScreenProps = BottomTabScreenProps<RootTabParamList, 'KnowledgeTab'>;
export type SettingsScreenProps = BottomTabScreenProps<RootTabParamList, 'SettingsTab'>;

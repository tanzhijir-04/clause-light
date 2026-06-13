import AsyncStorage from '@react-native-async-storage/async-storage';
import type { ContractListItem } from '../types/api';

const HISTORY_KEY = '@clauselight/history';
const MAX_HISTORY = 20;

// 分析记录
export const getHistory = async (): Promise<ContractListItem[]> => {
  const data = await AsyncStorage.getItem(HISTORY_KEY);
  return data ? JSON.parse(data) : [];
};

export const addToHistory = async (contract: ContractListItem): Promise<void> => {
  const existing = await getHistory();
  const updated = [contract, ...existing.filter((a) => a.id !== contract.id)];
  await AsyncStorage.setItem(HISTORY_KEY, JSON.stringify(updated.slice(0, MAX_HISTORY)));
};

export const removeFromHistory = async (id: string): Promise<void> => {
  const existing = await getHistory();
  await AsyncStorage.setItem(
    HISTORY_KEY,
    JSON.stringify(existing.filter((a) => a.id !== id))
  );
};

export const clearHistory = async (): Promise<void> => {
  await AsyncStorage.removeItem(HISTORY_KEY);
};

// 通用设置
export const getSetting = async (key: string): Promise<string | null> => {
  return AsyncStorage.getItem(key);
};

export const setSetting = async (key: string, value: string): Promise<void> => {
  await AsyncStorage.setItem(key, value);
};

export const removeSetting = async (key: string): Promise<void> => {
  await AsyncStorage.removeItem(key);
};

// 清除所有数据
export const clearAll = async (): Promise<void> => {
  const keys = await AsyncStorage.getAllKeys();
  const clauseKeys = keys.filter((k) => k.startsWith('@clauselight/'));
  await AsyncStorage.multiRemove(clauseKeys);
};

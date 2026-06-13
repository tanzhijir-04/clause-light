import React, { createContext, useContext, useState, useEffect, useCallback, useMemo } from 'react';
import AsyncStorage from '@react-native-async-storage/async-storage';

const CONNECTION_STORAGE_KEY = '@clauselight/connection';

export type ConnectionMode = 'lan' | 'scan' | 'cloud';
export type ConnectionStatus = 'connected' | 'cloud' | 'offline';

interface ConnectionConfig {
  mode: ConnectionMode;
  // LAN 模式
  serverIp: string;
  port: string;
  // 云端模式
  cloudUrl: string;
  apiKey: string;
}

interface ConnectionContextType {
  config: ConnectionConfig;
  status: ConnectionStatus;
  setMode: (mode: ConnectionMode) => void;
  setLanConfig: (ip: string, port: string) => void;
  setCloudConfig: (url: string, key: string) => void;
  testConnection: () => Promise<boolean>;
  baseUrl: string;
  wsUrl: string;
}

const defaultConfig: ConnectionConfig = {
  mode: 'lan',
  serverIp: '192.168.1.100',
  port: '8080',
  cloudUrl: '',
  apiKey: '',
};

const ConnectionContext = createContext<ConnectionContextType | undefined>(undefined);

export function ConnectionProvider({ children }: { children: React.ReactNode }) {
  const [config, setConfig] = useState<ConnectionConfig>(defaultConfig);
  const [status, setStatus] = useState<ConnectionStatus>('offline');

  // 加载保存的连接配置
  useEffect(() => {
    AsyncStorage.getItem(CONNECTION_STORAGE_KEY).then((stored) => {
      if (stored) {
        try {
          const parsed = JSON.parse(stored) as ConnectionConfig;
          setConfig(parsed);
        } catch {}
      }
    });
  }, []);

  // 保存配置
  const saveConfig = useCallback((newConfig: ConnectionConfig) => {
    setConfig(newConfig);
    AsyncStorage.setItem(CONNECTION_STORAGE_KEY, JSON.stringify(newConfig));
  }, []);

  const setMode = useCallback((mode: ConnectionMode) => {
    saveConfig({ ...config, mode });
  }, [config, saveConfig]);

  const setLanConfig = useCallback((ip: string, port: string) => {
    saveConfig({ ...config, serverIp: ip, port });
  }, [config, saveConfig]);

  const setCloudConfig = useCallback((url: string, key: string) => {
    saveConfig({ ...config, cloudUrl: url, apiKey: key });
  }, [config, saveConfig]);

  // 计算基础 URL
  const baseUrl = useMemo(() => {
    if (config.mode === 'cloud' && config.cloudUrl) {
      return config.cloudUrl;
    }
    return `http://${config.serverIp}:${config.port}`;
  }, [config]);

  const wsUrl = useMemo(() => {
    if (config.mode === 'cloud') {
      return '';
    }
    return `ws://${config.serverIp}:${config.port}/ws/client`;
  }, [config]);

  // 测试连接
  const testConnection = useCallback(async (): Promise<boolean> => {
    try {
      const controller = new AbortController();
      const timeout = setTimeout(() => controller.abort(), 3000);

      const response = await fetch(`${baseUrl}/api/contracts/`, {
        signal: controller.signal,
      });

      clearTimeout(timeout);

      if (response.ok) {
        setStatus(config.mode === 'cloud' ? 'cloud' : 'connected');
        return true;
      }
      setStatus('offline');
      return false;
    } catch {
      setStatus('offline');
      return false;
    }
  }, [baseUrl, config.mode]);

  return (
    <ConnectionContext.Provider
      value={{
        config,
        status,
        setMode,
        setLanConfig,
        setCloudConfig,
        testConnection,
        baseUrl,
        wsUrl,
      }}
    >
      {children}
    </ConnectionContext.Provider>
  );
}

export function useConnectionContext(): ConnectionContextType {
  const context = useContext(ConnectionContext);
  if (!context) {
    throw new Error('useConnectionContext must be used within ConnectionProvider');
  }
  return context;
}

import React from 'react';
import { StatusBar } from 'expo-status-bar';
import { GestureHandlerRootView } from 'react-native-gesture-handler';
import { NavigationContainer } from '@react-navigation/native';
import { ThemeProvider, useThemeContext } from './src/contexts/ThemeContext';
import { ConnectionProvider } from './src/contexts/ConnectionContext';
import { ToastProvider } from './src/contexts/ToastContext';
import RootNavigator from './src/navigation/RootNavigator';
import Toast from './src/components/Toast';

function AppContent() {
  const { isDark } = useThemeContext();

  return (
    <>
      <StatusBar style={isDark ? 'light' : 'dark'} />
      <NavigationContainer>
        <RootNavigator />
      </NavigationContainer>
      <Toast />
    </>
  );
}

export default function App() {
  return (
    <GestureHandlerRootView style={{ flex: 1 }}>
      <ThemeProvider>
        <ConnectionProvider>
          <ToastProvider>
            <AppContent />
          </ToastProvider>
        </ConnectionProvider>
      </ThemeProvider>
    </GestureHandlerRootView>
  );
}

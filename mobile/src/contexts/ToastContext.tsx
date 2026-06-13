import React, { createContext, useContext, useState, useCallback, useRef } from 'react';

interface ToastContextType {
  showToast: (message: string) => void;
  hideToast: () => void;
  message: string;
  visible: boolean;
}

const ToastContext = createContext<ToastContextType | undefined>(undefined);

export function ToastProvider({ children }: { children: React.ReactNode }) {
  const [message, setMessage] = useState('');
  const [visible, setVisible] = useState(false);
  const timerRef = useRef<ReturnType<typeof setTimeout>>();

  const hideToast = useCallback(() => {
    setVisible(false);
    setMessage('');
    if (timerRef.current) {
      clearTimeout(timerRef.current);
    }
  }, []);

  const showToast = useCallback((msg: string) => {
    // 清除之前的定时器
    if (timerRef.current) {
      clearTimeout(timerRef.current);
    }

    setMessage(msg);
    setVisible(true);

    // 3 秒后自动消失
    timerRef.current = setTimeout(() => {
      setVisible(false);
      setMessage('');
    }, 3000);
  }, []);

  return (
    <ToastContext.Provider value={{ showToast, hideToast, message, visible }}>
      {children}
    </ToastContext.Provider>
  );
}

export function useToastContext(): ToastContextType {
  const context = useContext(ToastContext);
  if (!context) {
    throw new Error('useToastContext must be used within ToastProvider');
  }
  return context;
}

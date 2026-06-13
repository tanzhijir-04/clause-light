import type { WSMessage } from '../types/api';

type MessageHandler = (msg: WSMessage) => void;
type ErrorHandler = (error: Event) => void;

export class ClauseWebSocket {
  private ws: WebSocket | null = null;
  private heartbeatInterval: ReturnType<typeof setInterval> | null = null;
  private reconnectTimer: ReturnType<typeof setTimeout> | null = null;
  private reconnectAttempts = 0;
  private maxReconnectAttempts = 5;
  private messageHandler: MessageHandler | null = null;
  private errorHandler: ErrorHandler | null = null;
  private _url: string;

  constructor(url: string) {
    this._url = url;
  }

  connect(onMessage: MessageHandler, onError: ErrorHandler) {
    this.messageHandler = onMessage;
    this.errorHandler = onError;

    this.ws = new WebSocket(this._url);

    this.ws.onmessage = (event) => {
      try {
        const msg = JSON.parse(event.data) as WSMessage;
        this.messageHandler?.(msg);
      } catch {}
    };

    this.ws.onerror = (error) => {
      this.errorHandler?.(error);
    };

    this.ws.onclose = () => {
      this.stopHeartbeat();
      this.tryReconnect();
    };

    this.ws.onopen = () => {
      this.reconnectAttempts = 0;
      this.startHeartbeat();
    };
  }

  private startHeartbeat() {
    this.stopHeartbeat();
    this.heartbeatInterval = setInterval(() => {
      if (this.ws?.readyState === WebSocket.OPEN) {
        this.ws.send(JSON.stringify({ type: 'ping' }));
      }
    }, 30000);
  }

  private stopHeartbeat() {
    if (this.heartbeatInterval) {
      clearInterval(this.heartbeatInterval);
      this.heartbeatInterval = null;
    }
  }

  private tryReconnect() {
    if (this.reconnectAttempts >= this.maxReconnectAttempts) {
      return;
    }

    const delay = Math.min(1000 * Math.pow(2, this.reconnectAttempts), 30000);
    this.reconnectAttempts++;

    this.reconnectTimer = setTimeout(() => {
      this.connect(this.messageHandler!, this.errorHandler!);
    }, delay);
  }

  sendAnalyze(text: string, contractType: string = '') {
    if (this.ws?.readyState === WebSocket.OPEN) {
      this.ws.send(
        JSON.stringify({
          type: 'analyze',
          text,
          contractType,
        })
      );
    }
  }

  disconnect() {
    this.stopHeartbeat();
    if (this.reconnectTimer) {
      clearTimeout(this.reconnectTimer);
      this.reconnectTimer = null;
    }
    this.reconnectAttempts = this.maxReconnectAttempts; // 阻止重连
    this.ws?.close();
    this.ws = null;
  }
}

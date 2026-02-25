import { useEffect, useRef, useState, useCallback } from 'react';
import { useAuthStore } from '../store/authStore';

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL || '';

interface WebSocketMessage {
  type: string;
  [key: string]: any;
}

type MessageHandler = (msg: WebSocketMessage) => void;

export function useWebSocket() {
  const { user, isAuthenticated } = useAuthStore();
  const wsRef = useRef<WebSocket | null>(null);
  const reconnectTimer = useRef<ReturnType<typeof setTimeout> | null>(null);
  const [connected, setConnected] = useState(false);
  const handlersRef = useRef<Set<MessageHandler>>(new Set());

  const subscribe = useCallback((handler: MessageHandler) => {
    handlersRef.current.add(handler);
    return () => { handlersRef.current.delete(handler); };
  }, []);

  const connect = useCallback(() => {
    if (!user?._id || !isAuthenticated) return;
    if (wsRef.current?.readyState === WebSocket.OPEN) return;

    // Build WS URL from backend URL
    const wsUrl = BACKEND_URL
      .replace(/^https:/, 'wss:')
      .replace(/^http:/, 'ws:')
      + `/api/ws/${user._id}`;

    try {
      const ws = new WebSocket(wsUrl);
      wsRef.current = ws;

      ws.onopen = () => {
        setConnected(true);
        console.log('[WS] Connected');
      };

      ws.onmessage = (event) => {
        try {
          const msg: WebSocketMessage = JSON.parse(event.data);
          handlersRef.current.forEach((h) => h(msg));
        } catch (e) {
          // ignore non-JSON messages
        }
      };

      ws.onclose = () => {
        setConnected(false);
        wsRef.current = null;
        // Reconnect after 3 seconds
        reconnectTimer.current = setTimeout(connect, 3000);
      };

      ws.onerror = () => {
        ws.close();
      };
    } catch (e) {
      // Reconnect on error
      reconnectTimer.current = setTimeout(connect, 5000);
    }
  }, [user?._id, isAuthenticated]);

  useEffect(() => {
    connect();
    return () => {
      if (reconnectTimer.current) clearTimeout(reconnectTimer.current);
      if (wsRef.current) {
        wsRef.current.close();
        wsRef.current = null;
      }
    };
  }, [connect]);

  // Keep-alive ping every 30s
  useEffect(() => {
    if (!connected) return;
    const interval = setInterval(() => {
      if (wsRef.current?.readyState === WebSocket.OPEN) {
        wsRef.current.send('ping');
      }
    }, 30000);
    return () => clearInterval(interval);
  }, [connected]);

  return { connected, subscribe };
}

import { useEffect, useRef, useState, useCallback } from "react";
import type { WsMessage } from "../types";

interface UseWebSocketReturn {
  isConnected: boolean;
  sendMessage: (data: Record<string, unknown>) => void;
  lastMessage: WsMessage | null;
  error: string | null;
}

const HEARTBEAT_INTERVAL = 30000; // 30s
const MAX_RECONNECT_DELAY = 30000; // 30s cap
const INITIAL_RECONNECT_DELAY = 1000; // 1s

export function useWebSocket(url: string): UseWebSocketReturn {
  const [isConnected, setIsConnected] = useState(false);
  const [lastMessage, setLastMessage] = useState<WsMessage | null>(null);
  const [error, setError] = useState<string | null>(null);

  const wsRef = useRef<WebSocket | null>(null);
  const reconnectAttemptRef = useRef(0);
  const reconnectTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const heartbeatTimerRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const unmountedRef = useRef(false);

  const clearTimers = useCallback(() => {
    if (reconnectTimerRef.current) {
      clearTimeout(reconnectTimerRef.current);
      reconnectTimerRef.current = null;
    }
    if (heartbeatTimerRef.current) {
      clearInterval(heartbeatTimerRef.current);
      heartbeatTimerRef.current = null;
    }
  }, []);

  const startHeartbeat = useCallback(() => {
    if (heartbeatTimerRef.current) {
      clearInterval(heartbeatTimerRef.current);
    }
    heartbeatTimerRef.current = setInterval(() => {
      if (wsRef.current?.readyState === WebSocket.OPEN) {
        wsRef.current.send(JSON.stringify({ type: "ping", payload: {} }));
      }
    }, HEARTBEAT_INTERVAL);
  }, []);

  const connect = useCallback(() => {
    if (unmountedRef.current) return;

    try {
      const ws = new WebSocket(url);

      ws.onopen = () => {
        if (unmountedRef.current) {
          ws.close();
          return;
        }
        setIsConnected(true);
        setError(null);
        reconnectAttemptRef.current = 0;
        startHeartbeat();
      };

      ws.onmessage = (event) => {
        try {
          const data: WsMessage = JSON.parse(event.data);
          // Ignore pong messages
          if (data.type === "pong") return;
          setLastMessage(data);
        } catch {
          console.error("Failed to parse WebSocket message:", event.data);
        }
      };

      ws.onerror = () => {
        setError("WebSocket connection error");
      };

      ws.onclose = () => {
        setIsConnected(false);
        clearTimers();

        if (unmountedRef.current) return;

        // Exponential backoff reconnection
        const attempt = reconnectAttemptRef.current;
        const delay = Math.min(
          INITIAL_RECONNECT_DELAY * Math.pow(2, attempt),
          MAX_RECONNECT_DELAY
        );
        reconnectAttemptRef.current = attempt + 1;

        reconnectTimerRef.current = setTimeout(() => {
          connect();
        }, delay);
      };

      wsRef.current = ws;
    } catch (err) {
      setError(err instanceof Error ? err.message : "Connection failed");
    }
  }, [url, startHeartbeat, clearTimers]);

  useEffect(() => {
    unmountedRef.current = false;
    connect();

    return () => {
      unmountedRef.current = true;
      clearTimers();
      if (wsRef.current) {
        wsRef.current.close();
        wsRef.current = null;
      }
    };
  }, [connect, clearTimers]);

  const sendMessage = useCallback((data: Record<string, unknown>) => {
    if (wsRef.current?.readyState === WebSocket.OPEN) {
      wsRef.current.send(JSON.stringify(data));
    } else {
      setError("WebSocket is not connected");
    }
  }, []);

  return { isConnected, sendMessage, lastMessage, error };
}

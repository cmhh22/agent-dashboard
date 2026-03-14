import { Injectable } from '@angular/core';
import { Observable, Subject } from 'rxjs';
import { environment } from '../../environments/environment';

export interface WebSocketMessage {
  type: 'stream' | 'complete' | 'error';
  content: string;
}

@Injectable({
  providedIn: 'root'
})
export class WebsocketService {
  private socket: WebSocket | null = null;
  private messageSubject = new Subject<WebSocketMessage>();
  private reconnectAttempts = 0;
  private maxReconnectAttempts = 5;
  private reconnectTimer: any = null;
  private intentionalClose = false;
  
  connect(): void {
    if (this.socket?.readyState === WebSocket.OPEN) {
      return; // Already connected
    }

    this.intentionalClose = false;
    this.socket = new WebSocket(environment.wsUrl);

    this.socket.onopen = () => {
      this.reconnectAttempts = 0;
    };

    this.socket.onmessage = (event) => {
      const message: WebSocketMessage = JSON.parse(event.data);
      this.messageSubject.next(message);
    };

    this.socket.onerror = (error) => {
      console.error('WebSocket error:', error);
      this.messageSubject.next({
        type: 'error',
        content: 'WebSocket connection error'
      });
    };

    this.socket.onclose = () => {
      console.log('WebSocket connection closed');
      if (!this.intentionalClose) {
        this.scheduleReconnect();
      }
    };
  }

  disconnect(): void {
    this.intentionalClose = true;
    if (this.reconnectTimer) {
      clearTimeout(this.reconnectTimer);
      this.reconnectTimer = null;
    }
    this.reconnectAttempts = 0;
    if (this.socket) {
      this.socket.close();
      this.socket = null;
    }
  }

  private scheduleReconnect(): void {
    if (this.reconnectAttempts >= this.maxReconnectAttempts) {
      console.warn('Max WebSocket reconnect attempts reached');
      return;
    }
    const delay = Math.min(1000 * Math.pow(2, this.reconnectAttempts), 30000);
    this.reconnectAttempts++;
    console.log(`Reconnecting WebSocket in ${delay}ms (attempt ${this.reconnectAttempts})`);
    this.reconnectTimer = setTimeout(() => this.connect(), delay);
  }

  sendMessage(message: string): void {
    if (this.socket?.readyState === WebSocket.OPEN) {
      this.socket.send(JSON.stringify({ message }));
    } else {
      console.error('WebSocket is not connected');
    }
  }

  getMessages(): Observable<WebSocketMessage> {
    return this.messageSubject.asObservable();
  }

  isConnected(): boolean {
    return this.socket?.readyState === WebSocket.OPEN;
  }
}

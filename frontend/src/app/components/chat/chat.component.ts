import { Component, OnInit, OnDestroy, ViewChild, ElementRef, AfterViewChecked } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { ChatService, ChatMessage } from '../../services/chat.service';
import { WebsocketService, WebSocketMessage } from '../../services/websocket.service';
import { Subscription } from 'rxjs';

@Component({
  selector: 'app-chat',
  standalone: true,
  imports: [CommonModule, FormsModule],
  templateUrl: './chat.component.html',
  styleUrls: ['./chat.component.scss']
})
export class ChatComponent implements OnInit, OnDestroy, AfterViewChecked {
  messages: ChatMessage[] = [];
  currentMessage = '';
  isLoading = false;
  uiNotice: { text: string; tone: 'error' | 'success' } | null = null;
  useStreaming = true;
  conversationId?: string;
  currentStreamingMessage = '';
  modelName = 'gpt-4o-mini';
  wsConnected = false;
  
  // Upload state
  uploadedFiles: { name: string; status: string }[] = [];
  isDragOver = false;
  
  private wsSubscription?: Subscription;
  private shouldScrollToBottom = false;
  private noticeTimer?: ReturnType<typeof setTimeout>;

  @ViewChild('messagesContainer') private messagesContainer?: ElementRef;

  constructor(
    private chatService: ChatService,
    private wsService: WebsocketService
  ) {}

  ngOnInit(): void {
    this.connectWebSocket();
  }

  ngOnDestroy(): void {
    if (this.noticeTimer) {
      clearTimeout(this.noticeTimer);
    }
    this.wsSubscription?.unsubscribe();
    this.wsService.disconnect();
  }

  private setNotice(text: string, tone: 'error' | 'success' = 'error'): void {
    this.uiNotice = { text, tone };
    if (this.noticeTimer) {
      clearTimeout(this.noticeTimer);
    }
    this.noticeTimer = setTimeout(() => {
      this.uiNotice = null;
    }, 4500);
  }

  ngAfterViewChecked(): void {
    if (this.shouldScrollToBottom) {
      this.scrollToBottom();
      this.shouldScrollToBottom = false;
    }
  }

  private scrollToBottom(): void {
    try {
      const el = this.messagesContainer?.nativeElement;
      if (el) {
        el.scrollTop = el.scrollHeight;
      }
    } catch (_) {}
  }

  connectWebSocket(): void {
    // Prevent duplicate subscriptions
    this.wsSubscription?.unsubscribe();
    this.wsService.connect();
    this.wsConnected = true;
    this.wsSubscription = this.wsService.getMessages().subscribe({
      next: (message: WebSocketMessage) => this.handleWebSocketMessage(message),
      error: () => { this.wsConnected = false; },
      complete: () => { this.wsConnected = false; }
    });
  }

  quickMessage(text: string): void {
    this.currentMessage = text;
    this.sendMessage();
  }

  sendMessage(): void {
    if (!this.currentMessage.trim()) return;

    const userMessage: ChatMessage = {
      role: 'user',
      content: this.currentMessage,
      timestamp: new Date()
    };

    this.messages.push(userMessage);
    this.shouldScrollToBottom = true;
    
    if (this.useStreaming && this.wsService.isConnected()) {
      this.sendStreamingMessage(this.currentMessage);
    } else {
      this.sendRegularMessage(this.currentMessage);
    }

    this.currentMessage = '';
  }

  private sendStreamingMessage(message: string): void {
    this.isLoading = true;
    this.currentStreamingMessage = '';
    
    // Add placeholder for streaming response
    const assistantMessage: ChatMessage = {
      role: 'assistant',
      content: '',
      timestamp: new Date()
    };
    this.messages.push(assistantMessage);
    
    this.wsService.sendMessage(message);
  }

  private sendRegularMessage(message: string): void {
    this.isLoading = true;
    
    this.chatService.sendMessage(message, this.conversationId).subscribe({
      next: (response) => {
        this.conversationId = response.conversation_id;
        
        const assistantMessage: ChatMessage = {
          role: 'assistant',
          content: response.response,
          timestamp: new Date(),
          toolCalls: response.tool_calls,
          sources: response.sources
        };
        
        this.messages.push(assistantMessage);
        this.isLoading = false;
        this.shouldScrollToBottom = true;
      },
      error: (error) => {
        console.error('Error sending message:', error);
        this.setNotice('No se pudo enviar el mensaje. Reintenta en unos segundos.', 'error');
        this.isLoading = false;
      }
    });
  }

  private handleWebSocketMessage(message: WebSocketMessage): void {
    const lastMessage = this.messages[this.messages.length - 1];
    
    switch (message.type) {
      case 'stream':
        if (lastMessage && lastMessage.role === 'assistant') {
          lastMessage.content += message.content;
          this.shouldScrollToBottom = true;
        }
        break;
      
      case 'complete':
        this.isLoading = false;
        break;
      
      case 'error':
        console.error('WebSocket error:', message.content);
        this.setNotice(message.content || 'Error en WebSocket. Cambia a modo sin streaming o reconecta.', 'error');
        this.isLoading = false;
        break;
    }
  }

  toggleStreaming(): void {
    this.useStreaming = !this.useStreaming;
    if (this.useStreaming) {
      this.connectWebSocket();
      this.setNotice('Streaming activado.', 'success');
    } else {
      this.wsSubscription?.unsubscribe();
      this.wsService.disconnect();
      this.setNotice('Streaming desactivado. Usando modo request/response.', 'success');
    }
  }

  clearChat(): void {
    this.messages = [];
    this.conversationId = undefined;
  }

  // ── File Upload ──
  onDragOver(event: DragEvent): void {
    event.preventDefault();
    event.stopPropagation();
    this.isDragOver = true;
  }

  onDragLeave(event: DragEvent): void {
    event.preventDefault();
    event.stopPropagation();
    this.isDragOver = false;
  }

  onDrop(event: DragEvent): void {
    event.preventDefault();
    event.stopPropagation();
    this.isDragOver = false;
    const files = event.dataTransfer?.files;
    if (files) {
      for (let i = 0; i < files.length; i++) {
        this.uploadFile(files[i]);
      }
    }
  }

  onFileSelect(event: Event): void {
    const input = event.target as HTMLInputElement;
    if (input.files) {
      for (let i = 0; i < input.files.length; i++) {
        this.uploadFile(input.files[i]);
      }
      input.value = ''; // reset so same file can be re-selected
    }
  }

  private uploadFile(file: File): void {
    const entry = { name: file.name, status: 'uploading' };
    this.uploadedFiles.push(entry);
    this.chatService.uploadFile(file).subscribe({
      next: () => {
        entry.status = 'done';
        this.setNotice(`Documento subido: ${file.name}`, 'success');
      },
      error: (err) => {
        console.error('Upload failed:', err);
        entry.status = 'error';
        this.setNotice(`Falló la subida de ${file.name}`, 'error');
      }
    });
  }
}

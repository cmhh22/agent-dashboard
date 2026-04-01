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
  private pendingAssistantIndex: number | null = null;

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
    if (!this.currentMessage.trim() || this.isLoading) return;

    const userMessage: ChatMessage = {
      role: 'user',
      content: this.currentMessage,
      timestamp: new Date()
    };

    this.messages.push(userMessage);

    // Reserve a single assistant bubble for both streaming and non-streaming modes.
    const assistantMessage: ChatMessage = {
      role: 'assistant',
      content: '',
      timestamp: new Date()
    };
    this.messages.push(assistantMessage);
    this.pendingAssistantIndex = this.messages.length - 1;

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

    this.wsService.sendMessage(message);
  }

  private sendRegularMessage(message: string): void {
    this.isLoading = true;
    
    this.chatService.sendMessage(message, this.conversationId).subscribe({
      next: (response) => {
        this.conversationId = response.conversation_id;

        const assistantMessage = this.getPendingAssistantMessage();
        if (assistantMessage) {
          assistantMessage.content = response.response;
          assistantMessage.toolCalls = response.tool_calls;
          assistantMessage.sources = response.sources;
        } else {
          this.messages.push({
            role: 'assistant',
            content: response.response,
            timestamp: new Date(),
            toolCalls: response.tool_calls,
            sources: response.sources
          });
        }

        this.pendingAssistantIndex = null;
        this.isLoading = false;
        this.shouldScrollToBottom = true;
      },
      error: (error) => {
        console.error('Error sending message:', error);
        this.dropEmptyPendingAssistant();
        this.setNotice('Unable to send message. Please try again in a few seconds.', 'error');
        this.pendingAssistantIndex = null;
        this.isLoading = false;
      }
    });
  }

  private handleWebSocketMessage(message: WebSocketMessage): void {
    const pendingMessage = this.getPendingAssistantMessage();
    const lastMessage = this.messages[this.messages.length - 1];
    
    switch (message.type) {
      case 'stream':
        if (pendingMessage) {
          pendingMessage.content += message.content;
          this.shouldScrollToBottom = true;
        } else if (lastMessage && lastMessage.role === 'assistant') {
          lastMessage.content += message.content;
          this.shouldScrollToBottom = true;
        }
        break;
      
      case 'complete':
        this.pendingAssistantIndex = null;
        this.isLoading = false;
        break;
      
      case 'error':
        console.error('WebSocket error:', message.content);
        this.dropEmptyPendingAssistant();
        this.setNotice(message.content || 'Real-time connection error. Switch to non-streaming mode or reconnect.', 'error');
        this.pendingAssistantIndex = null;
        this.isLoading = false;
        break;
    }
  }

  private getPendingAssistantMessage(): ChatMessage | null {
    if (this.pendingAssistantIndex === null) {
      return null;
    }
    return this.messages[this.pendingAssistantIndex] ?? null;
  }

  private dropEmptyPendingAssistant(): void {
    const pendingMessage = this.getPendingAssistantMessage();
    if (pendingMessage && !pendingMessage.content.trim() && this.pendingAssistantIndex !== null) {
      this.messages.splice(this.pendingAssistantIndex, 1);
    }
  }

  toggleStreaming(): void {
    this.useStreaming = !this.useStreaming;
    if (this.useStreaming) {
      this.connectWebSocket();
      this.setNotice('Streaming enabled.', 'success');
    } else {
      this.wsSubscription?.unsubscribe();
      this.wsService.disconnect();
      this.setNotice('Streaming disabled. Using standard response mode.', 'success');
    }
  }

  clearChat(): void {
    this.messages = [];
    this.conversationId = undefined;
    this.pendingAssistantIndex = null;
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
        this.setNotice(`Document uploaded: ${file.name}`, 'success');
      },
      error: (err) => {
        console.error('Upload failed:', err);
        entry.status = 'error';
        this.setNotice(`Upload failed for ${file.name}`, 'error');
      }
    });
  }
}

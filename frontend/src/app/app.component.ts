import { Component } from '@angular/core';
import { RouterOutlet } from '@angular/router';
import { ChatComponent } from './components/chat/chat.component';

@Component({
  selector: 'app-root',
  standalone: true,
  imports: [RouterOutlet, ChatComponent],
  template: `
    <app-chat></app-chat>
  `,
  styles: []
})
export class AppComponent {
  title = 'agent-dashboard-frontend';
}

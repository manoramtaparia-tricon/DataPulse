import { Component, inject, OnDestroy } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { ActivatedRoute, RouterLink } from '@angular/router';
import { ProjectChatService, TrackingResponse } from '../../services/project-chat/project-chat.service';

interface ChatMessage {
  sender: 'user' | 'assistant';
  kind: 'text' | 'loading' | 'tracking';
  text?: string;
  loading?: boolean;
  tracking?: TrackingResponse;
}

@Component({
  selector: 'app-project-chat',
  standalone: true,
  imports: [FormsModule, RouterLink],
  templateUrl: './project-chat.component.html',
  styleUrl: './project-chat.component.scss'
})
export class ProjectChatComponent implements OnDestroy {
  private readonly route = inject(ActivatedRoute);
  private readonly chatService = inject(ProjectChatService);
  private loaderIntervalId: ReturnType<typeof setInterval> | undefined;
  private isDestroyed = false;

  protected readonly project = this.chatService.getProject(this.route.snapshot.paramMap.get('id') ?? 'customer-data-platform');
  protected readonly loaderSteps = this.chatService.getLoaderSteps();

  protected messages: ChatMessage[] = [];

  protected question = '';
  protected loading = false;
  protected activeLoaderStepIndex = 0;

  protected updateQuestion(event: Event): void {
    this.question = (event.target as HTMLInputElement).value;
  }

  protected sendQuestion(): void {
    const trimmedQuestion = this.question.trim();

    if (!trimmedQuestion || this.loading) {
      return;
    }

    this.messages = [...this.messages, { sender: 'user', kind: 'text', text: trimmedQuestion }];
    this.question = '';
    this.loading = true;

    const loaderMessage: ChatMessage = {
      sender: 'assistant',
      kind: 'loading',
      text: this.loaderSteps[0],
      loading: true
    };

    this.messages = [...this.messages, loaderMessage];
    this.activeLoaderStepIndex = 0;

    this.loaderIntervalId = setInterval(() => {
      this.activeLoaderStepIndex = (this.activeLoaderStepIndex + 1) % this.loaderSteps.length;
      const lastMessage = this.messages[this.messages.length - 1];

      if (lastMessage?.loading) {
        this.messages = [
          ...this.messages.slice(0, -1),
          {
            ...lastMessage,
            text: this.loaderSteps[this.activeLoaderStepIndex]
          }
        ];
      }
    }, 520);

      void this.chatService.submitQuestion(this.project.title, trimmedQuestion)
        .then((tracking) => {
          if (this.isDestroyed) {
            return;
          }

          this.clearLoaderAnimation();
          this.messages = this.messages.slice(0, -1).concat({
            sender: 'assistant',
            kind: 'tracking',
            tracking
          });
          this.loading = false;
        })
        .catch(() => {
          if (this.isDestroyed) {
            return;
          }

          this.clearLoaderAnimation();
          this.messages = this.messages.slice(0, -1).concat({
            sender: 'assistant',
            kind: 'text',
            text: 'Unable to reach the diagnostic service right now. Please try again.'
          });
          this.loading = false;
        });
  }

  private clearLoaderAnimation(): void {
    if (this.loaderIntervalId !== undefined) {
      clearInterval(this.loaderIntervalId);
      this.loaderIntervalId = undefined;
    }
  }

  ngOnDestroy(): void {
    this.isDestroyed = true;
    this.clearLoaderAnimation();
  }
}

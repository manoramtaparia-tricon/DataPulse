import { Component, inject, OnDestroy } from '@angular/core';
import { ActivatedRoute, RouterLink } from '@angular/router';
import { ProjectChatService } from '../../services/project-chat/project-chat.service';

interface ChatMessage {
  sender: 'user' | 'assistant';
  text: string;
  loading?: boolean;
}

@Component({
  selector: 'app-project-chat',
  standalone: true,
  imports: [RouterLink],
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

  protected messages: ChatMessage[] = [
    {
      sender: 'user',
      text: 'Where is customer C123? Why is it not in the Gold table?'
    },
    {
      sender: 'assistant',
      text: 'Checking the data for customer C123 across all pipeline stages...'
    }
  ];

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

    this.messages = [...this.messages, { sender: 'user', text: trimmedQuestion }];
    this.question = '';
    this.loading = true;

    const loaderMessage: ChatMessage = {
      sender: 'assistant',
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

    void this.chatService.submitQuestion(this.project.title, trimmedQuestion).then((reply) => {
      if (this.isDestroyed) {
        return;
      }

      this.clearLoaderAnimation();
      this.messages = this.messages.slice(0, -1).concat({ sender: 'assistant', text: reply });
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

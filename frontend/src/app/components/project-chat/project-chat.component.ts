import { Component, inject, OnDestroy } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { ActivatedRoute, RouterLink } from '@angular/router';
import {
  ProjectChatService,
  RcaResponse,
  TrackingAction,
  TrackingResponse
} from '../../services/project-chat/project-chat.service';

type RcaState = 'idle' | 'running' | 'done';

interface ChatMessage {
  sender: 'user' | 'assistant';
  kind: 'text' | 'loading' | 'tracking' | 'rca';
  text?: string;
  loading?: boolean;
  loaderTitle?: string;
  loaderSteps?: string[];
  tracking?: TrackingResponse;
  rcaState?: RcaState;
  rca?: RcaResponse;
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
  private readonly rcaLoaderSteps = this.chatService.getRcaLoaderSteps();

  protected messages: ChatMessage[] = [];

  protected question = '';
  protected loading = false;
  protected activeLoaderStepIndex = 0;

  protected updateQuestion(event: Event): void {
    this.question = (event.target as HTMLInputElement).value;
  }

  // Show the table name
  protected shortTable(table: string | null | undefined): string {
    return table ? table.split('.').pop() ?? table : '';
  }

  // DATA_QUALITY_FILTER -> Data quality filter
  protected humanize(value: string | null | undefined): string {
    if (!value) {
      return '';
    }
    const text = value.replace(/_/g, ' ').toLowerCase();
    return text.charAt(0).toUpperCase() + text.slice(1);
  }

  protected verdictTone(verdict: string): 'success' | 'warning' | 'muted' {
    if (verdict === 'ROOT_CAUSE_IDENTIFIED') {
      return 'success';
    }
    return verdict === 'PROBABLE_CAUSE' ? 'warning' : 'muted';
  }

  /** The RCA action is shown only when the tracking verdict was MISSING or STUCK. */
  protected visibleActions(tracking: TrackingResponse): TrackingAction[] {
    return tracking.actions.filter((action) => action.id !== 'run_rca' || tracking.rca?.eligible === true);
  }

  protected actionLabel(action: TrackingAction, message: ChatMessage): string {
    if (action.id !== 'run_rca') {
      return action.label;
    }
    if (message.rcaState === 'running') {
      return 'Running RCA...';
    }
    return message.rcaState === 'done' ? 'RCA Complete' : action.label;
  }

  protected isActionDisabled(action: TrackingAction, message: ChatMessage): boolean {
    return action.id === 'run_rca' && (this.loading || message.rcaState === 'running' || message.rcaState === 'done');
  }

  protected onAction(action: TrackingAction, messageIndex: number): void {
    if (action.id === 'run_rca') {
      this.runRca(messageIndex);
    }
  }

  protected sendQuestion(): void {
    const trimmedQuestion = this.question.trim();

    if (!trimmedQuestion || this.loading) {
      return;
    }

    this.messages = [...this.messages, { sender: 'user', kind: 'text', text: trimmedQuestion }];
    this.question = '';
    this.beginLoading(`Checking the data for ${this.project.title}...`, this.loaderSteps);

    void this.chatService.submitQuestion(this.project.title, trimmedQuestion)
      .then((tracking) => this.resolveLoading({
        sender: 'assistant',
        kind: 'tracking',
        tracking,
        rcaState: 'idle'
      }))
      .catch((error: unknown) => this.resolveLoading({
        sender: 'assistant',
        kind: 'text',
        text: error instanceof Error ? error.message
          : 'Unable to reach the diagnostic service right now. Please try again.'
      }));
  }

  private runRca(messageIndex: number): void {
    const message = this.messages[messageIndex];
    const tracking = message?.tracking;
    const context = tracking?.rca?.eligible ? tracking.rca.context : null;

    if (!tracking || !context || this.loading || message.rcaState === 'running' || message.rcaState === 'done') {
      return;
    }

    this.updateMessage(messageIndex, { rcaState: 'running' });
    this.beginLoading(`Running root cause analysis for ${tracking.customerId}...`, this.rcaLoaderSteps);

    void this.chatService.runRca(context)
      .then((rca) => {
        this.updateMessage(messageIndex, { rcaState: 'done' });
        this.resolveLoading({ sender: 'assistant', kind: 'rca', rca });
      })
      .catch((error: unknown) => {
        // Allow a retry after a failed RCA.
        this.updateMessage(messageIndex, { rcaState: 'idle' });
        this.resolveLoading({
          sender: 'assistant',
          kind: 'text',
          text: error instanceof Error ? error.message
            : 'Unable to run the root cause analysis right now. Please try again.'
        });
      });
  }

  private beginLoading(title: string, steps: string[]): void {
    this.loading = true;
    this.activeLoaderStepIndex = 0;
    this.messages = [...this.messages, {
      sender: 'assistant',
      kind: 'loading',
      text: steps[0],
      loading: true,
      loaderTitle: title,
      loaderSteps: steps
    }];

    this.loaderIntervalId = setInterval(() => {
      this.activeLoaderStepIndex = (this.activeLoaderStepIndex + 1) % steps.length;
      const lastMessage = this.messages[this.messages.length - 1];

      if (lastMessage?.loading) {
        this.messages = [
          ...this.messages.slice(0, -1),
          {
            ...lastMessage,
            text: steps[this.activeLoaderStepIndex]
          }
        ];
      }
    }, 520);
  }

  /** Replace the trailing loader message with the final assistant message. */
  private resolveLoading(message: ChatMessage): void {
    if (this.isDestroyed) {
      return;
    }

    this.clearLoaderAnimation();
    this.messages = this.messages.slice(0, -1).concat(message);
    this.loading = false;
  }

  private updateMessage(index: number, patch: Partial<ChatMessage>): void {
    if (this.isDestroyed || !this.messages[index]) {
      return;
    }
    this.messages = this.messages.map((message, i) => i === index ? { ...message, ...patch } : message);
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

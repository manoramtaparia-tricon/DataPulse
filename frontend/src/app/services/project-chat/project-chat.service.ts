import { Injectable } from '@angular/core';

export interface ChatProjectSummary {
  id: string;
  title: string;
}

export interface TrackingTimelineItem {
  stage: string;
  detail: string;
  status: string;
  timestamp: string;
  tone: 'success' | 'warning' | 'muted';
}

export interface TrackingAction {
  label: string;
  tone: 'primary' | 'secondary';
}

export interface TrackingSummary {
  status: string;
  message: string;
}

export interface TrackingResponse {
  title: string;
  customerId: string;
  projectTitle: string;
  question: string;
  timeline: TrackingTimelineItem[];
  summary: TrackingSummary;
  actions: TrackingAction[];
}

@Injectable({
  providedIn: 'root'
})
export class ProjectChatService {
  private readonly apiBaseUrl = 'http://localhost:8001';

  private readonly projects: Record<string, ChatProjectSummary> = {
    'customer-data-platform': {
      id: 'customer-data-platform',
      title: 'Customer Data Platform'
    },
    'sales-analytics': {
      id: 'sales-analytics',
      title: 'Sales Analytics'
    },
    'marketing-data': {
      id: 'marketing-data',
      title: 'Marketing Data'
    }
  };

  getProject(id: string): ChatProjectSummary {
    return this.projects[id] ?? this.projects['customer-data-platform'];
  }

  async submitQuestion(projectTitle: string, question: string): Promise<TrackingResponse> {
    const response = await fetch(`${this.apiBaseUrl}/api/diagnose`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json'
      },
      body: JSON.stringify({
        projectTitle,
        question
      })
    });

    if (!response.ok) {
      const failure: unknown = await response.json();
      const message = failure && typeof failure === 'object' && 'message' in failure
        && typeof failure.message === 'string'
        ? failure.message : 'Unable to fetch the pipeline diagnosis.';
      throw new Error(message);
    }

    return response.json() as Promise<TrackingResponse>;
  }

  getLoaderSteps(): string[] {
    return [
      'Checking the data across pipeline stages...',
      'Identifying the data journey from project documentation...',
      'Querying tables and pipeline runs...',
      'Analyzing the results...'
    ];
  }
}

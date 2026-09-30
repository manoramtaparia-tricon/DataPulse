import { Injectable } from '@angular/core';

export interface ChatProjectSummary {
  id: string;
  title: string;
}

@Injectable({
  providedIn: 'root'
})
export class ProjectChatService {
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

  buildAssistantReply(projectTitle: string, question: string): string {
    return `I checked the ${projectTitle} pipeline for "${question}". The issue appears to be in the Bronze to Silver reconciliation path. I am correlating source events, pipeline runs, and entity mappings now.`;
  }

  submitQuestion(projectTitle: string, question: string): Promise<string> {
    return new Promise((resolve) => {
      const latency = 2200 + Math.floor(Math.random() * 900);

      setTimeout(() => {
        resolve(this.buildAssistantReply(projectTitle, question));
      }, latency);
    });
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

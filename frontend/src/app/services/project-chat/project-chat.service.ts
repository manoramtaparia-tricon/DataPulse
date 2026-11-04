import { Injectable } from '@angular/core';
import { environment } from '../../../environments/environment';

export interface ChatProjectSummary {
  id: string;
  title: string;
}

export interface TrackingTimelineItem {
  stage: string;
  layer?: string;
  table?: string;
  detail: string;
  count?: number | null;
  status: string;
  timestamp: string;
  tone: 'success' | 'warning' | 'muted';
}

export type TrackingActionId = 'run_rca' | 'view_queries';

export interface TrackingAction {
  id?: TrackingActionId;
  label: string;
  tone: 'primary' | 'secondary';
}

/** Tracking result echoed back to the API to run RCA (opaque to the UI). */
export type RcaContext = Record<string, unknown>;

/**
 * RCA is offered only when tracking found the entity MISSING or STUCK. Generic
 * (guardrail/out-of-scope) answers and fully-found entities are never eligible.
 */
export interface RcaEligibility {
  eligible: boolean;
  verdict?: 'MISSING' | 'STUCK';
  reason?: string;
  context: RcaContext | null;
}

export interface RcaEvidence {
  finding: string;
  source: string;
  reference?: string | null;
  observed_at?: string | null;
}

export interface RcaHypothesis {
  hypothesis: string;
  confidence: string;
  supporting?: string | null;
  contradicting?: string | null;
}

export interface RcaQuery {
  sql: string;
  row_count: number | null;
  error: string | null;
}

export interface RcaResponse {
  title: string;
  entity: { type: string | null; id: string | null };
  verdict: 'ROOT_CAUSE_IDENTIFIED' | 'PROBABLE_CAUSE' | 'INCONCLUSIVE' | string;
  confidence: 'HIGH' | 'MEDIUM' | 'LOW' | string;
  category: string;
  failingStage: {
    fromLayer: string | null;
    toLayer: string | null;
    table: string | null;
    transformation: string | null;
  };
  summary: string;
  rootCause: string | null;
  evidence: RcaEvidence[];
  hypotheses: RcaHypothesis[];
  pipelineStatus: string | null;
  missingEvidence: string[];
  nextChecks: string[];
  queries: RcaQuery[];
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
  rca?: RcaEligibility;
}

@Injectable({
  providedIn: 'root'
})
export class ProjectChatService {
  private readonly apiBaseUrl = environment.apiUrl;

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
    return this.post<TrackingResponse>('/api/diagnose', { projectTitle, question },
      'Unable to fetch the pipeline diagnosis.');
  }

  async runRca(context: RcaContext): Promise<RcaResponse> {
    return this.post<RcaResponse>('/api/rca', { context },
      'Unable to complete the root cause analysis.');
  }

  private async post<T>(path: string, body: unknown, fallbackError: string): Promise<T> {
    const response = await fetch(`${this.apiBaseUrl}${path}`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json'
      },
      body: JSON.stringify(body)
    });

    if (!response.ok) {
      const failure: unknown = await response.json().catch(() => null);
      const message = failure && typeof failure === 'object' && 'message' in failure
        && typeof failure.message === 'string'
        ? failure.message : fallbackError;
      throw new Error(message);
    }

    return response.json() as Promise<T>;
  }

  getLoaderSteps(): string[] {
    return [
      'Checking the data across pipeline stages...',
      'Identifying the data journey from project documentation...',
      'Querying tables and pipeline runs...',
      'Analyzing the results...'
    ];
  }

  getRcaLoaderSteps(): string[] {
    return [
      'Checking the drop rules for the missing records...',
      'Comparing layer freshness with ingestion times...',
      'Reviewing table history and pipeline runs...',
      'Building the root cause report...'
    ];
  }
}

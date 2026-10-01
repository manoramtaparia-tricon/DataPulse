import { Injectable } from '@angular/core';

export interface ProjectOverviewTab {
  label: string;
  active: boolean;
}

export interface ProjectDetail {
  id: string;
  title: string;
  description: string;
  keyEntities: string[];
  pipelineStages: string[];
}

@Injectable({
  providedIn: 'root'
})
export class ProjectDetailsService {
  private readonly projects: ProjectDetail[] = [
    {
      id: 'customer-data-platform',
      title: 'Customer Data Platform',
      description: 'End-to-end customer data pipeline from source to gold layer.',
      keyEntities: ['Customer (customer_id)', 'Account (account_id)', 'Order (order_id)'],
      pipelineStages: ['Source', 'Bronze', 'Silver', 'Reconciliation', 'Gold']
    },
    {
      id: 'sales-analytics',
      title: 'Sales Analytics',
      description: 'Sales and order data pipeline.',
      keyEntities: ['Sale (sale_id)', 'Order (order_id)', 'Region (region_id)'],
      pipelineStages: ['Source', 'Staging', 'Modeling', 'Metrics']
    },
    {
      id: 'marketing-data',
      title: 'Marketing Data',
      description: 'Marketing events pipeline.',
      keyEntities: ['Campaign (campaign_id)', 'Event (event_id)', 'Channel (channel_id)'],
      pipelineStages: ['Source', 'Ingestion', 'Normalization', 'Gold']
    }
  ];

  getProject(id: string): ProjectDetail | undefined {
    return this.projects.find((project) => project.id === id);
  }

  getOverviewTabs(): ProjectOverviewTab[] {
    return [
      { label: 'Overview', active: true },
    ];
  }
}

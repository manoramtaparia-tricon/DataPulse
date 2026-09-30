import { Injectable } from '@angular/core';

export interface ProjectSummary {
  id: string;
  title: string;
  description: string;
  updatedLabel: string;
}

@Injectable({
  providedIn: 'root'
})
export class HomeService {
  private readonly projects: ProjectSummary[] = [
    {
      id: 'customer-data-platform',
      title: 'Customer Data Platform',
      description: 'End-to-end customer data pipeline from source to gold layer.',
      updatedLabel: 'Updated 2 days ago'
    },
    {
      id: 'sales-analytics',
      title: 'Sales Analytics',
      description: 'Sales and order data pipeline.',
      updatedLabel: 'Updated 5 days ago'
    },
    {
      id: 'marketing-data',
      title: 'Marketing Data',
      description: 'Marketing events pipeline.',
      updatedLabel: 'Updated 1 week ago'
    }
  ];

  getProjects(): ProjectSummary[] {
    return this.projects;
  }
}

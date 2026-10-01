import { Component, inject } from '@angular/core';
import { ActivatedRoute, RouterLink } from '@angular/router';
import { ProjectDetail, ProjectDetailsService } from '../../services/project-details/project-details.service';

@Component({
  selector: 'app-project-details',
  standalone: true,
  imports: [RouterLink],
  templateUrl: './project-details.component.html',
  styleUrl: './project-details.component.scss'
})
export class ProjectDetailsComponent {
  private readonly route = inject(ActivatedRoute);
  private readonly projectDetailsService = inject(ProjectDetailsService);

  protected readonly tabs = this.projectDetailsService.getOverviewTabs();
  protected readonly project: ProjectDetail;

  constructor() {
    const projectId = this.route.snapshot.paramMap.get('id') ?? 'customer-data-platform';
    this.project = this.projectDetailsService.getProject(projectId) ??
      this.projectDetailsService.getProject('customer-data-platform')!;
  }
}

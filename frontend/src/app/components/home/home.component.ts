import { Component, inject } from '@angular/core';
import { RouterLink } from '@angular/router';
import { HomeService, ProjectSummary } from '../../services/home/home.service';

@Component({
  selector: 'app-home',
  standalone: true,
  imports: [RouterLink],
  templateUrl: './home.component.html',
  styleUrl: './home.component.scss'
})
export class HomeComponent {
  private readonly homeService = inject(HomeService);

  protected readonly projects: ProjectSummary[] = this.homeService.getProjects();
}

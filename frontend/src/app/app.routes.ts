import { Routes } from '@angular/router';
import { HomeComponent } from './components/home/home.component';
import { ProjectDetailsComponent } from './components/project-details/project-details.component';
import { ProjectChatComponent } from './components/project-chat/project-chat.component';

export const routes: Routes = [
	{
		path: '',
		component: HomeComponent
	},
	{
		path: 'projects/:id',
		component: ProjectDetailsComponent
	},
	{
		path: 'projects/:id/chat',
		component: ProjectChatComponent
	}
];

import { Routes } from '@angular/router';

// Each collection (video games today; board games and more later) owns a URL
// prefix and a folder under src/app/. `loadComponent` lazy-loads: each page's
// code is a separate bundle fetched the first time you visit it.
export const routes: Routes = [
  // pathMatch: 'full' means "only redirect when the URL is exactly ''" —
  // without it, every URL starts with '' and everything would redirect.
  { path: '', redirectTo: 'video-games', pathMatch: 'full' },
  {
    path: 'video-games',
    loadComponent: () =>
      import('./video-games/video-game-list/video-game-list').then((m) => m.VideoGameList),
    title: "Dexter's Library — Video Games",
  },
  {
    path: 'video-games/new',
    loadComponent: () =>
      import('./video-games/video-game-form/video-game-form').then((m) => m.VideoGameForm),
    title: 'Add a video game',
  },
  {
    path: 'video-games/:id/edit',
    loadComponent: () =>
      import('./video-games/video-game-form/video-game-form').then((m) => m.VideoGameForm),
    title: 'Edit video game',
  },
  {
    path: 'stats',
    loadComponent: () => import('./stats/stats/stats').then((m) => m.Stats),
    title: 'Stats',
  },
  // Unknown URLs fall back to the library rather than a 404 page.
  { path: '**', redirectTo: '' },
];

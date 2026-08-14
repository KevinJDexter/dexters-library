import { Injectable, signal } from '@angular/core';

import { VideoGame } from './video-game';

/**
 * In-memory store for the library. Holds hardcoded mock data until the backend
 * has a /api/video-games endpoint; components already talk to this service, so the
 * swap to HTTP later shouldn't touch any component code.
 */
@Injectable({ providedIn: 'root' })
export class VideoGames {
  // The writable signal stays private so only this service can mutate the
  // list; components get the read-only view below.
  private readonly state = signal<VideoGame[]>([
    { id: 1, title: 'Hades', platform: 'Switch', status: 'playing', coverUrl: null },
    { id: 2, title: 'Outer Wilds', platform: 'PC', status: 'finished', coverUrl: null },
    { id: 3, title: 'Elden Ring', platform: 'PS5', status: 'backlog', coverUrl: null },
    { id: 4, title: 'Chrono Trigger', platform: 'SNES', status: 'finished', coverUrl: null },
    { id: 5, title: 'Baldur’s Gate 3', platform: 'PC', status: 'playing', coverUrl: null },
    { id: 6, title: 'Metroid Prime', platform: 'VideoGameCube', status: 'backlog', coverUrl: null },
  ]);

  readonly games = this.state.asReadonly();

  byId(id: number): VideoGame | undefined {
    return this.games().find((game) => game.id === id);
  }

  add(draft: Omit<VideoGame, 'id'>): void {
    // Signals require replacing the array, not pushing into it — change
    // detection keys off the reference, not the contents.
    const nextId = Math.max(0, ...this.games().map((g) => g.id)) + 1;
    this.state.update((games) => [...games, { ...draft, id: nextId }]);
  }

  update(id: number, changes: Omit<VideoGame, 'id'>): void {
    this.state.update((games) =>
      games.map((game) => (game.id === id ? { ...changes, id } : game)),
    );
  }
}

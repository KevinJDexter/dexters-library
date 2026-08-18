import { Injectable, computed } from '@angular/core';
import { httpResource } from '@angular/common/http';

import { VideoGame } from './video-game';
import { environment } from '../../environments/environment';

/**
 * In-memory store for the library. Uses httpResource to fetch the list from the backend.
 */
@Injectable({ providedIn: 'root' })
export class VideoGames {
  private readonly videoGamesResource = httpResource<VideoGame[]>(
    () => `${environment.apiUrl}/api/games`,
  );

  readonly videoGames = computed(() => this.videoGamesResource.value() ?? []);

  readonly isLoading = this.videoGamesResource.isLoading;
  readonly error = this.videoGamesResource.error;

  byId(id: number): VideoGame | undefined {
    return this.videoGames().find((game) => game.id === id);
  }

  add(draft: Omit<VideoGame, 'id'>): void {
    // TODO: Not working as intended yet, will be handled in DL-10
    const nextId = Math.max(0, ...this.videoGames().map((g) => g.id)) + 1;
    this.videoGamesResource.update((games) => [...(games || []), { ...draft, id: nextId }]);
  }

  update(id: number, changes: Omit<VideoGame, 'id'>): void {
    // TODO: Not working as intended yet, will be handled in DL-13
    this.videoGamesResource.update((games) =>
      (games || []).map((game) => (game.id === id ? { ...changes, id } : game))
    );
  }

  refresh(): void {
    this.videoGamesResource.reload();
  }
}

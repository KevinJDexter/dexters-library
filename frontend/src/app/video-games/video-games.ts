import { Injectable, computed, inject } from '@angular/core';
import { HttpClient, httpResource } from '@angular/common/http';

import { VideoGame } from './video-game';
import { environment } from '../../environments/environment';
import { firstValueFrom } from 'rxjs';

/**
 * In-memory store for the library. Uses httpResource to fetch the list from the backend.
 */
@Injectable({ providedIn: 'root' })
export class VideoGames {
  private readonly http = inject(HttpClient);
  private readonly videoGamesResource = httpResource<VideoGame[]>(
    () => `${environment.apiUrl}/api/games`,
  );

  readonly videoGames = computed(() => this.videoGamesResource.value() ?? []);

  readonly isLoading = this.videoGamesResource.isLoading;
  readonly error = this.videoGamesResource.error;

  byId(id: number): VideoGame | undefined {
    return this.videoGames().find((game) => game.id === id);
  }

  async add(draft: Omit<VideoGame, 'id' | 'created_at'>): Promise<VideoGame> {
    const created = await firstValueFrom(
      this.http.post<VideoGame>(`${environment.apiUrl}/api/games`, draft, {
        headers: { 'X-Write-Secret': environment.writeSecret },
      })
    );
    this.videoGamesResource.update((games) => [...(games || []), created]);
    return created;
  }

  async update(id: number, changes: Omit<VideoGame, 'id' | 'created_at'>): Promise<VideoGame> {
    const updated = await firstValueFrom(
      this.http.patch<VideoGame>(`${environment.apiUrl}/api/games/${id}`, changes, {
        headers: { 'X-Write-Secret': environment.writeSecret },
      })
    );
    this.videoGamesResource.update((games) =>
      (games || []).map((game) => (game.id === id ? updated : game))
    );
    return updated;
  }

  async delete(id: number): Promise<void> {
    await firstValueFrom(
      this.http.delete<void>(`${environment.apiUrl}/api/games/${id}`, {
        headers: { 'X-Write-Secret': environment.writeSecret },
      })
    );
    this.videoGamesResource.update((games) => (games || []).filter((game) => game.id !== id));
  };

  async importCsv(file: File): Promise<number> {
    const form = new FormData();
    form.append('file', file);

    const result = await firstValueFrom(
      this.http.post<{ imported: number }>(`${environment.apiUrl}/api/games/import`, form, {
        headers: { 'X-Write-Secret': environment.writeSecret },
      })
    );
    this.refresh();
    return result.imported;
  }

  refresh(): void {
    this.videoGamesResource.reload();
  }
}

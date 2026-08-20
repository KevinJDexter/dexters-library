import { ChangeDetectionStrategy, Component, computed, inject, signal } from '@angular/core';
import { RouterLink } from '@angular/router';
import { MatButtonModule } from '@angular/material/button';
import { MatChipsModule } from '@angular/material/chips';
import { MatFormFieldModule } from '@angular/material/form-field';
import { MatIconModule } from '@angular/material/icon';
import { MatInputModule } from '@angular/material/input';
import { MatSelectModule } from '@angular/material/select';

import { VideoGameCard } from '../video-game-card/video-game-card';
import { VideoGameStatus } from '../video-game';
import { VideoGames } from '../video-games';
import { environment } from '../../../environments/environment';
import { HttpErrorResponse } from '@angular/common/http';

@Component({
  selector: 'app-video-game-list',
  imports: [
    RouterLink,
    MatFormFieldModule,
    MatInputModule,
    MatSelectModule,
    MatChipsModule,
    MatIconModule,
    MatButtonModule,
    VideoGameCard,
  ],
  templateUrl: './video-game-list.html',
  styleUrl: './video-game-list.css',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class VideoGameList {
  protected readonly store = inject(VideoGames);

  // Filter state lives in signals so `filtered` below recomputes on its own.
  protected readonly searchTerm = signal('');
  protected readonly statusFilter = signal<VideoGameStatus | 'all'>('all');
  protected readonly platformFilter = signal<string | 'all'>('all');
  protected readonly exportUrl = `${environment.apiUrl}/api/games/export`;

  // Derived from the data, so a new platform shows up in the dropdown the
  // moment a game with that platform exists.
  protected readonly platforms = computed(() =>
    [...new Set(this.store.videoGames().map((game) => game.platform))].sort(),
  );

  protected readonly filtered = computed(() => {
    const term = this.searchTerm().trim().toLowerCase();
    const status = this.statusFilter();
    const platform = this.platformFilter();

    return this.store.videoGames().filter(
      (game) =>
        (term === '' || game.title.toLowerCase().includes(term)) &&
        (status === 'all' || game.status === status) &&
        (platform === 'all' || game.platform === platform),
    );
  });

  protected async onFileSelected(event: Event): Promise<void> {
    const input = event.target as HTMLInputElement;
    const file = input.files?.[0];
    if (!file) {
      return;
    }

    try {
      const count = await this.store.importCsv(file);
      alert(`Imported ${count} games from CSV.`);
    } catch (error) {
      const detail = (error as HttpErrorResponse).error?.detail;

      if (typeof detail === 'string') {
        alert(`Failed to import CSV: ${detail}`);
      } else if (detail?.errors) {
        const messages = detail.errors.map((err: { row: number; message: string }) => `Row ${err.row}: ${err.message}`).join('\n');
        alert(`Failed to import CSV:\n${messages}`);
      } else {
        alert('Failed to import CSV: Unknown error.');
      }
    } finally {
      // Reset the input so the same file can be selected again if needed.
      input.value = '';
    }
  }
}

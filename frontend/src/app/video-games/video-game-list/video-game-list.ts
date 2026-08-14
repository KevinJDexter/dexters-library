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
  private readonly store = inject(VideoGames);

  // Filter state lives in signals so `filtered` below recomputes on its own.
  protected readonly searchTerm = signal('');
  protected readonly statusFilter = signal<VideoGameStatus | 'all'>('all');
  protected readonly platformFilter = signal<string | 'all'>('all');

  // Derived from the data, so a new platform shows up in the dropdown the
  // moment a game with that platform exists.
  protected readonly platforms = computed(() =>
    [...new Set(this.store.games().map((game) => game.platform))].sort(),
  );

  protected readonly filtered = computed(() => {
    const term = this.searchTerm().trim().toLowerCase();
    const status = this.statusFilter();
    const platform = this.platformFilter();

    return this.store.games().filter(
      (game) =>
        (term === '' || game.title.toLowerCase().includes(term)) &&
        (status === 'all' || game.status === status) &&
        (platform === 'all' || game.platform === platform),
    );
  });
}

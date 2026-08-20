import { ChangeDetectionStrategy, Component, inject, input, signal } from '@angular/core';
import { RouterLink } from '@angular/router';
import { MatButtonModule } from '@angular/material/button';
import { MatCardModule } from '@angular/material/card';
import { MatChipsModule } from '@angular/material/chips';
import { MatDialog } from '@angular/material/dialog';
import { MatIconModule } from '@angular/material/icon';
import { MatTooltipModule } from '@angular/material/tooltip';
import { firstValueFrom } from 'rxjs';

import { ConfirmDialog, ConfirmDialogData } from '../../shared/confirm-dialog/confirm-dialog';
import { STATUS_LABELS, VideoGame } from '../video-game';
import { VideoGames } from '../video-games';

@Component({
  selector: 'app-video-game-card',
  imports: [
    RouterLink,
    MatCardModule,
    MatChipsModule,
    MatButtonModule,
    MatIconModule,
    MatTooltipModule,
  ],
  templateUrl: './video-game-card.html',
  styleUrl: './video-game-card.css',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class VideoGameCard {
  // input.required is the signal-based replacement for @Input(); the app
  // won't compile if a parent renders this card without passing a game.
  readonly game = input.required<VideoGame>();
  private readonly store = inject(VideoGames);
  private readonly dialog = inject(MatDialog);
  readonly statusLabels = STATUS_LABELS;

  protected readonly deleteError = signal(false);
  // Guards against a second tap while the first delete is still in flight.
  protected readonly deleting = signal(false);

  protected async deleteGame(): Promise<void> {
    if (this.deleting()) {
      return;
    }

    const data: ConfirmDialogData = {
      title: 'Delete this game?',
      message: `"${this.game().title}" will be removed from your library. This can't be undone.`,
      confirmText: 'Delete',
      destructive: true,
    };

    // afterClosed() emits once, when the dialog closes — firstValueFrom turns
    // that into an awaitable Promise. Escape and backdrop clicks emit
    // undefined, so anything falsy means "don't delete".
    const confirmed = await firstValueFrom(
      this.dialog.open(ConfirmDialog, { data }).afterClosed(),
    );
    if (!confirmed) {
      return;
    }

    this.deleteError.set(false);
    this.deleting.set(true);
    try {
      await this.store.delete(this.game().id);
      // No navigation and no cleanup: the store drops the row, so this whole
      // card unmounts on its own.
    } catch {
      this.deleteError.set(true);
    } finally {
      this.deleting.set(false);
    }
  }
}

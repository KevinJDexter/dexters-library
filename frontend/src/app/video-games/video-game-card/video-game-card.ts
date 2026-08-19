import { ChangeDetectionStrategy, Component, input } from '@angular/core';
import { RouterLink } from '@angular/router';
import { MatButtonModule } from '@angular/material/button';
import { MatCardModule } from '@angular/material/card';
import { MatChipsModule } from '@angular/material/chips';
import { MatIconModule } from '@angular/material/icon';

import { STATUS_LABELS, VideoGame } from '../video-game';

@Component({
  selector: 'app-video-game-card',
  imports: [RouterLink, MatCardModule, MatChipsModule, MatButtonModule, MatIconModule],
  templateUrl: './video-game-card.html',
  styleUrl: './video-game-card.css',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class VideoGameCard {
  // input.required is the signal-based replacement for @Input(); the app
  // won't compile if a parent renders this card without passing a game.
  readonly game = input.required<VideoGame>();
  readonly statusLabels = STATUS_LABELS;
}

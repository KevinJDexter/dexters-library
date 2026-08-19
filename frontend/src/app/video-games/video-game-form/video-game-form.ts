import { ChangeDetectionStrategy, Component, OnInit, computed, inject, input, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { Router, RouterLink } from '@angular/router';
import { MatButtonModule } from '@angular/material/button';
import { MatFormFieldModule } from '@angular/material/form-field';
import { MatIconModule } from '@angular/material/icon';
import { MatInputModule } from '@angular/material/input';
import { MatSelectModule } from '@angular/material/select';

import { VideoGame, VideoGameStatus, STATUS_LABELS } from '../video-game';
import { VideoGames } from '../video-games';

@Component({
  selector: 'app-video-game-form',
  imports: [
    FormsModule,
    RouterLink,
    MatFormFieldModule,
    MatInputModule,
    MatSelectModule,
    MatButtonModule,
    MatIconModule,
  ],
  templateUrl: './video-game-form.html',
  styleUrl: './video-game-form.css',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class VideoGameForm implements OnInit {
  private readonly store = inject(VideoGames);
  private readonly router = inject(Router);
  protected readonly saveError = signal(false);
  protected readonly statusLabels = STATUS_LABELS;
  protected readonly statuses: VideoGameStatus[] = Object.keys(STATUS_LABELS) as VideoGameStatus[];

  // Bound from the :id route param by withComponentInputBinding() in
  // app.config.ts. Absent on /video-games/new, so it's optional — and it arrives
  // as a string because URLs are strings.
  readonly id = input<string>();

  protected readonly editing = computed(() => {
    const id = this.id();
    return id !== undefined ? this.store.byId(Number(id)) : undefined;
  });

  // Template-driven form state. Plain properties (not signals) are fine here:
  // ngModel drives the inputs and nothing else derives from these values.
  protected draft: Omit<VideoGame, 'id' | 'created_at'> = {
    title: '',
    platform: '',
    status: 'notPlayed',
    coverUrl: null,
  };

  ngOnInit(): void {
    // Route-bound inputs aren't populated yet when field initializers run,
    // so the edit case has to load its data here instead of at declaration.
    const existing = this.editing();
    if (existing) {
      this.draft = { ...existing };
    }
  }


  protected async save(): Promise<void> {
    this.saveError.set(false);
    const existing = this.editing();
    if (existing) {
      this.store.update(existing.id, {...this.draft});
    } else {
      try {
        await this.store.add({...this.draft});
      } catch {
        this.saveError.set(true);
        return;
      }
    }
    this.router.navigate(['/video-games']);
  }
}

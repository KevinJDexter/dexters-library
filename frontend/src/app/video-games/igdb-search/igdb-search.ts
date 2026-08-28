import { ChangeDetectionStrategy, Component, inject, output, signal } from '@angular/core';
import { MatButtonModule } from '@angular/material/button';
import { MatFormFieldModule } from '@angular/material/form-field';
import { MatIconModule } from '@angular/material/icon';
import { MatInputModule } from '@angular/material/input';

import { IgdbSearchResult } from '../video-game';
import { VideoGames } from '../video-games';
import { takeUntilDestroyed, toObservable } from '@angular/core/rxjs-interop';
import { debounceTime, switchMap } from 'rxjs/operators';
import { of } from 'rxjs';


const MIN_QUERY_LENGTH = 3; // IGDB rejects shorter queries, so don't even hit the backend

@Component({
  selector: 'app-igdb-search',
  imports: [
    MatFormFieldModule,
    MatInputModule,
    MatButtonModule,
    MatIconModule,
  ],
  templateUrl: './igdb-search.html',
  styleUrl: './igdb-search.css',
  changeDetection: ChangeDetectionStrategy.OnPush,
})

export class IgdbSearch {
  protected readonly store = inject(VideoGames);

  /**
   * Emitted when a result is picked. The parent form listens and pre-fills
   * its draft. output() is the signal-era replacement for @Output/EventEmitter.
   */
  readonly selected = output<IgdbSearchResult>();

  /** Bound to the input; the template writes to it on every keystroke. */
  protected readonly query = signal('');

  protected readonly results = signal<IgdbSearchResult[]>([]);
  protected readonly isSearching = signal(false);
  protected readonly searchError = signal<string | null>(null);
  /** True once a search has completed, so "no results" only shows after one. */
  protected readonly hasSearched = signal(false);

  private readonly searchTrigger = toObservable(this.query).pipe(
    debounceTime(300),
    switchMap((query) => {
      if (query.trim().length < MIN_QUERY_LENGTH) {
        this.hasSearched.set(false);
        return of([]); // Don't hit backend for short queries
      }
      return this.store.searchIgdb(query).then((results) => {
        this.hasSearched.set(true);
        return results;
      }).catch((err) => {
        this.searchError.set(err.error?.detail ?? 'Search failed. Try again later.');
        return [];
      });
    }),
    takeUntilDestroyed()
  );

  constructor() {
    this.searchTrigger.subscribe((results) => {
      this.results.set(results);
      this.isSearching.set(false);
    })
  }

  /** Called when user changes their search query */
  protected onQueryChange(value: string): void {
    if (value.trim().length >= MIN_QUERY_LENGTH) {
      this.isSearching.set(true);
    }
    this.searchError.set(null);
    this.query.set(value);
  }

  /** Emits the selected result */
  protected choose(result: IgdbSearchResult): void {
    this.selected.emit(result);
    // UX choice: clear the results so the list collapses after choosing.
    this.query.set('');
    this.results.set([]);
    this.hasSearched.set(false);
  }

  /** Clears the search back to its initial state. Wired to the X button. */
  protected clear(): void {
    this.query.set('');
    this.results.set([]);
    this.searchError.set(null);
    this.hasSearched.set(false);
  }
}

import { Component } from '@angular/core';
import { RouterLink, RouterLinkActive, RouterOutlet } from '@angular/router';
import { httpResource } from '@angular/common/http';
import { MatButtonModule } from '@angular/material/button';
import { MatToolbarModule } from '@angular/material/toolbar';

import { environment } from '../environments/environment';

/** Shape of the JSON coming back from the Python API's /api/health endpoint. */
interface HealthResponse {
  status: string;
  message: string;
  database: string;
}

@Component({
  selector: 'app-root',
  imports: [RouterOutlet, RouterLink, RouterLinkActive, MatToolbarModule, MatButtonModule],
  templateUrl: './app.html',
  styleUrl: './app.css',
})
export class App {
  private readonly apiUrl = environment.apiUrl;

  /**
   * `httpResource` fires the request automatically and hands back a set of signals:
   * `.value()`, `.isLoading()`, `.error()`. No subscribe, no unsubscribe, no leak.
   *
   * The URL is wrapped in an arrow function on purpose — that makes it reactive.
   * If the URL were built from a signal, changing that signal would re-fire the
   * request by itself. Nothing here depends on a signal yet, but the shape is right.
   */
  protected readonly health = httpResource<HealthResponse>(() => `${this.apiUrl}/api/health`);
}

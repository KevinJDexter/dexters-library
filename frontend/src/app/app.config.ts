import { ApplicationConfig, provideBrowserGlobalErrorListeners } from '@angular/core';
import { provideRouter, withComponentInputBinding } from '@angular/router';
import { provideHttpClient } from '@angular/common/http';

import { routes } from './app.routes';

export const appConfig: ApplicationConfig = {
  providers: [
    provideBrowserGlobalErrorListeners(),
    // withComponentInputBinding maps route params straight onto component
    // inputs — the game form's `id` input comes from the /games/:id/edit URL.
    provideRouter(routes, withComponentInputBinding()),
    // Registers Angular's HTTP client app-wide. Without this line, anything that
    // tries to make an HTTP request throws at runtime.
    provideHttpClient(),
  ],
};

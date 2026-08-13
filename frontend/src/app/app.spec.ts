import { TestBed } from '@angular/core/testing';
import { provideHttpClient } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { App } from './app';
import { environment } from '../environments/environment';

describe('App', () => {
  beforeEach(async () => {
    await TestBed.configureTestingModule({
      imports: [App],
      // The component now makes an HTTP call on creation. `provideHttpClientTesting`
      // swaps the real network layer for a fake one, so tests never hit the API —
      // they'd be slow, and they'd fail whenever the backend isn't running.
      providers: [provideHttpClient(), provideHttpClientTesting()],
    }).compileComponents();
  });

  it('should create the app', () => {
    const fixture = TestBed.createComponent(App);
    expect(fixture.componentInstance).toBeTruthy();
  });

  it('should render the app title', async () => {
    const fixture = TestBed.createComponent(App);
    fixture.detectChanges();

    // The component's httpResource fires a real (intercepted) request on creation.
    // Flush it so the resource settles and whenStable() doesn't hang waiting on it.
    const httpMock = TestBed.inject(HttpTestingController);
    httpMock
      .expectOne(`${environment.apiUrl}/api/health`)
      .flush({ status: 'ok', message: 'ok' });

    await fixture.whenStable();
    const compiled = fixture.nativeElement as HTMLElement;
    expect(compiled.querySelector('h1')?.textContent).toContain("Dexter's Library");
  });
});

import { TestBed } from '@angular/core/testing';
import { provideHttpClient } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { provideRouter } from '@angular/router';
import { App } from './app';
import { environment } from '../environments/environment';

describe('App', () => {
  beforeEach(async () => {
    await TestBed.configureTestingModule({
      imports: [App],
      // The component now makes an HTTP call on creation. `provideHttpClientTesting`
      // swaps the real network layer for a fake one, so tests never hit the API —
      // they'd be slow, and they'd fail whenever the backend isn't running.
      // The toolbar's routerLinks likewise need a router; an empty route table
      // is enough for the links to construct.
      providers: [provideHttpClient(), provideHttpClientTesting(), provideRouter([])],
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
      .flush({ status: 'ok', message: 'ok', database: 'ok' });

    await fixture.whenStable();
    const compiled = fixture.nativeElement as HTMLElement;
    expect(compiled.querySelector('.brand')?.textContent).toContain("Dexter's Library");
  });
});

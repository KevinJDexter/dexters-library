import { TestBed } from '@angular/core/testing';

import { VideoGames } from './video-games';

describe('VideoGames', () => {
  let service: VideoGames;

  beforeEach(() => {
    TestBed.configureTestingModule({});
    service = TestBed.inject(VideoGames);
  });

  it('should be created', () => {
    expect(service).toBeTruthy();
  });
});

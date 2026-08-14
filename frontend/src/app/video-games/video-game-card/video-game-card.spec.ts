import { ComponentFixture, TestBed } from '@angular/core/testing';
import { provideRouter } from '@angular/router';

import { VideoGame } from '../video-game';
import { VideoGameCard } from './video-game-card';

describe('VideoGameCard', () => {
  let component: VideoGameCard;
  let fixture: ComponentFixture<VideoGameCard>;

  const mockVideoGame: VideoGame = {
    id: 1,
    title: 'Hades',
    platform: 'Switch',
    status: 'playing',
    coverUrl: null,
  };

  beforeEach(async () => {
    await TestBed.configureTestingModule({
      imports: [VideoGameCard],
      providers: [provideRouter([])],
    }).compileComponents();

    fixture = TestBed.createComponent(VideoGameCard);
    component = fixture.componentInstance;
    // `game` is a required input; the test has to supply it the same way a
    // parent template would, or creation fails.
    fixture.componentRef.setInput('game', mockVideoGame);
    await fixture.whenStable();
  });

  it('should create', () => {
    expect(component).toBeTruthy();
  });
});

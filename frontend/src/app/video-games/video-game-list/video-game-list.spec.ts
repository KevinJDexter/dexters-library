import { ComponentFixture, TestBed } from '@angular/core/testing';
import { provideRouter } from '@angular/router';

import { VideoGameList } from './video-game-list';

describe('VideoGameList', () => {
  let component: VideoGameList;
  let fixture: ComponentFixture<VideoGameList>;

  beforeEach(async () => {
    await TestBed.configureTestingModule({
      imports: [VideoGameList],
      providers: [provideRouter([])],
    }).compileComponents();

    fixture = TestBed.createComponent(VideoGameList);
    component = fixture.componentInstance;
    await fixture.whenStable();
  });

  it('should create', () => {
    expect(component).toBeTruthy();
  });
});

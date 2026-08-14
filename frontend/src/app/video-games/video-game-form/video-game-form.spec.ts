import { ComponentFixture, TestBed } from '@angular/core/testing';
import { provideRouter } from '@angular/router';

import { VideoGameForm } from './video-game-form';

describe('VideoGameForm', () => {
  let component: VideoGameForm;
  let fixture: ComponentFixture<VideoGameForm>;

  beforeEach(async () => {
    await TestBed.configureTestingModule({
      imports: [VideoGameForm],
      providers: [provideRouter([])],
    }).compileComponents();

    fixture = TestBed.createComponent(VideoGameForm);
    component = fixture.componentInstance;
    await fixture.whenStable();
  });

  it('should create', () => {
    expect(component).toBeTruthy();
  });
});

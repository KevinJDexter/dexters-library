// The backend stores status as a plain string column holding one of these
// camelCase machine keys. This union is frontend-only narrowing: TypeScript
// will catch a typo like 'droped' at compile time, but nothing enforces it
// at the API boundary. Display text lives in a separate label map, not here.
export type VideoGameStatus =
  | 'notPlayed'
  | 'playing'
  | 'beaten'
  | 'onHold'
  | 'completed'
  | 'dropped';

export interface VideoGame {
  id: number;
  title: string;
  platform: string;
  status: VideoGameStatus;
  created_at: string;
  // TODO: may add in logic for this later, may omit entirely. Decision to come later.
  coverUrl: string | null;
}

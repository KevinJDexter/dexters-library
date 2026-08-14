// The backend stores status as a plain string column. This union type is
// frontend-only narrowing: TypeScript will catch a typo like 'finshed' at
// compile time, but nothing enforces it at the API boundary.
export type VideoGameStatus = 'playing' | 'backlog' | 'finished';

export interface VideoGame {
  id: number;
  title: string;
  platform: string;
  status: VideoGameStatus;
  // null until we wire up a metadata API that can supply cover art.
  coverUrl: string | null;
}

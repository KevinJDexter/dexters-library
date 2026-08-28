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

export const STATUS_LABELS: Record<VideoGameStatus, string> = {
  notPlayed: 'Not Played',
  playing: 'Playing',
  beaten: 'Beaten',
  onHold: 'On Hold',
  completed: 'Completed',
  dropped: 'Dropped',
};

/**
 * A game as the API returns it. snake_case because that's what Python sends —
 * this describes the wire, not TypeScript naming taste.
 *
 * Everything below `created_at` is IGDB metadata: nullable, and filled either
 * by an IGDB match or by hand. The backend never overwrites a value that's
 * already set.
 */
export interface VideoGame {
  id: number;
  title: string;
  platform: string;
  status: VideoGameStatus;
  created_at: string;

  igdb_id: number | null;
  /** IGDB image id like "co670h" — NOT a URL. See coverUrl() below. */
  cover_image_id: string | null;
  esrb_rating: string | null;
  summary: string | null;
  /** ISO date string (YYYY-MM-DD), or null. */
  first_release_date: string | null;
  max_local_players: number | null;
  max_online_players: number | null;
}

/**
 * What the form submits. Deliberately its own type rather than
 * Omit<VideoGame, ...>: the server owns everything else, and listing the four
 * fields a human actually fills is clearer than subtracting nine.
 *
 * Mirrors the backend's VideoGameCreate.
 */
export interface VideoGameDraft {
  title: string;
  platform: string;
  status: VideoGameStatus;
  /** When set, the server fetches that IGDB record and fills the metadata. */
  igdb_id: number | null;
}

/** One candidate from GET /api/igdb/search. */
export interface IgdbSearchResult {
  igdb_id: number;
  name: string;
  release_year: number | null;
  cover_url: string | null;
}

/**
 * Build a cover image URL from IGDB's image id.
 *
 * The backend stores the bare id precisely so the size is chosen here, at
 * render time, instead of being baked into the database. Swap the size token
 * for a bigger image: t_cover_big (264x374), t_720p, t_1080p.
 */
export function coverUrl(
  imageId: string | null,
  size: 't_cover_small' | 't_cover_big' | 't_720p' | 't_1080p' = 't_cover_big',
): string | null {
  if (!imageId) {
    return null;
  }
  return `https://images.igdb.com/igdb/image/upload/${size}/${imageId}.jpg`;
}

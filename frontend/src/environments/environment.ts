/**
 * Default settings — used by `ng build` (production) and by the unit tests.
 *
 * Angular swaps this file out for `environment.development.ts` during `ng serve`.
 * That swap is configured in angular.json under build > configurations > development
 * > fileReplacements. Nothing imports the development file directly; the build
 * system substitutes it. That's why both files must export the same shape.
 *
 * This URL is baked into the compiled JavaScript at build time, so it's public.
 * That's fine — it's an address, not a secret. Never put keys or passwords here.
 */
export const environment = {
  production: true,
  apiUrl: 'https://dexters-library-api.onrender.com',
};

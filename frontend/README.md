# CHIA County Explorer — Frontend (CE-C05)

React + Vite + TypeScript UI for the CHIA County Explorer, built in vertical
slices:

- **CE-C01** — application shell / layout, base route table (`/`,
  `/counties/:countyFips`, catch-all), a read-only typed API client, shared
  accessible state primitives (loading / error / not-found), and a minimal,
  neutral, accessible visual foundation (no design system).
- **CE-C02** — county selection (native `<select>` + label) with the URL as the
  authoritative selected-county state; malformed vs. unknown FIPS distinguished
  in place.
- **CE-C03** — the county profile: the Explorer read model is fetched for the
  URL-selected county (`CountyExplorerProvider` / `useCountyExplorer`, keyed to
  `:countyFips`), and the county header (name, state, FIPS, period, completeness)
  plus the four access dimensions are rendered from the API payload. Scores are
  shown as API-provided percentile values (rounded for display only) with the
  fixed score explanation and the geographic-coverage caveat.
- **CE-C04** — evidence, methodology, and composite, all from the same shared
  Explorer payload (no second request): per-dimension supporting evidence in a
  native `<details>` disclosure subordinate to the primary measure; the
  experimental composite in a page-level section after the four dimensions
  (persisted value, fixed `Experimental / Provisional` label, fixed disclosure
  prose — never recomputed, no weights/formula in code); methodology (version,
  normalization method, name, description, status, per-dimension
  `calculation_method` verbatim); and provenance (the API sources — name,
  publisher, dataset, reference period; no links, as all v0.1 URLs are null).
- **CE-C05** — interpretation, placed after the four dimensions and before the
  CE-C04 composite. Deterministic, application-generated descriptive text
  derived from the same shared Explorer payload (no new field, no second
  request): the highest-/lowest-scoring dimension(s) (all tied dimensions named
  jointly), the score gap between them, how many dimensions have an available
  score, and whether the experimental composite is available (naming any
  missing dimensions verbatim). MUA/P participates in the comparison but is
  never called a percentile — a factual qualifier is added whenever it is
  named. No cross-county comparison, no score thresholds/bands, and no
  individual-level, clinical, causal, predictive, or evaluative language
  (enforced by a forbidden-language test). With fewer than two available
  dimension scores, a neutral "not enough data" sentence replaces the
  comparison. CE-C04's sections are unchanged and keep their existing order.

No client-side analytical calculation: scores, normalization, and the composite
are rendered exactly as returned by the API.

## Requirements

- Node.js >= 20
- The CHIA API running at `http://localhost:8000` (`uvicorn app.main:app`) for
  live requests.

## Scripts

| Command | Purpose |
| --- | --- |
| `npm install` | Install dependencies |
| `npm run dev` | Start the Vite dev server (proxies `/api` → `http://localhost:8000`) |
| `npm run build` | Type-check (`tsc`) and build (`vite build`) |
| `npm run lint` | ESLint (TypeScript + React Hooks + jsx-a11y), zero warnings |
| `npm test` | Run the Vitest suite once |
| `npm run preview` | Preview the production build |

## Boundaries (do not violate in later slices)

- The API is the single source of truth. No client-side county list, no
  analytical scoring, no dimension/composite recalculation.
- `county_name` / `state_name` are rendered **exactly as returned** by the API
  (no external geographic-name enrichment).
- The dev server uses a Vite proxy for `/api`; the backend adds **no CORS**.
- `GET /api/v1/counties` and `GET /api/v1/counties/{county_fips}/explorer` are
  the only endpoints consumed.

## Layout

```
frontend/
  index.html
  vite.config.ts        # React plugin, /api dev proxy, Vitest (jsdom) config
  tsconfig.json
  .eslintrc.cjs
  src/
    main.tsx            # React root
    App.tsx             # CountyDirectoryProvider + RouterProvider
    router.tsx          # route table (exported `routes` for tests)
    lib/
      config.ts         # API_BASE_URL
      types.ts          # mirrors of CE-B01 / CE-B02 response contracts
      apiClient.ts      # listCounties(), getCountyExplorer()
      dimensions.ts     # canonical dimension order (access_profile key order)
      interpretation.ts # pure deterministic interpretation derivation (CE-C05)
      countyDirectory.tsx  # county-list context (CE-C02)
      countyExplorer.tsx   # Explorer read-model context, keyed to :countyFips (CE-C03)
    components/
      Layout.tsx
      CountySelector.tsx
      Loading.tsx
      ErrorState.tsx
      NotFound.tsx
      SupportingEvidence.tsx    # per-dimension evidence disclosure (CE-C04)
      ExperimentalComposite.tsx # composite section (CE-C04)
      MethodologyPanel.tsx      # methodology section (CE-C04)
      ProvenancePanel.tsx       # sources section (CE-C04)
      Interpretation.tsx        # interpretation section (CE-C05)
    pages/
      HomePage.tsx
      CountyPage.tsx     # FIPS validation + profile + dimensions + interpretation + evidence/composite/methodology/provenance
    styles/base.css      # reset + neutral tokens + focus + responsive container
    test/
      setup.ts
      harness.tsx        # renderApp(), fetch stubs, payload builders
```

# CHIA County Explorer — Frontend (CE-C01 foundation)

React + Vite + TypeScript foundation for the CHIA County Explorer UI. This slice
(CE-C01) establishes only the application skeleton:

- application shell / layout with an empty header slot (populated in CE-C03)
- base route table (`/`, `/counties/:countyFips`, catch-all)
- a read-only, typed API client for the CHIA County API
- shared, accessible UI state primitives (loading / error / not-found)
- a minimal, neutral, accessible visual foundation (no design system)

It renders an initial state with **no county assumed or selected**. County
selection and URL state are CE-C02; the county profile and the four dimensions
are CE-C03.

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
    App.tsx             # RouterProvider
    router.tsx          # base route table
    lib/
      config.ts         # API_BASE_URL
      types.ts          # mirrors of CE-B01 / CE-B02 response contracts
      apiClient.ts      # listCounties(), getCountyExplorer()
    components/
      Layout.tsx
      Loading.tsx
      ErrorState.tsx
      NotFound.tsx
    pages/
      HomePage.tsx
      CountyRoutePlaceholder.tsx
    styles/base.css      # reset + neutral tokens + focus + responsive container
    test/setup.ts
```

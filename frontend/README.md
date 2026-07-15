# VibeCheck-AI — Frontend (Next.js)

Production dashboard for the VibeCheck-AI analytics engine, built with the
Next.js App Router, React 18, TypeScript and Recharts.

> The Python `web-api` also ships a **zero-build** version of this same dashboard
> at `http://localhost:8000/`, so you can demo the platform without Node. This
> Next.js app is the deployable, componentised frontend.

## Develop

```bash
cd frontend
cp .env.example .env.local          # point NEXT_PUBLIC_API_URL at the web-api
npm install
npm run dev                         # http://localhost:3000
```

The app proxies `/api/*` to the FastAPI web-api (see `next.config.js`), so start
the backend first:

```bash
# from the repo root
pip install -e ".[server]"
python scripts/generate_mock_tickets.py -n 5000   # seed some data
vibecheck serve                                   # http://localhost:8000
```

## Structure

```
app/
  layout.tsx        root layout + global styles
  page.tsx          dashboard (client component)
  globals.css       dark theme
components/
  Kpis.tsx          top KPI strip
  Roadmap.tsx       prioritised roadmap list
  AreaChart.tsx     feedback-by-feature-area bar chart (Recharts)
  Alerts.tsx        routed Slack/Jira alerts
lib/
  api.ts            typed client for the web-api
```

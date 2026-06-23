# CyberDashboard — Security Tools Dashboard

A dark-themed, single-page security dashboard with Chart.js visualizations,
served by a small Python backend. Clean CSS-variable design system.

## Structure

```
CyberDashboard/
├── index.html     # dashboard UI (Chart.js, CSS variables, dark theme)
└── server.py      # backend that serves data to the dashboard
```

## Run

```bash
cd CyberDashboard
python server.py
# open the served URL (e.g. http://127.0.0.1:5000) in your browser
```

Front-end highlights: responsive dark theme via CSS custom properties, Chart.js
graphs for at-a-glance security metrics.

"""What `/` shows when the web UI has not been built: the API is up, and here is how to get the UI."""

PAGE = """<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>NomadGrid API is running</title>
  <style>
    body { margin: 0; font-family: -apple-system, Segoe UI, Roboto, Arial, sans-serif; background: #f2f6fa; color: #1a1a1a; }
    header { background: #003580; color: #fff; padding: 20px 28px; font-size: 22px; font-weight: 800; }
    header span { color: #febb02; }
    main { max-width: 760px; margin: 28px auto; padding: 0 20px; }
    .card { background: #fff; border: 1px solid #cbd5e1; border-radius: 12px; padding: 22px; margin-bottom: 16px; }
    h2 { margin: 0 0 8px; color: #003580; font-size: 17px; }
    code { background: #eef2f6; padding: 2px 6px; border-radius: 4px; font-size: 13px; }
    pre { background: #0b1f3f; color: #e8f0ff; padding: 14px; border-radius: 8px; overflow-x: auto; font-size: 13px; }
    a { color: #006ce4; }
  </style>
</head>
<body>
  <header>normad<span>.grid</span> &nbsp;·&nbsp; the booking API is running</header>
  <main>
    <div class="card">
      <h2>The web page has not been built yet</h2>
      <p>Everything works through the API. To get the website too, build the frontend once:</p>
      <pre>cd frontend
npm install
npm run build</pre>
      <p>Then reload this page. (With Docker, <code>docker compose up --build</code> does this for you.)</p>
    </div>
    <div class="card">
      <h2>Meanwhile</h2>
      <ul>
        <li><a href="/docs">Interactive API documentation</a> — try every endpoint from the browser</li>
        <li><a href="/api/health">/api/health</a> and <a href="/api/meta">/api/meta</a></li>
      </ul>
    </div>
  </main>
</body>
</html>
"""

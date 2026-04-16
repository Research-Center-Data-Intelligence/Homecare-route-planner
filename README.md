# CARAI-Artificial-Intelligence-group-2

Source map
https://download.geofabrik.de/europe/netherlands/limburg.html

Frontend starten:
1. Typ in terminal: cd backend
2. Daarna: python app.py
3. Typ in je browser: http://localhost:5000/

Done!

## GitHub Pages (frontend/dashboard.html) + backend/app.py

GitHub Pages host alleen statische bestanden. Daarom draait de frontend op GitHub Pages en de Flask-backend apart.

1. Zet in **Settings → Pages** de source op **GitHub Actions**.
2. De workflow `.github/workflows/deploy-pages.yml` publiceert `frontend/dashboard.html` als `index.html`.
3. Host `backend/app.py` op een Python host (bijv. Render/Railway/VM) en noteer de publieke backend-URL.
4. Stel in de browser op de GitHub Pages-site eenmalig in:
   - `localStorage.setItem('HOMECARE_API_BASE', 'https://jouw-backend-url')`
   - ververs daarna de pagina.
5. Zet op de backend `CORS_ALLOWED_ORIGINS` op je GitHub Pages origin, bijvoorbeeld:
   - `https://research-center-data-intelligence.github.io`

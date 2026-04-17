# airbc calibration worker

Service CPU long pour les calibrations scientifiques.

## But

Ce service est volontairement hors Vercel pour éviter:

- les timeouts sur les runs longs
- les limites mémoire des fonctions serverless
- les collisions entre trafic web interactif et optimisation scientifique

## Endpoints

- `GET /calibration/available-parameters`
- `POST /calibration/run`
- `POST /calibration/jobs`
- `GET /calibration/jobs/{jobId}`
- `GET /calibration/jobs/{jobId}/result`

## Démarrage local

```bash
cd apps/calibration-worker
python -m venv .venv
.venv\\Scripts\\activate
pip install -r requirements.txt
uvicorn main:app --host 0.0.0.0 --port 8010
```

## Déploiement recommandé

Déployer sur un hôte Python CPU durable:

- Railway
- Render
- Fly.io
- VM dédiée

Variable attendue côté `web`:

- `CALIBRATION_API_BASE_URL`

Exemple:

```env
CALIBRATION_API_BASE_URL=https://calibration-api.airbc.org
```

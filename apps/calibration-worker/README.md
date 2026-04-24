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

Python 3.12 is the recommended runtime. Python 3.14 is not supported yet
because the scientific stack is pinned to NumPy/SciPy versions with stable
3.11/3.12 wheels.

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
- `CALIBRATION_API_SHARED_SECRET`

Variable attendue côté `calibration-worker`:

- `CALIBRATION_WORKER_SHARED_SECRET`

Exemple:

```env
CALIBRATION_API_BASE_URL=https://calibration-api.airbc.org
CALIBRATION_API_SHARED_SECRET=replace_with_a_long_random_secret
CALIBRATION_WORKER_SHARED_SECRET=replace_with_the_same_long_random_secret
```

Le proxy Next du `web` injecte automatiquement le header privé
`x-airbc-worker-secret` vers le worker. Les routes `/calibration/*` refusent
les appels directs sans ce secret partagé.

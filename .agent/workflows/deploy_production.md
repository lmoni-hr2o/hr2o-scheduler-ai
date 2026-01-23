---
description: Deploy the full application (Frontend + Backend) to production
---

# Deploy Backend (Cloud Run)

Use this when you update Python code (`backend/python_solver`).

1. Deploy to Cloud Run:
```bash
cd backend/python_solver
gcloud run deploy timeplanner --source . --cpu 4 --memory 4Gi --concurrency 80 --region europe-west3 --allow-unauthenticated --min-instances 0 --max-instances 5
```
*Note: This automatically builds a new container and routes 100% traffic to it. Cost Optimization: Scales to 0 when idle, capped at 5 instances.*

# Deploy Frontend (Firebase Hosting)

Use this when you update Flutter code (`frontend/lib`).

1. Build the release version:
```bash
cd frontend
flutter build web --release
```

2. Upload to Firebase:
```bash
firebase deploy --only hosting
```
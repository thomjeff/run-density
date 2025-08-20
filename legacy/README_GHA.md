# GitHub Actions — Cloud Run deploy (density branch)

## Secrets required
- `GCP_PROJECT_ID` – your GCP project id
- `GCP_SA_EMAIL` – service account email with roles:
  - Cloud Build Editor
  - Cloud Run Admin
  - Service Account User
  - Storage Admin (for build cache)
- `GCP_SA_KEY` – JSON key of the above service account

## Branch
- Pushes to `density` branch will build and deploy automatically.

## Outputs
- The service is deployed as `run-congestion` in `us-central1` (change in workflow env if needed).

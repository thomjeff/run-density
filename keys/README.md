# Service Account Setup for Local GCS Testing

**Phase 3: Enable GCS Uploads from Local Container**

This directory contains Google Cloud service account JSON keys for testing GCS uploads from the local Docker container.

## ⚠️ Security Warning

**NEVER commit service account keys to git.** All `*.json` files in this directory are git-ignored.

## Setup Instructions

### 1. Create/Download Service Account Key

1. Go to [Google Cloud Console](https://console.cloud.google.com/iam-admin/serviceaccounts)
2. Select your project (`run-density`)
3. Create a new service account or use an existing one
4. Grant the service account the following IAM role:
   - **Storage Object Admin** (or **Storage Admin**) on the `run-density-reports` bucket
   - Optionally restrict to `run-density-reports/*` prefix for tighter access control
5. Create and download a JSON key for the service account

### 2. Place Key in Container

1. Save the downloaded JSON key as `keys/gcs-sa.json` in the project root
2. Verify the file exists: `ls -la keys/gcs-sa.json`

### 3. Enable GCS Uploads in dev.env

1. Open `dev.env`
2. Set `GCS_UPLOAD=true`
3. Uncomment and set `GOOGLE_CLOUD_PROJECT=run-density` (or your project ID)
4. Uncomment `GOOGLE_APPLICATION_CREDENTIALS=/tmp/keys/gcs-sa.json`

Example `dev.env` configuration:
```bash
GCS_UPLOAD=true
GOOGLE_CLOUD_PROJECT=run-density
GOOGLE_APPLICATION_CREDENTIALS=/tmp/keys/gcs-sa.json
```

### 4. Restart Container

```bash
make stop-docker
make dev-docker
```

## Validation

After starting the container with GCS enabled:

1. **Check container logs** for GCS initialization:
   ```bash
   docker logs run-density-dev | grep -i "cloud storage\|gcs"
   ```

2. **Verify environment variables**:
   ```bash
   docker exec run-density-dev printenv | grep -E "GCS_UPLOAD|GOOGLE_CLOUD_PROJECT|GOOGLE_APPLICATION_CREDENTIALS"
   ```

3. **Test GCS upload** by running E2E tests or generating a report and checking GCS bucket for uploaded files.

## Troubleshooting

### "Failed to initialize Cloud Storage client"
- Verify `keys/gcs-sa.json` exists and is readable
- Check that `GOOGLE_APPLICATION_CREDENTIALS` path is correct (`/tmp/keys/gcs-sa.json`)
- Verify service account has Storage Object Admin role

### "Permission denied" errors
- Ensure service account has `Storage Object Admin` or `Storage Admin` role
- Verify bucket name is correct (`run-density-reports`)

### GCS uploads not happening
- Check `GCS_UPLOAD=true` in `dev.env`
- Verify `GOOGLE_CLOUD_PROJECT` is set
- Check container logs for GCS-related errors

## File Structure

```
keys/
├── README.md           # This file
├── .gitkeep           # Keep directory in git (optional)
└── gcs-sa.json        # Service account key (git-ignored, add manually)
```

## IAM Roles Required

Minimum required IAM role for service account:
- **Storage Object Admin** on `run-density-reports` bucket

Recommended for tighter security:
- Custom role with `storage.objects.*` permissions restricted to `run-density-reports/*` prefix

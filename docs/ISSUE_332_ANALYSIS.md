# Issue #332 Analysis: Why a Simple GCS PNG Access Took So Long

## 📋 Issue Summary
**Issue #332**: Cloud Run Heatmaps Not Rendering  
**Expected**: Simple task - access PNG files on GCS via API  
**Reality**: 8+ hours of debugging across multiple failed approaches  
**Root Cause**: Service account credential configuration for signed URL generation  

## 🎯 The Problem That Should Have Been Simple

**What we needed**: Display heatmap PNG images from Google Cloud Storage in a web application.

**What seemed straightforward**:
1. Generate signed URLs for private GCS objects
2. Return URLs from API endpoints  
3. Display images in browser

**What actually happened**: Multiple cascading failures due to credential and configuration issues.

## 🕐 Timeline of Failed Attempts

### Attempt 1: Manual URL Construction (2 hours)
**Approach**: Manually construct GCS URLs  
**Failure**: Returned public URLs for private bucket → 403 Forbidden  
**Lesson**: Private buckets require signed URLs, not public URLs

### Attempt 2: Default Credentials (1 hour)  
**Approach**: Use default Cloud Run credentials for signed URL generation  
**Failure**: `you need a private key to sign credentials`  
**Lesson**: Compute Engine credentials (default) don't have private keys for signing

### Attempt 3: Impersonated Credentials (2 hours)
**Approach**: Use impersonated credentials to get signing capability  
**Failure**: `Invalid form of account ID default`  
**Lesson**: Can't impersonate the same service account that's already running

### Attempt 4: Service Account Key File (1 hour)
**Approach**: Create service account key file and include in Docker image  
**Failure**: Key file not available in build context  
**Lesson**: Docker build context doesn't include local files outside project

### Attempt 5: Base64 Environment Variable (1 hour)
**Approach**: Encode service account key as base64 environment variable  
**Failure**: `cannot access local variable 'project' where it is not associated with a value`  
**Lesson**: Variable scope issues in exception handling paths

### Attempt 6: Fixed Variable Scope (30 minutes)
**Approach**: Fix the project variable extraction from service account key  
**Success**: ✅ Working signed URLs with proper authentication

## 🔍 Root Cause Analysis

### Why This Should Have Been Simple
- **GCS signed URLs are well-documented**
- **Google Cloud Storage client has built-in methods**
- **Cloud Run service accounts are standard**
- **The code pattern is straightforward**

### Why It Took So Long

#### 1. **Credential Complexity**
```
❌ Expected: Use default credentials → Generate signed URLs
✅ Reality: Default credentials can't sign → Need service account with private key
```

**The fundamental issue**: Cloud Run's default Compute Engine credentials are designed for **authentication** (proving identity) but not **signing** (creating cryptographic signatures). Signed URLs require a private key, which default credentials don't have.

#### 2. **Service Account Configuration**
```
❌ Expected: Attach service account → Automatic signing capability  
✅ Reality: Need specific IAM roles + proper credential loading
```

**Required roles**:
- `roles/storage.objectViewer` - Read objects
- `roles/iam.serviceAccountTokenCreator` - Create signed tokens
- `roles/storage.admin` - Full storage access

#### 3. **Environment Variable Complexity**
```
❌ Expected: Set environment variable → Use in code
✅ Reality: Base64 encoding + JSON parsing + variable scope issues
```

**The service account key approach**:
1. Create service account key file
2. Base64 encode the entire JSON file
3. Set as environment variable in Cloud Run
4. Decode and parse in application code
5. Handle variable scope in all code paths

#### 4. **Code Path Complexity**
```python
# This looked simple but had hidden complexity:
if sa_key_b64:
    # Path 1: Use service account key
    creds = service_account.Credentials.from_service_account_info(sa_key_dict)
    # ❌ Missing: project = sa_key_dict.get('project_id')
else:
    # Path 2: Use default credentials  
    creds, project = google.auth.default()
    # ✅ project is defined here

# Later: client = storage.Client(credentials=creds, project=project)
# ❌ Fails in Path 1 because project is undefined
```

#### 5. **Deployment Pipeline Issues**
- **Traffic routing**: New revisions not automatically getting traffic
- **Environment variables**: Long base64 strings in deployment commands
- **Log visibility**: Debugging required checking multiple revision logs

## 🧠 Lessons Learned

### 1. **Credential Types Matter**
```
Authentication ≠ Signing
- Authentication: "I am who I say I am" (default credentials work)
- Signing: "I can create cryptographic signatures" (requires private key)
```

### 2. **Service Account Key Management**
- **Never store keys in code repositories**
- **Use environment variables for deployment**
- **Base64 encoding is necessary for complex JSON**
- **Variable scope must be handled in all code paths**

### 3. **Cloud Run Traffic Management**
- **New revisions don't automatically get traffic**
- **Always verify which revision is serving requests**
- **Use `gcloud run services update-traffic` to redirect**

### 4. **Debugging Strategy**
- **Check logs for specific error messages**
- **Verify environment variables are set correctly**
- **Test signed URLs directly with curl**
- **Monitor Cloud Run revision status**

## 🔧 The Final Working Solution

### Service Account Setup
```bash
# Create service account
gcloud iam service-accounts create run-density-web

# Grant required permissions
gcloud projects add-iam-policy-binding run-density \
  --member="serviceAccount:run-density-web@run-density.iam.gserviceaccount.com" \
  --role="roles/storage.objectViewer"

gcloud projects add-iam-policy-binding run-density \
  --member="serviceAccount:run-density-web@run-density.iam.gserviceaccount.com" \
  --role="roles/iam.serviceAccountTokenCreator"

# Attach to Cloud Run service
gcloud run services update run-density \
  --service-account=run-density-web@run-density.iam.gserviceaccount.com
```

### Service Account Key Management
```bash
# Create key file
gcloud iam service-accounts keys create /tmp/key.json \
  --iam-account=run-density-web@run-density.iam.gserviceaccount.com

# Base64 encode for environment variable
base64 -i /tmp/key.json

# Deploy with environment variable
gcloud run deploy run-density \
  --set-env-vars="SERVICE_ACCOUNT_KEY_B64=<base64-encoded-key>"
```

### Code Implementation
```python
def get_heatmap_signed_url(self, segment_id: str, expiry_seconds=3600):
    # Try to use base64 encoded service account key
    sa_key_b64 = os.getenv("SERVICE_ACCOUNT_KEY_B64")
    if sa_key_b64:
        sa_key_json = base64.b64decode(sa_key_b64).decode('utf-8')
        sa_key_dict = json.loads(sa_key_json)
        creds = service_account.Credentials.from_service_account_info(sa_key_dict)
        # ✅ CRITICAL: Extract project from service account key
        project = sa_key_dict.get('project_id', 'run-density')
    else:
        # Fallback to default credentials
        creds, project = google.auth.default()
    
    client = storage.Client(credentials=creds, project=project)
    bucket = client.bucket(self.bucket)
    blob = bucket.blob(blob_path)
    
    return blob.generate_signed_url(
        version="v4",
        expiration=datetime.timedelta(seconds=expiry_seconds),
        method="GET",
    )
```

## 📊 Success Metrics

### Before Fix
- ❌ API returned `null` for heatmap URLs
- ❌ Browser showed "No heatmap data available"
- ❌ Console errors: `Failed to load resource: 404`
- ❌ Signed URL generation failed with credential errors

### After Fix
- ✅ API returns valid signed URLs with authentication parameters
- ✅ URLs contain `X-Goog-Algorithm=GOOG4-RSA-SHA256`
- ✅ URLs contain `X-Goog-Signature=<cryptographic-signature>`
- ✅ Direct URL access returns HTTP 200 with PNG content
- ✅ All segments (A1, B2, F1, L1) working correctly

## 🎯 Key Takeaways

### For Future GCS Signed URL Implementation
1. **Use service account keys, not default credentials**
2. **Handle variable scope in all code paths**
3. **Verify Cloud Run traffic routing**
4. **Test signed URLs directly with curl**
5. **Monitor logs for specific error messages**

### For Similar "Simple" Tasks
1. **Research credential requirements thoroughly**
2. **Understand the difference between authentication and signing**
3. **Plan for environment variable complexity**
4. **Test each approach completely before moving to the next**
5. **Document the working solution immediately**

## 🚨 Prevention Strategies

### Code Review Checklist
- [ ] Are all variables defined in all code paths?
- [ ] Are service account permissions sufficient for the operation?
- [ ] Are environment variables properly encoded and decoded?
- [ ] Is the Cloud Run service using the correct service account?

### Testing Checklist
- [ ] Test signed URLs directly with curl
- [ ] Verify environment variables are set in Cloud Run
- [ ] Check which revision is serving traffic
- [ ] Monitor logs for specific error patterns

### Documentation Requirements
- [ ] Document the exact service account setup process
- [ ] Document the environment variable encoding process
- [ ] Document the code implementation with all edge cases
- [ ] Document the testing and verification process

---

**Conclusion**: What appeared to be a simple "access PNG file from GCS" task revealed significant complexity in Google Cloud credential management, service account configuration, and Cloud Run deployment patterns. The solution required understanding the difference between authentication and signing, proper service account key management, and careful handling of variable scope in exception paths.

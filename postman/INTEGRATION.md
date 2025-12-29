# Postman + GitHub Integration Guide

**Purpose:** Detailed guide for managing Postman collections in GitHub and integrating with Postman workspace.

---

## Overview

This document explains how to manage Postman test collections in the `run-density` GitHub repository and sync them with Postman workspaces.

**Key Concepts:**
- **Collections** = Test cases organized in folders
- **Environments** = Variable sets for different environments (local, docker, cloud)
- **GitHub** = Source of truth for test definitions
- **Postman** = Testing tool that imports from GitHub

---

## Workflow: GitHub → Postman

### Step 1: Collections are Stored in GitHub

Collections are JSON files in `postman/collections/`:
- `Runflow-v2-API.postman_collection.json` - Main collection
- `Runflow-v2-Scenarios.postman_collection.json` - Scenario-based tests

Environments are JSON files in `postman/environments/`:
- `Local.postman_environment.json` - Local development
- `Docker.postman_environment.json` - Docker Compose
- `Cloud.postman_environment.json` - Production

### Step 2: Import into Postman

**Method A: Import from GitHub (Recommended)**

1. Open Postman
2. Click **Import** button (top left)
3. Select **Code Repository** tab
4. Choose **GitHub**
5. Authenticate with GitHub (if not already)
6. Navigate to: `thomjeff/run-density`
7. Select file: `postman/collections/Runflow-v2-API.postman_collection.json`
8. Click **Import**

**Method B: Import from Local File**

1. Clone repository: `git clone https://github.com/thomjeff/run-density.git`
2. Open Postman
3. Click **Import** button
4. Select **File** tab
5. Navigate to: `run-density/postman/collections/Runflow-v2-API.postman_collection.json`
6. Click **Import**

### Step 3: Import Environment

Repeat import process for environment file:
- `postman/environments/Local.postman_environment.json`

After import, select environment from dropdown (top right corner).

---

## Workflow: Postman → GitHub

### Step 1: Make Changes in Postman

1. Open collection in Postman
2. Make changes (add requests, update tests, etc.)
3. Test changes locally
4. Verify tests pass

### Step 2: Export to GitHub

1. In Postman, click collection name → **...** (three dots) → **Export**
2. Choose **Collection v2.1** format
3. Save to: `postman/collections/Runflow-v2-API.postman_collection.json`
4. Commit and push to GitHub:
   ```bash
   git add postman/collections/Runflow-v2-API.postman_collection.json
   git commit -m "Update Postman collection: Add new error test case"
   git push
   ```

### Step 3: Team Sync

Team members pull latest changes:
```bash
git pull
```

Then re-import collection in Postman (or use Postman's sync feature if using Postman Cloud).

---

## Postman Cloud Integration (Optional)

For teams using Postman Cloud, you can sync collections:

### Setup

1. Create Postman account (if not already)
2. Create workspace in Postman Cloud
3. Push collection to Postman Cloud
4. Connect GitHub repository to Postman Cloud

### Benefits

- ✅ Automatic sync between Postman Cloud and GitHub
- ✅ Team collaboration in Postman Cloud
- ✅ Version history in both places
- ✅ Pull request integration

### Setup Steps

1. In Postman, click **Sync** button
2. Choose **Create Workspace** or **Join Workspace**
3. Push collection to cloud
4. In Postman Cloud, go to **Settings** → **GitHub Integration**
5. Connect repository: `thomjeff/run-density`
6. Enable auto-sync

---

## CI/CD Integration

### Using Newman CLI

Newman is Postman's command-line tool for running collections in CI/CD.

**Install:**
```bash
npm install -g newman
```

**Run Tests:**
```bash
newman run postman/collections/Runflow-v2-API.postman_collection.json \
  -e postman/environments/Local.postman_environment.json \
  --reporters cli,json \
  --reporter-json-export results.json
```

**Output Formats:**
- `cli` - Console output
- `json` - JSON report
- `junit` - JUnit XML (for CI/CD)
- `html` - HTML report

### GitHub Actions

See `.github/workflows/postman-tests.yml.example` for complete workflow.

**Key Steps:**
1. Install Newman
2. Start Docker services
3. Wait for server
4. Run Postman tests
5. Upload results as artifacts

---

## Best Practices

### 1. Version Control

- ✅ **Commit frequently** - Keep collections in sync with code
- ✅ **Use descriptive commits** - "Add error test for invalid start_time"
- ✅ **Review in PRs** - Use pull requests for test changes
- ✅ **Tag versions** - Tag major collection versions

### 2. Collection Organization

- ✅ **Group by feature** - Organize requests in folders
- ✅ **Use descriptive names** - Clear request and folder names
- ✅ **Add descriptions** - Document each request's purpose
- ✅ **Include examples** - Add example responses

### 3. Environment Management

- ✅ **Separate environments** - One file per environment
- ✅ **Use variables** - Don't hardcode URLs or paths
- ✅ **Document variables** - Explain what each variable does
- ✅ **Keep secrets out** - Don't commit API keys or tokens

### 4. Test Scripts

- ✅ **Validate responses** - Check status codes and structure
- ✅ **Extract variables** - Save run_id for follow-up requests
- ✅ **Clear assertions** - Use descriptive test names
- ✅ **Handle errors** - Test both success and error cases

---

## Troubleshooting

### Import Issues

**Problem:** Collection won't import from GitHub
- **Solution:** Check JSON is valid (use JSON validator)
- **Solution:** Verify file path is correct
- **Solution:** Try importing from local file first

**Problem:** Environment variables not working
- **Solution:** Select environment from dropdown (top right)
- **Solution:** Verify environment file is imported
- **Solution:** Check variable names match exactly

### Sync Issues

**Problem:** Changes in Postman not reflected in GitHub
- **Solution:** Manually export and commit collection
- **Solution:** Use Postman Cloud for automatic sync

**Problem:** Team members see different collections
- **Solution:** Ensure everyone pulls latest from GitHub
- **Solution:** Re-import collection after pulling changes

### Test Execution Issues

**Problem:** Tests pass in Postman but fail in Newman
- **Solution:** Check environment file path in Newman command
- **Solution:** Verify server is running before tests
- **Solution:** Check Newman version: `newman --version`
- **Solution:** Use `--env-var` to override variables

---

## Resources

- **Postman Documentation:** https://learning.postman.com/
- **Newman CLI:** https://learning.postman.com/docs/running-collections/using-newman-cli/
- **GitHub Integration:** https://learning.postman.com/docs/integrations/available-integrations/github/
- **Postman Cloud:** https://www.postman.com/product/api-repository/

---

**Last Updated:** 2025-01-26

# Run-Density Documentation

**Version:** v2.0.2+  
**Last Updated:** 2025-12-26  
**Architecture:** Local-only, UUID-based runflow structure, API-driven configuration

**Issue #553 Complete:** All analysis inputs (events, start times, file paths) are now configurable via API request. No hardcoded values.

This documentation is organized by audience and topic for easy navigation.

---

## 📚 Documentation by Audience

### 👥 For Users (Race Organizers, Operational Planners)

**Focus:** Using the API to request analyses and understand results

| Document | Purpose |
|----------|---------|
| [API User Guide](user-guide/api-user-guide.md) | **START HERE** - Complete API usage guide |

**Quick Start:**
1. Read [API User Guide](user-guide/api-user-guide.md) for complete API usage
2. Review example requests and common use cases
3. Understand error handling and validation

---

### 💻 For Developers

**Focus:** Development workflow, coding standards, architecture, and testing

| Document | Purpose |
|----------|---------|
| [Developer Guide](dev-guides/developer-guide.md) | **START HERE** - Complete v2 developer guide |
| [Docker Development](dev-guides/docker-dev.md) | Docker development workflow |
| [Quick Reference](reference/QUICK_REFERENCE.md) | Variable names, terminology, standards (v2.0.2+) |
| [Canonical Data Sources](dev-guides/CANONICAL_DATA_SOURCES.md) | Data source specifications (v2.0.2+) |
| [Testing Guide](testing/testing-guide.md) | Comprehensive testing guide |
| [UI Testing Checklist](testing/ui-testing-checklist.md) | UI testing procedures |

**Quick Start:**
1. Read [Developer Guide](dev-guides/developer-guide.md) for v2 architecture
2. Follow [Docker Development](dev-guides/docker-dev.md) for development workflow
3. Reference [Testing Guide](testing/testing-guide.md) for testing procedures

**Core Commands:**
```bash
make dev         # Start development container
make e2e         # Run end-to-end tests
```

---

### 🤖 For AI Coders (Cursor, ChatGPT, etc.)

**Focus:** AI assistant onboarding and critical rules

| Document | Purpose |
|----------|---------|
| [AI Developer Guide](dev-guides/ai-developer-guide.md) | **START HERE** - Complete AI assistant onboarding and rules |

**Quick Start:**
1. Read [AI Developer Guide](dev-guides/ai-developer-guide.md) - Complete all verification steps
2. Review mandatory rules and common mistakes
3. Reference [Developer Guide v2](dev-guides/developer-guide-v2.md) for v2 patterns
4. Use [Quick Reference](reference/QUICK_REFERENCE.md) for exact field names

---

## 🗂️ Documentation Structure

```
docs/
├── README.md (this file)              # Documentation index
│
├── user-guide/                        # User Documentation
│   └── api-user-guide.md              # Complete API usage guide
│
├── dev-guides/                        # Developer Documentation
│   ├── ai-developer-guide.md          # AI assistant onboarding and rules
│   ├── developer-guide.md             # Complete developer guide
│   ├── docker-dev.md                  # Docker development workflow
│   └── CANONICAL_DATA_SOURCES.md      # Data source specifications
│
├── testing/                           # Testing Documentation
│   ├── testing-guide.md               # Comprehensive testing guide
│   ├── ui-testing-checklist.md        # UI testing procedures
│   └── tests-cleanup-report.md        # Test cleanup analysis
│
└── reference/                         # Technical Reference
    └── QUICK_REFERENCE.md             # Variable names, terminology, constants
```

---

## 📖 Document Summaries

### Core Guides

#### [AI Developer Guide](dev-guides/ai-developer-guide.md)
**Audience:** AI Assistants  
**Purpose:** Complete onboarding and critical rules  
**Updated:** 2025-12-26

Covers:
- Mandatory setup and verification steps
- Non-negotiable development rules
- Common mistakes to avoid
- Development workflow
- Project architecture overview

---

#### [Developer Guide](dev-guides/developer-guide.md)
**Audience:** Developers  
**Purpose:** Complete v2 developer guide  
**Updated:** v2.0.2+

Covers:
- v2 architecture and design patterns
- Development environment setup
- Data sources and naming conventions
- Testing approach and tools
- Logging standards
- Common development tasks

---

#### [Docker Development](dev-guides/docker-dev.md)
**Audience:** Developers  
**Purpose:** Docker development workflow  
**Updated:** Version 3.1

Covers:
- Quick start (3-command workflow)
- E2E testing procedures
- Configuration and environment variables
- File structure and volume mounts
- Troubleshooting guides

---

#### [API User Guide](user-guide/api-user-guide.md)
**Audience:** Users (Race Organizers)  
**Purpose:** Complete API usage guide  
**Updated:** v2.0.2+

Covers:
- API endpoint usage
- Request/response formats
- Data file preparation
- Understanding results
- Output structure
- Error handling

---

### Testing Documentation

#### [Testing Guide](testing/testing-guide.md)
**Audience:** Developers  
**Purpose:** Comprehensive testing guide  
**Updated:** 2025-12-26

Covers:
- Testing strategy and test pyramid
- Test organization and file structure
- How to run tests (unit, integration, E2E)
- Writing tests (best practices)
- Test maintenance

---

#### [UI Testing Checklist](testing/ui-testing-checklist.md)
**Audience:** Developers  
**Purpose:** UI testing procedures  
**Updated:** 2025-12-26

Covers:
- Systematic UI testing approach
- Checklist for UI verification
- Common UI issues and fixes

---

### Reference Documentation

#### [Quick Reference](reference/QUICK_REFERENCE.md)
**Audience:** Developers, AI Assistants  
**Purpose:** Fast lookups for variables, terminology, standards

Covers:
- Variable naming rules
- Field name mappings
- CSV export standards
- Constants reference (v2.0.2+)

---

#### [Canonical Data Sources](dev-guides/CANONICAL_DATA_SOURCES.md)
**Audience:** Developers  
**Purpose:** Data source specifications

Covers:
- Input file formats and requirements
- Data source naming conventions
- File structure and column definitions
- v2.0.2+ API-driven approach

---

## 🆘 Getting Help

**Questions about:**
- **API usage?** → See [API User Guide](user-guide/api-user-guide.md)
- **Development workflow?** → See [Docker Development](dev-guides/docker-dev.md)
- **Code standards?** → See [AI Developer Guide](dev-guides/ai-developer-guide.md)
- **Field names?** → See [Quick Reference](reference/QUICK_REFERENCE.md)
- **Architecture?** → See [Developer Guide v2](dev-guides/developer-guide-v2.md)
- **Testing?** → See [Testing Guide](testing/testing-guide.md)

---

## 🔄 Document Lifecycle

### Recently Updated (v2.0.2+ - December 2025)
- ✅ `dev-guides/ai-developer-guide.md` - NEW consolidated AI assistant guide
- ✅ `user-guide/api-user-guide.md` - Complete API usage guide
- ✅ `dev-guides/developer-guide-v2.md` - Complete v2 developer guide
- ✅ `dev-guides/docker-dev.md` - Version 3.1
- ✅ `testing/testing-guide.md` - Comprehensive testing guide

### Active (Current)
- ✅ All documents in `user-guide/`, `dev-guides/`, `testing/`, `reference/`

### Archived
- Legacy documentation archived to `archive/docs/` for historical reference

---

**Last Updated:** 2025-12-26  
**Maintained By:** Development Team
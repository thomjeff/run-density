# Run-Density Documentation

**Version:** v2.0.8  
**Last Updated:** 2026-06-10  
**Architecture:** Local-only, UUID-based runflow structure, API-driven configuration where all analysis parameters are provided via API. 

This documentation is organized by audience and topic for easy navigation.

---

## 📚 Documentation by Audience

### 👥 For Users (Race Organizers, Operational Planners)

**Focus:** Building race configuration, requesting analyses, and understanding results

| Document | Purpose |
|----------|---------|
| [Race Configuration Guide](user-guide/race-configuration.md) | **START HERE** - Leg-based course authoring (leg library, event recipes, corridor pairing, locations) |
| [API User Guide](user-guide/api-user-guide.md) | Complete API usage guide |
| [Course Mapping Guide](user-guide/course-mapping.md) | Legacy draw-the-line course authoring (simple races) |
| [Cloud Container Guide](user-guide/cloud-container.md) | Skinny cloud Locations UI (read-only) |

**Quick Start:**
1. Build your config package with the [Race Configuration Guide](user-guide/race-configuration.md)
2. Read [API User Guide](user-guide/api-user-guide.md) for running analyses
3. Understand error handling and validation

---

### 💻 For Developers

**Focus:** Development workflow, coding standards, architecture, and testing

| Document | Purpose |
|----------|---------|
| [Developer Guide](dev-guides/developer-guide.md) | **START HERE** - Complete v2 developer guide |
| [Docker Development](dev-guides/docker-dev.md) | Docker development workflow |
| [Leg Library & Corridor Pairing](dev-guides/segment-library-2027.md) | Leg platform internals (org library, recipes, pairing, sync) |
| [Quick Reference](reference/quick-reference.md) | Variable names, terminology, standards (v2.0.2+) |
| [Data Sources](dev-guides/data-sources.md) | Data source specifications (v2.0.2+) |
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
3. Reference [Developer Guide](dev-guides/developer-guide.md) for v2 patterns
4. Use [Quick Reference](reference/QUICK_REFERENCE.md) for exact field names

---

## 🗂️ Documentation Structure

```
docs/
├── README.md (this file)              # Documentation index
│
├── user-guide/                        # User Documentation
│   ├── race-configuration.md          # Leg-based course authoring (recommended)
│   ├── course-mapping.md              # Legacy draw-the-line authoring
│   ├── api-user-guide.md              # Complete API usage guide
│   └── cloud-container.md             # Cloud (skinny) Locations UI
│
├── dev-guides/                        # Developer Documentation
│   ├── ai-developer-guide.md          # AI assistant onboarding and rules
│   ├── developer-guide.md             # Complete developer guide
│   ├── docker-dev.md                  # Docker development workflow
│   ├── segment-library-2027.md        # Leg library, recipes & corridor pairing internals
│   └── data-sources.md                # Data source specifications
│
├── testing/                           # Testing Documentation
│   ├── testing-guide.md               # Comprehensive testing guide
│   ├── ui-testing-checklist.md        # UI testing procedures
│   └── tests-cleanup-report.md        # Test cleanup analysis
│
└── reference/                         # Technical Reference
    └── quick-reference.md             # Variable names, terminology, constants
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

#### [Race Configuration Guide](user-guide/race-configuration.md)
**Audience:** Users (Race Organizers, Course Mappers)  
**Purpose:** Leg-based course authoring workflow  
**Updated:** 2026-06

Covers:
- Organization leg library (import, edit, export GPX legs)
- Event recipes and applying them to build the combined course
- Corridor pairing for opposing-pass flow analysis
- Locations on legs, proxy timing, and operations editing
- direction/flow type selection guidance

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

#### [Cloud Container Guide](user-guide/cloud-container.md)
**Audience:** External viewers, operations leads  
**Purpose:** Skinny cloud Locations UI usage and deployment  
**Updated:** 2026-01-26

Covers:
- Build/push/deploy workflow
- Local smoke test
- Stable Cloud Run URL usage
- Password gate behavior

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

#### [Quick Reference](reference/quick-reference.md)
**Audience:** Developers, AI Assistants  
**Purpose:** Fast lookups for variables, terminology, standards

Covers:
- Variable naming rules
- Field name mappings
- CSV export standards
- Constants reference (v2.0.2+)

---

#### [Data Sources](dev-guides/data-sources.md)
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
- **Building a course/config package?** → See [Race Configuration Guide](user-guide/race-configuration.md)
- **API usage?** → See [API User Guide](user-guide/api-user-guide.md)
- **Development workflow?** → See [Docker Development](dev-guides/docker-dev.md)
- **Code standards?** → See [AI Developer Guide](dev-guides/ai-developer-guide.md)
- **Field names?** → See [Quick Reference](reference/quick-reference.md)
- **Architecture?** → See [Developer Guide](dev-guides/developer-guide.md)
- **Leg library internals?** → See [Leg Library & Corridor Pairing](dev-guides/segment-library-2027.md)
- **Testing?** → See [Testing Guide](testing/testing-guide.md)

---

## 🔄 Document Lifecycle

### Recently Updated (June 2026 — leg platform & corridor pairing)
- ✅ `user-guide/race-configuration.md` - NEW leg-based course authoring guide
- ✅ `dev-guides/segment-library-2027.md` - Rewritten for implemented leg platform (org library, pairing, sync)
- ✅ `user-guide/course-mapping.md` - Marked as legacy workflow; points to Race Configuration
- ✅ `CHANGELOG.md` - Unreleased section for leg platform, corridor pairing (#785), and sync fixes

### Previously Updated (v2.0.2+ - December 2025)
- ✅ `dev-guides/ai-developer-guide.md` - Consolidated AI assistant guide
- ✅ `user-guide/api-user-guide.md` - Complete API usage guide
- ✅ `dev-guides/developer-guide.md` - Complete developer guide
- ✅ `dev-guides/docker-dev.md` - Version 3.1
- ✅ `testing/testing-guide.md` - Comprehensive testing guide

### Active (Current)
- ✅ All documents in `user-guide/`, `dev-guides/`, `testing/`, `reference/`

### Archived
- Legacy documentation archived to `archive/docs/` for historical reference

---

**Last Updated:** 2026-06-10  
**Maintained By:** Development Team
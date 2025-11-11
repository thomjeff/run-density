# Run-Density Documentation

**Version:** v1.8.4  
**Last Updated:** 2025-11-11  
**Architecture:** Local-only, UUID-based runflow structure

This documentation is organized for three primary audiences: **Product Managers**, **Developers**, and **Technical Architects**.

---

## 📚 Documentation by Audience

### 👔 For Product Managers

**Focus:** Features, capabilities, and operational usage

| Document | Purpose |
|----------|---------|
| [README.md](../README.md) | Product overview, features, quick start |
| [UI Testing Checklist](ui-testing-checklist.md) | Comprehensive testing for deployments |
| [ADR-001: Frontend Stack](adr/ADR-001%20Front-End%20Stack.md) | Technology decisions and rationale |

**Quick Start:**
- Read the main [README.md](../README.md) for product overview
- Review UI features and capabilities
- Understand testing process via [UI Testing Checklist](ui-testing-checklist.md)

---

### 💻 For Developers

**Focus:** Development workflow, coding standards, and testing

| Document | Purpose |
|----------|---------|
| [CONTRIBUTING.md](../CONTRIBUTING.md) | **START HERE** - Contributor guide and workflow |
| [DOCKER_DEV.md](DOCKER_DEV.md) | Complete Docker development guide |
| [Developer Checklist](onboarding/developer-checklist.md) | Onboarding steps for new developers |
| [GUARDRAILS.md](GUARDRAILS.md) | Non-negotiable development rules |
| [Logging Standards](LOGGING.md) | Logging patterns and conventions (Issue #467) |
| [Quick Reference](reference/QUICK_REFERENCE.md) | Variable names, terminology, standards |
| [ADR-002: Naming Normalization](adr/ADR-002%20Naming%20Normalization.md) | Naming conventions and field mappings |

**Quick Start:**
1. Read [DOCKER_DEV.md](DOCKER_DEV.md) for development workflow
2. Follow [Developer Checklist](onboarding/developer-checklist.md) for environment setup
3. Reference [GUARDRAILS.md](GUARDRAILS.md) for coding standards
4. Use [Quick Reference](reference/QUICK_REFERENCE.md) for field names and constants

**Core Commands:**
```bash
make dev         # Start development container
make test        # Run smoke tests
make e2e-local   # Run end-to-end tests
```

---

### 🏗️ For Technical Architects

**Focus:** System architecture, design decisions, and technical specifications

| Document | Purpose |
|----------|---------|
| [Architecture: Output Structure](architecture/output.md) | **START HERE** - Runflow directory structure |
| [Architecture: Environment Detection](architecture/env-detection.md) | Environment configuration and detection |
| [Reference: Density Analysis](reference/DENSITY_ANALYSIS_README.md) | Density calculation algorithms and LOS |
| [Reference: Global Time Grid](reference/GLOBAL_TIME_GRID_ARCHITECTURE.md) | Time grid architecture for cross-event analysis |
| [ADR-001: Frontend Stack](adr/ADR-001%20Front-End%20Stack.md) | Frontend technology decisions |
| [ADR-002: Naming Normalization](adr/ADR-002%20Naming%20Normalization.md) | Naming standards and field mappings |

**Quick Start:**
1. Read [output.md](architecture/output.md) for current architecture
2. Review [env-detection.md](architecture/env-detection.md) for environment model
3. Understand algorithms via reference docs
4. Review ADRs for historical context

---

## 🗂️ Documentation Structure

```
docs/
├── README.md (this file)           # Documentation index
├── DOCKER_DEV.md                   # **Developer Guide** - Docker workflow
├── GUARDRAILS.md                   # Development rules and standards
├── ui-testing-checklist.md         # UI testing procedures
│
├── architecture/                   # **Technical Architecture**
│   ├── output.md                   # Runflow directory structure
│   └── env-detection.md            # Environment configuration
│
├── reference/                      # **Technical Reference**
│   ├── DENSITY_ANALYSIS_README.md  # Density algorithms and LOS
│   ├── GLOBAL_TIME_GRID_ARCHITECTURE.md  # Time grid design
│   └── QUICK_REFERENCE.md          # Variable names and constants
│
├── onboarding/                     # **New Developer Resources**
│   └── developer-checklist.md      # Setup and onboarding steps
│
└── adr/                            # **Architecture Decision Records**
    ├── ADR-001 Front-End Stack.md  # Frontend technology decisions
    └── ADR-002 Naming Normalization.md  # Naming standards
```

---

## 📖 Document Summaries

### Core Guides

#### [DOCKER_DEV.md](DOCKER_DEV.md)
**Audience:** Developers  
**Purpose:** Complete Docker development workflow  
**Updated:** Phase 2 (Issue #466)

Covers:
- Quick start (3-command workflow)
- E2E testing procedures
- Configuration and environment variables
- File structure and volume mounts
- Troubleshooting guides

---

#### [GUARDRAILS.md](GUARDRAILS.md)
**Audience:** Developers, AI Assistants  
**Purpose:** Non-negotiable development rules  
**Status:** Active

Covers:
- Mandatory pre-task checks
- Code quality standards
- Testing requirements
- Anti-patterns to avoid

---

### Architecture Documentation

####[architecture/output.md](architecture/output.md)
**Audience:** Technical Architects, Developers  
**Purpose:** Comprehensive runflow/ structure guide  
**Created:** Phase 2 Step 5

Covers:
- Complete directory structure
- File-by-file descriptions
- API usage examples
- Migration notes
- Best practices and troubleshooting

---

#### [architecture/env-detection.md](architecture/env-detection.md)
**Audience:** Technical Architects  
**Purpose:** Environment configuration model  
**Updated:** Phase 1 (Issue #464)

Covers:
- Local-only environment model
- Configuration variables
- Path resolution logic

---

### Reference Documentation

#### [reference/DENSITY_ANALYSIS_README.md](reference/DENSITY_ANALYSIS_README.md)
**Audience:** Technical Architects, Data Scientists  
**Purpose:** Density algorithm specifications

Covers:
- Areal density calculations
- Level of Service (LOS) classification
- Time-over-threshold metrics
- API endpoint specifications

---

#### [reference/GLOBAL_TIME_GRID_ARCHITECTURE.md](reference/GLOBAL_TIME_GRID_ARCHITECTURE.md)
**Audience:** Technical Architects  
**Purpose:** Time grid design for cross-event analysis

Covers:
- Global time window creation
- Per-event index mapping
- Flow analysis temporal alignment
- Implementation details

---

#### [reference/QUICK_REFERENCE.md](reference/QUICK_REFERENCE.md)
**Audience:** Developers  
**Purpose:** Fast lookups for variables, terminology, standards

Covers:
- Variable naming rules
- Field name mappings
- CSV export standards
- Constants reference

---

### Onboarding

#### [onboarding/developer-checklist.md](onboarding/developer-checklist.md)
**Audience:** New Developers  
**Purpose:** Step-by-step onboarding guide

Covers:
- Environment setup
- Running tests
- Understanding codebase
- Making first contributions

---

### Architecture Decision Records (ADRs)

#### [adr/ADR-001 Front-End Stack.md](adr/ADR-001%20Front-End%20Stack.md)
**Date:** 2025-10-23  
**Status:** Accepted

Decision to use Flask + Jinja2 + Vanilla JS for Race-Crew Web UI.

---

#### [adr/ADR-002 Naming Normalization.md](adr/ADR-002%20Naming%20Normalization.md)
**Date:** 2025-10-26  
**Status:** Accepted

Standards for canonical naming and field mappings (`seg_id` vs `segment_id`).

---

## 🔄 Document Lifecycle

### Recently Updated (Phase 2 - November 2025)
- ✅ `DOCKER_DEV.md` - Version 3.0 (Issue #466)
- ✅ `architecture/output.md` - NEW comprehensive guide
- ✅ `architecture/env-detection.md` - Phase 1 update

### Active (Current)
- ✅ `GUARDRAILS.md` - Development standards
- ✅ `ui-testing-checklist.md` - Testing procedures
- ✅ `reference/*` - Technical specifications
- ✅ `adr/*` - Decision records

### Archived (November 2025)
See `archive/docs-pre-phase-2-2025-11/` for:
- v1.7-era architecture planning docs
- Pre-Phase 2 import dependency audits
- Outdated testing strategies
- Cloud Run operations guides

---

## 🆘 Getting Help

**Questions about:**
- **Development workflow?** → See [DOCKER_DEV.md](DOCKER_DEV.md)
- **Code standards?** → See [GUARDRAILS.md](GUARDRAILS.md)
- **Field names?** → See [Quick Reference](reference/QUICK_REFERENCE.md)
- **Architecture decisions?** → See [ADRs](adr/)
- **Output structure?** → See [output.md](architecture/output.md)

---

**Last Updated:** 2025-11-11 (Post-Phase 2)  
**Maintained By:** Development Team  
**Next Review:** When new architecture changes are planned


# ADR-001: Frontend Stack Policy for Sydney Milestone

**Status:** Accepted  
**Date:** October 23, 2025  
**Deciders:** Senior Technical Architect (ChatGPT), Development Team  
**Context:** Epic #279 (Race-Crew Web UI), Sydney Milestone (#14)

---

## 📋 Context and Problem Statement

During implementation planning for Sydney milestone Epic #279 (Race-Crew Web UI), a critical architectural question emerged:

**Should the Race-Crew Web UI be built using:**
- **Option A**: Continue with existing Flask + Jinja2 + Leaflet stack
- **Option B**: Migrate to React + TypeScript + modern build tooling

Initial issue descriptions (#317, #280, #318) referenced React/TypeScript components, suggesting a framework migration. However, architectural review revealed the existing Jinja2 implementation is mature, functional, and production-ready.

This ADR documents the decision to maintain architectural consistency within the Sydney milestone.

---

## 🎯 Decision

**For the Sydney milestone (#14), we will:**

**Continue using Flask + Jinja2 + Vanilla JavaScript + Leaflet**

All Race-Crew Web UI features (#314, #317, #280, #318) will be implemented as:
- Server-rendered Jinja2 templates (`templates/pages/*.html`)
- Vanilla JavaScript (extracted to `static/js/`)
- Leaflet for mapping (not react-leaflet)
- Tailwind CSS for styling
- No build tooling (no pnpm, webpack, vite)

---

## 🧠 Rationale

### **Reasons for Continuing Jinja2 Architecture**

1. **Feature Already Implemented**
   - Segments Map exists and works (`templates/pages/segments.html`)
   - Has all required functionality: Leaflet rendering, LOS colors, tooltips, table sync
   - No user-facing gap to fill with React

2. **Consistency Across UI**
   - All existing pages use Jinja2 (dashboard, density, flow, health, reports)
   - Password gate (#314) naturally fits Jinja2 session middleware
   - Mixed architecture creates maintenance burden

3. **Cloud Run Performance**
   - Jinja2 keeps cold-start times minimal (<2s)
   - No client-side build artifacts to serve
   - Simpler deployment pipeline (single Docker image)

4. **Development Velocity**
   - Team familiar with Flask/Jinja2 patterns
   - No learning curve for React ecosystem
   - Faster iteration within Sydney deadline (Oct 25)

5. **Scope Alignment**
   - Sydney focuses on completing visualization features, not technology migration
   - React migration is a large effort (3-5 days minimum)
   - Better suited for dedicated post-Sydney milestone

6. **Technical Simplicity**
   - No bundler, transpiler, or dependency management complexity
   - Pure server-side rendering with progressive enhancement
   - Easier debugging and testing

---

## 🚫 Why React Was Considered (and Deferred)

### **Potential Benefits of React/TypeScript:**
- Modern component architecture
- Better code reuse via props/hooks
- Type safety
- Rich ecosystem (charting libraries, UI kits)

### **Why Not Now:**
- Requires complete frontend infrastructure setup
- Adds ~15-20 dependencies to manage
- Increases build pipeline complexity
- Breaks existing pages during migration
- Outside Sydney milestone timeline

### **Future Consideration:**
If React is desired post-Sydney, create a dedicated milestone ("Chicago") with:
- RFC for architecture migration
- Incremental page-by-page migration plan
- Build tooling setup (Vite + pnpm)
- Type safety strategy (TypeScript)
- Component library selection (Shadcn, MUI, etc.)

---

## 📝 Implementation Guidelines

### **For Sydney Milestone Issues (#314, #317, #280, #318):**

**✅ DO:**
- Use Jinja2 templates in `templates/pages/`
- Write vanilla JavaScript in `static/js/`
- Use Leaflet (CDN: `https://unpkg.com/leaflet@1.9.4/`)
- Fetch data via FastAPI endpoints (`/api/*`)
- Use Python `StorageService` for environment-aware data access
- Extract shared JS to reusable modules (`base_map.js`, etc.)

**❌ DON'T:**
- Add React, Vue, Svelte, or any SPA framework
- Create `package.json` or install Node dependencies
- Reference TypeScript (.tsx) files
- Use build tools (webpack, vite, rollup)
- Suggest `pnpm dev` or `npm start` commands

### **Code Organization:**
```
templates/
  pages/
    segments.html       # Jinja2 template
    density.html
    ...
static/
  js/
    map/
      base_map.js       # Shared Leaflet initialization
      segments.js       # Segments-specific logic
      heatmap.js        # Density heatmap logic (Issue #280)
  css/
    main.css
```

---

## 📊 Architectural Comparison

| Aspect | Current (Flask/Jinja2) | Alternative (React/TS) | Decision |
|--------|------------------------|------------------------|----------|
| **Complexity** | Low | High | ✅ Keep low |
| **Learning Curve** | Minimal | Steep | ✅ Minimize |
| **Cold Start** | <2s | 3-5s | ✅ Keep fast |
| **Build Time** | None | 30-60s | ✅ No build |
| **Dependencies** | ~15 Python | 50+ npm packages | ✅ Keep simple |
| **Testing** | Flask E2E | Jest + Playwright | ✅ Keep current |
| **Deployment** | Single container | Multi-stage build | ✅ Keep simple |

---

## 🔄 Consequences

### **Positive:**
- ✅ Faster delivery of Sydney milestone features
- ✅ Consistent developer experience
- ✅ Simpler deployment and testing
- ✅ No new technology onboarding required
- ✅ Maintains Cloud Run performance

### **Negative:**
- ⚠️ Limited component reusability (vanilla JS vs React components)
- ⚠️ No type safety (JavaScript vs TypeScript)
- ⚠️ Manual DOM manipulation (vs declarative React)

### **Mitigation:**
- Extract shared JS utilities to reduce duplication
- Use JSDoc for type hints in vanilla JS
- Follow consistent coding patterns across pages
- Consider React migration post-Sydney if needed

---

## 📎 Related Issues

- **Epic #279**: Race-Crew Web UI (RF-FE-002)
- **Issue #314**: Password Gate with Session Management
- **Issue #317**: Implement Segments Map (Leaflet visualization)
- **Issue #280**: Density Heatmaps Visualization
- **Issue #318**: Implement Bin-Level Details Table
- **Issue #321**: Runner Orchestration Layer (future architecture work)

---

## 🔮 Future Review

**When to Revisit:**
- After Sydney milestone completion (post-Oct 25, 2025)
- If user feedback requests SPA-style interactivity
- If frontend complexity exceeds maintainability threshold
- If performance issues emerge with vanilla JS approach

**Trigger for Reconsideration:**
- New milestone ("Chicago" or later) dedicated to frontend modernization
- Business requirement for real-time updates (WebSockets + React)
- Team capacity increases (dedicated frontend developer hired)

---

## ✅ Decision Outcome

**For Sydney Milestone:**
**Maintain Flask + Jinja2 + Vanilla JavaScript + Leaflet architecture**

All Phase 2 issues (#314, #317, #280, #318) will be implemented within this framework.

React/TypeScript migration remains a **viable option for future milestones** but is explicitly **out of scope** for Sydney.

---

**Author:** Development Team  
**Reviewed By:** Senior Technical Architect (ChatGPT)  
**Approved:** October 23, 2025  
**Applies To:** Sydney Milestone (#14), Epic #279


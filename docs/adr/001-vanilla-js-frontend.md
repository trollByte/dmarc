# ADR 001: Vanilla JavaScript Frontend (No React/Vue/Angular)

**Status:** Accepted

**Date:** 2026-01-15

**Context:**
The DMARC Dashboard requires a web interface for visualizing email authentication reports, managing alerts, and configuring system settings. We needed to decide on a frontend technology stack.

**Options Considered:**

1. **React** - Most popular, large ecosystem, component-based
2. **Vue.js** - Progressive framework, easier learning curve
3. **Angular** - Full-featured framework, TypeScript-first
4. **Vanilla JavaScript** - No framework, direct DOM manipulation

---

## Decision

We chose **Vanilla JavaScript** with no frontend framework.

---

## Rationale

### 1. Simplicity and Maintainability

**No Build Step Required:**
- No webpack, babel, or complex build pipelines
- No dependency management for 100+ npm packages
- Direct file editing with immediate browser refresh
- Easier for contributors without frontend framework experience

**Single-File Architecture:**
- All frontend code in `frontend/js/app.js` (~5000 lines)
- Centralized state management with global variables
- No module bundling or code splitting complexity
- Easy to search, debug, and understand flow

### 2. Performance

**Zero Framework Overhead:**
- No virtual DOM reconciliation
- No framework initialization time
- Smaller initial payload (<200KB total, including Chart.js)
- Faster time-to-interactive

**Benchmarks (Initial Load):**
- Vanilla JS: ~150ms to interactive
- React (estimated): ~400ms to interactive (including framework init)
- Vue (estimated): ~300ms to interactive

### 3. Project Scope and Complexity

**Dashboard Complexity Level: Low-Medium**
- ~10 pages: Dashboard, Reports, Analytics, Alerts, Users, Settings
- Limited interactivity: Mostly data visualization and forms
- No complex state synchronization across components
- No real-time collaborative editing

**Framework Benefits Not Needed:**
- Component reusability (minimal component reuse in this app)
- State management libraries (Redux/Vuex) overkill for our needs
- Reactive data binding (can achieve with manual DOM updates)
- Server-side rendering (SPA is fine for authenticated dashboard)

### 4. Development Team Profile

**Python Backend Focus:**
- Team expertise is primarily backend Python/FastAPI
- Adding React/Vue would require learning curve
- Vanilla JS familiar to all developers (HTML/CSS/JS basics)
- Easier onboarding for new contributors

### 5. Security Considerations

**Smaller Attack Surface:**
- No framework vulnerabilities to patch (React XSS, Vue template injection)
- Fewer dependencies means fewer supply chain risks
- Direct control over CSP implementation
- No framework-specific security gotchas

**Example:** React requires `unsafe-inline` for inline styles, or complex build config. Vanilla JS lets us avoid this entirely.

### 6. Deployment and Hosting

**Static File Serving:**
- Simple Nginx static file serving (no Node.js needed)
- No server-side rendering requirements
- Easy CDN deployment
- Lower hosting costs

### 7. Testability

**Testing Approach:**
- Jest for unit tests (156+ tests)
- Playwright for E2E tests (full browser workflows)
- No framework-specific testing utilities needed
- Standard DOM assertions work everywhere

---

## Trade-offs and Limitations

### What We Gave Up

**1. Component Reusability:**
- No component library (Material-UI, Vuetify)
- Manual duplication for repeated UI patterns (modals, cards)
- Harder to maintain consistency across pages

**Mitigation:** CSS utility classes and shared functions (`createModal()`, `createCard()`)

**2. Reactivity:**
- No automatic DOM updates on state changes
- Manual `renderDashboard()` calls after data changes
- Potential for stale UI if updates are missed

**Mitigation:** Clear naming conventions (`load*`, `render*`, `update*`) and single re-render functions per page

**3. Developer Experience:**
- No hot module replacement
- No TypeScript autocomplete (though we could add TS without a framework)
- Manual DOM manipulation is more verbose

**Mitigation:** Structured code with clear sections, JSDoc comments for key functions

**4. Advanced Patterns:**
- No lazy loading/code splitting (entire app.js loads upfront)
- No progressive web app features (could add manually)
- No optimized list rendering (virtual scrolling)

**Mitigation:** Acceptable for dashboard with <100 concurrent users and limited data pagination

---

## When to Reconsider

This decision should be revisited if:

1. **App complexity increases significantly:**
   - Adding real-time collaborative features
   - Complex multi-step workflows with shared state
   - Heavy client-side data processing

2. **Performance degrades:**
   - Initial load >1s on slow networks
   - Sluggish interactions due to DOM manipulation
   - Need for code splitting/lazy loading

3. **Team composition changes:**
   - New hires with strong React/Vue experience
   - Frontend becoming primary development focus

4. **User requirements change:**
   - Mobile app needed (React Native/Vue Native)
   - Offline-first requirements (better PWA support)

---

## Alternatives Rejected

### Why Not React?

**Pros:**
- Large ecosystem of components and tools
- Strong hiring pool (React developers abundant)
- Better for complex SPAs with heavy state management

**Cons:**
- Overhead not justified for our dashboard complexity
- Build pipeline complexity (webpack, babel)
- 40KB+ gzipped framework (vs 0KB for vanilla)
- Team learning curve

### Why Not Vue?

**Pros:**
- Easier learning curve than React
- Good documentation
- Progressive adoption possible (could start small)

**Cons:**
- Still requires build step for SFC (Single File Components)
- Framework bundle size (~20KB gzipped)
- Less familiar to Python-focused team

### Why Not Angular?

**Pros:**
- Full-featured framework (routing, forms, HTTP out of box)
- TypeScript first-class

**Cons:**
- Heaviest framework (~50KB+ gzipped)
- Steepest learning curve
- Overkill for our use case

---

## Implementation Details

### Current Architecture

**File Structure:**
```
frontend/
├── index.html          # Single-page app shell
├── js/
│   └── app.js         # All JavaScript (~5000 lines)
├── css/
│   └── styles.css     # All styles (~6900 lines)
└── assets/            # Images, icons
```

**State Management:**
```javascript
// Global state (memory-only)
let accessToken = null;
let refreshToken = null;
let currentUser = null;
let currentFilters = {};
let chartInstances = {};
```

**Page Routing:**
```javascript
// Simple hash-based routing
function navigateTo(pageId) {
  window.location.hash = pageId;
  renderPage(pageId);
}

window.addEventListener('hashchange', () => {
  const pageId = window.location.hash.slice(1) || 'dashboard';
  renderPage(pageId);
});
```

**Data Flow:**
```
User Action → Event Handler → fetch() API Call → Update State → render*() Function → DOM Update
```

### Code Organization

**Naming Conventions:**
- `load*()` - Fetch data from API
- `render*()` - Update DOM with data
- `update*()` - Modify existing DOM elements
- `handle*()` - Event handlers
- `create*()` - Factory functions for DOM elements

**Example:**
```javascript
async function loadDashboard() {
  const data = await fetch('/api/dashboard/summary');
  renderDashboard(data);
}

function renderDashboard(data) {
  document.getElementById('totalReports').textContent = data.total_reports;
  renderCharts(data.charts);
  renderAlerts(data.alerts);
}
```

### Libraries Used

**Minimal Dependencies:**
- **Chart.js 4.4.0** - Chart rendering (~200KB)
- **Leaflet** - Geographic maps (only loaded on analytics page)
- **No other dependencies**

---

## Success Metrics

After 6 months of development:

**Positive Outcomes:**
- ✅ Frontend development by backend team (no dedicated frontend developer needed)
- ✅ Zero build step issues in CI/CD
- ✅ Fast load times (<200ms on localhost)
- ✅ 156 frontend unit tests passing
- ✅ Full E2E test coverage with Playwright

**Challenges:**
- ⚠️ Some code duplication (modal patterns, form validation)
- ⚠️ Large single file (app.js at 5000 lines, could split)
- ⚠️ Manual reactivity can cause bugs if render functions aren't called

---

## Conclusion

Vanilla JavaScript was the right choice for this project given:
- Dashboard complexity level (low-medium)
- Team expertise (backend-focused)
- Performance requirements (fast load, minimal overhead)
- Deployment simplicity (static files only)

The decision prioritized **simplicity, maintainability, and developer productivity** over framework-enabled advanced patterns we didn't need.

---

## References

- [You Might Not Need a Framework](https://youmightnotneedaframework.com/)
- [The Cost of JavaScript Frameworks](https://timkadlec.com/remembers/2020-04-21-the-cost-of-javascript-frameworks/)
- Frontend source: `/frontend/js/app.js`
- Test suite: `/frontend/tests/`

---

**Authors:** DMARC Dashboard Team
**Last Updated:** 2026-02-06

# 💻 Frontend, Visualization & BI Dashboard Rules

- **Framework & Stack**:
  - Web dashboards and competitive analytics UIs must follow modern modular architecture (e.g., Next.js with React or Streamlit for analytics prototypes as defined in `.ai/context.md`).
- **Typing & Strictness**:
  - TypeScript in `strict` mode is mandatory for JavaScript/TypeScript frontend codebases. No untyped `any` escape hatches.
  - Python-based UI prototypes (e.g., Streamlit) must follow `02-python.md` type hinting and lint standards.
- **Modularity & Architecture**:
  - Isolate presentation components from state management, data-fetching layers, and API clients.
  - Reusable components must reside in dedicated UI folders with deterministic test specs.
- **Linting & Code Quality**:
  - Enforce ESLint, Prettier, and zero console/build warnings before code delivery.

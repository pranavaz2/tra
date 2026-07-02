# packages/ — Shared Internal Packages

This folder contains **shared internal packages** for Travix AI.

---

## Purpose

The `packages/` directory holds code that is shared between multiple parts of the monorepo
— for example, shared Dart packages used by both the mobile app and any future web interface,
or shared Python utilities used across multiple backend services.

This folder exists to enable **code sharing without coupling** — packages here have clear
interfaces and are treated as internal libraries, not as application code.

---

## When to Create a Package

Create a package in this directory when:

1. **Code is genuinely shared** between two or more applications in the monorepo.
2. **The code has a clear, stable interface** — it's not just code that happens to be
   duplicated during development.
3. **The dependency is unidirectional** — packages never depend on application code.

Do NOT create a package just to avoid a little duplication. Premature abstraction into
packages adds maintenance overhead. Three duplicated lines of code are better than a
premature shared package.

---

## Flutter / Dart Packages

Dart packages in this directory are managed with **Melos** — a monorepo tool for Dart
and Flutter that manages workspaces, versioning, and cross-package scripts.

Each Dart package follows the standard Flutter package structure:

```
packages/
└── {package_name}/
    ├── lib/
    │   └── src/
    │       └── {package_name}.dart
    ├── test/
    ├── pubspec.yaml
    └── README.md
```

Packages are referenced from `apps/mobile/pubspec.yaml` using path dependencies:

```yaml
dependencies:
  travix_ui_kit:
    path: ../../packages/travix_ui_kit
```

---

## Expected Packages

| Package | Language | Purpose | Status |
|---|---|---|---|
| `travix_ui_kit` | Dart | Shared Material 3 design system components | Future |
| `travix_models` | Dart | Shared data models (if web app is added) | Future |

---

## Status

> No packages have been created yet. This folder will be populated when a genuine need for
> shared code is identified.
>
> Do not create packages speculatively. Wait until code is actually needed in two or more places.

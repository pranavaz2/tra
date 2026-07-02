# apps/mobile/ — Travix AI Flutter Application

This directory contains the **Flutter mobile application** for Travix AI.

---

## Overview

The mobile app is the **presentation layer** of Travix AI. It is responsible exclusively
for displaying data and capturing user input. All business logic, data processing, and AI
orchestration happen in `apps/api/` — the Flutter app never makes business decisions.

---

## Architecture

The Flutter app follows **Clean Architecture** with **Vertical Slice** feature organization:

```
lib/
├── main.dart                   # App entry point
├── app.dart                    # Root widget and GoRouter setup
│
├── core/                       # Cross-cutting app concerns
│   ├── router/                 # GoRouter configuration
│   ├── theme/                  # Material 3 theme
│   ├── network/                # Dio HTTP client + interceptors
│   ├── storage/                # Drift local SQLite database
│   ├── error/                  # Error types and error widgets
│   └── constants/              # App-wide constants
│
├── features/                   # One folder per product feature
│   └── {feature_name}/
│       ├── data/               # API clients, local DAOs, repository implementations
│       ├── domain/             # Entities, use cases, repository interfaces
│       └── presentation/       # Riverpod providers, screens, widgets
│
└── shared/                     # Reusable widgets and utilities
    ├── widgets/
    └── utils/
```

See `CLAUDE.md` Section 6 for the complete directory structure specification.

---

## Technology

| Technology | Purpose |
|---|---|
| Flutter (stable channel) | Cross-platform mobile framework |
| Riverpod + `@riverpod` | State management with code generation |
| GoRouter | Declarative navigation |
| Dio | HTTP client with interceptor support |
| Drift | Reactive SQLite ORM for offline data |
| Flutter Secure Storage | Secure token storage (Keystore/Secure Enclave) |
| Material 3 | Design system |

---

## Key Rules

These rules are non-negotiable. See `CLAUDE.md` for the complete list.

- **No business logic in Flutter.** The app calls the API and displays results.
- **All state through Riverpod.** No raw `setState` for business-level state.
- **All navigation through GoRouter.** No direct `Navigator.push` for main flows.
- **All HTTP through the Dio client** in `core/network/`. No raw `http` package.
- **Tokens in Flutter Secure Storage only.** Never `SharedPreferences`.

---

## Local Development

```bash
# Install Flutter dependencies
cd apps/mobile
flutter pub get

# Run code generation (Riverpod, Drift, JSON serialization)
dart run build_runner build --delete-conflicting-outputs

# Run the app
flutter run

# Run tests
flutter test

# Analyze code
flutter analyze

# Format code
dart format lib/ test/
```

---

## Status

> This directory will be bootstrapped as part of TASK-003 (Flutter App Bootstrap).
> The Flutter project does not yet exist — `flutter create` will be run during that task.

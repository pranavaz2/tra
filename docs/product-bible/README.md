# docs/product-bible/

This folder contains the **Product Bible** for Travix AI — the authoritative source of truth
for product vision, requirements, feature definitions, and user experience expectations.

---

## Purpose

The product bible defines **what** Travix AI is and **why** it exists. Engineering decisions
are made in service of this document. When an implementation choice is unclear, the product
bible is the reference that resolves ambiguity.

---

## Contents

This folder will contain:

| Document | Purpose |
|---|---|
| `vision.md` | Product vision, mission, and long-term goals |
| `user-personas.md` | Target user types and their needs |
| `feature-catalog.md` | Complete feature list with acceptance criteria |
| `user-journeys.md` | End-to-end user flow descriptions |
| `terminology.md` | Ubiquitous language — shared vocabulary for the product |

---

## How to Use This Folder

- **Engineers:** Read the relevant feature definition before starting implementation.
  Code should match the terminology and behavior described here exactly.
- **AI agents:** The `terminology.md` file defines the ubiquitous language. Entity names,
  field names, and domain concepts in code must match the terms in that document.
- **Product changes:** All product changes must be reflected in this folder before
  engineering work begins.

---

## Status

> This folder will be populated as the product specification is finalized.
> Do not begin implementation of any feature without a corresponding entry in this folder.

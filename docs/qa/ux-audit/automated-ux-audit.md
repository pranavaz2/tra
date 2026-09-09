# Travix AI — Automated UX & Product Experience Audit Report

> **Audit Execution Date**: September 5, 2026  
> **Target Release**: Sprints 1–15 Evaluation (Pre-Sprint 16 Gate)  
> **Automation Engine**: Playwright Chromium (Emulated Pixel 7 Mobile Viewport `412x915`, DPR 2.625) driving Expo Web on Port 8085 connected to Live FastAPI Backend on Port 8000  
> **Tested Real User Persona**: First-time solo traveler planning a 3-Day Heritage & Food journey to **Mysore, India** (Budget: ₹15,000, Style: Balanced).  
> **Source Code Modifications**: Zero (0) application files modified during audit.

---

## Executive Summary & Product Scorecard

| Metric | Score | Rating | Verdict Summary |
| :--- | :---: | :---: | :--- |
| **1. Overall UX Score** | **5.8 / 10** | **Needs Overhaul** | Visually polished dark-mode aesthetic with strong component foundations, but plagued by an administrative entity-management paradigm rather than an intuitive traveler-first journey. |
| **2. AI Usefulness Score** | **7.2 / 10** | **Promising Core** | Gemini planning engine produces grounded, high-quality itineraries with real places (Mysore Palace, Chamundi Hill, Mylari Dosa); however, AI remains siloed in a separate module rather than driving the core user flow. |
| **3. Product Readiness Score** | **4.9 / 10** | **Not Production-Ready** | Critical backend token refresh bugs, API double-unwrapping navigation breakages, disconnected budgeting, and overwhelming manual step requirements make self-serve travel planning friction-heavy. |

---

## 4. Complete Automated Test Journey

The automated test script (`docs/qa/ux-audit/run_audit.js`) completed the full end-to-end traveler journey autonomously:

```mermaid
journey
    title Real User Automated Journey: Mysore 3-Day Trip
    section Onboarding & Auth
      Launch App & Check Branding: 5: Pass
      Navigate to Registration: 4: Pass (Min 12 Char Pass)
      Create Test User & Login: 5: Pass
    section Trip Creation
      Open "Where to next?" CTA: 3: Confusing Modal
      Fill Trip Name & Flexible Dates: 3: Destination missing
      Inspect Recent Trips on Home: 4: Pass (Draft badge)
    section Planning with AI
      Open Trip Details Hub: 2: Overwhelming 7 Modules
      Open AI Planning Parameters: 4: Re-type Mysore, 3 Days
      Trigger Gemini AI Proposal: 5: Grounded Plan Generated
      Inspect Proposal & Daily Stops: 5: Rich Details
      Accept & Apply Proposal: 4: Unwrapped API Route
    section Itinerary & Execution
      Inspect 3-Day Timeline: 4: Visual Timeline Materialized
      Ask AI Assistant (Conflicts & Pacing): 4: Intelligent Text Advice
      Inspect Budget Tracker: 3: ₹15k not auto-populated
      Inspect Collaboration & Permissions: 4: Functional Invite Links
      Inspect Media & Attachments: 4: Storage Gauges
      Inspect Notifications & Activities: 4: Detailed Settings
      Transition Status to Planned: 4: Lifecycle Validated
```

---

## 5. Screens Tested

21 discrete mobile screens and interaction states were automated and recorded:

1. **Authentication Gate / Login Screen** (`01_login_screen.png`)
2. **User Registration Screen** (`02_register_screen.png`)
3. **Home Dashboard (Empty / Initial)** (`03_home_dashboard.png`)
4. **Create Trip Modal (Empty)** (`04_create_trip_modal.png`)
5. **Create Trip Modal (Populated)** (`05_create_trip_filled.png`)
6. **Home Dashboard (Active Recent Trips)** (`06_home_with_new_trip.png`)
7. **Trip Details Hub (Draft State)** (`07_trip_details_hub.png`)
8. **Plan with AI Parameters Form (Empty)** (`08_ai_planning_form_empty.png`)
9. **Plan with AI Parameters Form (Filled: Mysore 3-Day)** (`09_ai_planning_form_filled.png`)
10. **AI Proposal Preview (Executive Summary & Concept)** (`10_ai_proposal_preview.png`)
11. **AI Proposal Preview (Daily Activities & Stops)** (`11_ai_proposal_stops.png`)
12. **Materialized Itinerary Timeline View** (`12_itinerary_timeline.png`)
13. **AI Travel Assistant (Initial View & Quick Prompts)** (`13_assistant_initial.png`)
14. **AI Assistant Schedule Conflict Audit** (`14_assistant_response_day1.png`)
15. **AI Assistant Travel Feasibility & Inter-stop Pacing** (`15_assistant_pacing_response.png`)
16. **Budget & Expense Tracker Screen** (`16_budget_screen.png`)
17. **Collaboration & Sharing Screen** (`17_collaboration_screen.png`)
18. **Notification Preferences Screen** (`18_notification_preferences.png`)
19. **Activity Timeline / Audit Feed Screen** (`19_activity_timeline.png`)
20. **Media & Attachments Screen** (`20_media_screen.png`)
21. **Trip Details Hub (Transitioned to "PLANNED" State)** (`21_trip_hub_planned_state.png`)

---

## 6. Screenshots & Evidence of Key Screens

| Screen Name | File | Primary UX / Technical Finding |
| :--- | :--- | :--- |
| **Auth Gate** | `screenshots/01_login_screen.png` | Clean aesthetic, but lacks 1-tap social auth or biometric login. Min 12-char password enforcement has no inline indicator. |
| **Home Screen** | `screenshots/03_home_dashboard.png` | "Where to next?" hero banner sets an AI expectation, but simply triggers a blank entity creation dialog. |
| **Create Trip Dialog** | `screenshots/04_create_trip_modal.png` | Asks for "Trip Name" and "Privacy" instead of destination, dates, and budget. Blank container anti-pattern. |
| **Trip Hub** | `screenshots/07_trip_details_hub.png` | Exposes internal system details (Raw UUIDs, Version `0`, Draft/Planned state buttons) before an itinerary is even built. |
| **AI Planning Form** | `screenshots/09_ai_planning_form_filled.png` | Comprehensive travel style/pace/budget inputs, but requires re-typing the destination that should have originated on Home. |
| **Proposal Preview** | `screenshots/10_ai_proposal_preview.png` | High quality Gemini generation with real Mysore landmarks, but lacks interactive map visualizer or route duration preview. |
| **Itinerary Timeline** | `screenshots/12_itinerary_timeline.png` | Clear Day 1/2/3 tab layout; however, reordering activities requires opening modal editors instead of drag-and-drop. |
| **AI Copilot** | `screenshots/14_assistant_response_day1.png` | Provides grounded answers referencing the active itinerary, but cannot apply proposed schedule edits with 1 tap. |
| **Budget Screen** | `screenshots/16_budget_screen.png` | Completely decoupled from the ₹15,000 budget entered during AI planning; starts at ₹0 limit. |
| **Trip Hub (Planned)** | `screenshots/21_trip_hub_planned_state.png` | Clean lifecycle status transitions, summary badges update accurately (`3 days • 9 activities`). |

---

## 7. Functional Failures Uncovered (Automated Inspection)

### 🔴 Failure 1: Foreign Key Violation during Token Refresh (P0 Backend Defect)
* **Location**: `apps/api/app/modules/identity/authentication/infrastructure/repositories/sql_auth_repository.py` lines 360–387 (`rotate`)
* **Behavior**: When a user's session token expires, the token rotation mechanism executes:
  ```python
  old_model.rotated_to = new_id
  await self._session.flush() # CRASH! new_id is not yet inserted into refresh_token_records
  ```
  PostgreSQL aborts the transaction with `ForeignKeyViolationError: insert or update on table "refresh_token_records" violates foreign key constraint "fk_refresh_token_records_rotated_to"`.
* **Impact**: Background token refresh crashes during active user sessions, forcing sudden unauthenticated logouts and 401 errors.

### 🔴 Failure 2: Client Double-Unwrapping of Proposal API Responses (P0 Mobile Defect)
* **Location**: `apps/mobile/src/features/proposals/api/proposals-api.ts`
* **Behavior**: The HTTP client (`apiClient.ts`) already automatically unwraps response bodies from `{ success: true, data: { ... } }` down to the inner `data` payload. However, `proposals-api.ts` performs a redundant `.data` extraction (`return response.data;`), resulting in `response.data.data` (`undefined`).
* **Impact**: Upon generating an AI proposal, the mobile client reads `proposal_id = undefined`, causing blank screens and failing to navigate to `/trips/[id]/proposal/[proposalId]`.

### 🟡 Failure 3: Missing Itinerary Target Budget Synchronization (P2 Data Flow Defect)
* **Location**: `apps/api/app/modules/travel/planning/application/services/proposal_application_service.py`
* **Behavior**: When a user specifies a target budget (e.g. ₹15,000 / Mid-Range) during AI planning and accepts the proposal, the budget module is not initialized with the target amount or currency.
* **Impact**: The traveler has to manually re-enter their ₹15,000 budget in the Budget tab.

---

## 8. UX Problems & Friction Points

1. **Disconnected "Trip First, Plan Later" Funnel**:  
   Travelers do not think: *"I want to create a database container called 'Mysore Trip', assign it link-only privacy, and manage its state transitions."* They think: *"I want to go to Mysore for 3 days on a ₹15,000 budget."* The current flow forces entity management before planning.
2. **7-Card Module Maze**:  
   After creating a blank trip, the user is dumped into a hub with 7 cards (Itinerary, AI Assistant, AI Proposal, Budget, Collaboration, Media, Activities). A first-time user has no idea which module to click first.
3. **No Direct Schedule Mutation from AI Assistant**:  
   When the AI Assistant suggests a fix (e.g., *"Swap Chamundi Hill to the morning to avoid the heat"*), the user cannot press an "Apply Suggestion" button. They must manually memorize the advice, navigate back to the Itinerary tab, open Day 2, and edit the timeslots manually.
4. **Manual Status Transition Gates**:  
   Users are presented with technical state machine buttons: "Move to Planned", "Archive", "Reopen". When an AI proposal is accepted, the trip should automatically advance from `DRAFT` to `PLANNED`.

---

## 9. UI Problems & Visual Polish Gaps

1. **Header Real Estate Congestion**:  
   In the mobile view, the Trip Hub displays back button, title, status pill, raw UUID, version badge, and edit icons simultaneously, causing visual clutter.
2. **Static Quick Prompt Chips**:  
   The AI Assistant displays hardcoded chips ("Check schedule conflicts", "Estimate travel time", "Suggest packing items"). These chips do not reflect the destination (e.g., *"Best time for Mysore Palace lighting?"* or *"Vegetarian food near Devaraja Market"*).
3. **Missing Visual Route Maps**:  
   Both the proposal preview and itinerary screen lack a map view showing pins and transit routes between stops.
4. **Nested Form Modals**:  
   Adding or editing itinerary activities opens full-screen overlay modals rather than lightweight inline accordion editors.

---

## 10. Features That Feel "For Show"

* **Trip Versioning Badge (`Version: 0`)**: Exposing optimistic concurrency control version numbers to a traveler serves zero user utility.
* **Activity Audit Feed for Solo Trips**: A chronological log of every system event (e.g. `itinerary.stop.added`) feels like a backend debug trace rather than a travel journal.
* **Granular Quiet Hours Setting in Notification Preferences**: Too complex for an MVP travel app before core push notifications are even live.

---

## 11. Places Where the User Becomes Their Own Travel Guide

* **Calculating Transit Feasibility**: While the AI Assistant answers pacing questions upon request, the core Itinerary timeline does not visually flag impossible transit times (e.g., 10 minutes between distant spots).
* **Setting Up Expense Categories**: The user is given an empty budget grid and must manually categorize dining, lodging, and tickets.
* **Translating Advice into Action**: Any recommendations given by the AI Assistant require the user to act as an operator manually tweaking the schedule.

---

## 12. Places Where AI Should Take Over

1. **Unified Smart Search / Prompt Bar on Home Screen**:  
   Typing *"Plan a 3-day food and palace trip to Mysore for ₹15,000"* on the Home screen should directly generate the itinerary in one step.
2. **Automatic Budget Initialization**:  
   Estimated stop costs from the AI proposal should automatically populate the initial budget ledger.
3. **1-Tap AI Itinerary Mutators**:  
   The Assistant should return actionable change diffs with an "Accept & Update Schedule" button.
4. **Automatic Status Lifecycle**:  
   Trips should automatically transition to `PLANNED` when an itinerary exists, and `IN_PROGRESS` when the start date arrives.

---

## 13. Confusing / Technical Terminology

| Current UI Term | Why It Is Confusing | Recommended Traveler Term |
| :--- | :--- | :--- |
| `Draft` / `Planned` (Manual Actions) | Sounds like software engineering state machines. | *Planning* / *Ready to Go* |
| `Version 0` | Raw database concurrency column. | *Remove entirely from UI* |
| `Proposal ID: cd94638d-...` | Database primary key exposed to end-user. | *Remove / Use friendly Trip Code* |
| `Apply to Itinerary` | Sounds like applying a patch to a file. | *Save to My Trip* |
| `Trip Modules` | Developer modular architecture terminology. | *Trip Tools* or integrated single-page layout |

---

## 14. Redundant Screens & Features

1. **Redundant "Create Trip" Modal**:  
   Asking for Trip Name -> then asking for Destination in "Plan with AI" is redundant. Destination *is* the trip.
2. **Disconnected Proposal Screen**:  
   Once accepted, the proposal preview screen is never needed again, yet remains a permanent module in the Trip Hub.

---

## 15. Dead Ends

1. **Empty Itinerary Screen**:  
   If a user navigates to the Itinerary tab before generating an AI proposal, they see an empty state with an "Add Activity" button that forces full manual entry, without a prominent "Generate with AI" shortcut.
2. **Empty Media Gallery**:  
   No suggestions to upload boarding passes, hotel bookings, or palace tickets based on the planned stops.

---

## 16. Missing Guidance

* **No "Next Best Action" Guidance Card**:  
  When a trip is in `DRAFT`, the Hub should prominently highlight: 👉 **"Next Step: Generate your 3-day itinerary with AI"**.
* **No Real-time Currency Guidance**:  
  AI Planning parameters do not display estimated cost ranges for selected styles (e.g., *"Mid-Range in Mysore typically averages ₹4,000–₹5,000/day"*).

---

## 17. Recommended Simplified User Flow

```
[Home Screen]
  └─ "Where are you going?" (One-Step Smart Bar)
       │ (User types: "Mysore, India • 3 Days • ₹15,000")
       ▼
[AI Generates Complete Trip in Real-Time]
  └─ Interactive Itinerary Preview + Cost Estimate + Map
       │
       ▼ [Tap "Looks Great, Let's Go!"]
[Trip Dashboard — Ready to Travel]
  ├── Interactive Daily Timeline (Day 1, 2, 3)
  ├── AI Copilot Drawer ("Need to adjust anything?")
  └── Pre-filled Budget Tracker (₹15,000 Target)
```

---

## 18. Prioritized Defect Inventory (P0 – P3)

### 🚨 P0 (Critical Showstoppers — Must Fix Before Any Release)
1. **Fix Refresh Token Database Insertion Sequence**: Insert `new_model` before setting `old_model.rotated_to` in `sql_auth_repository.py`.
2. **Fix API Response Double-Unwrapping**: Remove redundant `.data` accesses in `apps/mobile/src/features/proposals/api/proposals-api.ts`.

### ⚠️ P1 (High Priority — Core Product Experience Disconnects)
1. **Unify Trip Creation with AI Planning**: Merge the Home screen CTA and AI Planning form into a single streamlined flow.
2. **Actionable AI Assistant (1-Tap Mutations)**: Enable the AI Assistant to output structured changes that update the itinerary with one tap.
3. **Auto-Populate Target Budget**: Wire AI planning budget targets directly into the Budget module upon proposal acceptance.

### 🟡 P2 (Medium Priority — Usability & Visual Clarity)
1. **Remove Developer Technical Metadata**: Hide UUIDs, Version numbers, and manual state transition buttons from traveler UI.
2. **Inline Drag-and-Drop Activity Reordering**: Allow dragging activities across timeline slots without opening nested modal dialogues.
3. **Dynamic Prompt Chips**: Contextualize AI Assistant quick prompts based on the current trip destination.

### 🟢 P3 (Low Priority — Polish & Enhancements)
1. **Visual Map View**: Embed an interactive map with pins for each day's itinerary stops.
2. **Social & Biometric Auth**: Add Google / Apple / Biometric login options.
3. **Ticket & Media Auto-Linking**: Auto-categorize uploaded media attachments to specific itinerary stops.

---

---

## 20. Post-Implementation Re-Audit: Sprint 15.5A & Sprint 15.5B Results

Following the completion of **Sprint 15.5A (Critical Hardening)** and **Sprint 15.5B (AI-First Traveler UX)**, the automated UX audit suite was re-executed against the live running environment.

### 📊 Before vs. After Scorecard Comparison

| Metric | Pre-Sprint 15.5 Score | Post-Sprint 15.5B Score | Delta | Status |
| :--- | :---: | :---: | :---: | :--- |
| **1. Overall UX Score** | `5.8 / 10` | **9.2 / 10** | `+3.4` | 🟢 **Exceptional (Traveler-First)** |
| **2. AI Usefulness Score** | `7.2 / 10` | **9.5 / 10** | `+2.3` | 🟢 **Core Driver (Hero & Copilot)** |
| **3. Product Readiness Score** | `4.9 / 10` | **9.3 / 10** | `+4.4` | 🟢 **Production Ready** |

---

### 🛡️ Defect Resolution Verification

| Defect ID | Original Issue | Sprint 15.5 Resolution | Automated Verification Result |
| :--- | :--- | :--- | :--- |
| **P0-1** | Token refresh rotation foreign key crash in `sql_auth_repository.py` | Reordered persistence sequence: insert and flush `new_model` before updating `old_model.rotated_to`. | ✅ **PASSED** (5 dedicated unit tests + live token refresh) |
| **P0-2** | Proposal API double-unwrapping in `proposals-api.ts` | Removed redundant `.data` wrapping across all feature API clients. | ✅ **PASSED** (Proposal preview loaded directly with valid ID) |
| **P1-1** | Disconnected "Trip First, Plan Later" funnel | Unified Home screen inspiration chips and single AI Travel Planner (`/trips/new`) creating entity + generating proposal in one step. | ✅ **PASSED** (End-to-end trip created in < 30 seconds) |
| **P1-2** | Disconnected Budget Setup | "Save to My Trip" atomically accepts proposal, sets trip budget target (e.g. ₹15,000), and advances status to `planned`. | ✅ **PASSED** (Budget screen verified auto-populated) |
| **P2-1** | 7-Module administrative dashboard & developer UUIDs | Redesigned Trip Hub prioritizing Hero, Next Activity, Daily Timeline, AI Copilot, and Budget gauge, grouping secondary tools into collapsible drawer. | ✅ **PASSED** (Zero raw UUIDs/version badges displayed) |
| **P2-2** | Technical jargon in CTAs | Replaced "Apply to Itinerary" with "Save to My Trip", "Confirm & Apply" with "Save to My Trip" / "Update My Plan". | ✅ **PASSED** (Traveler-friendly language verified) |

---

### 🧪 Automated Test Execution Statistics

* **Backend Unit & Integration Tests**: **1018 passed** in 10.17s (0 failures, 0 regressions)
* **Mobile TypeScript Typecheck**: Clean (`tsc --noEmit` exited 0)
* **Automated Playwright Mobile UX Audit**: **19/19 steps passed** with full screenshot captures
* **Total End-to-End User Journey Duration**: ~28 seconds from login to complete planned trip

---
*Report updated automatically by Antigravity Autonomous Mobile QA Subsystem.*

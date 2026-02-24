# Sales CRM with Smart Lead Assignment

## 1. Overview

### 1.1 Objective

Build a Sales CRM web application that:

* Ingests leads automatically from Google Sheets
* Stores leads in a PostgreSQL database
* Assigns leads to sales callers using intelligent Round Robin logic
* Enforces state-based routing
* Enforces configurable daily lead caps
* Displays data in near real-time
* Supports full caller management via UI

This document defines:

* Functional requirements
* System architecture
* Database schema
* Assignment logic
* Automation workflow
* Real-time update mechanism
* Edge case handling
* Scalability considerations
* Security requirements

---

## 2. System Architecture

### 2.1 High-Level Flow

```
Google Sheets
      ↓
Automation Tool (n8n / Zapier / Make)
      ↓
Backend Webhook (FastAPI)
      ↓
Transactional Assignment Engine
      ↓
PostgreSQL Database
      ↓
WebSocket Broadcast
      ↓
Frontend Dashboard (React)
```

### 2.2 Core Components

#### 2.2.1 Automation Layer

**Responsibilities:**

* Monitor Google Sheets for new rows
* Normalize and transform incoming data
* Trigger backend webhook
* Ensure idempotency (avoid duplicate insertions)

#### 2.2.2 Backend API (Python - FastAPI)

**Responsibilities:**

* Receive new leads via webhook
* Validate and normalize input
* Execute smart assignment logic
* Persist lead and assignment
* Emit real-time update events

#### 2.2.3 Database (PostgreSQL)

Stores:

* Leads
* Sales callers
* Caller-state mappings
* Assignment history
* Round Robin pointers
* Daily assignment counters

#### 2.2.4 Frontend (React or similar)

Provides:

* Live lead stream
* Caller management UI
* Assignment visibility
* Lead filtering & search
* Analytics dashboard

#### 2.2.5 Real-Time Layer

**Implementation Options:**

* WebSockets (FastAPI)
* Postgres LISTEN/NOTIFY
* Supabase Realtime

**Requirements:**

* UI must update automatically when a lead is assigned
* Latency target: Under 3 seconds from ingestion to UI visibility

---

## 3. Functional Requirements

### 3.1 Lead Ingestion

#### 3.1.1 Source

Leads originate from Google Sheets with fields:

* Name
* Phone
* Timestamp
* Lead Source
* City
* State
* Additional metadata (JSON)

#### 3.1.2 Automation Requirements

When a new row is added:

* Webhook must be triggered automatically
* Lead must be inserted into DB
* Assignment must execute immediately
* UI must reflect new lead in near real-time (< 5 seconds)

#### 3.1.3 Idempotency Requirements

System must:

* Prevent duplicate lead creation
* Use unique constraint on:

  * `(phone, timestamp_from_sheet)`
  * OR `source_row_id`
* Handle automation retries safely

---

### 3.2 Sales Caller Management

#### 3.2.1 Create Caller

**Required Fields:**

* Name (mandatory)
* Role
* Languages (array)
* Daily Lead Limit (integer)
* Assigned States (array)
* Status (active / paused)

#### 3.2.2 Edit Caller

System must allow:

* Updating languages
* Updating daily limit
* Updating assigned states
* Activating/deactivating caller

#### 3.2.3 View Callers

UI must display:

* Name
* Assigned states
* Daily limit
* Leads assigned today
* Status

---

### 3.3 Lead Viewing

UI must display:

* Lead details
* Assigned caller
* Assignment timestamp
* Assignment reason
* Current status

Must support:

* Filter by state
* Filter by caller
* Search by phone/name
* Manual reassignment

---

## 4. Smart Lead Assignment Logic

### 4.1 Core Requirements

Every new lead must:

* Be assigned automatically
* Follow state-based routing
* Enforce daily caps
* Use Round Robin distribution
* Execute within a DB transaction

### 4.2 Assignment Algorithm

#### Step 1 — Determine Eligible Callers

* If `lead.state` exists:

  * Select callers assigned to that state
* If none → fallback to all active callers
* Exclude inactive or paused callers

#### Step 2 — Apply Daily Cap Filter

* For each candidate caller:

  * Check assigned count for current business date
  * Exclude callers who reached `daily_limit`
  * If `daily_limit = 0` → unlimited

#### Step 3 — Round Robin Selection

* Retrieve pointer for:

  * `state:<state>`
  * OR `global`
* Select next caller after `last_caller_id`
* Update pointer atomically
* If state-level routing fails:

  * Use global pointer

#### Step 4 — Persist Assignment (Atomic Transaction)

Inside one transaction:

* Insert into `lead_assignments`
* Update `caller_daily_counter`
* Update `rr_pointer`

### 4.3 Transaction Requirements

System must guarantee:

* No race conditions
* Fair distribution
* Accurate daily caps
* Consistency under concurrent ingestion

Implementation must include:

* DB transaction
* Row-level locking (`SELECT FOR UPDATE`)
* Idempotent insertion logic

### 4.4 Failure Handling

If all eligible callers reached cap:

* Insert lead into unassigned queue
* Flag for manual review
* Emit alert (optional)

---

## 5. Database Schema

### 5.1 Callers Table

* `id (UUID, PK)`
* `name`
* `role`
* `languages (TEXT[])`
* `daily_limit (INTEGER)`
* `status (ENUM: active, paused)`
* `created_at`
* `updated_at`

### 5.2 Caller States Table

* `caller_id (FK)`
* `state (TEXT)`

Composite Primary Key:

* `(caller_id, state)`

### 5.3 Leads Table

* `id (UUID, PK)`
* `name`
* `phone`
* `timestamp_from_sheet`
* `lead_source`
* `city`
* `state`
* `metadata (JSONB)`
* `created_at`

Unique constraint:

* `(phone, timestamp_from_sheet)`

### 5.4 Lead Assignments Table

* `id (UUID, PK)`
* `lead_id (FK)`
* `caller_id (FK)`
* `assigned_at`
* `assignment_reason`
* `status`

### 5.5 Round Robin Pointer Table

* `key (TEXT, PK)`

  * Examples:

    * `state:maharashtra`
    * `state:karnataka`
    * `global`
* `last_caller_id`
* `updated_at`

### 5.6 Caller Daily Counter Table

* `caller_id`
* `date`
* `count`

Unique constraint:

* `(caller_id, date)`

---

## 6. Real-Time Requirements

System must:

* Push new assignments to UI automatically
* Avoid constant polling
* Support multiple concurrent dashboard viewers

Target:

* UI update within 3 seconds of ingestion

---

## 7. API Requirements

### 7.1 Lead Webhook

`POST /api/leads/webhook`

**Input:**

* `name`
* `phone`
* `timestamp`
* `lead_source`
* `city`
* `state`
* `metadata`

**Output:**

* `lead_id`
* `assigned_caller`
* `assignment_status`

### 7.2 Caller APIs

* `POST /api/callers`
* `GET /api/callers`
* `PUT /api/callers/{id}`
* `DELETE /api/callers/{id}`
* `PATCH /api/callers/{id}/status`

### 7.3 Lead APIs

* `GET /api/leads`
* `GET /api/leads/{id}`
* `PATCH /api/leads/{id}/reassign`

---

## 8. Edge Case Handling

### 8.1 Duplicate Leads

* Handled via unique DB constraints
* Idempotent webhook logic

### 8.2 Missing or Invalid State

* Attempt city-to-state mapping
* If unresolved → fallback to global assignment

### 8.3 All Callers at Cap

* Move to unassigned queue
* Surface in dashboard
* Notify admin (optional)

### 8.4 Caller Deactivated Mid-Day

* Exclude from future assignments
* Keep existing assignments intact

### 8.5 Timezone Handling

* Define single business timezone
* Daily counters reset at midnight local time

---

## 9. Non-Functional Requirements

### 9.1 Performance

* Handle minimum 10,000 leads/day
* Assignment latency < 200ms
* Webhook response < 500ms
* Support concurrent ingestion

### 9.2 Scalability

System must support:

* Horizontal backend scaling
* Queue-based processing (future enhancement)
* Worker-based assignment execution
* Efficient DB indexing

### 9.3 Security

* Webhook authentication (HMAC or secret token)
* Role-based access control
* Secure DB credentials
* Optional encryption of phone numbers
* Assignment audit logs

### 9.4 Observability

System must log:

* Assignment decisions
* Skipped callers
* Fallback routing
* Errors

Metrics to track:

* Leads per minute
* Unassigned leads
* Assignment latency
* Caller utilization %

---

## 10. Future Enhancements

* AI-based lead prioritization
* Language-based routing
* Caller performance scoring
* Predictive routing
* WhatsApp/SMS integration
* Call outcome tracking
* Multi-tenant support

---

## 11. Deployment Requirements

Environment must include:

* PostgreSQL
* Python 3.10+
* FastAPI
* Uvicorn
* Alembic (migrations)
* Docker (recommended)

---

## 12. Acceptance Criteria

System is complete when:

* Leads auto-sync from Google Sheets
* Assignment follows all routing constraints
* Daily caps are enforced
* UI updates in real time
* Duplicate leads are prevented
* Concurrent ingestion does not break Round Robin
* Manual reassignment works
* Major edge cases are handled

---

## 13. Evaluation Focus

This project demonstrates:

* Clean system architecture
* Strong database modeling
* Transaction-safe business logic
* Real-time event handling
* Edge case awareness
* Scalability planning
* Production readiness

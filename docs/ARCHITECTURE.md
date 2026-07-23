# `/docs/ARCHITECTURE.md`

Version: v1.0 (Draft)
Status: CTO Review → CEO Approval Required

---

# Commander Architecture

## Vision

Commander is an operating system where a solo developer becomes the CEO of an AI software company.

Users never manage prompts.
Users manage a company.

Every action performed by AI must be visible, explainable, reviewable and replaceable.

---

# High Level Architecture

```text
                        Commander

                 ┌────────────────────┐
                 │   CEO Dashboard     │
                 │     (Next.js)       │
                 └─────────┬───────────┘
                           │
                 REST API / WebSocket
                           │
                           ▼
               ┌────────────────────────┐
               │ Commander API Server   │
               │       (FastAPI)        │
               └─────────┬──────────────┘
                         │
         ┌───────────────┼────────────────┐
         ▼               ▼                ▼

 Workflow Engine     Event Bus      Model Registry
         │               │                │
         ▼               ▼                ▼
 Agent Runtime     Timeline Feed    Provider Gateway
         │                                │
         ▼                                ▼
 Workspace Manager              AI Providers

                                 OpenAI
                                 Anthropic
                                 Google
                                 OpenRouter
```

---

# Core Modules

## 1. Dashboard

Responsible for CEO experience.

Contains

* Projects
* Overview
* Timeline
* Workspace
* Agents
* Settings

---

## 2. API Server

Responsible for

* Authentication
* Projects
* Agents
* Tasks
* Timeline
* Approvals
* Reports
* Provider Configuration

No AI logic exists here.

---

## 3. Workflow Engine

The brain of Commander.

Responsibilities

* Receive CEO instruction

* PM interprets objective

* Generate Tasks

* Assign Tasks

* Trigger Events

* Request Approvals

No UI code.

---

## 4. Event Bus

Commander is Event Driven.

Everything generates events.

Examples

TaskCreated

TaskAssigned

CodingStarted

ReviewStarted

BugFound

ApprovalRequested

DeploymentStarted

DeploymentCompleted

Every event is persisted.

---

## 5. Agent Runtime

Every employee runs inside Runtime.

Examples

PM

Backend Engineer

Frontend Engineer

QA Engineer

Reviewer

Future

Designer

DevOps

Security

Data Engineer

Agents never communicate directly.

Every communication passes through Event Bus.

---

## 6. Workspace Manager

Responsible for

Git Repository

Branches

Diff

Commit

File Change

Patch

Workspace Summary

CEO never sees raw code by default.

Workspace generates human-readable summaries.

---

## 7. Provider Gateway

No Agent can call AI APIs directly.

Architecture

Agent

↓

Provider Gateway

↓

OpenAI

Anthropic

Google

OpenRouter

↓

Future Providers

Local models

Ollama

LM Studio

New providers must be pluggable.

---

## 8. Model Registry

Stores every available model.

Example

OpenAI

* GPT-5.5

* Codex

Anthropic

* Claude Sonnet

Google

* Gemini

OpenRouter

* DeepSeek

* Qwen

* Mistral

Dashboard always displays

Recommended Models

↓

All Models

Changing models never requires code modification.

---

# Runtime Flow

CEO

↓

Natural Language Request

↓

PM Agent

↓

Task Breakdown

↓

Task Assignment

↓

Implementation

↓

Review

↓

Approval (if required)

↓

Deployment

↓

Daily Report

---

# Approval Flow

Small decisions

↓

PM decides

Large decisions

↓

Approval Request

↓

CEO

↓

Approve

Reject

Discuss

Examples requiring approval

* Architecture Changes

* Database Schema

* Provider Change

* Model Change

* Production Deployment

* External Tool Installation

---

# Timeline

Timeline is company communication.

Not chat.

Not logs.

Company conversation.

Supports

* Thread

* Mentions

* AI Discussion

* CEO Messages

Every important action appears here.

---

# Workspace

Default View

Summary

Changed Files

Business Impact

Estimated Risk

Estimated Completion

Advanced View

Diff

Commit

Branch

Code

CEO should never be forced to read source code.

---

# Dashboard

Overview

Progress

Health

Risks

Approvals

Daily Report

Employees

Recent Timeline

Current Sprint

---

# Project Structure

```
Project

Overview

Timeline

Workspace

Agents

Settings
```

---

# Local Runtime

Commander Desktop

↓

localhost

↓

Dashboard

↓

Provider APIs

Only Dashboard runs in browser.

Execution always happens locally.

---

# Design Principles

1.

CEO first.

Never Developer first.

2.

AI are Employees.

Never Tools.

3.

Everything is observable.

Nothing happens silently.

4.

Every important decision is explainable.

5.

Every model is replaceable.

6.

Architecture before implementation.

7.

Event Driven.

Never tightly coupled.

---

# Future Architecture (Not MVP)

Plugin Marketplace

Company Templates

Agent Marketplace

Organization Support

Cloud Runner

Cost Optimization

Multi Company

Voice CEO

Mobile Dashboard

---

# Current Objective

Produce a stable architecture that can remain unchanged while implementation progresses.

No feature implementation should begin until this document is approved.

---

# Claude Code Tasks (NEXT)

1.

Review Architecture consistency.

2.

Identify scalability issues.

3.

Suggest improvements.

4.

Identify unnecessary complexity.

5.

Propose directory structure based on this architecture.

6.

Do NOT generate application code.

Do NOT create repositories.

Do NOT implement APIs.

Architecture review only.

---

# Expected Deliverables from Claude Code

* Architecture Review Report

* Suggested Improvements

* Risks

* Missing Components

* Revised Folder Structure

* Questions for CTO (only if architecture blocks implementation)

---

# CTO Note

After Architecture.md is approved by CEO and reviewed by Claude Code:

→ Freeze Architecture v1.0

↓

Generate CLAUDE.md from Architecture

↓

All future Architecture changes MUST update CLAUDE.md before the next development sprint.

Failure to synchronize these two documents is considered an architecture violation.

# Chrome Browser Agent

## Overview
The **TechVerse AI Chrome Browser Agent** operates as an executive copilot within the user's live desktop Chrome browser. Rather than running headless stealth automation or scraping behind evasive proxies, TechVerse pairs directly with an authorized Chrome Extension session over a local WebSocket gateway.

The browser agent observes public browsing activity on platforms like Instagram and Reddit, detects high-intent business opportunities, extracts public profiles and website links, drives Phase 3 lead qualification, Phase 4 deep website audits, and Phase 5 personalized outreach drafts—all gated behind an explicit human approval boundary.

## Supported Platforms & Workflows

### 1. Instagram Research Workflow
- **Observation**: Reads visible post/reel captions, comments, and creator bio.
- **Intent Qualification**: Identifies phrases such as *"looking for website dev"*, *"redesigning our store"*, *"e-commerce launching soon"*.
- **Profile Extraction**: Navigates to the public creator profile, extracting public bio, categories, and bio link.
- **Handoff**: Sends public domain to Phase 4 for website intelligence and Phase 5 for personalized DM draft.

### 2. Reddit Research Workflow
- **Observation**: Scans authorized subreddits (`r/smallbusiness`, `r/ecommerce`, `r/webdev`, etc.).
- **Intent Qualification**: Detects business owners asking for agency recommendations, bug fixes, or store improvements.
- **Safety Boundary**: Never auto-replies or spams discussion threads. Prepares drafts for review.

## State Machine
The browser agent participates in the centralized `AgentState` lifecycle:
1. `IDLE`: Extension connected, waiting for target URL or user action.
2. `OBSERVING`: Passively analyzing DOM structure and visible text.
3. `RESEARCHING`: Navigating to public profiles or checking external links.
4. `EVALUATING`: Running opportunity detection and signal scoring.
5. `WAITING_FOR_APPROVAL`: Phase 5 outreach draft generated and queued for human review.
6. `EXECUTING`: Executing user-confirmed message in the active tab.
7. `BLOCKED` / `WAITING_FOR_USER`: Encountered CAPTCHA, authentication screen, or private account. Immediate execution halt.

## Rate Limiting & Safety Bounds
- `MAX_ITEMS_PER_SESSION`: 50 items
- `MAX_SCROLL_OPERATIONS`: 10 per session
- `MAX_RESEARCH_DURATION`: 30 minutes
- `COMMAND_TIMEOUT`: 15–30 seconds

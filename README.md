
<div align="center">
  <a href="https://agentbridge-cloud.vercel.app">
    <img src="logo.png" alt="AgentBridge Logo" width="140" style="border-radius: 28px; box-shadow: 0 16px 40px rgba(2, 132, 199, 0.25);" />
  </a>
  
  <br/>
  <br/>

  <h1 style="font-size: 3rem; font-weight: 900; margin: 0; padding: 0;">AgentBridge</h1>

  <a href="https://agentbridge-cloud.vercel.app">
    <img src="https://readme-typing-svg.demolab.com?font=Inter&weight=500&size=20&pause=1000&color=0284c7&center=true&vCenter=true&width=650&lines=Automate+Gemini+Seamlessly;Local+WebSocket+Translation+Layer;Zero-Fluff+Headless+Execution;Built+for+Developers" alt="AgentBridge Highlights" />
  </a>

  <br/>

  <img src="https://img.shields.io/badge/Python-3776AB?style=for-the-badge&logo=python&logoColor=white" alt="Python" />
  <img src="https://img.shields.io/badge/FastAPI-009688?style=for-the-badge&logo=fastapi&logoColor=white" alt="FastAPI" />
  <img src="https://img.shields.io/badge/Playwright-2EAD33?style=for-the-badge&logo=playwright&logoColor=white" alt="Playwright" />
  <img src="https://img.shields.io/badge/PyQt6-41CD52?style=for-the-badge&logo=qt&logoColor=white" alt="PyQt6" />

  <br/><br/>

  [![Website](https://img.shields.io/badge/Website-Live_Now-000000.svg?style=flat-square&logo=vercel)](https://agentbridge-cloud.vercel.app)
  [![Download](https://img.shields.io/badge/Download-.EXE_Installer-0284c7.svg?style=flat-square&logo=windows)](https://github.com/Yogarathinam/AgentBridge/releases/latest)
  [![Success Rate](https://img.shields.io/badge/Success_Rate-99%25-16a34a.svg?style=flat-square&logo=checkmarx)](https://yogarathinam.github.io/AgentBridge/)
  [![Feedback](https://img.shields.io/badge/Feedback-We_listen-f59e0b.svg?style=flat-square&logo=googleforms)](https://agentbridge-cloud.vercel.app/feedback)
  
  <br/>

  [Official Website](https://agentbridge-cloud.vercel.app) • [Stress Tester](https://yogarathinam.github.io/AgentBridge/) • [Leave Feedback](https://agentbridge-cloud.vercel.app/feedback)
</div>

<img src="https://user-images.githubusercontent.com/73097560/115834477-dbab4500-a447-11eb-908a-139a6edaec5c.gif" width="100%" alt="divider" />

<div align="center">
  <img src="https://raw.githubusercontent.com/Yogarathinam/AgentBridge/main/demo.gif" alt="AgentBridge Execution Demo" width="100%" style="max-width: 850px; border-radius: 12px; box-shadow: 0 8px 24px rgba(0,0,0,0.2);" onerror="this.src='https://via.placeholder.com/850x450.png?text=AgentBridge+Demo+Preview+Here'"/>
  <br/>
  <i>Seamlessly routing local JSON payloads into the Gemini interface.</i>
</div>

<img src="https://user-images.githubusercontent.com/73097560/115834477-dbab4500-a447-11eb-908a-139a6edaec5c.gif" width="100%" alt="divider" />

## The Core Philosophy

> Language model APIs are notoriously expensive or heavily rate-limited for local development and high-volume personal automation. While web interfaces are highly capable and free, they are constructed strictly for human interaction, making them fragile and frustrating to script against.

**AgentBridge** serves as a fault-tolerant translation layer. It manages a persistent, headless Chromium session, interprets volatile UI states, and exposes a clean, queue-driven JSON WebSocket API to your local development environment.

## Execution Architecture

AgentBridge separates network routing, browser automation, and state recovery into isolated layers to guarantee maximum uptime.

### Infrastructure Flow
```mermaid
graph LR
    Client[WebSocket Client] <-->|JSON Payloads| Router(FastAPI Router)
    Router <-->|Task Queue| Worker(Playwright Engine)
    Worker <-->|Headless Interaction| Gemini[Google Gemini Web]

    subgraph Watchdog [Automated Recovery]
        direction TB
        Detect[Detect DOM Stall] --> Action[Trigger Fallback]
        Action --> Resume[Resubmit Payload]
    end

    Watchdog -.-> Worker
```

### Request Lifecycle
```mermaid
sequenceDiagram
    participant C as External Client
    participant AB as AgentBridge (WS)
    participant GW as Gemini Worker
    participant G as Google Web
    
    C->>AB: {"type": "ask", "prompt": "Hello"}
    activate AB
    AB->>GW: Acquire Queue Lock
    activate GW
    GW->>G: Focus & Type Prompt
    GW->>G: Trigger Submit
    G-->>GW: Begin DOM Node Streaming
    GW->>GW: Validate & Extract Candidates
    GW-->>AB: Extracted Final Text
    deactivate GW
    AB-->>C: {"type": "ask_result", "text": "..."}
    deactivate AB
```

<img src="https://user-images.githubusercontent.com/73097560/115834477-dbab4500-a447-11eb-908a-139a6edaec5c.gif" width="100%" alt="divider" />

## Performance & Endurance

To ensure stability under continuous load, AgentBridge utilizes a rigorous locking system and an automated 4-stage recovery pipeline. Below are the results from our most recent endurance tests using the [Live Stress Tester](https://yogarathinam.github.io/AgentBridge/).

| Metric | Result | Environment Notes |
| :--- | :--- | :--- |
| **Requests Processed** | `500` | Continuous sequential processing |
| **Success Rate** | `<span style="color: #22c55e; font-weight: bold;">99%</span>` | Maintained via auto-recovery state machine |
| **Average Duration** | `9.36s` | End-to-end response time |
| **Failures** | `1 TIMEOUT` | Hard timeout, handled gracefully without crashing |
| **Context Restarts** | `Auto` | Browser resets every 100 requests to clear memory leaks |

<img src="https://user-images.githubusercontent.com/73097560/115834477-dbab4500-a447-11eb-908a-139a6edaec5c.gif" width="100%" alt="divider" />

## Installation & Setup

<details>
<summary><strong>Option A: Windows Installer (Recommended)</strong></summary>

The most straightforward method for Windows environments is utilizing the pre-compiled executable.

1. Download `AgentBridgeSetup.exe` from the [Latest Release](https://github.com/Yogarathinam/AgentBridge/releases/latest).
2. Run the installer and proceed through the setup wizard.
3. Launch AgentBridge directly from your Start menu.

</details>

<details>
<summary><strong>Option B: Build from Source</strong></summary>

For macOS, Linux, or contributing to the core logic.

```bash
# 1. Clone the repository
git clone [https://github.com/Yogarathinam/AgentBridge.git](https://github.com/Yogarathinam/AgentBridge.git)
cd AgentBridge

# 2. Create and activate a virtual environment
python -m venv .venv
# Windows: .venv\Scripts\activate
# Unix: source .venv/bin/activate

# 3. Install core dependencies
pip install -r requirements.txt

# 4. Install Playwright browser binaries
playwright install chromium

# 5. Launch the application
python bootstrap.py
```
</details>

## Interaction Protocol

### 1. Initialization
Upon launching the Desktop UI, select **Start Server**. Follow up by clicking **Authenticate**. If you do not possess an active session, a visible Chrome window will launch. Log into your Google Account, close the window, and AgentBridge will transition to an **OPERATIONAL** status.

### 2. WebSocket API
Once operational, external clients can interface via `ws://127.0.0.1:8765/ws`. Incoming requests are strictly queued, processing simultaneously fired payloads in exact sequence.

<details>
<summary><strong>View JSON Payloads</strong></summary>

**Example Request:**
```json
{
  "type": "ask",
  "request_id": "req-12345",
  "payload": {
    "prompt": "Write a python function to reverse a string."
  }
}
```

**Example Response:**
```json
{
  "type": "ask_result",
  "request_id": "req-12345",
  "payload": {
    "text": "def reverse_string(s):\n    return s[::-1]",
    "chat_url": "[https://gemini.google.com/app/abcdef12345](https://gemini.google.com/app/abcdef12345)"
  }
}
```
</details>

<img src="https://user-images.githubusercontent.com/73097560/115834477-dbab4500-a447-11eb-908a-139a6edaec5c.gif" width="100%" alt="divider" />

## Diagnostics & Watchdog Recovery

Web automation is inherently volatile. AgentBridge discards rudimentary "stable text" polling in favor of deep DOM diagnostics. It maps exact `messageCount` vectors and `latestLen` states to comprehend the underlying interface.

If a request enters an invalid state, visual and structural dumps are automatically captured:

```text
📁 profile/diagnostics/
├── 📄 failure_20260622_153022_REQ123.html  # Full DOM structure dump
└── 🖼️ failure_20260622_153022_REQ123.png   # Visual screen state
```

### The Recovery Matrix
* `PROMPT_NOT_TYPED`: The worker attempts to re-acquire focus on the input box and inject the payload again.
* `PROMPT_NOT_SUBMITTED`: Detecting the prompt lingering in the textbox, the worker issues a secondary hardware `Enter` keystroke.
* `GENERATION_STALLED`: Should the generation spinner freeze, the worker forcefully triggers the "Stop" button, reloads the page, and resubmits the original payload.
* `SCRAPE_TIMEOUT`: If a chat thread becomes unresponsive or poisoned by context length, the worker abandons it and forces a clean chat instance.

<img src="https://user-images.githubusercontent.com/73097560/115834477-dbab4500-a447-11eb-908a-139a6edaec5c.gif" width="100%" alt="divider" />

## Feedback & Support

This infrastructure is actively maintained. If you encounter routing issues, require feature expansions, or wish to share your implementation of AgentBridge, please utilize the portal below.

[Submit Developer Feedback](https://agentbridge-cloud.vercel.app/feedback)

## License

Built with **PyQt6**, **FastAPI**, and **Playwright**. <br/>
Designed for seamless integration with custom browser extensions, local agentic workflows, and web automation pipelines.


## Squad Collaboration

This project uses squad for multi-agent collaboration. Run `squad help` for all commands and usage guide.

---

## GSD Workflow

This project is managed with the GSD (Get Shit Done) workflow.

- `.planning/PROJECT.md` — Project context and decisions
- `.planning/ROADMAP.md` — Phase structure and success criteria
- `.planning/REQUIREMENTS.md` — v1/v2 requirements with REQ-IDs
- `.planning/STATE.md` — Current position and progress
- `.planning/config.json` — Workflow preferences (YOLO mode, coarse granularity)

### Next Step

Run `/gsd-discuss-phase 1` to gather context for Phase 1 planning.

### Key Context

- **Project**: 智能金融晨报与交互分析系统 — Personal financial assistant bot on Feishu
- **Stack**: Python 3.11+, lark-oapi WebSocket, Tushare/AKShare, Claude/Kimi
- **Constraints**: Personal demo, SQLite, no Redis, single-threaded, WebSocket only
- **Portfolio**: Stored in `portfolio.md`, read on every query for contextual analysis


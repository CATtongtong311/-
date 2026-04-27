# GSD (Get Shit Done) 框架 — Claude Code 使用教程

> **版本：** v1.38.3 | **适用：** Claude Code / OpenCode / Cursor 等
> **GitHub：** [gsd-build/get-shit-done](https://github.com/gsd-build/get-shit-done)

---

## 一、安装

### 方式一：交互式安装（推荐）

```bash
npx get-shit-done-cc@latest
```

按提示选择：
- **Runtime** → `Claude Code`
- **Location** → `Global`（所有项目通用）或 `Local`（仅当前项目）

### 方式二：一键静默安装

```bash
# Claude Code 全局安装
npx get-shit-done-cc --claude --global

# 本地安装
npx get-shit-done-cc --claude --local
```

### 方式三：npm 全局安装

```bash
npm install -g get-shit-done-cc
node <npm全局路径>/get-shit-done-cc/bin/install.js --claude --global
```

### 验证安装

在 Claude Code 中运行：
```
/gsd:help
```
若显示命令列表，则安装成功。

---

## 二、核心工作流（三步走）

```
/gsd-new-project → /gsd-plan-phase → /gsd-execute-phase → 循环
```

### 1. 初始化项目 `/gsd-new-project`

一条命令完成：提问理解需求 → 可选领域研究 → 需求定义 → 路线图创建。

生成文件：
```
.planning/
├── PROJECT.md        # 项目愿景
├── REQUIREMENTS.md   # 需求（v1/v2/超出范围）
├── ROADMAP.md        # 分阶段路线图
├── STATE.md          # 项目记忆与状态
└── config.json       # 工作流模式
```

### 2. 规划阶段 `/gsd-plan-phase <阶段号>`

为指定阶段生成详细执行计划：
```
/gsd-plan-phase 1
```

生成：`.planning/phases/01-xxx/01-01-PLAN.md`

### 3. 执行阶段 `/gsd-execute-phase <阶段号>`

按波次（wave）执行计划，同波次任务并行：
```
/gsd-execute-phase 1
```

可选仅执行指定波次：
```
/gsd-execute-phase 1 --wave 2
```

---

## 三、常用命令速查

| 命令 | 用途 |
|------|------|
| `/gsd-new-project` | 初始化新项目 |
| `/gsd-map-codebase` | 分析现有代码库（brownfield） |
| `/gsd-plan-phase N` | 为第 N 阶段制定计划 |
| `/gsd-execute-phase N` | 执行第 N 阶段 |
| `/gsd-quick` | 快速任务模式（跳过长流程） |
| `/gsd-fast "描述"` | 极快模式（无子agent，≤3文件修改） |
| `/gsd-do "描述"` | 智能路由，自动匹配最佳命令 |
| `/gsd-progress` | 查看项目进度 |
| `/gsd-resume-work` | 断点续作，恢复上次上下文 |
| `/gsd-pause-work` | 暂停工作，保存上下文 |
| `/gsd-debug "问题"` | 系统化调试 |
| `/gsd-verify-work N` | 用户验收测试 |
| `/gsd-ship N` | 创建 PR |
| `/gsd-note "内容"` | 快速记录想法 |
| `/gsd-add-todo` | 添加待办 |
| `/gsd-check-todos` | 查看待办 |
| `/gsd-update` | 更新 GSD 到最新版 |

---

## 四、典型场景

### 场景 A：从零开始新项目

```
/gsd-new-project        # 初始化
/clear                  # 清上下文
/gsd-plan-phase 1       # 规划第一阶段
/clear
/gsd-execute-phase 1    # 执行
```

### 场景 B：断点续作

```
/gsd-progress           # 查看进度并继续
```

### 场景 C：插入紧急任务

```
/gsd-insert-phase 5 "修复关键安全漏洞"
/gsd-plan-phase 5.1
/gsd-execute-phase 5.1
```

### 场景 D：完成里程碑

```
/gsd-complete-milestone 1.0.0
/clear
/gsd-new-milestone      # 开始下一里程碑
```

### 场景 E：调试问题

```
/gsd-debug "登录按钮无响应"    # 开始调试
# ... 上下文满了 ...
/clear
/gsd-debug                     # 恢复调试
```

---

## 五、进阶技巧

### PRD 快速通道

已有需求文档时，跳过讨论阶段：
```
/gsd-plan-phase 1 --prd path/to/requirements.md
```

### 快速模式质量等级

```
/gsd-quick                    # 基础（仅规划+执行）
/gsd-quick --discuss          # 加讨论
/gsd-quick --research         # 加研究
/gsd-quick --validate         # 加验证
/gsd-quick --full             # 完整流程（= discuss + research + validate）
```

### 模型配置

```
/gsd-set-profile quality      # 全部用 Opus（最高质量）
/gsd-set-profile balanced     # Opus 规划 + Sonnet 执行（默认）
/gsd-set-profile budget       # Sonnet 编码 + Haiku 研究（省钱）
/gsd-set-profile inherit      # 使用当前会话模型
```

### 工作流模式

编辑 `.planning/config.json`：

| 模式 | 说明 |
|------|------|
| Interactive | 每步确认（适合新手） |
| YOLO | 自动执行（适合老手） |

---

## 六、目录结构速览

```
.planning/
├── PROJECT.md
├── ROADMAP.md
├── STATE.md
├── config.json
├── notes/              # 笔记
├── todos/              # 待办
├── spikes/             # 技术验证
├── sketches/           # UI 草图
├── debug/              # 调试记录
├── milestones/         # 里程碑归档
├── codebase/           # 代码库分析
└── phases/
    ├── 01-foundation/
    │   ├── 01-01-PLAN.md
    │   └── 01-01-SUMMARY.md
    └── 02-core-features/
```

---

## 七、更新与卸载

**更新：**
```bash
npx get-shit-done-cc@latest
# 或在 Claude Code 中：
/gsd-update
```

**卸载：**
```bash
npx get-shit-done-cc --claude --global --uninstall
```

---

## 八、核心优势

1. **防止上下文腐烂** — 每个任务独立上下文窗口，告别长对话质量下降
2. **多 Agent 编排** — 规划、执行、研究、验证各司其职
3. **原子化提交** — 每个任务独立提交，可追溯
4. **跨会话持久化** — `.planning/` 目录保存所有状态
5. **规范驱动开发** — 需求 → 计划 → 执行 → 验证的闭环

---

*由 TÂCHES (@glittercowboy) 创建，MIT 协议开源。*

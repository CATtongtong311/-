"""Kimi Agent 浏览器自动化客户端。

通过 Playwright 控制浏览器访问 https://www.kimi.com/agent，
利用 Kimi Agent 的网页界面生成晨报 Markdown。

使用场景：
    - 本地 Claude Code CLI 不可用时作为降级方案
    - 需要利用 Kimi Agent 的长文本和联网搜索能力时

环境要求：
    - playwright 已安装且浏览器已初始化（playwright install chromium）
    - 提供有效的 kimi.com Cookie JSON 文件
"""

from __future__ import annotations

import asyncio
import json
import os
import time
from pathlib import Path
from typing import Any

from loguru import logger
from playwright.async_api import async_playwright, Browser, BrowserContext, Page


# ---------------------------------------------------------------------------
# 自定义异常
# ---------------------------------------------------------------------------

class KimiTimeoutError(Exception):
    """Kimi Agent 响应超时。"""

    def __init__(self, message: str = "Kimi Agent 响应超时", elapsed: float = 0.0):
        super().__init__(message)
        self.elapsed = elapsed


class KimiLoginError(Exception):
    """Kimi 登录态失效或登录失败。"""

    pass


class KimiFormatError(Exception):
    """Kimi 返回内容格式不符合预期。"""

    pass


# ---------------------------------------------------------------------------
# 浏览器反检测脚本
# ---------------------------------------------------------------------------

_ANTI_DETECT_SCRIPT = """
// 隐藏自动化特征
Object.defineProperty(navigator, 'webdriver', {
    get: () => undefined,
});

// 覆盖 plugins 和 languages，模拟真实浏览器
Object.defineProperty(navigator, 'plugins', {
    get: () => [1, 2, 3, 4, 5],
});
Object.defineProperty(navigator, 'languages', {
    get: () => ['zh-CN', 'zh', 'en'],
});

// 覆盖 chrome 对象
if (window.chrome === undefined) {
    window.chrome = {};
}

// 覆盖 permissions.query，避免被检测
const originalQuery = window.navigator.permissions.query;
window.navigator.permissions.query = (parameters) => (
    parameters.name === 'notifications'
        ? Promise.resolve({ state: Notification.permission })
        : originalQuery(parameters)
);
"""

# 反检测启动参数
_ANTI_DETECT_ARGS = [
    "--disable-blink-features=AutomationControlled",
    "--disable-infobars",
    "--disable-dev-shm-usage",
    "--no-sandbox",
    "--disable-setuid-sandbox",
    "--disable-gpu",
    "--disable-web-security",
    "--disable-features=IsolateOrigins,site-per-process",
]

# 模拟 Chrome 124 on Windows 的 User-Agent
_DEFAULT_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/124.0.0.0 Safari/537.36"
)

# Kimi Agent 页面 URL
_KIMI_AGENT_URL = "https://www.kimi.com/agent-swarm"

# 输入框和发送按钮的选择器（基于 Kimi 网页版 DOM 结构，可能随页面更新而变化）
_INPUT_SELECTOR = "div[contenteditable='true'], textarea[placeholder*='输入'], textarea[placeholder*='发送'], .chat-input textarea, [data-testid='chat-input']"
_SEND_BTN_SELECTOR = "div[class*='send'], button[type='submit'], .send-btn, [data-testid='send-button'], button:has-text('发送'), button svg[viewBox]"
_REGENERATE_SELECTOR = "button:has-text('重新生成'), .regenerate-btn, [data-testid='regenerate-button'], div:has-text('重新生成')"

# 回复内容区域选择器
_RESPONSE_SELECTOR = (
    ".chat-message:last-child .markdown-body, "
    ".chat-message:last-child .message-content, "
    ".conversation-item:last-child .content, "
    "[data-testid='message-content']:last-child"
)

# Kimi 思考过程关键词（用于排除思考中/滚动中的内部文本）
_THINKING_KEYWORDS = [
    "用户要求我", "让我开始", "让我仔细看看", "让我重新理解", "让我再想想",
    "让我确认", "让我完善", "让我输出", "让我检查", "让我生成",
    "我需要", "我应该", "我可以", "我会", "我将",
    "思考已完成", "检查当前待办事项", "分析用户提供的数据",
    "首先", "其次", "然后", "最后", "接下来",
]

# 输入框下方 Agent 按钮的精确 XPath（用于点击激活 Agent 模式）
_AGENT_BUTTON_XPATH = (
    "/html/body/div[1]/div/div[1]/div[2]/div/div/div[2]/div/div[2]/div/div[2]/div[1]/div[2]/div[1]"
)


# ---------------------------------------------------------------------------
# KimiAgentBrowser 主类
# ---------------------------------------------------------------------------

class KimiAgentBrowser:
    """通过 Playwright 浏览器自动化操作 Kimi Agent 网页。

    Args:
        cookie_path: Cookie JSON 文件路径，用于保持登录态。
        headless: 是否无头模式运行，默认 False（方便调试和观察）。
        user_data_dir: 可选的用户数据目录，用于持久化浏览器状态。
    """

    def __init__(
        self,
        cookie_path: str | Path,
        headless: bool = False,
        user_data_dir: str | Path | None = None,
    ):
        self.cookie_path = Path(cookie_path)
        self.headless = headless
        self.user_data_dir = Path(user_data_dir) if user_data_dir else None

        self._playwright: Any | None = None
        self._browser: Browser | None = None
        self._context: BrowserContext | None = None
        self._page: Page | None = None
        self._initialized: bool = False

    # ------------------------------------------------------------------
    # 浏览器生命周期
    # ------------------------------------------------------------------

    async def _init_browser(self) -> None:
        """启动 Chromium 浏览器，配置反检测参数。

        优先使用持久化上下文（persistent context），浏览器状态（Cookie、
        localStorage、缓存等）自动保存在磁盘上，比手动管理 Cookie 文件更可靠。
        """
        logger.info("正在启动 Chromium 浏览器...")

        self._playwright = await async_playwright().start()

        # 持久化用户数据目录（推荐，自动保存所有浏览器状态）
        persistent_dir = self.user_data_dir
        if persistent_dir is None:
            persistent_dir = Path("data/browser_data")
        persistent_dir.mkdir(parents=True, exist_ok=True)

        launch_kwargs: dict[str, Any] = {
            "headless": self.headless,
            "args": _ANTI_DETECT_ARGS,
        }

        # 使用持久化上下文：自动保存 Cookie + localStorage + 缓存
        logger.info("使用持久化用户数据目录: {}", persistent_dir)
        self._context = await self._playwright.chromium.launch_persistent_context(
            user_data_dir=str(persistent_dir),
            **launch_kwargs,
            viewport={"width": 1920, "height": 1080},
            user_agent=_DEFAULT_UA,
            locale="zh-CN",
            timezone_id="Asia/Shanghai",
            permissions=[],
        )

        # 注入反检测脚本
        await self._context.add_init_script(_ANTI_DETECT_SCRIPT)

        # 兼容性：同时加载 Cookie 文件（如果存在）
        await self._load_cookies()

        # 持久化上下文通常已有页面，如果没有则新建
        pages = self._context.pages
        if pages:
            self._page = pages[0]
        else:
            self._page = await self._context.new_page()

        self._initialized = True
        logger.info("浏览器启动完成，viewport=1920x1080")

    async def close(self) -> None:
        """关闭浏览器并清理资源。"""
        logger.info("正在关闭浏览器...")

        if self._page:
            try:
                await self._page.close()
            except Exception as e:
                logger.warning("关闭页面时出错: {}", e)
            self._page = None

        # 持久化上下文：关闭 context 即可，数据已自动保存到磁盘
        if self._context:
            try:
                await self._context.close()
            except Exception as e:
                logger.warning("关闭上下文时出错: {}", e)
            self._context = None

        if self._playwright:
            try:
                await self._playwright.stop()
            except Exception as e:
                logger.warning("停止 Playwright 时出错: {}", e)
            self._playwright = None

        self._initialized = False
        logger.info("浏览器已关闭")

    # ------------------------------------------------------------------
    # Cookie 管理
    # ------------------------------------------------------------------

    async def _load_cookies(self) -> None:
        """从 JSON 文件加载 Cookie 到浏览器上下文。"""
        if not self.cookie_path.exists():
            logger.warning("Cookie 文件不存在: {}", self.cookie_path)
            return

        try:
            raw = self.cookie_path.read_text(encoding="utf-8")
            cookies = json.loads(raw)

            # 支持两种格式：直接数组 或 {"cookies": [...]}
            if isinstance(cookies, dict) and "cookies" in cookies:
                cookies = cookies["cookies"]

            if not isinstance(cookies, list):
                logger.warning("Cookie 文件格式不正确，应为数组")
                return

            # 确保每个 cookie 都有必要的字段
            valid_cookies = []
            for c in cookies:
                if isinstance(c, dict) and "name" in c and "value" in c:
                    # 补充缺失的字段
                    cookie_item = {
                        "name": c["name"],
                        "value": c["value"],
                        "domain": c.get("domain", ".kimi.com"),
                        "path": c.get("path", "/"),
                        "expires": c.get("expires", -1),
                        "httpOnly": c.get("httpOnly", False),
                        "secure": c.get("secure", True),
                        "sameSite": c.get("sameSite", "Lax"),
                    }
                    valid_cookies.append(cookie_item)

            if valid_cookies and self._context:
                await self._context.add_cookies(valid_cookies)
                logger.info("已加载 {} 个 Cookie", len(valid_cookies))
            else:
                logger.warning("没有有效的 Cookie 可加载")

        except json.JSONDecodeError as e:
            logger.error("Cookie 文件 JSON 解析失败: {}", e)
        except Exception as e:
            logger.error("加载 Cookie 时出错: {}", e)

    async def _save_cookies(self) -> None:
        """保存当前浏览器上下文的 Cookie 到文件。"""
        if not self._context:
            logger.warning("浏览器上下文未初始化，无法保存 Cookie")
            return

        try:
            cookies = await self._context.cookies()
            self.cookie_path.parent.mkdir(parents=True, exist_ok=True)
            self.cookie_path.write_text(
                json.dumps(cookies, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
            logger.info("已保存 {} 个 Cookie 到 {}", len(cookies), self.cookie_path)
        except Exception as e:
            logger.error("保存 Cookie 时出错: {}", e)

    # ------------------------------------------------------------------
    # 登录态检查
    # ------------------------------------------------------------------

    async def _ensure_login(self) -> bool:
        """检查当前是否处于登录态。

        Returns:
            True 表示已登录，False 表示未登录或 Cookie 已失效。
        """
        if not self._page:
            logger.error("页面未初始化")
            return False

        try:
            # 访问 Kimi 首页并检查是否有登录相关的 UI 元素
            await self._page.goto(_KIMI_AGENT_URL, wait_until="domcontentloaded", timeout=30000)
            # sameSite=Strict 的 Cookie 在 goto 导航时不会被发送，需要刷新一次
            await self._page.reload(wait_until="domcontentloaded", timeout=30000)
            await asyncio.sleep(2)  # 等待页面 JS 执行

            # 检查是否存在登录按钮或登录提示
            login_indicators = [
                "text=登录",
                "text=注册",
                "text=手机号登录",
                "text=微信登录",
                "[data-testid='login-button']",
                ".login-btn",
            ]

            for selector in login_indicators:
                try:
                    element = await self._page.query_selector(selector)
                    if element and await element.is_visible():
                        logger.warning("检测到登录按钮，Cookie 可能已失效: {}", selector)
                        return False
                except Exception:
                    continue

            # 检查是否有用户头像或用户名显示（登录态标志）
            user_indicators = [
                "[data-testid='user-avatar']",
                ".user-avatar",
                "img[alt*='头像']",
                "text=我的",
            ]

            for selector in user_indicators:
                try:
                    element = await self._page.query_selector(selector)
                    if element and await element.is_visible():
                        logger.info("检测到用户头像，登录态有效")
                        return True
                except Exception:
                    continue

            # 兜底：检查 URL 是否被重定向到登录页
            current_url = self._page.url
            if "login" in current_url.lower() or "auth" in current_url.lower():
                logger.warning("页面被重定向到登录页: {}", current_url)
                return False

            # 如果既没有登录按钮也没有用户头像，假设已登录（Kimi 的 DOM 可能变化）
            logger.info("未检测到明确的登录/未登录标志，假设登录态有效")
            return True

        except Exception as e:
            logger.error("检查登录态时出错: {}", e)
            return False

    # ------------------------------------------------------------------
    # 核心交互：发送 Prompt
    # ------------------------------------------------------------------

    async def send_prompt(
        self,
        prompt: str,
        timeout: int = 1200,
        agent_mode: bool = False,
        fixed_wait_sec: int = 0,
    ) -> str:
        """发送 Prompt 到 Kimi 并等待完整回复。

        流程：
            1. 访问 Kimi Agent 页面
            2. 定位输入框并输入 Prompt
            3. 点击发送按钮
            4. 轮询检测生成完成（每 5 秒检测一次 DOM）
            5. 完成标志：出现"重新生成"按钮 或 内容 30 秒无变化
            6. 抓取完整回复文本

        Args:
            prompt: 要发送的完整 Prompt 文本。
            timeout: 最大等待时间（秒），默认 1200（20 分钟）。

        Returns:
            Kimi Agent 生成的完整回复文本（Markdown 格式）。

        Raises:
            KimiLoginError: 登录态失效。
            KimiTimeoutError: 超过最大等待时间仍未完成。
            KimiFormatError: 无法从页面提取回复内容。
        """
        if not self._initialized:
            await self._init_browser()

        if not self._page:
            raise RuntimeError("浏览器页面未初始化")

        # 检查登录态
        is_logged_in = await self._ensure_login()
        if not is_logged_in:
            raise KimiLoginError("Kimi 登录态已失效，请重新获取 Cookie")

        page = self._page
        start_time = time.monotonic()

        logger.info("准备发送 Prompt，长度={} 字符", len(prompt))

        # 根据参数决定是否启用 Agent 模式
        if agent_mode:
            await self._ensure_agent_mode(page)
        else:
            logger.info("使用普通模式（非 Agent），直接生成 Markdown 回复")

        # 定位输入框
        input_box = await self._find_input_box(page)
        if not input_box:
            raise KimiFormatError("无法定位到输入框，页面结构可能已变更")

        # 清空并输入 Prompt
        await input_box.click()
        await input_box.fill("")  # 先清空
        await input_box.fill(prompt)
        logger.debug("Prompt 已输入到输入框")

        # 点击发送按钮
        send_btn = await self._find_send_button(page)
        if not send_btn:
            # 尝试直接按 Enter 发送
            await input_box.press("Enter")
            logger.debug("通过 Enter 键发送")
        else:
            await send_btn.click()
            logger.debug("通过发送按钮点击发送")

        logger.info("已发送 Prompt，开始等待回复生成...")

        last_content = ""

        if fixed_wait_sec > 0:
            # 固定等待模式：发送后直接等待指定时间，让 Kimi 完全生成并稳定
            logger.info(
                "使用固定等待模式：发送后等待 {} 秒（约 {:.0f} 分钟）...",
                fixed_wait_sec,
                fixed_wait_sec / 60,
            )
            await asyncio.sleep(fixed_wait_sec)
            last_content = await self._extract_response(page, prompt)
            total_elapsed = time.monotonic() - start_time
            logger.info(
                "固定等待结束，已用时={:.1f}s，提取内容长度={}",
                total_elapsed,
                len(last_content),
            )
        else:
            # 轮询检测模式（默认）
            last_change_time = time.monotonic()
            check_interval = 5.0  # 每 5 秒检测一次
            stable_threshold = 60.0  # 内容 60 秒无变化视为完成（Kimi 生成文件较慢）

            while True:
                await asyncio.sleep(check_interval)
                elapsed = time.monotonic() - start_time

                if elapsed > timeout:
                    await self._save_cookies()
                    raise KimiTimeoutError(
                        f"等待 Kimi 回复超时（{timeout}秒）",
                        elapsed=elapsed,
                    )

                # 尝试提取当前回复内容（传入 prompt 用于排除用户消息）
                current_content = await self._extract_response(page, prompt)

                if current_content:
                    if current_content != last_content:
                        last_content = current_content
                        last_change_time = time.monotonic()
                        logger.debug(
                            "内容已更新，当前长度={}，已用时={:.1f}s",
                            len(current_content),
                            elapsed,
                        )
                    else:
                        # 内容未变化，检查是否超过稳定阈值
                        stable_time = time.monotonic() - last_change_time
                        if stable_time >= stable_threshold:
                            logger.info(
                                "内容已稳定 {} 秒，判定生成完成，总长度={}",
                                stable_time,
                                len(current_content),
                            )
                            break

                # 检查是否出现"重新生成"按钮（明确的完成标志）
                if await self._check_regenerate_button(page):
                    logger.info("检测到'重新生成'按钮，判定生成完成")
                    # 再提取一次确保拿到完整内容
                    final_content = await self._extract_response(page, prompt)
                    if final_content:
                        last_content = final_content
                    break

            total_elapsed = time.monotonic() - start_time
        logger.info(
            "Kimi 回复生成完成，总用时={:.1f}s，内容长度={}",
            total_elapsed,
            len(last_content),
        )

        # 保存最新的 Cookie
        await self._save_cookies()

        return last_content

    # ------------------------------------------------------------------
    # DOM 辅助方法
    # ------------------------------------------------------------------

    async def _ensure_agent_mode(self, page: Page) -> None:
        """确保页面处于 K2.6 Agent 模式（非 Agent 集群）。

        登录后页面结构（已登录态）：
            - 输入框左下方："Agent" 蓝色按钮（纯文本，不含"集群"）
            - 输入框右下方："K2.6 Agent ▼" 下拉选择器
            - 下拉菜单中有"K2.6 Agent"和"K2.6 Agent 集群"两个选项
            - 目标：确保选中"K2.6 Agent"（红框所示）

        未登录/旧版页面结构可能显示"Agent 集群"，兜底兼容。
        """
        # ------------------------------------------------------------------
        # 步骤1：先检查当前是否已经是 K2.6 Agent 模式
        # ------------------------------------------------------------------
        try:
            already_agent = await page.evaluate("""
                () => {
                    const all = document.querySelectorAll('div, span, button');
                    for (const el of all) {
                        const text = el.innerText?.trim() || '';
                        if (text === 'K2.6 Agent' && el.offsetParent !== null) {
                            const rect = el.getBoundingClientRect();
                            if (rect.left > window.innerWidth * 0.6 && rect.top > window.innerHeight * 0.5) {
                                return true;
                            }
                        }
                    }
                    return false;
                }
            """)
            if already_agent:
                logger.debug("当前已是 K2.6 Agent 模式，无需切换")
                return
        except Exception:
            pass

        # ------------------------------------------------------------------
        # 步骤2：展开右下方下拉菜单并选择"K2.6 Agent"（不含"集群"）
        # ------------------------------------------------------------------
        try:
            # 2a. 点击下拉触发器（位于输入框右下方、包含 Agent 文本的元素）
            dropdown_clicked = await page.evaluate("""
                () => {
                    const inputBox = document.querySelector("div[contenteditable='true']");
                    const inputRect = inputBox ? inputBox.getBoundingClientRect() : null;
                    const all = document.querySelectorAll('div, span, button');
                    for (const el of all) {
                        const text = el.innerText?.trim() || '';
                        const rect = el.getBoundingClientRect();
                        // 位于页面右侧（>60%宽度）且包含 Agent 相关文本
                        if ((text.includes('K2.6 Agent') || text.includes('Agent 集群'))
                            && rect.left > window.innerWidth * 0.6
                            && rect.top > window.innerHeight * 0.5
                            && el.offsetParent !== null) {
                            el.click();
                            return text;
                        }
                    }
                    return null;
                }
            """)
            if dropdown_clicked:
                logger.info("已展开 Agent 模式下拉菜单: '{}'", dropdown_clicked)
                await asyncio.sleep(1)

                # 2b. 在下拉菜单中点击"K2.6 Agent"（精确匹配，排除"集群"）
                selected = await page.evaluate("""
                    () => {
                        const all = document.querySelectorAll('div, span, li, button, [role="menuitem"]');
                        for (const el of all) {
                            const text = el.innerText?.trim() || '';
                            // 精确匹配"K2.6 Agent"（不是"K2.6 Agent 集群"）
                            if (text === 'K2.6 Agent' && el.offsetParent !== null) {
                                el.click();
                                return text;
                            }
                        }
                        return null;
                    }
                """)
                if selected:
                    logger.info("已选择 K2.6 Agent 模式")
                    await asyncio.sleep(1)
                    return
                else:
                    logger.warning("展开下拉菜单后未找到'K2.6 Agent'选项，可能已选中或页面结构变化")
        except Exception:
            pass

        # ------------------------------------------------------------------
        # 步骤3：点击左下角"Agent"按钮（纯文本，不含"集群"）
        # ------------------------------------------------------------------
        try:
            clicked = await page.evaluate("""
                () => {
                    const inputBox = document.querySelector("div[contenteditable='true']");
                    if (!inputBox) return null;
                    const inputRect = inputBox.getBoundingClientRect();
                    const all = document.querySelectorAll('button, div[role="button"], span[role="button"], div');
                    for (const el of all) {
                        const text = el.innerText?.trim() || '';
                        const rect = el.getBoundingClientRect();
                        // 匹配纯"Agent"（不含"集群"）且位于输入框下方左侧区域
                        if (text === 'Agent'
                            && rect.left > 300 && rect.left < window.innerWidth * 0.5
                            && rect.top > inputRect.bottom - 20
                            && rect.top < inputRect.bottom + 120
                            && rect.width > 40 && rect.height > 20
                            && el.offsetParent !== null) {
                            el.click();
                            return text;
                        }
                    }
                    return null;
                }
            """)
            if clicked:
                logger.info("已点击左下角 Agent 按钮: '{}'", clicked)
                await asyncio.sleep(1)
                return
        except Exception:
            pass

        # ------------------------------------------------------------------
        # 步骤4：通过精确 XPath 点击（兼容未登录时的旧版界面）
        # ------------------------------------------------------------------
        try:
            clicked = await page.evaluate(f"""
                () => {{
                    const el = document.evaluate(
                        "{_AGENT_BUTTON_XPATH}",
                        document,
                        null,
                        XPathResult.FIRST_ORDERED_NODE_TYPE,
                        null
                    ).singleNodeValue;
                    if (el && el.offsetParent !== null) {{
                        el.click();
                        return el.innerText?.trim() || 'Agent按钮(XPath)';
                    }}
                    return null;
                }}
            """)
            if clicked:
                logger.info("已通过 XPath 点击 Agent 按钮: '{}'", clicked)
                await asyncio.sleep(1)
                return
        except Exception:
            pass

        # ------------------------------------------------------------------
        # 步骤5：兜底——JS 遍历查找输入框下方任何包含"Agent"的可见元素
        # ------------------------------------------------------------------
        try:
            clicked = await page.evaluate("""
                () => {
                    const inputBox = document.querySelector("div[contenteditable='true']");
                    if (!inputBox) return null;
                    const inputRect = inputBox.getBoundingClientRect();
                    const all = document.querySelectorAll('button, div[role="button"], span[role="button"], div');
                    for (const el of all) {
                        const text = el.innerText?.trim() || '';
                        const rect = el.getBoundingClientRect();
                        if (text.includes('Agent')
                            && rect.left > 300
                            && rect.top > inputRect.bottom - 20
                            && rect.top < inputRect.bottom + 120
                            && rect.width > 40 && rect.height > 20
                            && el.offsetParent !== null) {
                            el.click();
                            return text;
                        }
                    }
                    return null;
                }
            """)
            if clicked:
                logger.info("已通过兜底 JS 点击 Agent 按钮: '{}'", clicked)
                await asyncio.sleep(1)
                return
        except Exception:
            pass

        # ------------------------------------------------------------------
        # 步骤6：Playwright 选择器最终兜底
        # ------------------------------------------------------------------
        agent_selectors = [
            "button:has-text('Agent')",
            "div:has-text('Agent')",
            "span:has-text('Agent')",
            "[data-testid='agent-mode-button']",
            ".agent-mode-btn",
        ]
        for selector in agent_selectors:
            try:
                elements = await page.query_selector_all(selector)
                for el in elements:
                    text = await el.inner_text()
                    if "Agent" in text and await el.is_visible():
                        box = await el.bounding_box()
                        if box and box["x"] > 300:
                            await el.click()
                            logger.info("已通过选择器点击 Agent 按钮: '{}'", text.strip())
                            await asyncio.sleep(1)
                            return
            except Exception:
                continue

        logger.debug("未找到 Agent 模式按钮，可能已默认处于 Agent 模式")

    async def _find_input_box(self, page: Page) -> Any:
        """定位聊天输入框。"""
        selectors = [
            "div[contenteditable='true']",
            "textarea[placeholder*='输入']",
            "textarea[placeholder*='发送']",
            "textarea[placeholder*='问题']",
            ".chat-input textarea",
            "[data-testid='chat-input']",
            "textarea",
        ]

        for selector in selectors:
            try:
                element = await page.query_selector(selector)
                if element and await element.is_visible():
                    logger.debug("找到输入框: {}", selector)
                    return element
            except Exception:
                continue

        logger.warning("未能找到输入框")
        return None

    async def _find_send_button(self, page: Page) -> Any:
        """定位发送按钮。"""
        selectors = [
            "div[class*='send']",
            "button[type='submit']",
            ".send-btn",
            "[data-testid='send-button']",
            "button:has-text('发送')",
            "button:has(svg)",
            "button[class*='send']",
        ]

        for selector in selectors:
            try:
                element = await page.query_selector(selector)
                if element and await element.is_visible() and await element.is_enabled():
                    logger.debug("找到发送按钮: {}", selector)
                    return element
            except Exception:
                continue

        logger.warning("未能找到发送按钮，将使用 Enter 键发送")
        return None

    async def _check_regenerate_button(self, page: Page) -> bool:
        """检查页面上是否存在"重新生成"按钮。"""
        selectors = [
            "button:has-text('重新生成')",
            ".regenerate-btn",
            "[data-testid='regenerate-button']",
            "div:has-text('重新生成')",
            "button:has-text('Regenerate')",
            "span:has-text('重新生成')",
        ]

        for selector in selectors:
            try:
                element = await page.query_selector(selector)
                if element and await element.is_visible():
                    return True
            except Exception:
                continue

        return False

    async def _extract_response(self, page: Page, exclude_text: str = "") -> str:
        """从页面提取最后一条助手回复的文本内容。

        页面布局（基于截图观察）：
            - 左侧边栏：历史会话列表（宽度约 260px）
            - 中间消息区：助手 Markdown 回复（x 约 260–800）
            - 右侧 Computer 面板：搜索/工具结果（x > 800）
            - 底部：输入框区域

        提取策略：
            1. 坐标过滤：只扫描中间消息区（排除右侧 Computer 面板）
            2. 质量分：优先选择包含晨报关键词的文本块
            3. 兜底：全局最长文本
        """
        # 策略1：坐标过滤 + 质量分（只取中间消息区，排除右侧 Computer 面板）
        try:
            result = await page.evaluate(
                """
                (exclude) => {
                    const elements = document.querySelectorAll('div, article, section');
                    const candidates = [];
                    const w = window.innerWidth;
                    const h = window.innerHeight;

                    for (const el of elements) {
                        const rect = el.getBoundingClientRect();
                        const text = el.innerText?.trim() || '';

                        // 基础过滤
                        if (rect.width < 150 || rect.height < 60) continue;
                        if (text.length < 200 || text.length > 50000) continue;
                        if (el.offsetParent === null) continue;

                        // 坐标过滤：中间消息区（排除左侧边栏和右侧 Computer 面板）
                        // 左侧边栏约 260px，右侧 Computer 面板约从 1000px 开始（1920宽屏幕）
                        if (rect.left < 260 || rect.left > 1000) continue;
                        if (rect.top < 80 || rect.top > h - 200) continue;

                        // 排除用户自己的 prompt 内容
                        if (exclude && exclude.length > 5 && text.includes(exclude.substring(0, 50))) continue;

                        // 计算质量分
                        let score = text.length;

                        // 极加分项：包含晨报关键词
                        if (text.includes('晨报')) score += 10000;
                        if (text.includes('仓位建议')) score += 8000;
                        if (text.includes('情绪评级')) score += 8000;
                        if (text.includes('免责声明')) score += 5000;
                        if (text.includes('具体操作')) score += 3000;

                        // 强排除：Computer 面板和思考过程（即使坐标过滤了，双重保险）
                        if (text.includes("Kimi's Computer")) continue;
                        if (text.includes("iPython")) continue;
                        if (text.includes("网页搜索")) continue;

                        // 排除 Kimi 思考过程关键词
                        const thinkingKeywords = [
                            "用户要求我", "让我开始", "让我仔细看看", "让我重新理解", "让我再想想",
                            "让我确认", "让我完善", "让我输出", "让我检查", "让我生成",
                            "我需要", "我应该", "我可以", "我会", "我将",
                            "思考已完成", "检查当前待办事项", "分析用户提供的数据",
                        ];
                        let isThinking = false;
                        for (const kw of thinkingKeywords) {
                            if (text.includes(kw)) { isThinking = true; break; }
                        }
                        if (isThinking) continue;

                        candidates.push({text, score});
                    }
                    candidates.sort((a, b) => b.score - a.score);
                    return candidates[0]?.text || '';
                }
                """,
                exclude_text,
            )
            if result and len(result.strip()) > 100:
                return result.strip()
        except Exception:
            pass

        # 策略2：点击复制按钮获取内容（最可靠，但需要页面上有复制按钮）
        try:
            copied = await page.evaluate(
                """
                async () => {
                    // 找所有消息气泡
                    const allDivs = document.querySelectorAll('div');
                    let lastMsg = null;
                    for (const el of allDivs) {
                        const rect = el.getBoundingClientRect();
                        if (rect.left > 260 && rect.left < 800 && rect.top > 80 && rect.width > 300) {
                            lastMsg = el;
                        }
                    }
                    if (!lastMsg) return '';

                    // 找复制按钮（通常是 svg 或包含复制图标的按钮）
                    const btns = lastMsg.querySelectorAll('button, div[role="button"], svg, [class*="copy"]');
                    for (const btn of btns) {
                        const rect = btn.getBoundingClientRect();
                        // 复制按钮通常在消息底部
                        if (rect.y > window.innerHeight * 0.75 && rect.width > 20 && rect.height > 20) {
                            btn.click();
                            return 'clicked';
                        }
                    }
                    return '';
                }
                """
            )
            if copied == 'clicked':
                await asyncio.sleep(0.5)
                # 尝试读取剪贴板
                clipboard_text = await page.evaluate(
                    "async () => { try { return await navigator.clipboard.readText(); } catch(e) { return ''; } }"
                )
                if clipboard_text and len(clipboard_text.strip()) > 200:
                    return clipboard_text.strip()
        except Exception:
            pass

        # 策略3：兜底——全局最长可见文本块
        try:
            result = await page.evaluate(
                """
                (exclude) => {
                    const elements = document.querySelectorAll('div, article, section, main');
                    const results = [];
                    for (const el of elements) {
                        const text = el.innerText?.trim() || '';
                        if (text.length > 200 && text.length < 50000 && el.offsetParent !== null) {
                            if (exclude && exclude.length > 5 && text.includes(exclude.substring(0, 50))) continue;
                            if (text.includes("Kimi's Computer")) continue;
                            results.push(text);
                        }
                    }
                    return results.sort((a, b) => b.length - a.length)[0] || '';
                }
                """,
                exclude_text,
            )
            if result and len(result.strip()) > 100:
                return result.strip()
        except Exception:
            pass

        return ""

    # ------------------------------------------------------------------
    # 晨报生成入口
    # ------------------------------------------------------------------

    async def generate_report(
        self,
        input_data: dict[str, Any],
        fixed_wait_sec: int = 0,
    ) -> dict[str, Any]:
        """完整的晨报生成入口。

        接收结构化数据，组装超级 Prompt，调用 Kimi Agent 生成晨报，
        返回结构化的结果字典。

        Args:
            input_data: 包含以下字段的字典：
                - portfolio: 用户持仓信息
                - market_snapshot: 全球市场快照
                - holdings_news: 持仓个股新闻
                - date_str: 日期字符串（可选，默认今天）
                - extra_context: 额外上下文（可选）

        Returns:
            结构化字典：
                {
                    "success": bool,
                    "markdown": str,      # 生成的晨报 Markdown
                    "sentiment": str,     # 情绪判断（bullish/bearish/neutral）
                    "raw_length": int,    # 原始文本长度
                    "elapsed_sec": float, # 耗时（秒）
                    "error": str | None,  # 错误信息（如果失败）
                }
        """
        from .kimi_report_prompt import build_kimi_prompt

        start_time = time.monotonic()
        result: dict[str, Any] = {
            "success": False,
            "markdown": "",
            "sentiment": "neutral",
            "raw_length": 0,
            "elapsed_sec": 0.0,
            "error": None,
        }

        try:
            date_str = input_data.get("date_str", time.strftime("%Y-%m-%d"))
            yesterday_str = input_data.get("yesterday_str", "")
            fetch_time = input_data.get("fetch_time", time.strftime("%H:%M"))

            # 组装超级 Prompt（数据已注入）
            full_prompt = build_kimi_prompt({
                "date": date_str,
                "yesterday": yesterday_str,
                "market_snapshot": input_data.get("market_snapshot", {}),
                "portfolio": input_data.get("portfolio", {}),
                "holdings_news": input_data.get("holdings_news", {}),
                "fetch_time": fetch_time,
            })

            logger.info(
                "开始生成晨报，日期={}，Prompt长度={}",
                date_str,
                len(full_prompt),
            )

            # 调用 Kimi Agent（支持固定等待模式，让思考过程完全结束后再提取）
            markdown = await self.send_prompt(
                full_prompt, timeout=1200, fixed_wait_sec=fixed_wait_sec
            )

            if not markdown:
                raise KimiFormatError("Kimi 返回了空内容")

            # 解析情绪倾向
            sentiment = self._detect_sentiment(markdown)

            elapsed = time.monotonic() - start_time

            result.update({
                "success": True,
                "markdown": markdown,
                "sentiment": sentiment,
                "raw_length": len(markdown),
                "elapsed_sec": round(elapsed, 2),
            })

            logger.info(
                "晨报生成成功，长度={}，情绪={}，耗时={:.1f}s",
                len(markdown),
                sentiment,
                elapsed,
            )

        except KimiLoginError as e:
            result["error"] = f"登录失败: {e}"
            logger.error("晨报生成失败 - 登录错误: {}", e)

        except KimiTimeoutError as e:
            result["error"] = f"超时: {e}"
            result["elapsed_sec"] = round(e.elapsed, 2)
            logger.error("晨报生成失败 - 超时: {}", e)

        except KimiFormatError as e:
            result["error"] = f"格式错误: {e}"
            logger.error("晨报生成失败 - 格式错误: {}", e)

        except Exception as e:
            result["error"] = f"未知错误: {e}"
            logger.exception("晨报生成过程中发生未知错误")

        finally:
            if result["elapsed_sec"] == 0.0:
                result["elapsed_sec"] = round(time.monotonic() - start_time, 2)

        return result

    @staticmethod
    def _detect_sentiment(text: str) -> str:
        """从晨报文本中检测整体情绪倾向。

        通过关键词匹配判断情绪：
            - bullish: 积极、看涨、买入、加仓、突破等
            - bearish: 消极、看跌、卖出、减仓、下跌等
            - neutral: 无明显倾向
        """
        text_lower = text.lower()

        bullish_keywords = [
            "积极", "乐观", "看涨", "买入", "加仓", "突破", "上涨",
            "反弹", "利好", "强势", "机会", "看多", "推荐",
        ]
        bearish_keywords = [
            "消极", "悲观", "看跌", "卖出", "减仓", "下跌", "回调",
            "利空", "弱势", "风险", "谨慎", "看空", "回避",
        ]

        bullish_score = sum(1 for kw in bullish_keywords if kw in text_lower)
        bearish_score = sum(1 for kw in bearish_keywords if kw in text_lower)

        if bullish_score > bearish_score * 1.5:
            return "bullish"
        elif bearish_score > bullish_score * 1.5:
            return "bearish"
        else:
            return "neutral"

    # ------------------------------------------------------------------
    # 上下文管理器支持
    # ------------------------------------------------------------------

    async def __aenter__(self) -> KimiAgentBrowser:
        await self._init_browser()
        return self

    async def __aexit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        await self.close()


# ---------------------------------------------------------------------------
# 便捷函数
# ---------------------------------------------------------------------------

async def generate_morning_report_with_kimi(
    input_data: dict[str, Any],
    cookie_path: str | Path,
    headless: bool = False,
) -> dict[str, Any]:
    """使用 Kimi Agent 浏览器生成晨报的便捷函数。

    Args:
        input_data: 晨报所需的数据字典。
        cookie_path: Cookie JSON 文件路径。
        headless: 是否无头模式运行。

    Returns:
        结构化结果字典，同 KimiAgentBrowser.generate_report。
    """
    browser = KimiAgentBrowser(cookie_path=cookie_path, headless=headless)
    try:
        result = await browser.generate_report(input_data)
        return result
    finally:
        await browser.close()

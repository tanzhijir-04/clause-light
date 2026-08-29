"""快速 E2E 测试 — 跳过耗时的上传分析"""

import os
import sys
import time
import subprocess

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from playwright.sync_api import sync_playwright

BASE_URL = "http://127.0.0.1:8000"
SCREENSHOT_DIR = "tests/screenshots/quick"
results = {"pass": 0, "fail": 0}


def screenshot(page, name):
    page.screenshot(path=f"{SCREENSHOT_DIR}/{name}.png")


def log_test(name, status, detail=""):
    if status == "pass":
        results["pass"] += 1
        print(f"  [PASS] {name}")
    else:
        results["fail"] += 1
        print(f"  [FAIL] {name} - {detail}")


def main():
    os.makedirs(SCREENSHOT_DIR, exist_ok=True)

    print("=" * 60)
    print("ClauseLight 快速功能测试")
    print("=" * 60)

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False)
        context = browser.new_context(viewport={"width": 1400, "height": 900})
        page = context.new_page()

        # 1. 仪表盘
        print("\n[1/7] 仪表盘")
        page.goto(BASE_URL)
        page.wait_for_load_state("networkidle")
        page.wait_for_timeout(1000)
        screenshot(page, "01_dashboard")
        title = page.locator(".content-title")
        log_test("仪表盘标题", "pass" if title.count() > 0 and "仪表盘" in title.first.text_content() else "fail")

        # 2. 合同列表
        print("\n[2/7] 合同列表")
        page.click('text=合同管理')
        page.wait_for_timeout(1500)
        screenshot(page, "02_contracts")
        rows = page.locator("table tbody tr")
        log_test("合同表格", "pass" if rows.count() > 0 else "fail", f"{rows.count()}行")

        # 3. 合同详情
        print("\n[3/7] 合同详情")
        if rows.count() > 0:
            rows.first.click()
            page.wait_for_timeout(1500)
            screenshot(page, "03_detail")
            score = page.locator(".score-green, .score-yellow, .score-red")
            log_test("评分显示", "pass" if score.count() > 0 else "fail")

        # 4. 原文标注
        print("\n[4/7] 原文标注")
        annotated_tab = page.locator("text=原文标注")
        if annotated_tab.count() > 0:
            is_disabled = annotated_tab.evaluate('el => el.style.pointerEvents === "none"')
            if not is_disabled:
                annotated_tab.click()
                page.wait_for_timeout(1000)
                screenshot(page, "04_annotated")
                marks = page.locator(".clause-mark")
                log_test("原文标注", "pass" if marks.count() > 0 else "fail", f"{marks.count()}个高亮")
                unknown_marks = page.locator(".clause-mark.unknown")
                if unknown_marks.count() > 0:
                    log_test("unknown 不显示为绿色", "pass" if page.locator(".clause-mark.unknown.green").count() == 0 else "fail")
                source_links = page.locator(".legal-citation a")
                if source_links.count() > 0:
                    log_test("法条来源链接", "pass" if all(source_links.nth(i).get_attribute("href") for i in range(source_links.count())) else "fail")

                # 点击高亮
                if marks.count() > 0:
                    page.evaluate('document.querySelector(".clause-mark").click()')
                    page.wait_for_timeout(500)
                    screenshot(page, "05_panel")
                    panel = page.locator("#annotation-panel")
                    log_test("批注面板", "pass" if not panel.evaluate('el => el.classList.contains("collapsed")') else "fail")
            else:
                log_test("原文标注", "pass", "标签禁用（预期）")

        # 5. 条款列表
        print("\n[5/7] 条款列表")
        list_tab = page.locator("text=条款列表")
        if list_tab.count() > 0:
            list_tab.click()
            page.wait_for_timeout(500)
            screenshot(page, "06_clause_list")
            items = page.locator(".clause-item")
            log_test("条款列表", "pass" if items.count() > 0 else "fail", f"{items.count()}个条款")

        # 6. 知识库
        print("\n[6/7] 知识库")
        page.click('text=知识库')
        page.wait_for_timeout(2000)
        screenshot(page, "07_knowledge")
        title = page.locator(".content-title")
        log_test("知识库页面", "pass" if title.count() > 0 and "知识库" in title.first.text_content() else "fail")

        tabs = page.locator(".tab")
        log_test("知识库标签", "pass" if tabs.count() >= 4 else "fail", f"{tabs.count()}个标签")

        # 7. 其他页面
        print("\n[7/7] 其他页面")
        for name, text in [("同步管理", "同步"), ("模型管理", "模型"), ("设置", "设置")]:
            page.click(f'text={name}')
            page.wait_for_timeout(1500)
            screenshot(page, f"08_{name}")
            title = page.locator(".content-title")
            log_test(name, "pass" if title.count() > 0 and text in title.first.text_content() else "fail")

        browser.close()

    print("\n" + "=" * 60)
    print(f"结果: 通过 {results['pass']} / 失败 {results['fail']}")
    print("=" * 60)


if __name__ == "__main__":
    main()

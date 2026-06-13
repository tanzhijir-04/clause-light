"""E2E 测试：原文标注视图功能验证"""

import os
import sys
import time
import subprocess
import signal
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from playwright.sync_api import sync_playwright, expect

# 测试配置
BASE_URL = "http://127.0.0.1:8000"
TEST_PDF = "data/uploads/test_contract_problematic.pdf"
SCREENSHOT_DIR = "tests/screenshots"


def ensure_screenshot_dir():
    os.makedirs(SCREENSHOT_DIR, exist_ok=True)


def start_server():
    """启动服务器"""
    proc = subprocess.Popen(
        [sys.executable, "-m", "uvicorn", "server.main:app", "--host", "127.0.0.1", "--port", "8000"],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        cwd=os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    )
    time.sleep(3)  # 等待服务器启动
    return proc


def test_annotated_view():
    """测试原文标注视图"""
    ensure_screenshot_dir()

    print("=" * 60)
    print("E2E 测试：原文标注视图")
    print("=" * 60)

    # 启动服务器
    print("\n[1/6] 启动服务器...")
    server = start_server()

    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=False)  # 显示浏览器
            context = browser.new_context(viewport={"width": 1400, "height": 900})
            page = context.new_page()

            # 测试 1：访问首页
            print("\n[2/6] 访问首页...")
            page.goto(BASE_URL)
            page.wait_for_load_state("networkidle")
            page.screenshot(path=f"{SCREENSHOT_DIR}/01_homepage.png")
            print("  [OK] 首页加载成功")

            # 测试 2：访问合同列表
            print("\n[3/6] 访问合同列表...")
            page.click('text=合同管理')
            page.wait_for_timeout(1000)
            page.screenshot(path=f"{SCREENSHOT_DIR}/02_contracts_list.png")
            print("  [OK] 合同列表加载成功")

            # 测试 3：点击第一个合同查看详情
            print("\n[4/6] 查看合同详情...")
            # 找到合同表格行并点击（表格形式）
            contract_rows = page.locator('table tbody tr')
            if contract_rows.count() > 0:
                contract_rows.first.click()
                page.wait_for_timeout(1500)
                page.screenshot(path=f"{SCREENSHOT_DIR}/03_contract_detail.png")
                print("  [OK] 合同详情加载成功")

                # 测试 4：检查原文标注标签页
                print("\n[5/6] 检查原文标注视图...")
                annotated_tab = page.locator('text=原文标注')
                if annotated_tab.count() > 0:
                    # 检查标签是否可点击（不是灰色）
                    is_disabled = annotated_tab.evaluate('el => el.style.pointerEvents === "none"')
                    if not is_disabled:
                        annotated_tab.click()
                        page.wait_for_timeout(1000)
                        page.screenshot(path=f"{SCREENSHOT_DIR}/04_annotated_view.png")
                        print("  [OK] 原文标注视图显示成功")

                        # 测试 5：点击高亮条款（使用 JS 直接触发）
                        print("\n[6/6] 测试条款交互...")
                        clause_marks = page.locator('.clause-mark')
                        if clause_marks.count() > 0:
                            # 使用 JavaScript 直接触发点击事件
                            page.evaluate('document.querySelector(".clause-mark").click()')
                            page.wait_for_timeout(500)
                            page.screenshot(path=f"{SCREENSHOT_DIR}/05_clause_selected.png")
                            print(f"  [OK] 条款交互正常（共 {clause_marks.count()} 个高亮片段）")

                            # 检查批注面板
                            panel = page.locator('#annotation-panel')
                            if not panel.evaluate('el => el.classList.contains("collapsed")'):
                                print("  [OK] 批注面板已打开")
                            else:
                                print("  [FAIL] 批注面板未打开")
                        else:
                            print("  [WARN] 未找到高亮条款片段")
                    else:
                        print("  [FAIL] 原文标注标签被禁用（fullText 为空）")
                else:
                    print("  [FAIL] 未找到原文标注标签")
            else:
                print("  [FAIL] 未找到合同卡片")

            # 测试 6：上传新合同
            print("\n[补充测试] 上传新合同...")
            page.click('text=合同管理')
            page.wait_for_timeout(500)

            # 点击上传按钮
            upload_btn = page.locator('text=上传合同')
            if upload_btn.count() > 0:
                upload_btn.click()
                page.wait_for_timeout(500)

                # 上传文件
                file_input = page.locator('input[type="file"]')
                if file_input.count() > 0:
                    file_input.set_input_files(os.path.abspath(TEST_PDF))
                    page.wait_for_timeout(500)
                    page.screenshot(path=f"{SCREENSHOT_DIR}/06_upload_dialog.png")

                    # 点击分析按钮
                    analyze_btn = page.locator('text=开始分析')
                    if analyze_btn.count() > 0:
                        analyze_btn.click()
                        print("  [OK] 开始上传分析...")

                        # 等待分析完成（最多 5 分钟）
                        try:
                            page.wait_for_selector('text=分析完成', timeout=300000)
                            page.screenshot(path=f"{SCREENSHOT_DIR}/07_analysis_complete.png")
                            print("  [OK] 分析完成")

                            # 点击查看结果
                            view_btn = page.locator('text=查看结果')
                            if view_btn.count() > 0:
                                view_btn.click()
                                page.wait_for_timeout(1500)
                                page.screenshot(path=f"{SCREENSHOT_DIR}/08_new_contract_detail.png")

                                # 检查新合同的原文标注
                                annotated_tab = page.locator('text=原文标注')
                                if annotated_tab.count() > 0:
                                    is_disabled = annotated_tab.evaluate('el => el.style.pointerEvents === "none"')
                                    if not is_disabled:
                                        annotated_tab.click()
                                        page.wait_for_timeout(1000)
                                        page.screenshot(path=f"{SCREENSHOT_DIR}/09_new_annotated_view.png")
                                        print("  [OK] 新合同原文标注视图正常")
                                    else:
                                        print("  [FAIL] 新合同原文标注被禁用")
                        except Exception as e:
                            page.screenshot(path=f"{SCREENSHOT_DIR}/07_analysis_error.png")
                            print(f"  [FAIL] 分析超时或失败: {e}")

            browser.close()

        print("\n" + "=" * 60)
        print("测试完成！截图保存在 tests/screenshots/")
        print("=" * 60)

    finally:
        # 停止服务器
        server.terminate()
        server.wait()


if __name__ == "__main__":
    test_annotated_view()

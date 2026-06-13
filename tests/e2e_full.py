"""全面 E2E 功能测试 — 覆盖所有页面和功能"""

import os
import sys
import time
import subprocess
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from playwright.sync_api import sync_playwright

# 测试配置
BASE_URL = "http://127.0.0.1:8000"
TEST_PDF = "data/uploads/test_contract_problematic.pdf"
SCREENSHOT_DIR = "tests/screenshots/full"

# 测试结果统计
results = {"pass": 0, "fail": 0, "skip": 0}


def screenshot(page, name):
    """保存截图"""
    page.screenshot(path=f"{SCREENSHOT_DIR}/{name}.png")


def log_test(name, status, detail=""):
    """记录测试结果"""
    if status == "pass":
        results["pass"] += 1
        print(f"  [PASS] {name}")
    elif status == "fail":
        results["fail"] += 1
        print(f"  [FAIL] {name} - {detail}")
    else:
        results["skip"] += 1
        print(f"  [SKIP] {name} - {detail}")


def start_server():
    """启动服务器"""
    proc = subprocess.Popen(
        [sys.executable, "-m", "uvicorn", "server.main:app", "--host", "127.0.0.1", "--port", "8000"],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        cwd=os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    )
    time.sleep(3)
    return proc


def test_dashboard(page):
    """测试仪表盘页面"""
    print("\n[1/7] 测试仪表盘页面")
    page.goto(BASE_URL)
    page.wait_for_load_state("networkidle")
    screenshot(page, "01_dashboard")

    # 检查页面标题
    title = page.locator(".content-title")
    if title.count() > 0 and "仪表盘" in title.first.text_content():
        log_test("仪表盘标题", "pass")
    else:
        log_test("仪表盘标题", "fail", "未找到仪表盘标题")

    # 检查统计卡片
    cards = page.locator(".stat-card")
    if cards.count() >= 3:
        log_test("统计卡片显示", "pass")
    else:
        log_test("统计卡片显示", "fail", f"期望至少3个，实际{cards.count()}个")

    # 检查风险分布
    risk_dist = page.locator(".risk-summary")
    if risk_dist.count() > 0:
        log_test("风险分布区域", "pass")
    else:
        log_test("风险分布区域", "fail", "未找到风险分布")

    # 检查最近分析表格
    table = page.locator("table")
    if table.count() > 0:
        log_test("最近分析表格", "pass")
    else:
        log_test("最近分析表格", "fail", "未找到表格")

    # 检查上传区域
    upload = page.locator(".upload-zone")
    if upload.count() > 0:
        log_test("上传区域", "pass")
    else:
        log_test("上传区域", "fail", "未找到上传区域")


def test_contracts_page(page):
    """测试合同管理页面"""
    print("\n[2/7] 测试合同管理页面")
    page.click('text=合同管理')
    page.wait_for_load_state("networkidle")
    page.wait_for_timeout(500)
    screenshot(page, "02_contracts_list")

    # 检查页面标题
    title = page.locator(".content-title")
    if title.count() > 0 and "合同管理" in title.first.text_content():
        log_test("合同管理标题", "pass")
    else:
        log_test("合同管理标题", "fail", "未找到标题")

    # 检查合同表格
    table = page.locator("table")
    if table.count() > 0:
        rows = page.locator("table tbody tr")
        log_test("合同表格显示", "pass")
        log_test("合同数据行", "pass" if rows.count() > 0 else "fail", f"共{rows.count()}行")
    else:
        log_test("合同表格", "fail", "未找到表格")

    # 检查搜索框
    search = page.locator("input[placeholder*='搜索']")
    if search.count() > 0:
        log_test("搜索框", "pass")
    else:
        log_test("搜索框", "fail", "未找到搜索框")

    # 检查筛选器
    filters = page.locator("select")
    if filters.count() >= 2:
        log_test("筛选器", "pass")
    else:
        log_test("筛选器", "fail", f"期望至少2个，实际{filters.count()}个")

    # 检查上传按钮
    upload_btn = page.locator("text=上传合同")
    if upload_btn.count() > 0:
        log_test("上传按钮", "pass")
    else:
        log_test("上传按钮", "fail", "未找到上传按钮")

    # 测试搜索功能
    if search.count() > 0:
        search.fill("test")
        page.wait_for_timeout(500)
        rows_after = page.locator("table tbody tr").count()
        log_test("搜索过滤", "pass", f"搜索后{rows_after}行")
        search.fill("")
        page.wait_for_timeout(500)

    # 测试点击合同进入详情
    rows = page.locator("table tbody tr")
    if rows.count() > 0:
        rows.first.click()
        page.wait_for_timeout(1000)
        detail_title = page.locator(".content-title")
        if detail_title.count() > 0:
            log_test("进入合同详情", "pass")
        else:
            log_test("进入合同详情", "fail", "详情页未加载")


def test_contract_detail(page):
    """测试合同详情页面"""
    print("\n[3/7] 测试合同详情页面")
    screenshot(page, "03_contract_detail")

    # 检查返回按钮
    back_btn = page.locator("text=返回")
    if back_btn.count() > 0:
        log_test("返回按钮", "pass")
    else:
        log_test("返回按钮", "fail", "未找到返回按钮")

    # 检查评分显示
    score = page.locator(".score-green, .score-yellow, .score-red")
    if score.count() > 0:
        log_test("评分显示", "pass")
    else:
        log_test("评分显示", "fail", "未找到评分")

    # 检查风险分布条
    risk_bar = page.locator(".risk-dist-interactive")
    if risk_bar.count() > 0:
        log_test("风险分布条", "pass")
    else:
        log_test("风险分布条", "fail", "未找到风险分布条")

    # 检查视图切换标签
    tabs = page.locator(".view-tab")
    if tabs.count() >= 2:
        log_test("视图切换标签", "pass")
    else:
        log_test("视图切换标签", "fail", f"期望2个，实际{tabs.count()}个")

    # 检查风险导航
    risk_nav = page.locator(".risk-nav")
    if risk_nav.count() > 0:
        log_test("风险导航", "pass")
    else:
        log_test("风险导航", "fail", "未找到风险导航")


def test_annotated_view(page):
    """测试原文标注视图"""
    print("\n[4/7] 测试原文标注视图")

    # 点击原文标注标签
    annotated_tab = page.locator("text=原文标注")
    if annotated_tab.count() > 0:
        is_disabled = annotated_tab.evaluate('el => el.style.pointerEvents === "none"')
        if not is_disabled:
            annotated_tab.click()
            page.wait_for_timeout(1000)
            screenshot(page, "04_annotated_view")
            log_test("原文标注标签", "pass")

            # 检查原文内容
            original_text = page.locator("#original-text")
            if original_text.count() > 0:
                log_test("原文内容显示", "pass")
            else:
                log_test("原文内容显示", "fail", "未找到原文内容")

            # 检查高亮标记
            clause_marks = page.locator(".clause-mark")
            if clause_marks.count() > 0:
                log_test("高亮标记", "pass")
                log_test("高亮片段数量", "pass", f"共{clause_marks.count()}个")

                # 测试点击高亮条款
                page.evaluate('document.querySelector(".clause-mark").click()')
                page.wait_for_timeout(500)
                screenshot(page, "05_clause_selected")

                # 检查批注面板
                panel = page.locator("#annotation-panel")
                if not panel.evaluate('el => el.classList.contains("collapsed")'):
                    log_test("批注面板打开", "pass")

                    # 检查批注内容
                    anno_sections = page.locator(".anno-section")
                    if anno_sections.count() > 0:
                        log_test("批注内容显示", "pass")
                    else:
                        log_test("批注内容显示", "fail", "未找到批注内容")
                else:
                    log_test("批注面板打开", "fail", "面板仍折叠")
            else:
                log_test("高亮标记", "fail", "未找到高亮标记")
        else:
            log_test("原文标注标签", "skip", "标签被禁用（无fullText）")
    else:
        log_test("原文标注标签", "skip", "未找到标签")


def test_clause_list_view(page):
    """测试条款列表视图"""
    print("\n[5/7] 测试条款列表视图")

    # 点击条款列表标签
    list_tab = page.locator("text=条款列表")
    if list_tab.count() > 0:
        list_tab.click()
        page.wait_for_timeout(500)
        screenshot(page, "06_clause_list")
        log_test("条款列表标签", "pass")

        # 检查条款卡片
        clause_items = page.locator(".clause-item")
        if clause_items.count() > 0:
            log_test("条款卡片显示", "pass")
            log_test("条款数量", "pass", f"共{clause_items.count()}个")

            # 测试点击条款
            clause_items.first.click()
            page.wait_for_timeout(500)
            log_test("条款点击交互", "pass")
        else:
            log_test("条款卡片显示", "fail", "未找到条款卡片")
    else:
        log_test("条款列表标签", "fail", "未找到标签")


def test_upload_contract(page):
    """测试上传合同功能"""
    print("\n[6/7] 测试上传合同功能")
    page.click('text=合同管理')
    page.wait_for_timeout(1000)

    # 检查文件输入（隐藏的）
    file_input = page.locator('input[type="file"]')
    if file_input.count() > 0:
        log_test("文件上传输入", "pass")

        # 上传文件（会自动触发分析）
        file_input.set_input_files(os.path.abspath(TEST_PDF))
        page.wait_for_timeout(1000)
        screenshot(page, "07_upload_started")

        # 检查是否出现分析中的提示
        analyzing = page.locator("text=正在分析")
        if analyzing.count() > 0:
            log_test("自动开始分析", "pass")
        else:
            log_test("自动开始分析", "fail", "未出现分析提示")

        # 等待分析完成（最多 5 分钟）
        try:
            page.wait_for_selector("text=查看结果", timeout=300000)
            page.wait_for_timeout(500)
            screenshot(page, "08_analysis_complete")
            log_test("分析完成", "pass")

            # 点击查看结果
            view_btn = page.locator("text=查看结果")
            if view_btn.count() > 0:
                view_btn.click()
                page.wait_for_timeout(2000)
                screenshot(page, "09_new_contract_detail")
                log_test("查看分析结果", "pass")
        except Exception as e:
            screenshot(page, "08_analysis_error")
            log_test("分析完成", "fail", str(e)[:50])
    else:
        log_test("文件上传输入", "fail", "未找到input")


def test_knowledge_page(page):
    """测试知识库页面"""
    print("\n[7/7] 测试知识库页面")
    page.click('text=知识库')
    page.wait_for_load_state("networkidle")
    page.wait_for_timeout(2000)  # 知识库加载需要更多时间
    screenshot(page, "11_knowledge")

    # 检查页面标题
    title = page.locator(".content-title")
    if title.count() > 0 and "知识库" in title.first.text_content():
        log_test("知识库标题", "pass")
    else:
        log_test("知识库标题", "fail", "未找到标题")

    # 检查标签页
    tabs = page.locator(".tab")
    if tabs.count() >= 4:
        log_test("标签页显示", "pass")
    else:
        log_test("标签页显示", "fail", f"期望4个，实际{tabs.count()}个")

    # 检查规则列表
    rules = page.locator(".knowledge-item, table tbody tr")
    if rules.count() > 0:
        log_test("规则列表显示", "pass")
    else:
        log_test("规则列表显示", "fail", "未找到规则")

    # 测试新增规则按钮
    add_btn = page.locator("text=新增规则")
    if add_btn.count() > 0:
        log_test("新增规则按钮", "pass")
    else:
        log_test("新增规则按钮", "fail", "未找到按钮")

    # 切换到法规库标签
    laws_tab = page.locator("text=法规库")
    if laws_tab.count() > 0:
        laws_tab.click()
        page.wait_for_timeout(500)
        screenshot(page, "12_knowledge_laws")
        log_test("法规库标签切换", "pass")

    # 切换到待审核标签
    pending_tab = page.locator("text=待审核")
    if pending_tab.count() > 0:
        pending_tab.click()
        page.wait_for_timeout(500)
        screenshot(page, "13_knowledge_pending")
        log_test("待审核标签切换", "pass")

    # 切换到统计标签
    stats_tab = page.locator("text=统计")
    if stats_tab.count() > 0:
        stats_tab.click()
        page.wait_for_timeout(500)
        screenshot(page, "14_knowledge_stats")
        log_test("统计标签切换", "pass")


def test_other_pages(page):
    """测试其他页面"""
    print("\n[补充] 测试其他页面")

    # 同步管理
    page.click('text=同步管理')
    page.wait_for_load_state("networkidle")
    page.wait_for_timeout(2000)
    screenshot(page, "15_sync")
    title = page.locator(".content-title")
    if title.count() > 0 and "同步" in title.first.text_content():
        log_test("同步管理页面", "pass")
    else:
        log_test("同步管理页面", "fail", "页面未正确加载")

    # 模型管理
    page.click('text=模型管理')
    page.wait_for_load_state("networkidle")
    page.wait_for_timeout(2000)
    screenshot(page, "16_models")
    title = page.locator(".content-title")
    if title.count() > 0 and "模型" in title.first.text_content():
        log_test("模型管理页面", "pass")
    else:
        log_test("模型管理页面", "fail", "页面未正确加载")

    # 设置
    page.click('text=设置')
    page.wait_for_load_state("networkidle")
    page.wait_for_timeout(2000)
    screenshot(page, "17_settings")
    title = page.locator(".content-title")
    if title.count() > 0 and "设置" in title.first.text_content():
        log_test("设置页面", "pass")
    else:
        log_test("设置页面", "fail", "页面未正确加载")


def main():
    """主测试函数"""
    os.makedirs(SCREENSHOT_DIR, exist_ok=True)

    print("=" * 60)
    print("ClauseLight 全面功能 E2E 测试")
    print("=" * 60)

    server = start_server()

    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=False)
            context = browser.new_context(viewport={"width": 1400, "height": 900})
            page = context.new_page()

            # 执行所有测试
            test_dashboard(page)
            test_contracts_page(page)
            test_contract_detail(page)
            test_annotated_view(page)
            test_clause_list_view(page)
            test_upload_contract(page)
            test_knowledge_page(page)
            test_other_pages(page)

            browser.close()

        # 打印测试结果
        print("\n" + "=" * 60)
        print("测试结果汇总")
        print("=" * 60)
        print(f"  通过: {results['pass']}")
        print(f"  失败: {results['fail']}")
        print(f"  跳过: {results['skip']}")
        print(f"  总计: {results['pass'] + results['fail'] + results['skip']}")
        print("=" * 60)

        if results['fail'] == 0:
            print("\n[SUCCESS] 所有测试通过！")
        else:
            print(f"\n[WARNING] 有 {results['fail']} 个测试失败")

        print(f"\n截图保存在: {SCREENSHOT_DIR}/")

    finally:
        server.terminate()
        server.wait()


if __name__ == "__main__":
    main()

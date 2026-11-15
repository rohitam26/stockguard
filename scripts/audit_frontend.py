import os
import time
from playwright.sync_api import sync_playwright

def run_frontend_audit():
    console_errors = []
    page_errors = []

    final_ui_dir = os.path.abspath("docs/screenshots/final-ui")
    os.makedirs(final_ui_dir, exist_ok=True)
    root_screenshots_dir = os.path.abspath("docs/screenshots")

    with sync_playwright() as p:
        try:
            browser = p.chromium.launch(channel="chrome", headless=True)
        except Exception:
            browser = p.chromium.launch(channel="msedge", headless=True)

        context = browser.new_context(viewport={"width": 1440, "height": 920})
        page = context.new_page()

        page.on("console", lambda msg: console_errors.append(msg.text) if msg.type == "error" else None)
        page.on("pageerror", lambda err: page_errors.append(str(err)))

        print("Navigating to http://127.0.0.1:8000/ ...")
        page.goto("http://127.0.0.1:8000/", wait_until="networkidle")
        time.sleep(2)

        # 1. Test Navigation Links & Tabs (All 6 tabs)
        tabs = [
            "tab-overview",
            "tab-inventory",
            "tab-reservations",
            "tab-orders",
            "tab-events",
            "tab-health"
        ]
        tab_results = {}
        for tab in tabs:
            btn = page.locator(f"button[data-tab='{tab}']")
            btn.click()
            time.sleep(0.4)
            pane = page.locator(f"#{tab}")
            is_active = "active" in pane.get_attribute("class")
            tab_results[tab] = is_active
            print(f"Tab '{tab}' clicked -> Active: {is_active}")

        # Return to Overview
        page.click("button[data-tab='tab-overview']")
        time.sleep(0.5)

        # 2. Check Metrics on Overview
        kpi_skus = page.locator("#kpiTotalSkus").inner_text()
        kpi_avail = page.locator("#kpiAvailableStock").inner_text()
        kpi_res = page.locator("#kpiActiveReservations").inner_text()
        kpi_orders = page.locator("#kpiTotalOrders").inner_text()
        arch_mq_text = page.locator("#archMqDesc").inner_text()

        print(f"Metrics: SKUs={kpi_skus}, Avail={kpi_avail}, Res={kpi_res}, Orders={kpi_orders}")
        print(f"Broker Description displayed: {arch_mq_text}")

        # 3. Test Product Creation Form
        page.click("button[data-tab='tab-inventory']")
        time.sleep(0.5)
        test_sku = f"FE-UI-{int(time.time())}"
        page.fill("#pSku", test_sku)
        page.fill("#pName", "Frontend Intelligence Terminal")
        page.fill("#pPrice", "129.99")
        page.fill("#pStock", "25")
        page.fill("#pThreshold", "5")
        page.click("#formCreateProduct button[type='submit']")
        time.sleep(1.5)
        print(f"Submitted create product form for {test_sku}")

        # 4. Test Stock Filter Buttons
        for f in ["all", "in_stock", "low_stock", "depleted"]:
            page.click(f"button[data-filter='{f}']")
            time.sleep(0.3)
        page.click("button[data-filter='all']")

        # 5. Test Stock Adjustment Form
        page.select_option("#adjSku", value=test_sku)
        page.fill("#adjDelta", "10")
        page.fill("#adjReason", "UI manual restock test")
        page.click("#formAdjustStock button[type='submit']")
        time.sleep(1.5)
        print("Submitted stock adjustment form (+10)")

        # 6. Test Reservation Creation Form
        page.click("button[data-tab='tab-reservations']")
        time.sleep(0.5)
        page.select_option("#resSku", value=test_sku)
        page.fill("#resQty", "2")
        page.click("#formCreateReservation button[type='submit']")
        time.sleep(1.5)
        print("Submitted reservation creation form (qty 2)")

        # 7. Test Order Checkout & Saga Stepper
        page.click("button[data-tab='tab-orders']")
        time.sleep(0.5)
        page.fill("#ordCustomer", "cust-ui-tester")
        page.select_option("#ordSku", value=test_sku)
        page.fill("#ordQty", "1")
        # Check simulate failure box
        page.check("#ordSimulatePaymentFailure")
        page.click("#formCreateOrder button[type='submit']")
        time.sleep(3)
        saga_log = page.locator("#sagaLog").inner_text()
        print("Saga Execution Log:\n", saga_log[:300])

        # 8. CAPTURE ALL 7 REQUIRED SCREENSHOTS IN docs/screenshots/final-ui/
        print("\nCapturing all 7 screenshots in docs/screenshots/final-ui/ ...")

        # 1. overview-dashboard.png
        page.click("button[data-tab='tab-overview']")
        time.sleep(1)
        path_overview = os.path.join(final_ui_dir, "overview-dashboard.png")
        page.screenshot(path=path_overview)
        page.screenshot(path=os.path.join(root_screenshots_dir, "01_dashboard_overview.png"))
        print(f"Captured: {path_overview}")

        # 2. inventory-management.png
        page.click("button[data-tab='tab-inventory']")
        time.sleep(1)
        path_inv = os.path.join(final_ui_dir, "inventory-management.png")
        page.screenshot(path=path_inv)
        print(f"Captured: {path_inv}")

        # 3. atomic-reservations.png
        page.click("button[data-tab='tab-reservations']")
        time.sleep(1)
        path_res = os.path.join(final_ui_dir, "atomic-reservations.png")
        page.screenshot(path=path_res)
        page.screenshot(path=os.path.join(root_screenshots_dir, "03_atomic_reservations.png"))
        print(f"Captured: {path_res}")

        # 4. order-saga.png
        page.click("button[data-tab='tab-orders']")
        time.sleep(1)
        path_saga = os.path.join(final_ui_dir, "order-saga.png")
        page.screenshot(path=path_saga)
        page.screenshot(path=os.path.join(root_screenshots_dir, "02_order_saga_visualizer.png"))
        print(f"Captured: {path_saga}")

        # 5. transactional-outbox.png
        page.click("button[data-tab='tab-events']")
        time.sleep(1)
        path_outbox = os.path.join(final_ui_dir, "transactional-outbox.png")
        page.screenshot(path=path_outbox)
        page.screenshot(path=os.path.join(root_screenshots_dir, "04_transactional_outbox.png"))
        print(f"Captured: {path_outbox}")

        # 6. system-health.png
        page.click("button[data-tab='tab-health']")
        time.sleep(1)
        path_health = os.path.join(final_ui_dir, "system-health.png")
        page.screenshot(path=path_health)
        print(f"Captured: {path_health}")

        # 7. mobile-dashboard.png
        page.set_viewport_size({"width": 390, "height": 844})
        page.click("button[data-tab='tab-overview']")
        time.sleep(1)
        path_mobile = os.path.join(final_ui_dir, "mobile-dashboard.png")
        page.screenshot(path=path_mobile)
        print(f"Captured: {path_mobile}")

        # Restore desktop viewport & capture swagger docs
        page.set_viewport_size({"width": 1440, "height": 920})
        page.goto("http://127.0.0.1:8000/docs", wait_until="networkidle")
        time.sleep(2)
        page.screenshot(path=os.path.join(root_screenshots_dir, "05_swagger_api_docs.png"))

        browser.close()

    print("\n=== FRONTEND AUDIT SUMMARY ===")
    print(f"Console Errors: {len(console_errors)} (Errors: {console_errors})")
    print(f"Page Errors: {len(page_errors)} (Errors: {page_errors})")
    print(f"Tab Switching: {tab_results}")
    return console_errors, page_errors, tab_results

if __name__ == "__main__":
    run_frontend_audit()

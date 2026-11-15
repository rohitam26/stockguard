import os
import time
from playwright.sync_api import sync_playwright

def run_frontend_audit():
    console_errors = []
    page_errors = []

    with sync_playwright() as p:
        try:
            browser = p.chromium.launch(channel="chrome", headless=True)
        except Exception:
            browser = p.chromium.launch(channel="msedge", headless=True)

        context = browser.new_context(viewport={"width": 1400, "height": 900})
        page = context.new_page()

        page.on("console", lambda msg: console_errors.append(msg.text) if msg.type == "error" else None)
        page.on("pageerror", lambda err: page_errors.append(str(err)))

        print("Navigating to http://127.0.0.1:8000/ ...")
        page.goto("http://127.0.0.1:8000/", wait_until="networkidle")
        time.sleep(2)

        # 1. Test Navigation Links & Tabs
        tabs = ["tab-overview", "tab-inventory", "tab-reservations", "tab-orders", "tab-events"]
        tab_results = {}
        for tab in tabs:
            btn = page.locator(f"button[data-tab='{tab}']")
            btn.click()
            time.sleep(0.5)
            pane = page.locator(f"#{tab}")
            is_active = "active" in pane.get_attribute("class")
            tab_results[tab] = is_active
            print(f"Tab '{tab}' clicked -> Active: {is_active}")

        # Return to Overview
        page.click("button[data-tab='tab-overview']")
        time.sleep(1)

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
        page.fill("#pName", "Frontend Test Gadget")
        page.fill("#pPrice", "89.50")
        page.fill("#pStock", "15")
        page.fill("#pThreshold", "3")
        page.click("#formCreateProduct button[type='submit']")
        time.sleep(1.5)
        print(f"Submitted create product form for {test_sku}")

        # 4. Test Stock Adjustment Form
        page.select_option("#adjSku", value=test_sku)
        page.fill("#adjDelta", "5")
        page.fill("#adjReason", "UI manual restock test")
        page.click("#formAdjustStock button[type='submit']")
        time.sleep(1.5)
        print("Submitted stock adjustment form (+5)")

        # 5. Test Reservation Creation Form
        page.click("button[data-tab='tab-reservations']")
        time.sleep(0.5)
        page.select_option("#resSku", value=test_sku)
        page.fill("#resQty", "2")
        page.click("#formCreateReservation button[type='submit']")
        time.sleep(1.5)
        print("Submitted reservation creation form (qty 2)")

        # 6. Test Order Checkout & Saga Stepper
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

        # 7. Test Responsive Breakpoint (Mobile 375x812)
        page.set_viewport_size({"width": 375, "height": 812})
        time.sleep(1)
        mobile_title = page.locator("#pageTitle").is_visible()
        print(f"Mobile view title visible: {mobile_title}")

        # Capture updated screenshots
        output_dir = os.path.abspath("docs/screenshots")
        page.set_viewport_size({"width": 1400, "height": 900})
        page.click("button[data-tab='tab-overview']")
        time.sleep(1)
        page.screenshot(path=os.path.join(output_dir, "01_dashboard_overview.png"))

        page.click("button[data-tab='tab-orders']")
        time.sleep(1)
        page.screenshot(path=os.path.join(output_dir, "02_order_saga_visualizer.png"))

        page.click("button[data-tab='tab-reservations']")
        time.sleep(1)
        page.screenshot(path=os.path.join(output_dir, "03_atomic_reservations.png"))

        page.click("button[data-tab='tab-events']")
        time.sleep(1)
        page.screenshot(path=os.path.join(output_dir, "04_transactional_outbox.png"))

        page.goto("http://127.0.0.1:8000/docs", wait_until="networkidle")
        time.sleep(2)
        page.screenshot(path=os.path.join(output_dir, "05_swagger_api_docs.png"))

        browser.close()

    print("\n=== FRONTEND AUDIT SUMMARY ===")
    print(f"Console Errors: {len(console_errors)} (Errors: {console_errors})")
    print(f"Page Errors: {len(page_errors)} (Errors: {page_errors})")
    print(f"Tab Switching: {tab_results}")
    return console_errors, page_errors, tab_results

if __name__ == "__main__":
    run_frontend_audit()

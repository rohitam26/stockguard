import os
import time
from playwright.sync_api import sync_playwright

def capture():
    output_dir = os.path.abspath("docs/screenshots")
    os.makedirs(output_dir, exist_ok=True)

    with sync_playwright() as p:
        # Launch using preinstalled Chrome or Edge
        try:
            browser = p.chromium.launch(channel="chrome", headless=True)
        except Exception:
            browser = p.chromium.launch(channel="msedge", headless=True)

        context = browser.new_context(viewport={"width": 1400, "height": 900})
        page = context.new_page()

        print("Navigating to http://127.0.0.1:8000/ ...")
        page.goto("http://127.0.0.1:8000/", wait_until="networkidle")
        time.sleep(2)  # Wait for dashboard JS fetch

        # Screenshot 1: Main Dashboard Overview
        p1 = os.path.join(output_dir, "01_dashboard_overview.png")
        page.screenshot(path=p1)
        print("Captured:", p1)

        # Screenshot 2: Order & Saga Orchestrator tab
        page.click("button[data-tab='tab-orders']")
        time.sleep(1)
        p2 = os.path.join(output_dir, "02_order_saga_visualizer.png")
        page.screenshot(path=p2)
        print("Captured:", p2)

        # Screenshot 3: Atomic Reservations tab
        page.click("button[data-tab='tab-reservations']")
        time.sleep(1)
        p3 = os.path.join(output_dir, "03_atomic_reservations.png")
        page.screenshot(path=p3)
        print("Captured:", p3)

        # Screenshot 4: Transactional Outbox tab
        page.click("button[data-tab='tab-events']")
        time.sleep(1)
        p4 = os.path.join(output_dir, "04_transactional_outbox.png")
        page.screenshot(path=p4)
        print("Captured:", p4)

        # Screenshot 5: Interactive Swagger UI Docs
        page.goto("http://127.0.0.1:8000/docs", wait_until="networkidle")
        time.sleep(2)
        p5 = os.path.join(output_dir, "05_swagger_api_docs.png")
        page.screenshot(path=p5)
        print("Captured:", p5)

        browser.close()
        print("All screenshots successfully captured!")

if __name__ == "__main__":
    capture()

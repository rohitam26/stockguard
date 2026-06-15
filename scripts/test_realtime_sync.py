import time
import uuid
from playwright.sync_api import sync_playwright

def run_realtime_sync_test():
    print("=== STARTING STOCKGUARD REAL-TIME MULTI-WINDOW SYNCHRONIZATION TEST ===")

    with sync_playwright() as p:
        try:
            browser = p.chromium.launch(channel="chrome", headless=True)
        except Exception:
            browser = p.chromium.launch(channel="msedge", headless=True)

        # Context A (Window A - Mutation Actor)
        context_a = browser.new_context(viewport={"width": 1280, "height": 800})
        page_a = context_a.new_page()

        # Context B (Window B - Passive Observer)
        context_b = browser.new_context(viewport={"width": 1280, "height": 800})
        page_b = context_b.new_page()

        print("[TEST STEP 1] Opening Window A and Window B to http://127.0.0.1:8000/ ...")
        page_a.goto("http://127.0.0.1:8000/", wait_until="networkidle")
        page_b.goto("http://127.0.0.1:8000/", wait_until="networkidle")
        time.sleep(2)

        # Verify initial live sync indicators
        sync_a = page_a.locator("#syncText").inner_text()
        sync_b = page_b.locator("#syncText").inner_text()
        print(f"Window A Sync Status: '{sync_a}' | Window B Sync Status: '{sync_b}'")
        assert "Connected" in sync_a or "Live Sync" in sync_a, "Window A must display Connected status"
        assert "Connected" in sync_b or "Live Sync" in sync_b, "Window B must display Connected status"

        initial_skus_b = int(page_b.locator("#kpiTotalSkus").inner_text().replace(",", ""))
        print(f"Window B Initial Catalog SKUs: {initial_skus_b}")

        # [TEST STEP 2] Create product in Window A
        test_sku = f"RT-SYNC-{uuid.uuid4().hex[:6].upper()}"
        print(f"\n[TEST STEP 2] Creating Product '{test_sku}' in Window A...")
        page_a.click("button[data-tab='tab-inventory']")
        time.sleep(0.5)
        page_a.fill("#pSku", test_sku)
        page_a.fill("#pName", f"Real-Time Sync Product {test_sku}")
        page_a.fill("#pPrice", "149.50")
        page_a.fill("#pStock", "20")
        page_a.fill("#pThreshold", "5")
        page_a.click("#formCreateProduct button[type='submit']")
        time.sleep(1.5)
        print("Product created in Window A.")

        # [TEST STEP 3] Verify Window B reflects new product automatically without user refresh
        print("\n[TEST STEP 3] Waiting for Window B to automatically poll backend (max 7s)...")
        # Polling interval is 5 seconds. We poll Window B's DOM every 500ms up to 8s
        start_wait = time.time()
        detected_in_b = False
        while time.time() - start_wait < 8.0:
            current_skus_b = int(page_b.locator("#kpiTotalSkus").inner_text().replace(",", ""))
            # Check if SKU appears in table
            content_b = page_b.locator("#overviewInventoryBody").inner_text()
            if test_sku in content_b and current_skus_b >= initial_skus_b + 1:
                detected_in_b = True
                elapsed = time.time() - start_wait
                print(f"[SUCCESS] Window B detected new SKU '{test_sku}' automatically in {elapsed:.2f}s! Total SKUs: {current_skus_b}")
                break
            time.sleep(0.5)

        assert detected_in_b, f"Window B failed to reflect new product {test_sku} within polling interval!"

        # [TEST STEP 4] Adjust Stock in Window A and observe Window B
        print(f"\n[TEST STEP 4] Adjusting Stock for '{test_sku}' (+15 units) in Window A...")
        page_a.select_option("#adjSku", value=test_sku)
        page_a.fill("#adjDelta", "15")
        page_a.fill("#adjReason", "Realtime sync test delta")
        page_a.click("#formAdjustStock button[type='submit']")
        time.sleep(1.5)
        print("Stock adjustment applied in Window A.")

        # Verify Window B reflects 35 units (20 + 15) automatically
        print("[TEST STEP 5] Waiting for Window B to reflect updated available stock (35 units)...")
        start_wait = time.time()
        stock_updated_in_b = False
        while time.time() - start_wait < 8.0:
            row_text = page_b.locator(f"#overviewInventoryBody tr:has-text('{test_sku}')").inner_text()
            if "35" in row_text:
                stock_updated_in_b = True
                elapsed = time.time() - start_wait
                print(f"[SUCCESS] Window B automatically updated '{test_sku}' available stock to 35 in {elapsed:.2f}s! (Row: {row_text})")
                break
            time.sleep(0.5)

        assert stock_updated_in_b, f"Window B failed to reflect updated stock (35) for {test_sku}!"

        # [TEST STEP 6] Create Atomic Reservation in Window A & verify Window B
        print(f"\n[TEST STEP 6] Creating Atomic Reservation for '{test_sku}' (5 units) in Window A...")
        page_a.click("button[data-tab='tab-reservations']")
        time.sleep(0.5)
        page_a.select_option("#resSku", value=test_sku)
        page_a.fill("#resQty", "5")
        page_a.click("#formCreateReservation button[type='submit']")
        time.sleep(1.5)
        print("Reservation created in Window A.")

        # In Window B, switch to reservations tab and wait for auto-poll
        page_b.click("button[data-tab='tab-reservations']")
        time.sleep(0.5)
        print("[TEST STEP 7] Waiting for Window B to automatically show active reservation for 5 units...")
        start_wait = time.time()
        res_detected_in_b = False
        while time.time() - start_wait < 8.0:
            res_content = page_b.locator("#reservationsTableBody").inner_text()
            if test_sku in res_content and "ACTIVE" in res_content:
                res_detected_in_b = True
                elapsed = time.time() - start_wait
                print(f"[SUCCESS] Window B automatically reflected active reservation for '{test_sku}' in {elapsed:.2f}s!")
                break
            time.sleep(0.5)

        assert res_detected_in_b, "Window B failed to reflect new reservation automatically!"

        # [TEST STEP 8] Release Reservation in Window A & verify Window B updates
        print(f"\n[TEST STEP 8] Releasing Reservation in Window A...")
        release_btn = page_a.locator(f"#reservationsTableBody tr:has-text('{test_sku}') button.btn-release-res").first
        if release_btn.is_visible():
            release_btn.click()
            time.sleep(1.5)
            print("Reservation released in Window A.")

        print("Waiting for Window B to reflect RELEASED status...")
        start_wait = time.time()
        released_in_b = False
        while time.time() - start_wait < 8.0:
            row_b = page_b.locator(f"#reservationsTableBody tr:has-text('{test_sku}')").inner_text()
            if "RELEASED" in row_b:
                released_in_b = True
                elapsed = time.time() - start_wait
                print(f"[SUCCESS] Window B automatically updated reservation to RELEASED in {elapsed:.2f}s!")
                break
            time.sleep(0.5)

        assert released_in_b, "Window B failed to reflect released reservation automatically!"

        # [TEST STEP 9] Disconnection & Reconnection Test
        print("\n[TEST STEP 9] Simulating Network Disconnection on Window A...")
        # Intercept and abort API requests on Window A to simulate backend outage
        page_a.route("**/api/v1/**", lambda route: route.abort("failed"))

        # 9A: Verify Reconnecting state after first failure
        start_wait = time.time()
        reconnecting_detected = False
        while time.time() - start_wait < 10.0:
            status = page_a.evaluate("() => ({ text: document.getElementById('syncText').textContent, cls: document.getElementById('syncDot').className })")
            if "reconnecting" in status["cls"].lower() or "reconnecting" in status["text"].lower():
                reconnecting_detected = True
                elapsed = time.time() - start_wait
                print(f"[SUCCESS] Step 9A: Reconnecting state triggered on 1st failure in {elapsed:.2f}s: Text='{status['text']}', Class='{status['cls']}'")
                break
            time.sleep(0.5)
        assert reconnecting_detected, "Window A failed to show Reconnecting state on initial failure!"

        # 9B: Verify Disconnected state after second consecutive failure
        print("Waiting for 2nd failure to trigger Disconnected state (consecutiveFailures >= 2)...")
        disconnected_detected = False
        while time.time() - start_wait < 18.0:
            status = page_a.evaluate("() => ({ text: document.getElementById('syncText').textContent, cls: document.getElementById('syncDot').className })")
            if "disconnected" in status["cls"].lower() or "disconnected" in status["text"].lower():
                disconnected_detected = True
                elapsed = time.time() - start_wait
                print(f"[SUCCESS] Step 9B: Disconnected state triggered after >=2 failures in {elapsed:.2f}s: Text='{status['text']}', Class='{status['cls']}'")
                break
            time.sleep(0.5)
        assert disconnected_detected, "Window A failed to show Disconnected state after two failures!"

        # [TEST STEP 10] Restore Connectivity & Verify Reconnection
        print("\n[TEST STEP 10] Restoring Network Connectivity on Window A...")
        page_a.unroute("**/api/v1/**")

        # Wait for next poll cycle to restore connected status
        start_wait = time.time()
        reconnected = False
        while time.time() - start_wait < 15.0:
            status = page_a.evaluate("() => ({ text: document.getElementById('syncText').textContent, cls: document.getElementById('syncDot').className })")
            is_connected_class = "connected" in status["cls"].split() or status["cls"] == "sync-dot connected"
            is_connected_text = "Live Sync" in status["text"] or status["text"].strip() == "Connected"
            if is_connected_class and is_connected_text:
                reconnected = True
                elapsed = time.time() - start_wait
                print(f"[SUCCESS] Step 10: Window A restored connection automatically in {elapsed:.2f}s: Text='{status['text']}', Class='{status['cls']}'")
                break
            time.sleep(0.5)

        assert reconnected, f"Window A failed to restore Connected state after connectivity was restored! Status: {status}"

        browser.close()

    print("\n=== ALL REAL-TIME MULTI-WINDOW & DISCONNECTION TESTS PASSED ===")
    return True

if __name__ == "__main__":
    run_realtime_sync_test()

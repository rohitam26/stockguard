// StockGuard — Premium SaaS Inventory Intelligence & Real-Time Distributed Engine
document.addEventListener("DOMContentLoaded", () => {
  // Navigation Tabs
  const navItems = document.querySelectorAll(".nav-item");
  const tabPanes = document.querySelectorAll(".tab-pane");

  navItems.forEach(item => {
    item.addEventListener("click", () => {
      const tabId = item.getAttribute("data-tab");
      navItems.forEach(n => n.classList.remove("active"));
      tabPanes.forEach(p => p.classList.remove("active"));
      item.classList.add("active");
      const targetPane = document.getElementById(tabId);
      if (targetPane) targetPane.classList.add("active");
    });
  });

  // Global State
  let products = [];
  let inventoryList = [];
  let reservations = [];
  let orders = [];
  let outboxEvents = [];
  let currentStockFilter = "all";

  // Synchronization State
  let isSyncing = false;
  let syncIntervalMs = 5000; // 5-second automatic refresh
  let syncTimerId = null;
  let consecutiveFailures = 0;
  let lastSyncTime = null;

  // Filter Buttons on Inventory Tab
  const filterBtns = document.querySelectorAll(".filter-btn");
  filterBtns.forEach(btn => {
    btn.addEventListener("click", () => {
      filterBtns.forEach(b => b.classList.remove("active"));
      btn.classList.add("active");
      currentStockFilter = btn.getAttribute("data-filter") || "all";
      renderInventoryTable();
    });
  });

  // Helper Toast Notifications
  function showToast(message, type = "info") {
    const container = document.getElementById("toastContainer");
    if (!container) return;
    const toast = document.createElement("div");
    toast.className = `toast ${type}`;
    toast.textContent = message;
    container.appendChild(toast);
    setTimeout(() => {
      toast.style.opacity = "0";
      setTimeout(() => toast.remove(), 300);
    }, 4000);
  }

  // HTML Sanitizer to prevent DOM XSS
  function escapeHtml(str) {
    if (str == null) return "";
    return String(str)
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;")
      .replace(/'/g, "&#39;");
  }

  // Generate Client UUID
  function generateUUID() {
    return "idemp-" + Math.random().toString(36).substring(2, 10) + "-" + Date.now();
  }

  // Refresh Idempotency Key
  const resIdempInput = document.getElementById("resIdempotency");
  const btnGenResKey = document.getElementById("btnGenResKey");
  if (resIdempInput) resIdempInput.value = generateUUID();
  if (btnGenResKey) {
    btnGenResKey.addEventListener("click", () => {
      resIdempInput.value = generateUUID();
    });
  }

  // Connection Indicator State Machine
  function updateConnectionIndicator(state, label) {
    const dot = document.getElementById("syncDot");
    const text = document.getElementById("syncText");
    const timeDisplay = document.getElementById("syncTime");

    if (dot) dot.className = `sync-dot ${state}`;
    if (text) text.textContent = label;
    if (timeDisplay) {
      if (lastSyncTime) {
        timeDisplay.textContent = `Synced: ${lastSyncTime.toLocaleTimeString()}`;
      } else {
        timeDisplay.textContent = "Connecting...";
      }
    }
  }

  // Fetch Health & Architecture
  async function fetchHealth() {
    const res = await fetch("/api/v1/health", { cache: "no-store" });
    if (!res.ok) throw new Error(`Health status: HTTP ${res.status}`);
    const data = await res.json();
    const dbText = document.getElementById("dbStatusText");
    const mqText = document.getElementById("mqStatusText");
    const archDbDesc = document.getElementById("archDbDesc");
    const archMqDesc = document.getElementById("archMqDesc");
    const mqDot = document.getElementById("mqStatusDot");
    const srvDbPill = document.getElementById("srvDbPill");
    const srvMqPill = document.getElementById("srvMqPill");

    if (data.database.status === "healthy") {
      if (dbText) dbText.textContent = `${data.database.engine} Connected`;
      if (archDbDesc) archDbDesc.textContent = `${data.database.engine} (Host: ${data.database.url_masked})`;
      if (srvDbPill) {
        srvDbPill.textContent = "Online (Healthy)";
        srvDbPill.className = "service-status-pill online";
      }
    } else {
      if (dbText) dbText.textContent = "DB Degraded";
      if (srvDbPill) {
        srvDbPill.textContent = "Degraded";
        srvDbPill.className = "service-status-pill amber";
      }
    }

    if (data.messaging.connected) {
      if (mqText) mqText.textContent = `${data.messaging.broker} Connected`;
      if (mqDot) mqDot.className = "status-dot healthy";
      if (archMqDesc) archMqDesc.textContent = `${data.messaging.broker} (Topology Declared, Exchanges & Queues Bound)`;
      if (srvMqPill) {
        srvMqPill.textContent = "Connected (Port 5672)";
        srvMqPill.className = "service-status-pill online";
      }
    } else {
      if (mqText) mqText.textContent = "In-Memory Bus (Fallback)";
      if (mqDot) mqDot.className = "status-dot degraded";
      if (archMqDesc) archMqDesc.textContent = "In-Memory Event Bus (Fallback active: External RabbitMQ broker unreachable on port 5672)";
      if (srvMqPill) {
        srvMqPill.textContent = "Fallback Active (Port 5672 Offline)";
        srvMqPill.className = "service-status-pill amber";
      }
    }
  }

  // Fetch Products & Inventory
  async function fetchInventoryAndProducts() {
    const [prodRes, invRes] = await Promise.all([
      fetch("/api/v1/products?limit=500", { cache: "no-store" }),
      fetch("/api/v1/inventory?limit=500", { cache: "no-store" })
    ]);
    if (!prodRes.ok || !invRes.ok) throw new Error("Failed to fetch product/inventory data");
    products = await prodRes.json();
    inventoryList = await invRes.json();

    updateKPIs();
    renderInventoryTable();
    populateSkuDropdowns();
  }

  // Update KPI Cards & Stock Allocation Visual Bar
  function updateKPIs() {
    const kpiSkus = document.getElementById("kpiTotalSkus");
    if (kpiSkus) kpiSkus.textContent = products.length;

    const totalAvail = inventoryList.reduce((acc, item) => acc + item.available_stock, 0);
    const totalReserved = inventoryList.reduce((acc, item) => acc + item.reserved_stock, 0);
    const totalAllocated = inventoryList.reduce((acc, item) => acc + item.allocated_stock, 0);
    const lowStockCount = inventoryList.filter(item => item.is_low_stock).length;

    const kpiAvail = document.getElementById("kpiAvailableStock");
    if (kpiAvail) kpiAvail.textContent = totalAvail.toLocaleString();

    const kpiLowWarn = document.getElementById("kpiLowStockWarning");
    if (kpiLowWarn) kpiLowWarn.textContent = `${lowStockCount} SKU(s) low in stock`;

    const activeResCount = reservations.filter(r => r.status === "ACTIVE").length;
    const kpiActiveRes = document.getElementById("kpiActiveReservations");
    if (kpiActiveRes) kpiActiveRes.textContent = activeResCount;

    const kpiTotalOrd = document.getElementById("kpiTotalOrders");
    if (kpiTotalOrd) kpiTotalOrd.textContent = orders.length;

    const totalRev = orders
      .filter(o => o.status === "COMPLETED" || o.status === "PAID")
      .reduce((acc, o) => acc + parseFloat(o.total_amount || 0), 0);
    const kpiRev = document.getElementById("kpiTotalRevenue");
    if (kpiRev) kpiRev.textContent = `$${totalRev.toFixed(2)} revenue`;

    // Dynamic Stock Allocation Distribution Bar
    const totalPool = totalAvail + totalReserved + totalAllocated;
    const barAvail = document.getElementById("barAvail");
    const barRes = document.getElementById("barRes");
    const barAlloc = document.getElementById("barAlloc");
    const percentText = document.getElementById("healthBarPercentText");
    const legAvail = document.getElementById("legendAvailVal");
    const legRes = document.getElementById("legendResVal");
    const legAlloc = document.getElementById("legendAllocVal");

    if (totalPool > 0) {
      const availPct = Math.round((totalAvail / totalPool) * 100);
      const resPct = Math.round((totalReserved / totalPool) * 100);
      const allocPct = 100 - availPct - resPct;

      if (barAvail) barAvail.style.width = `${availPct}%`;
      if (barRes) barRes.style.width = `${resPct}%`;
      if (barAlloc) barAlloc.style.width = `${allocPct}%`;

      if (percentText) percentText.textContent = `${availPct}% Available · ${resPct}% Reserved · ${allocPct}% Allocated`;
    } else {
      if (percentText) percentText.textContent = "0 Units in Inventory";
    }

    if (legAvail) legAvail.textContent = totalAvail.toLocaleString();
    if (legRes) legRes.textContent = totalReserved.toLocaleString();
    if (legAlloc) legAlloc.textContent = totalAllocated.toLocaleString();
  }

  // Populate SKU dropdowns
  function populateSkuDropdowns() {
    const dropdowns = [
      document.getElementById("adjSku"),
      document.getElementById("resSku"),
      document.getElementById("ordSku")
    ];

    dropdowns.forEach(dropdown => {
      if (!dropdown) return;
      const currentVal = dropdown.value;
      dropdown.innerHTML = '<option value="">-- Choose SKU --</option>';
      products.forEach(p => {
        const opt = document.createElement("option");
        opt.value = p.sku;
        opt.textContent = `${p.sku} - ${p.name} ($${parseFloat(p.price).toFixed(2)})`;
        dropdown.appendChild(opt);
      });
      if (currentVal) dropdown.value = currentVal;
    });
  }

  // Render Live Inventory Table with Search & Status Filtering
  function renderInventoryTable() {
    const tbody = document.getElementById("overviewInventoryBody");
    if (!tbody) return;
    const searchFilter = (document.getElementById("inventorySearch") ? document.getElementById("inventorySearch").value : "").toLowerCase();

    if (!inventoryList.length) {
      tbody.innerHTML = '<tr><td colspan="8" class="text-center py-4">No inventory items found. Add products above.</td></tr>';
      return;
    }

    const prodMap = new Map(products.map(p => [p.sku, p]));
    const filtered = inventoryList.filter(item => {
      const prod = prodMap.get(item.sku);
      const name = prod ? prod.name.toLowerCase() : "";
      const matchesSearch = item.sku.toLowerCase().includes(searchFilter) || name.includes(searchFilter);
      if (!matchesSearch) return false;

      // Status Filter
      if (currentStockFilter === "in_stock") return item.available_stock > 0 && !item.is_low_stock;
      if (currentStockFilter === "low_stock") return item.is_low_stock && item.available_stock > 0;
      if (currentStockFilter === "depleted") return item.available_stock === 0;
      return true;
    });

    tbody.innerHTML = "";
    if (!filtered.length) {
      tbody.innerHTML = '<tr><td colspan="8" class="text-center py-4" style="color: var(--text-secondary);">No products match filter criteria.</td></tr>';
      return;
    }

    filtered.forEach(item => {
      const prod = prodMap.get(item.sku);
      const priceStr = prod ? `$${parseFloat(prod.price).toFixed(2)}` : "-";
      const nameStr = escapeHtml(prod ? prod.name : item.sku);
      const safeSku = escapeHtml(item.sku);

      let statusBadge = '<span class="badge badge-in-stock">In Stock</span>';
      if (item.available_stock === 0) {
        statusBadge = '<span class="badge badge-out-of-stock">Depleted</span>';
      } else if (item.is_low_stock) {
        statusBadge = '<span class="badge badge-low-stock">Low Stock</span>';
      }

      const tr = document.createElement("tr");
      tr.innerHTML = `
        <td><code style="font-weight: 700; color: var(--primary-forest); font-size: 0.85rem;">${safeSku}</code></td>
        <td style="font-weight: 600;">${nameStr}</td>
        <td>${priceStr}</td>
        <td><strong style="color: var(--emerald); font-size: 0.95rem;">${item.available_stock}</strong></td>
        <td><span style="color: #B45309; font-weight: 600;">${item.reserved_stock}</span></td>
        <td><span style="color: var(--primary-forest); font-weight: 600;">${item.allocated_stock}</span></td>
        <td>${statusBadge}</td>
        <td>
          <button class="btn btn-secondary btn-sm btn-quick-restock" data-sku="${safeSku}" title="Quick +10 Restock">
            +10 Restock
          </button>
        </td>
      `;
      tbody.appendChild(tr);
    });

    // Attach quick restock buttons
    document.querySelectorAll(".btn-quick-restock").forEach(btn => {
      btn.addEventListener("click", async () => {
        const sku = btn.getAttribute("data-sku");
        await handleRestock(sku, 10, "Quick dashboard restock");
      });
    });
  }

  // Inventory Search Listener
  const invSearch = document.getElementById("inventorySearch");
  if (invSearch) {
    invSearch.addEventListener("input", renderInventoryTable);
  }

  // Quick Restock Handler
  async function handleRestock(sku, delta, reason) {
    try {
      const res = await fetch("/api/v1/inventory/adjust", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ sku, quantity_delta: delta, reason })
      });
      if (!res.ok) {
        const err = await res.json();
        throw new Error(err.detail || "Restock failed");
      }
      showToast(`Stock updated for ${sku} (+${delta})`, "success");
      await performFullSync(true);
    } catch (e) {
      showToast(e.message, "error");
    }
  }

  // Form: Create Product
  const formCreateProduct = document.getElementById("formCreateProduct");
  if (formCreateProduct) {
    formCreateProduct.addEventListener("submit", async e => {
      e.preventDefault();
      const sku = document.getElementById("pSku").value.trim();
      const name = document.getElementById("pName").value.trim();
      const price = parseFloat(document.getElementById("pPrice").value);
      const initial_stock = parseInt(document.getElementById("pStock").value, 10);
      const low_stock_threshold = parseInt(document.getElementById("pThreshold").value, 10);

      try {
        const res = await fetch("/api/v1/products", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ sku, name, price, initial_stock, low_stock_threshold })
        });
        if (!res.ok) {
          const err = await res.json();
          throw new Error(err.detail || "Failed to create product");
        }
        showToast(`Product ${sku} created successfully`, "success");
        formCreateProduct.reset();
        await performFullSync(true);
      } catch (err) {
        showToast(err.message, "error");
      }
    });
  }

  // Form: Stock Adjustment
  const formAdjustStock = document.getElementById("formAdjustStock");
  if (formAdjustStock) {
    formAdjustStock.addEventListener("submit", async e => {
      e.preventDefault();
      const sku = document.getElementById("adjSku").value;
      const quantity_delta = parseInt(document.getElementById("adjDelta").value, 10);
      const reason = document.getElementById("adjReason").value.trim();

      await handleRestock(sku, quantity_delta, reason);
      formAdjustStock.reset();
    });
  }

  // Fetch Reservations
  async function fetchReservations() {
    const res = await fetch("/api/v1/reservations", { cache: "no-store" });
    if (!res.ok) throw new Error("Failed to fetch reservations");
    reservations = await res.json();
    renderReservationsTable();
    updateKPIs();
  }

  function renderReservationsTable() {
    const tbody = document.getElementById("reservationsTableBody");
    if (!tbody) return;
    if (!reservations.length) {
      tbody.innerHTML = '<tr><td colspan="6" class="text-center py-4" style="color: var(--text-secondary);">No active reservations recorded.</td></tr>';
      return;
    }
    tbody.innerHTML = "";
    reservations.forEach(r => {
      const tr = document.createElement("tr");
      const badgeClass = r.status === "ACTIVE" ? "badge-active" : (r.status === "CONFIRMED" ? "badge-completed" : "badge-released");
      const safeId = escapeHtml(r.id);
      const safeSku = escapeHtml(r.sku);
      tr.innerHTML = `
        <td><code style="font-weight: 600; color: var(--primary-forest);">${safeId.substring(0, 8)}...</code></td>
        <td><strong>${safeSku}</strong></td>
        <td><strong style="color: #B45309;">${r.quantity}</strong></td>
        <td><span class="badge ${badgeClass}">${escapeHtml(r.status)}</span></td>
        <td style="font-size: 0.82rem; color: var(--text-secondary);">${new Date(r.expires_at).toLocaleTimeString()}</td>
        <td>
          ${r.status === "ACTIVE" ? `<button class="btn btn-secondary btn-sm btn-release-res" data-id="${safeId}">Release</button>` : "-"}
        </td>
      `;
      tbody.appendChild(tr);
    });

    document.querySelectorAll(".btn-release-res").forEach(b => {
      b.addEventListener("click", async () => {
        const id = b.getAttribute("data-id");
        try {
          const res = await fetch(`/api/v1/reservations/${id}/release`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ reason: "User released from dashboard" })
          });
          if (!res.ok) throw new Error("Release failed");
          const updated = await res.json();
          const idx = reservations.findIndex(r => r.id === id);
          if (idx !== -1) reservations[idx] = updated;
          showToast(`Reservation ${id.substring(0, 8)} released`, "success");
          renderReservationsTable();
          await performFullSync(true);
        } catch (err) {
          showToast(err.message, "error");
        }
      });
    });
  }

  // Form: Create Reservation
  const formCreateReservation = document.getElementById("formCreateReservation");
  if (formCreateReservation) {
    formCreateReservation.addEventListener("submit", async e => {
      e.preventDefault();
      const sku = document.getElementById("resSku").value;
      const quantity = parseInt(document.getElementById("resQty").value, 10);
      const ttl_seconds = parseInt(document.getElementById("resTtl").value, 10);
      const idempotency_key = document.getElementById("resIdempotency").value;

      try {
        const res = await fetch("/api/v1/reservations", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ sku, quantity, ttl_seconds, idempotency_key })
        });
        if (!res.ok) {
          const err = await res.json();
          throw new Error(err.detail || "Reservation failed");
        }
        const resData = await res.json();
        reservations.unshift(resData);
        showToast(`Reserved ${quantity} unit(s) of ${sku}`, "success");
        document.getElementById("resIdempotency").value = generateUUID();
        renderReservationsTable();
        await performFullSync(true);
      } catch (err) {
        showToast(err.message, "error");
      }
    });
  }

  // Button: Expire Stale Reservations
  const btnExpireStale = document.getElementById("btnExpireStale");
  if (btnExpireStale) {
    btnExpireStale.addEventListener("click", async () => {
      try {
        const res = await fetch("/api/v1/reservations/expire-stale", { method: "POST" });
        const data = await res.json();
        showToast(`Expiry sweep completed. Expired: ${data.expired_count}`, "info");
        await performFullSync(true);
      } catch (e) {
        showToast("Expiry sweep failed", "error");
      }
    });
  }

  // Fetch Orders
  async function fetchOrders() {
    const res = await fetch("/api/v1/orders", { cache: "no-store" });
    if (!res.ok) throw new Error("Failed to fetch orders");
    orders = await res.json();
    renderOrdersTable();
    updateKPIs();
  }

  function renderOrdersTable() {
    const tbody = document.getElementById("ordersTableBody");
    if (!tbody) return;
    if (!orders.length) {
      tbody.innerHTML = '<tr><td colspan="6" class="text-center py-4" style="color: var(--text-secondary);">No orders placed yet.</td></tr>';
      return;
    }
    tbody.innerHTML = "";
    orders.forEach(o => {
      let statusBadge = `<span class="badge badge-active">${escapeHtml(o.status)}</span>`;
      if (o.status === "COMPLETED") statusBadge = `<span class="badge badge-completed">COMPLETED</span>`;
      else if (o.status === "CANCELLED" || o.status === "FAILED") statusBadge = `<span class="badge badge-failed">${escapeHtml(o.status)}</span>`;

      const safeOrderNum = escapeHtml(o.order_number);
      const safeCustomer = escapeHtml(o.customer_id);
      const safeOrderId = escapeHtml(o.id);

      const tr = document.createElement("tr");
      tr.innerHTML = `
        <td><strong style="color: var(--primary-forest); font-family: var(--font-mono);">${safeOrderNum}</strong></td>
        <td>${safeCustomer}</td>
        <td><strong>$${parseFloat(o.total_amount).toFixed(2)}</strong></td>
        <td>${statusBadge}</td>
        <td style="font-size: 0.82rem; color: var(--text-secondary);">${new Date(o.created_at).toLocaleTimeString()}</td>
        <td>
          ${o.status === "PENDING" ? `<button class="btn btn-primary btn-sm btn-exec-checkout" data-id="${safeOrderId}">Checkout Saga</button>` : "-"}
        </td>
      `;
      tbody.appendChild(tr);
    });

    document.querySelectorAll(".btn-exec-checkout").forEach(btn => {
      btn.addEventListener("click", () => {
        const orderId = btn.getAttribute("data-id");
        executeSaga(orderId, false);
      });
    });
  }

  // Execute Saga with Visual Stepper & Real-time Console Log
  async function executeSaga(orderId, simulateFailure) {
    const stepRes = document.getElementById("stepReservation");
    const stepPay = document.getElementById("stepPayment");
    const stepFul = document.getElementById("stepFulfillment");
    const sagaLog = document.getElementById("sagaLog");

    // Reset steps
    [stepRes, stepPay, stepFul].forEach(s => {
      if (!s) return;
      s.className = "saga-step active";
      s.querySelector(".step-badge").textContent = "Processing...";
      s.querySelector(".step-badge").className = "step-badge badge-active";
    });

    if (sagaLog) {
      sagaLog.textContent = `[${new Date().toLocaleTimeString()}] Initiating Saga for Order ID: ${orderId}\n` +
        `[STEP 1] Reserving inventory items atomically with row-locking...\n`;
    }

    try {
      const res = await fetch(`/api/v1/orders/${orderId}/checkout?simulate_failure=${simulateFailure}`, {
        method: "POST"
      });
      const data = await res.json();

      if (data.success) {
        if (stepRes) {
          stepRes.className = "saga-step success";
          stepRes.querySelector(".step-badge").textContent = "Reserved";
          stepRes.querySelector(".step-badge").className = "step-badge badge-completed";
        }
        if (stepPay) {
          stepPay.className = "saga-step success";
          stepPay.querySelector(".step-badge").textContent = "Paid ($" + data.payment_status + ")";
          stepPay.querySelector(".step-badge").className = "step-badge badge-completed";
        }
        if (stepFul) {
          stepFul.className = "saga-step success";
          stepFul.querySelector(".step-badge").textContent = data.fulfillment_status;
          stepFul.querySelector(".step-badge").className = "step-badge badge-completed";
        }

        if (sagaLog) {
          sagaLog.textContent +=
            `[STEP 1 OK] Stock reserved. Reservation IDs: ${data.reservations.join(", ")}\n` +
            `[STEP 2 OK] Payment settled. Status: ${data.payment_status}\n` +
            `[STEP 3 OK] Fulfillment initiated. Status: ${data.fulfillment_status}\n` +
            `[SAGA COMPLETE] Distributed Saga finished with 100% data consistency.`;
        }
        showToast("Order checkout & Saga completed successfully!", "success");
      } else {
        // Backward Compensation Path
        if (data.stage === "RESERVATION") {
          if (stepRes) {
            stepRes.className = "saga-step failed";
            stepRes.querySelector(".step-badge").textContent = "Stock Depleted";
            stepRes.querySelector(".step-badge").className = "step-badge badge-failed";
          }
          [stepPay, stepFul].forEach(s => {
            if (!s) return;
            s.className = "saga-step";
            s.querySelector(".step-badge").textContent = "Skipped";
            s.querySelector(".step-badge").className = "step-badge badge-idle";
          });
        } else if (data.stage === "PAYMENT") {
          if (stepRes) {
            stepRes.className = "saga-step failed";
            stepRes.querySelector(".step-badge").textContent = "Compensated (Released)";
            stepRes.querySelector(".step-badge").className = "step-badge badge-failed";
          }
          if (stepPay) {
            stepPay.className = "saga-step failed";
            stepPay.querySelector(".step-badge").textContent = "Declined";
            stepPay.querySelector(".step-badge").className = "step-badge badge-failed";
          }
          if (stepFul) {
            stepFul.className = "saga-step";
            stepFul.querySelector(".step-badge").textContent = "Cancelled";
            stepFul.querySelector(".step-badge").className = "step-badge badge-idle";
          }
        }

        if (sagaLog) {
          sagaLog.textContent +=
            `[SAGA ERROR in ${data.stage}]: ${data.message}\n` +
            `[SAGA COMPENSATION TRIGGERED]: Acquired reservations released back to available pool.\n` +
            `[FINAL STATE]: Order cancelled/failed. Zero orphan reservations.`;
        }
        showToast(`Saga failed: ${data.message} (Compensated)`, "warning");
      }

      await performFullSync(true);
    } catch (e) {
      if (sagaLog) sagaLog.textContent += `[ERROR] Saga execution failed: ${e.message}\n`;
      showToast(e.message, "error");
    }
  }

  // Form: Create Order
  const formCreateOrder = document.getElementById("formCreateOrder");
  if (formCreateOrder) {
    formCreateOrder.addEventListener("submit", async e => {
      e.preventDefault();
      const customer_id = document.getElementById("ordCustomer").value.trim();
      const sku = document.getElementById("ordSku").value;
      const quantity = parseInt(document.getElementById("ordQty").value, 10);
      const simulateFailure = document.getElementById("ordSimulatePaymentFailure").checked;

      try {
        const res = await fetch("/api/v1/orders", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            customer_id,
            items: [{ sku, quantity }],
            idempotency_key: generateUUID()
          })
        });
        if (!res.ok) {
          const err = await res.json();
          throw new Error(err.detail || "Order creation failed");
        }
        const order = await res.json();
        showToast(`Order ${order.order_number} created`, "info");
        await performFullSync(true);
        // Immediately run Saga
        await executeSaga(order.id, simulateFailure);
      } catch (err) {
        showToast(err.message, "error");
      }
    });
  }

  // Fetch Outbox
  async function fetchOutbox() {
    const res = await fetch("/api/v1/outbox", { cache: "no-store" });
    if (!res.ok) throw new Error("Failed to fetch outbox events");
    outboxEvents = await res.json();
    renderOutboxTable(outboxEvents);
  }

  function renderOutboxTable(messages) {
    const tbody = document.getElementById("outboxTableBody");
    if (!tbody) return;
    if (!messages.length) {
      tbody.innerHTML = '<tr><td colspan="7" class="text-center py-4" style="color: var(--text-secondary);">No outbox events recorded.</td></tr>';
      return;
    }
    tbody.innerHTML = "";
    messages.forEach(m => {
      const tr = document.createElement("tr");
      const safeId = escapeHtml(m.id);
      const safeEventType = escapeHtml(m.event_type);
      const safeAggType = escapeHtml(m.aggregate_type);
      const safeAggId = escapeHtml(m.aggregate_id);

      const statusBadge = m.status === "PUBLISHED" ?
        '<span class="badge badge-completed">PUBLISHED</span>' :
        '<span class="badge badge-active">PENDING</span>';
      tr.innerHTML = `
        <td><code style="font-weight: 600; color: var(--primary-forest);">${safeId.substring(0, 8)}...</code></td>
        <td><strong>${safeEventType}</strong></td>
        <td>${safeAggType} (<code style="font-size: 0.78rem;">${safeAggId.substring(0, 8)}</code>)</td>
        <td>${statusBadge}</td>
        <td><strong>${m.retry_count}</strong></td>
        <td style="font-size: 0.82rem; color: var(--text-secondary);">${new Date(m.created_at).toLocaleTimeString()}</td>
        <td style="font-size: 0.82rem; color: var(--text-secondary);">${m.processed_at ? new Date(m.processed_at).toLocaleTimeString() : "-"}</td>
      `;
      tbody.appendChild(tr);
    });
  }

  // Outbox manual flush
  const btnFlushOutbox = document.getElementById("btnFlushOutbox");
  if (btnFlushOutbox) {
    btnFlushOutbox.addEventListener("click", async () => {
      try {
        const res = await fetch("/api/v1/outbox/process", { method: "POST" });
        const data = await res.json();
        showToast(`Outbox processed: ${data.processed_count} message(s) published`, "success");
        await performFullSync(true);
      } catch (e) {
        showToast("Failed to process outbox", "error");
      }
    });
  }

  // Unified Full Sync Runner with Overlapping Request Prevention & Graceful Error Handling
  async function performFullSync(isManual = false) {
    if (isSyncing) return; // Prevent overlapping requests!
    isSyncing = true;

    try {
      await Promise.all([
        fetchHealth(),
        fetchInventoryAndProducts(),
        fetchReservations(),
        fetchOrders(),
        fetchOutbox()
      ]);

      consecutiveFailures = 0;
      lastSyncTime = new Date();
      const statusMsg = syncIntervalMs > 0 ? `Live Sync: ${syncIntervalMs / 1000}s` : "Connected (Manual)";
      updateConnectionIndicator("connected", statusMsg);
      if (isManual) {
        showToast("Data synchronized with backend", "info");
      }
    } catch (err) {
      consecutiveFailures++;
      console.warn("Sync cycle encountered error:", err);
      if (consecutiveFailures >= 2) {
        updateConnectionIndicator("disconnected", "Backend Disconnected");
      } else {
        updateConnectionIndicator("reconnecting", "Reconnecting...");
      }
    } finally {
      isSyncing = false;
    }
  }

  // Configurable Auto-Refresh Poller
  function setupAutoSync(intervalMs) {
    if (syncTimerId) {
      clearInterval(syncTimerId);
      syncTimerId = null;
    }
    syncIntervalMs = intervalMs;
    if (syncIntervalMs > 0) {
      syncTimerId = setInterval(() => {
        performFullSync(false);
      }, syncIntervalMs);
      updateConnectionIndicator("connected", `Live Sync: ${syncIntervalMs / 1000}s`);
    } else {
      updateConnectionIndicator("fallback", "Sync Paused");
    }
  }

  // Select Polling Interval Listener
  const selectInterval = document.getElementById("selectSyncInterval");
  if (selectInterval) {
    selectInterval.addEventListener("change", e => {
      const ms = parseInt(e.target.value, 10);
      setupAutoSync(ms);
      if (ms > 0) {
        showToast(`Auto-sync set to ${ms / 1000}s`, "info");
      } else {
        showToast("Auto-sync paused", "warning");
      }
    });
  }

  // Manual Refresh Button Listener
  const btnRefreshAll = document.getElementById("btnRefreshAll");
  if (btnRefreshAll) {
    btnRefreshAll.addEventListener("click", async () => {
      await performFullSync(true);
    });
  }

  // Clean up interval timer on page unload
  window.addEventListener("beforeunload", () => {
    if (syncTimerId) {
      clearInterval(syncTimerId);
      syncTimerId = null;
    }
  });

  // Initial Boot Sync & Start 5s Poller
  performFullSync(false);
  setupAutoSync(5000);
});

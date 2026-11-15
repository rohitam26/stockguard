// StockGuard Interactive Enterprise Dashboard Script
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

  // Helper Toast
  function showToast(message, type = "info") {
    const container = document.getElementById("toastContainer");
    const toast = document.createElement("div");
    toast.className = `toast ${type}`;
    toast.textContent = message;
    container.appendChild(toast);
    setTimeout(() => {
      toast.style.opacity = "0";
      setTimeout(() => toast.remove(), 300);
    }, 4000);
  }

  // Generate UUID
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

  // Fetch Health & Architecture
  async function fetchHealth() {
    try {
      const res = await fetch("/api/v1/health");
      const data = await res.json();
      const dbText = document.getElementById("dbStatusText");
      const mqText = document.getElementById("mqStatusText");
      const archDbDesc = document.getElementById("archDbDesc");
      const archMqDesc = document.getElementById("archMqDesc");

      if (data.database.status === "healthy") {
        dbText.textContent = `${data.database.engine} Connected`;
        archDbDesc.textContent = `${data.database.engine} (Host: ${data.database.url_masked})`;
      } else {
        dbText.textContent = "DB Degraded";
      }

      mqText.textContent = data.messaging.broker;
      archMqDesc.textContent = `${data.messaging.broker} (Topology Declared)`;
    } catch (e) {
      console.error("Health fetch error:", e);
    }
  }

  // Fetch Products & Inventory
  async function fetchInventoryAndProducts() {
    try {
      const [prodRes, invRes] = await Promise.all([
        fetch("/api/v1/products"),
        fetch("/api/v1/inventory")
      ]);
      products = await prodRes.json();
      inventoryList = await invRes.json();

      updateKPIs();
      renderInventoryTable();
      populateSkuDropdowns();
    } catch (e) {
      console.error("Inventory fetch error:", e);
      showToast("Failed to load inventory data", "error");
    }
  }

  // Update KPI Cards
  function updateKPIs() {
    document.getElementById("kpiTotalSkus").textContent = products.length;

    const totalAvail = inventoryList.reduce((acc, item) => acc + item.available_stock, 0);
    const lowStockCount = inventoryList.filter(item => item.is_low_stock).length;
    document.getElementById("kpiAvailableStock").textContent = totalAvail;
    document.getElementById("kpiLowStockWarning").textContent = `${lowStockCount} SKU(s) low in stock`;

    const activeResCount = reservations.filter(r => r.status === "ACTIVE").length;
    document.getElementById("kpiActiveReservations").textContent = activeResCount;

    document.getElementById("kpiTotalOrders").textContent = orders.length;
    const totalRev = orders
      .filter(o => o.status === "COMPLETED" || o.status === "PAID")
      .reduce((acc, o) => acc + parseFloat(o.total_amount || 0), 0);
    document.getElementById("kpiTotalRevenue").textContent = `$${totalRev.toFixed(2)} revenue`;
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

  // Render Live Inventory Table
  function renderInventoryTable() {
    const tbody = document.getElementById("overviewInventoryBody");
    const searchFilter = (document.getElementById("inventorySearch").value || "").toLowerCase();

    if (!inventoryList.length) {
      tbody.innerHTML = '<tr><td colspan="8" class="text-center py-4">No inventory items found. Add products above.</td></tr>';
      return;
    }

    const prodMap = new Map(products.map(p => [p.sku, p]));
    const filtered = inventoryList.filter(item => {
      const prod = prodMap.get(item.sku);
      const name = prod ? prod.name.toLowerCase() : "";
      return item.sku.toLowerCase().includes(searchFilter) || name.includes(searchFilter);
    });

    tbody.innerHTML = "";
    filtered.forEach(item => {
      const prod = prodMap.get(item.sku);
      const priceStr = prod ? `$${parseFloat(prod.price).toFixed(2)}` : "-";
      const nameStr = prod ? prod.name : item.sku;

      let statusBadge = '<span class="badge badge-in-stock">In Stock</span>';
      if (item.available_stock === 0) {
        statusBadge = '<span class="badge badge-out-of-stock">Depleted</span>';
      } else if (item.is_low_stock) {
        statusBadge = '<span class="badge badge-low-stock">Low Stock</span>';
      }

      const tr = document.createElement("tr");
      tr.innerHTML = `
        <td><strong>${item.sku}</strong></td>
        <td>${nameStr}</td>
        <td>${priceStr}</td>
        <td><strong style="color: #60a5fa">${item.available_stock}</strong></td>
        <td><span style="color: #fbbf24">${item.reserved_stock}</span></td>
        <td><span style="color: #a78bfa">${item.allocated_stock}</span></td>
        <td>${statusBadge}</td>
        <td>
          <button class="btn btn-secondary btn-sm btn-quick-restock" data-sku="${item.sku}">
            Restock +10
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
      await fetchInventoryAndProducts();
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
        await fetchInventoryAndProducts();
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
    try {
      // In a real system or with our endpoint:
      // Let's call /api/v1/orders or inspect active state
      renderReservationsTable();
    } catch (e) {
      console.error("Reservations fetch error:", e);
    }
  }

  function renderReservationsTable() {
    const tbody = document.getElementById("reservationsTableBody");
    if (!reservations.length) {
      tbody.innerHTML = '<tr><td colspan="6" class="text-center py-4">No active reservations recorded.</td></tr>';
      return;
    }
    tbody.innerHTML = "";
    reservations.forEach(r => {
      const tr = document.createElement("tr");
      const badgeClass = r.status === "ACTIVE" ? "badge-active" : (r.status === "CONFIRMED" ? "badge-completed" : "badge-released");
      tr.innerHTML = `
        <td><code>${r.id.substring(0, 8)}...</code></td>
        <td><strong>${r.sku}</strong></td>
        <td>${r.quantity}</td>
        <td><span class="badge ${badgeClass}">${r.status}</span></td>
        <td>${new Date(r.expires_at).toLocaleTimeString()}</td>
        <td>
          ${r.status === "ACTIVE" ? `<button class="btn btn-secondary btn-sm btn-release-res" data-id="${r.id}">Release</button>` : "-"}
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
          await fetchInventoryAndProducts();
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
        await fetchInventoryAndProducts();
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
        await fetchInventoryAndProducts();
        await fetchOrders();
      } catch (e) {
        showToast("Expiry sweep failed", "error");
      }
    });
  }

  // Fetch Orders
  async function fetchOrders() {
    try {
      const res = await fetch("/api/v1/orders");
      orders = await res.json();
      renderOrdersTable();
      updateKPIs();
    } catch (e) {
      console.error("Orders fetch error:", e);
    }
  }

  function renderOrdersTable() {
    const tbody = document.getElementById("ordersTableBody");
    if (!orders.length) {
      tbody.innerHTML = '<tr><td colspan="6" class="text-center py-4">No orders placed yet.</td></tr>';
      return;
    }
    tbody.innerHTML = "";
    orders.forEach(o => {
      let statusBadge = `<span class="badge badge-active">${o.status}</span>`;
      if (o.status === "COMPLETED") statusBadge = `<span class="badge badge-completed">COMPLETED</span>`;
      else if (o.status === "CANCELLED" || o.status === "FAILED") statusBadge = `<span class="badge badge-failed">${o.status}</span>`;

      const tr = document.createElement("tr");
      tr.innerHTML = `
        <td><strong>${o.order_number}</strong></td>
        <td>${o.customer_id}</td>
        <td>$${parseFloat(o.total_amount).toFixed(2)}</td>
        <td>${statusBadge}</td>
        <td>${new Date(o.created_at).toLocaleTimeString()}</td>
        <td>
          ${o.status === "PENDING" ? `<button class="btn btn-primary btn-sm btn-exec-checkout" data-id="${o.id}">Checkout Saga</button>` : "-"}
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

  // Execute Saga with Visual Stepper
  async function executeSaga(orderId, simulateFailure) {
    const stepRes = document.getElementById("stepReservation");
    const stepPay = document.getElementById("stepPayment");
    const stepFul = document.getElementById("stepFulfillment");
    const sagaLog = document.getElementById("sagaLog");

    // Reset steps
    [stepRes, stepPay, stepFul].forEach(s => {
      s.className = "saga-step active";
      s.querySelector(".step-badge").textContent = "Processing...";
      s.querySelector(".step-badge").className = "step-badge badge-active";
    });

    sagaLog.textContent = `[${new Date().toLocaleTimeString()}] Initiating Saga for Order ID: ${orderId}\n` +
      `[STEP 1] Reserving inventory items atomically with row-locking...\n`;

    try {
      const res = await fetch(`/api/v1/orders/${orderId}/checkout?simulate_failure=${simulateFailure}`, {
        method: "POST"
      });
      const data = await res.json();

      if (data.success) {
        // Step 1 Success
        stepRes.className = "saga-step success";
        stepRes.querySelector(".step-badge").textContent = "Reserved";
        stepRes.querySelector(".step-badge").className = "step-badge badge-completed";

        // Step 2 Success
        stepPay.className = "saga-step success";
        stepPay.querySelector(".step-badge").textContent = "Paid ($" + data.payment_status + ")";
        stepPay.querySelector(".step-badge").className = "step-badge badge-completed";

        // Step 3 Success
        stepFul.className = "saga-step success";
        stepFul.querySelector(".step-badge").textContent = data.fulfillment_status;
        stepFul.querySelector(".step-badge").className = "step-badge badge-completed";

        sagaLog.textContent +=
          `[STEP 1 OK] Stock reserved. Reservation IDs: ${data.reservations.join(", ")}\n` +
          `[STEP 2 OK] Payment settled. Status: ${data.payment_status}\n` +
          `[STEP 3 OK] Fulfillment initiated. Status: ${data.fulfillment_status}\n` +
          `[SAGA COMPLETE] Distributed Saga finished with 100% data consistency.`;
        showToast("Order checkout & Saga completed successfully!", "success");
      } else {
        // Compensation path!
        if (data.stage === "RESERVATION") {
          stepRes.className = "saga-step failed";
          stepRes.querySelector(".step-badge").textContent = "Stock Depleted";
          stepRes.querySelector(".step-badge").className = "step-badge badge-failed";
          [stepPay, stepFul].forEach(s => {
            s.className = "saga-step";
            s.querySelector(".step-badge").textContent = "Skipped";
            s.querySelector(".step-badge").className = "step-badge badge-idle";
          });
        } else if (data.stage === "PAYMENT") {
          stepRes.className = "saga-step failed";
          stepRes.querySelector(".step-badge").textContent = "Compensated (Released)";
          stepRes.querySelector(".step-badge").className = "step-badge badge-failed";

          stepPay.className = "saga-step failed";
          stepPay.querySelector(".step-badge").textContent = "Declined";
          stepPay.querySelector(".step-badge").className = "step-badge badge-failed";

          stepFul.className = "saga-step";
          stepFul.querySelector(".step-badge").textContent = "Cancelled";
          stepFul.querySelector(".step-badge").className = "step-badge badge-idle";
        }

        sagaLog.textContent +=
          `[SAGA ERROR in ${data.stage}]: ${data.message}\n` +
          `[SAGA COMPENSATION TRIGGERED]: Acquired reservations released back to available pool.\n` +
          `[FINAL STATE]: Order cancelled/failed. Zero orphan reservations.`;
        showToast(`Saga failed: ${data.message} (Compensated)`, "warning");
      }

      await fetchInventoryAndProducts();
      await fetchOrders();
    } catch (e) {
      sagaLog.textContent += `[ERROR] Saga execution failed: ${e.message}\n`;
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
        await fetchOrders();
        // Immediately run Saga
        await executeSaga(order.id, simulateFailure);
      } catch (err) {
        showToast(err.message, "error");
      }
    });
  }

  // Fetch Outbox
  async function fetchOutbox() {
    try {
      const res = await fetch("/api/v1/outbox");
      if (res.ok) {
        const outboxMessages = await res.json();
        renderOutboxTable(outboxMessages);
      }
    } catch (e) {
      console.error("Outbox fetch error:", e);
    }
  }

  function renderOutboxTable(messages) {
    const tbody = document.getElementById("outboxTableBody");
    if (!messages.length) {
      tbody.innerHTML = '<tr><td colspan="7" class="text-center py-4">No outbox events recorded.</td></tr>';
      return;
    }
    tbody.innerHTML = "";
    messages.forEach(m => {
      const tr = document.createElement("tr");
      const statusBadge = m.status === "PUBLISHED" ?
        '<span class="badge badge-completed">PUBLISHED</span>' :
        '<span class="badge badge-active">PENDING</span>';
      tr.innerHTML = `
        <td><code>${m.id.substring(0, 8)}...</code></td>
        <td><strong>${m.event_type}</strong></td>
        <td>${m.aggregate_type} (${m.aggregate_id.substring(0, 8)})</td>
        <td>${statusBadge}</td>
        <td>${m.retry_count}</td>
        <td>${new Date(m.created_at).toLocaleTimeString()}</td>
        <td>${m.processed_at ? new Date(m.processed_at).toLocaleTimeString() : "-"}</td>
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
        await fetchOutbox();
      } catch (e) {
        showToast("Failed to process outbox", "error");
      }
    });
  }

  // Refresh All Button
  const btnRefreshAll = document.getElementById("btnRefreshAll");
  if (btnRefreshAll) {
    btnRefreshAll.addEventListener("click", async () => {
      await fetchHealth();
      await fetchInventoryAndProducts();
      await fetchOrders();
      await fetchOutbox();
      showToast("Data refreshed", "info");
    });
  }

  // Initial Boot
  fetchHealth();
  fetchInventoryAndProducts();
  fetchOrders();
  fetchOutbox();
});

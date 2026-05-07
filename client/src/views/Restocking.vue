<template>
  <div class="restocking">
    <div class="page-header">
      <h2>Restocking</h2>
      <p>Budget-aware restock recommendations based on demand forecasts</p>
    </div>

    <div v-if="loading" class="loading">Loading restocking data...</div>
    <div v-else-if="error" class="error">{{ error }}</div>
    <div v-else>
      <!-- Budget Controls -->
      <div class="card">
        <div class="card-header">
          <h3 class="card-title">Budget</h3>
        </div>
        <div class="budget-controls">
          <div class="budget-slider-row">
            <label class="budget-label" for="budget-slider">Budget</label>
            <input
              id="budget-slider"
              type="range"
              min="5000"
              max="250000"
              step="1000"
              v-model.number="budget"
              class="budget-slider"
            />
            <!-- Number input is two-way bound to the same budget ref -->
            <input
              type="number"
              min="5000"
              max="250000"
              step="1000"
              v-model.number="budget"
              class="budget-number-input"
            />
            <span class="budget-display">{{ formatCurrency(budget) }}</span>
          </div>
        </div>
      </div>

      <!-- Recommendations Card -->
      <div class="card">
        <div class="card-header">
          <h3 class="card-title">Recommended Restocking ({{ recommendations.length }} items)</h3>
          <button
            class="btn-primary"
            :disabled="recommendations.length === 0 || submitting"
            @click="placeOrder"
          >
            {{ submitting ? 'Placing Order...' : 'Place Order' }}
          </button>
        </div>

        <div v-if="recommendations.length === 0" class="empty-state">
          No items can be restocked within the current budget.
        </div>
        <div v-else>
          <div class="table-container">
            <table>
              <thead>
                <tr>
                  <th>SKU</th>
                  <th>Item</th>
                  <th>Category</th>
                  <th>Forecast</th>
                  <th>On Hand</th>
                  <th>Qty</th>
                  <th>Unit Cost</th>
                  <th>Line Total</th>
                </tr>
              </thead>
              <tbody>
                <tr v-for="rec in recommendations" :key="rec.sku">
                  <td><strong>{{ rec.sku }}</strong></td>
                  <td>{{ rec.name }}</td>
                  <td>
                    <span class="badge info">{{ rec.category }}</span>
                  </td>
                  <td>{{ rec.forecasted_demand }}</td>
                  <td>{{ rec.current_on_hand }}</td>
                  <td><strong>{{ rec.suggested_quantity }}</strong></td>
                  <td>{{ formatCurrency(rec.unit_cost) }}</td>
                  <td><strong>{{ formatCurrency(rec.line_total) }}</strong></td>
                </tr>
              </tbody>
            </table>
          </div>

          <div class="stats-grid restock-stats">
            <div class="stat-card info">
              <div class="stat-label">Items</div>
              <div class="stat-value">{{ recommendations.length }}</div>
            </div>
            <div class="stat-card warning">
              <div class="stat-label">Total Cost</div>
              <div class="stat-value">{{ formatCurrency(totalCost) }}</div>
            </div>
            <div class="stat-card success">
              <div class="stat-label">Remaining Budget</div>
              <div class="stat-value">{{ formatCurrency(remainingBudget) }}</div>
            </div>
            <div class="stat-card">
              <div class="stat-label">Budget Utilization</div>
              <div class="stat-value">{{ budgetUtilization }}%</div>
            </div>
          </div>
        </div>
      </div>

      <!-- Order Confirmation Card -->
      <div v-if="lastOrder" class="card confirmation-card">
        <div class="card-header">
          <h3 class="card-title">Order Submitted</h3>
          <span class="badge success">Submitted</span>
        </div>
        <div class="confirmation-details">
          <div class="confirmation-row">
            <span class="confirmation-label">Order Number</span>
            <span class="confirmation-value"><strong>{{ lastOrder.order_number }}</strong></span>
          </div>
          <div class="confirmation-row">
            <span class="confirmation-label">Total Cost</span>
            <span class="confirmation-value">{{ formatCurrency(lastOrder.total_cost) }}</span>
          </div>
          <div class="confirmation-row">
            <span class="confirmation-label">Lead Time</span>
            <span class="confirmation-value">{{ lastOrder.lead_time_days }} days</span>
          </div>
          <div class="confirmation-row">
            <span class="confirmation-label">Expected Delivery</span>
            <span class="confirmation-value">{{ formatDate(lastOrder.expected_delivery) }}</span>
          </div>
        </div>
      </div>

      <!-- Submit Error -->
      <div v-if="submitError" class="error">{{ submitError }}</div>

      <!-- Recently Submitted (session-only, last 3) -->
      <div v-if="submittedOrders.length > 0" class="card">
        <div class="card-header">
          <h3 class="card-title">Recently Submitted (this session)</h3>
        </div>
        <div class="table-container">
          <table>
            <thead>
              <tr>
                <th>Order #</th>
                <th>Total Cost</th>
                <th>Expected Delivery</th>
                <th>Status</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="order in recentOrders" :key="order.id">
                <td><strong>{{ order.order_number }}</strong></td>
                <td>{{ formatCurrency(order.total_cost) }}</td>
                <td>{{ formatDate(order.expected_delivery) }}</td>
                <td><span class="badge info">{{ order.status }}</span></td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>
    </div>
  </div>
</template>

<script>
import { ref, computed, onMounted } from 'vue'
import { api } from '../api'

export default {
  name: 'Restocking',
  setup() {
    const loading = ref(true)
    const error = ref(null)
    const submitting = ref(false)
    const submitError = ref(null)

    const forecasts = ref([])
    const inventoryItems = ref([])

    // Budget with default of $50,000
    const budget = ref(50000)

    // Orders submitted during this browser session
    const submittedOrders = ref([])

    // Last placed order for confirmation display
    const lastOrder = ref(null)

    const loadData = async () => {
      try {
        loading.value = true
        error.value = null

        // Load forecasts and inventory in parallel; inventory has no month dimension
        const [forecastsData, inventoryData] = await Promise.all([
          api.getDemandForecasts(),
          api.getInventory()
        ])

        forecasts.value = forecastsData
        inventoryItems.value = inventoryData
      } catch (err) {
        error.value = 'Failed to load restocking data: ' + err.message
      } finally {
        loading.value = false
      }
    }

    // Build an inventory lookup keyed by SKU for O(1) access in the computed below
    const inventoryBySku = computed(() => {
      const map = {}
      for (const item of inventoryItems.value) {
        map[item.sku] = item
      }
      return map
    })

    // Core recommendation algorithm — runs reactively whenever budget or source data change
    const recommendations = computed(() => {
      // Sort forecasts descending by forecasted_demand so highest-priority items
      // consume the budget first
      const sorted = [...forecasts.value].sort(
        (a, b) => b.forecasted_demand - a.forecasted_demand
      )

      let remaining = budget.value
      const result = []

      for (const forecast of sorted) {
        if (remaining <= 0) break

        const inv = inventoryBySku.value[forecast.item_sku]
        if (!inv) continue // Skip forecasts with no matching inventory row

        const { unit_cost, category, quantity_on_hand } = inv

        if (!unit_cost || unit_cost <= 0) continue

        // Full coverage = forecasted_demand units
        let qty = forecast.forecasted_demand

        const fullCost = unit_cost * qty

        if (fullCost > remaining) {
          // Partial fill: take as many units as the remaining budget allows
          qty = Math.floor(remaining / unit_cost)
          if (qty === 0) continue // Can't even afford one unit — skip
        }

        const line_total = unit_cost * qty
        remaining -= line_total

        result.push({
          sku: forecast.item_sku,
          name: forecast.item_name,
          category,
          unit_cost,
          suggested_quantity: qty,
          line_total,
          forecasted_demand: forecast.forecasted_demand,
          current_on_hand: quantity_on_hand
        })
      }

      return result
    })

    const totalCost = computed(() =>
      recommendations.value.reduce((sum, r) => sum + r.line_total, 0)
    )

    const remainingBudget = computed(() => budget.value - totalCost.value)

    const budgetUtilization = computed(() => {
      if (budget.value === 0) return '0.0'
      return ((totalCost.value / budget.value) * 100).toFixed(1)
    })

    // Last 3 submitted orders for the "recently submitted" section
    const recentOrders = computed(() => submittedOrders.value.slice(-3).reverse())

    const placeOrder = async () => {
      if (recommendations.value.length === 0) return

      submitting.value = true
      submitError.value = null
      lastOrder.value = null

      try {
        const payload = {
          budget: budget.value,
          items: recommendations.value.map(r => ({
            sku: r.sku,
            quantity: r.suggested_quantity
          }))
        }

        const order = await api.createRestockOrder(payload)
        lastOrder.value = order

        // Prepend to session list so newest is first
        submittedOrders.value.push(order)
      } catch (err) {
        submitError.value =
          'Failed to place order: ' +
          (err.response?.data?.detail || err.message)
      } finally {
        submitting.value = false
      }
    }

    const formatCurrency = (value) => {
      if (value == null) return '$0'
      return '$' + Number(value).toLocaleString('en-US', {
        minimumFractionDigits: 2,
        maximumFractionDigits: 2
      })
    }

    const formatDate = (dateString) => {
      if (!dateString) return '-'
      const d = new Date(dateString)
      if (isNaN(d.getTime())) return dateString
      return d.toLocaleDateString('en-US', {
        year: 'numeric',
        month: 'short',
        day: 'numeric'
      })
    }

    onMounted(loadData)

    return {
      loading,
      error,
      submitting,
      submitError,
      budget,
      recommendations,
      totalCost,
      remainingBudget,
      budgetUtilization,
      submittedOrders,
      recentOrders,
      lastOrder,
      placeOrder,
      formatCurrency,
      formatDate
    }
  }
}
</script>

<style scoped>
.budget-controls {
  padding: 0.5rem 0 0.25rem;
}

.budget-slider-row {
  display: flex;
  align-items: center;
  gap: 1rem;
  flex-wrap: wrap;
}

.budget-label {
  font-size: 0.875rem;
  font-weight: 600;
  color: #64748b;
  min-width: 50px;
}

.budget-slider {
  flex: 1;
  min-width: 200px;
  accent-color: #2563eb;
  cursor: pointer;
}

.budget-number-input {
  width: 120px;
  padding: 0.375rem 0.625rem;
  border: 1px solid #e2e8f0;
  border-radius: 6px;
  font-size: 0.875rem;
  color: #0f172a;
  outline: none;
  transition: border-color 0.2s;
}

.budget-number-input:focus {
  border-color: #2563eb;
}

.budget-display {
  font-size: 1.125rem;
  font-weight: 700;
  color: #0f172a;
  min-width: 120px;
  text-align: right;
}

.btn-primary {
  background: #2563eb;
  color: white;
  border: none;
  padding: 0.5rem 1.25rem;
  border-radius: 6px;
  font-size: 0.875rem;
  font-weight: 600;
  cursor: pointer;
  transition: background 0.2s, opacity 0.2s;
}

.btn-primary:hover:not(:disabled) {
  background: #1d4ed8;
}

.btn-primary:disabled {
  opacity: 0.45;
  cursor: not-allowed;
}

.empty-state {
  padding: 2rem;
  text-align: center;
  color: #64748b;
  font-size: 0.938rem;
}

.restock-stats {
  margin-top: 1.25rem;
  margin-bottom: 0;
}

.confirmation-card {
  border-left: 4px solid #059669;
}

.confirmation-details {
  display: flex;
  flex-direction: column;
  gap: 0.75rem;
  padding: 0.25rem 0;
}

.confirmation-row {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 0.5rem 0;
  border-bottom: 1px solid #f1f5f9;
}

.confirmation-row:last-child {
  border-bottom: none;
}

.confirmation-label {
  font-size: 0.875rem;
  color: #64748b;
  font-weight: 500;
}

.confirmation-value {
  font-size: 0.875rem;
  color: #0f172a;
}
</style>

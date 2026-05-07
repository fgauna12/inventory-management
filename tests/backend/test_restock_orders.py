"""
Tests for restocking order API endpoints.
"""
from datetime import date, datetime, timedelta


# Known SKUs from server/data/inventory.json — picked so tests cover multiple
# categories with distinct lead times in CATEGORY_LEAD_TIMES.
SKU_CIRCUIT_BOARD = "PCB-001"     # Circuit Boards, lead time 14
SKU_SENSOR = "TMP-201"            # Sensors,        lead time 10
SKU_CHEAP_SENSOR = "PRS-203"      # Sensors,        lead time 10, $12.75


class TestRestockOrdersEndpoints:
    """Test suite for /api/restock-orders endpoints."""

    def test_create_restock_order_happy_path(self, client):
        """Submitting a valid order returns 201 with computed totals."""
        payload = {
            "budget": 5000,
            "items": [{"sku": SKU_CHEAP_SENSOR, "quantity": 10}],
        }
        response = client.post("/api/restock-orders", json=payload)
        assert response.status_code == 201

        order = response.json()
        assert order["status"] == "Submitted"
        assert order["order_number"].startswith("RST-")
        assert order["budget"] == 5000.0
        assert len(order["items"]) == 1

        line = order["items"][0]
        assert line["sku"] == SKU_CHEAP_SENSOR
        assert line["category"] == "Sensors"
        assert line["quantity"] == 10
        # PRS-203 unit_cost is 12.75 in mock data
        assert abs(line["line_total"] - 127.50) < 0.01
        assert abs(order["total_cost"] - 127.50) < 0.01

    def test_get_restock_orders_returns_submitted(self, client):
        """Submitted orders should appear in the GET listing."""
        payload = {
            "budget": 1000,
            "items": [{"sku": SKU_CHEAP_SENSOR, "quantity": 1}],
        }
        created = client.post("/api/restock-orders", json=payload).json()

        response = client.get("/api/restock-orders")
        assert response.status_code == 200
        orders = response.json()
        assert isinstance(orders, list)
        assert any(o["id"] == created["id"] for o in orders)

    def test_create_restock_order_over_budget(self, client):
        """Over-budget orders return 400 with a budget-exceeded message."""
        payload = {
            "budget": 10,
            "items": [{"sku": SKU_CHEAP_SENSOR, "quantity": 100}],
        }
        response = client.post("/api/restock-orders", json=payload)
        assert response.status_code == 400
        assert "exceeds budget" in response.json()["detail"]

    def test_create_restock_order_empty_items(self, client):
        """Empty item list returns 400."""
        response = client.post(
            "/api/restock-orders", json={"budget": 1000, "items": []}
        )
        assert response.status_code == 400
        assert "at least one item" in response.json()["detail"].lower()

    def test_create_restock_order_non_positive_quantity(self, client):
        """Zero or negative quantity returns 400."""
        response = client.post(
            "/api/restock-orders",
            json={"budget": 1000, "items": [{"sku": SKU_CHEAP_SENSOR, "quantity": 0}]},
        )
        assert response.status_code == 400
        assert "must be positive" in response.json()["detail"]

    def test_create_restock_order_unknown_sku(self, client):
        """Unknown SKU returns 404."""
        response = client.post(
            "/api/restock-orders",
            json={"budget": 1000, "items": [{"sku": "DOES-NOT-EXIST", "quantity": 1}]},
        )
        assert response.status_code == 404
        assert "DOES-NOT-EXIST" in response.json()["detail"]

    def test_lead_time_is_max_of_categories(self, client):
        """Multi-category order's lead time = slowest category's lead time."""
        # Circuit Boards = 14, Sensors = 10 → expect 14
        payload = {
            "budget": 5000,
            "items": [
                {"sku": SKU_CIRCUIT_BOARD, "quantity": 1},
                {"sku": SKU_SENSOR, "quantity": 1},
            ],
        }
        response = client.post("/api/restock-orders", json=payload)
        assert response.status_code == 201
        order = response.json()
        assert order["lead_time_days"] == 14

    def test_expected_delivery_equals_submitted_plus_lead_time(self, client):
        """expected_delivery = submitted_at date + lead_time_days."""
        payload = {
            "budget": 5000,
            "items": [{"sku": SKU_CIRCUIT_BOARD, "quantity": 1}],
        }
        response = client.post("/api/restock-orders", json=payload)
        assert response.status_code == 201
        order = response.json()

        submitted = datetime.fromisoformat(order["submitted_at"]).date()
        expected = date.fromisoformat(order["expected_delivery"])
        assert expected == submitted + timedelta(days=order["lead_time_days"])

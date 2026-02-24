"""
Test file for Subscriptions, Quotes, and Discount Codes APIs
Tests: Plans, Discount Codes, Quotes, Store Pricing
"""
import pytest
import requests
import os
from datetime import datetime

BASE_URL = os.environ.get('EXPO_PUBLIC_BACKEND_URL', 'https://agreements-mgmt.preview.emergentagent.com')


class TestSubscriptionPlans:
    """Test subscription plans endpoints"""
    
    def test_get_all_plans(self):
        """Test GET /api/subscriptions/plans - returns all plans"""
        response = requests.get(f"{BASE_URL}/api/subscriptions/plans")
        assert response.status_code == 200
        
        data = response.json()
        assert "plans" in data
        assert len(data["plans"]) >= 5  # At least 3 individual + 2 store plans
        assert data["currency"] == "usd"
        assert "terms" in data
        print(f"✓ GET all plans: {len(data['plans'])} plans returned")
    
    def test_get_individual_plans(self):
        """Test GET /api/subscriptions/plans?plan_type=individual"""
        response = requests.get(f"{BASE_URL}/api/subscriptions/plans?plan_type=individual")
        assert response.status_code == 200
        
        data = response.json()
        plans = data["plans"]
        assert len(plans) == 3  # monthly, annual, intro
        
        # Verify individual plans have correct IDs
        plan_ids = [p["id"] for p in plans]
        assert "monthly" in plan_ids
        assert "annual" in plan_ids
        assert "intro" in plan_ids
        print(f"✓ GET individual plans: {plan_ids}")
    
    def test_get_store_plans(self):
        """Test GET /api/subscriptions/plans?plan_type=store"""
        response = requests.get(f"{BASE_URL}/api/subscriptions/plans?plan_type=store")
        assert response.status_code == 200
        
        data = response.json()
        plans = data["plans"]
        assert len(plans) == 2  # store_standard, store_volume
        
        plan_ids = [p["id"] for p in plans]
        assert "store_standard" in plan_ids
        assert "store_volume" in plan_ids
        print(f"✓ GET store plans: {plan_ids}")
    
    def test_get_plan_details_monthly(self):
        """Test GET /api/subscriptions/plans/monthly"""
        response = requests.get(f"{BASE_URL}/api/subscriptions/plans/monthly")
        assert response.status_code == 200
        
        plan = response.json()
        assert plan["id"] == "monthly"
        assert plan["name"] == "Monthly"
        assert plan["price"] == 100.0
        assert plan["interval"] == "month"
        assert plan["trial_days"] == 7
        assert "features" in plan
        print(f"✓ GET monthly plan details: ${plan['price']}/{plan['interval']}")
    
    def test_get_plan_details_annual(self):
        """Test GET /api/subscriptions/plans/annual - has discount info"""
        response = requests.get(f"{BASE_URL}/api/subscriptions/plans/annual")
        assert response.status_code == 200
        
        plan = response.json()
        assert plan["id"] == "annual"
        assert plan["price"] == 1000.0
        assert plan["original_price"] == 1200.0
        assert plan["discount_percent"] == 17
        assert plan["badge"] == "BEST VALUE"
        print(f"✓ GET annual plan: ${plan['price']}/year ({plan['discount_percent']}% off)")
    
    def test_get_plan_not_found(self):
        """Test GET /api/subscriptions/plans/invalid returns 404"""
        response = requests.get(f"{BASE_URL}/api/subscriptions/plans/invalid_plan")
        assert response.status_code == 404
        print("✓ GET invalid plan returns 404")


class TestStorePricing:
    """Test store plan pricing calculations"""
    
    def test_store_pricing_5_users(self):
        """Test store pricing with 5 users - standard rate"""
        response = requests.get(f"{BASE_URL}/api/subscriptions/plans/store/calculate?num_users=5")
        assert response.status_code == 200
        
        data = response.json()
        assert data["error"] == False
        assert data["plan_id"] == "store_standard"
        assert data["num_users"] == 5
        assert data["price_per_user"] == 75.0
        assert data["total_monthly"] == 375.0
        print(f"✓ Store pricing 5 users: ${data['total_monthly']}/month @ ${data['price_per_user']}/user")
    
    def test_store_pricing_6_users(self):
        """Test store pricing with 6 users - volume discount"""
        response = requests.get(f"{BASE_URL}/api/subscriptions/plans/store/calculate?num_users=6")
        assert response.status_code == 200
        
        data = response.json()
        assert data["error"] == False
        assert data["plan_id"] == "store_volume"
        assert data["num_users"] == 6
        assert data["price_per_user"] == 65.0
        assert data["total_monthly"] == 390.0
        assert data["discount_monthly"] == 60.0  # $10 * 6 users saved
        print(f"✓ Store pricing 6 users: ${data['total_monthly']}/month (saves ${data['discount_monthly']})")
    
    def test_store_pricing_10_users(self):
        """Test store pricing with 10 users - volume discount"""
        response = requests.get(f"{BASE_URL}/api/subscriptions/plans/store/calculate?num_users=10")
        assert response.status_code == 200
        
        data = response.json()
        assert data["plan_id"] == "store_volume"
        assert data["price_per_user"] == 65.0
        assert data["total_monthly"] == 650.0
        assert data["discount_monthly"] == 100.0  # $10 * 10 users saved
        print(f"✓ Store pricing 10 users: ${data['total_monthly']}/month (saves ${data['discount_monthly']})")
    
    def test_store_pricing_minimum_users(self):
        """Test store pricing with less than 5 users returns error"""
        response = requests.get(f"{BASE_URL}/api/subscriptions/plans/store/calculate?num_users=3")
        assert response.status_code == 200
        
        data = response.json()
        assert data["error"] == True
        assert "Minimum 5 users" in data["message"]
        assert data["min_users"] == 5
        print(f"✓ Store pricing <5 users: error - {data['message']}")


class TestDiscountCodes:
    """Test discount code CRUD operations"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Store created code ID for cleanup"""
        self.created_code_id = None
    
    def test_get_discount_codes(self):
        """Test GET /api/subscriptions/discount-codes - lists all codes"""
        response = requests.get(f"{BASE_URL}/api/subscriptions/discount-codes?active_only=false")
        assert response.status_code == 200
        
        codes = response.json()
        assert isinstance(codes, list)
        print(f"✓ GET discount codes: {len(codes)} codes found")
    
    def test_create_discount_code_with_custom_code(self):
        """Test POST /api/subscriptions/discount-codes - create with custom code"""
        import random
        random_suffix = ''.join([str(random.randint(0, 9)) for _ in range(4)])
        custom_code = f"TEST{random_suffix}"
        
        payload = {
            "code": custom_code,
            "discount_percent": 15,
            "max_uses": 100,
            "expires_days": 30,
            "description": "Test discount code",
            "plan_types": ["individual", "store"]
        }
        
        response = requests.post(f"{BASE_URL}/api/subscriptions/discount-codes", json=payload)
        assert response.status_code == 200
        
        data = response.json()
        assert data["code"] == custom_code
        assert data["discount_percent"] == 15
        assert data["max_uses"] == 100
        assert data["times_used"] == 0
        assert data["status"] == "active"
        assert "individual" in data["plan_types"]
        assert "store" in data["plan_types"]
        
        # Store for later tests and cleanup
        self.created_code_id = data["_id"]
        self.__class__.test_code_id = data["_id"]
        self.__class__.test_code = custom_code
        print(f"✓ Created discount code {custom_code}: {data['discount_percent']}% off")
    
    def test_create_discount_code_auto_generated(self):
        """Test POST /api/subscriptions/discount-codes - auto-generate code"""
        payload = {
            "discount_percent": 10,
            "description": "Auto-generated test code",
            "plan_types": ["individual"]
        }
        
        response = requests.post(f"{BASE_URL}/api/subscriptions/discount-codes", json=payload)
        assert response.status_code == 200
        
        data = response.json()
        assert data["code"].startswith("MVP")  # Auto-generated codes start with MVP
        assert len(data["code"]) == 9  # MVP + 6 chars
        assert data["discount_percent"] == 10
        
        # Store for cleanup
        self.__class__.auto_code_id = data["_id"]
        print(f"✓ Created auto-generated code: {data['code']}")
    
    def test_create_discount_code_invalid_percent(self):
        """Test POST - invalid discount percentage returns 400"""
        payload = {
            "discount_percent": 30,  # Invalid - not in [5, 10, 15, 20, 25]
            "description": "Invalid code"
        }
        
        response = requests.post(f"{BASE_URL}/api/subscriptions/discount-codes", json=payload)
        assert response.status_code == 400
        assert "Discount must be one of" in response.json()["detail"]
        print("✓ Invalid discount percent returns 400")
    
    def test_validate_discount_code_valid(self):
        """Test GET /api/subscriptions/discount-codes/validate/{code}"""
        # Use the code we created earlier
        test_code = getattr(self.__class__, 'test_code', 'MVPJV324H')
        
        response = requests.get(f"{BASE_URL}/api/subscriptions/discount-codes/validate/{test_code}?plan_type=individual")
        assert response.status_code == 200
        
        data = response.json()
        assert data["valid"] == True
        assert data["discount_percent"] in [5, 10, 15, 20, 25]
        print(f"✓ Validate code {test_code}: {data['discount_percent']}% discount")
    
    def test_validate_discount_code_invalid(self):
        """Test validate with non-existent code"""
        response = requests.get(f"{BASE_URL}/api/subscriptions/discount-codes/validate/INVALIDCODE123")
        assert response.status_code == 200
        
        data = response.json()
        assert data["valid"] == False
        assert "Invalid or expired" in data["message"]
        print("✓ Invalid code returns valid=false")
    
    def test_deactivate_discount_code(self):
        """Test DELETE /api/subscriptions/discount-codes/{code_id}"""
        # Use the auto-generated code for deactivation
        code_id = getattr(self.__class__, 'auto_code_id', None)
        if not code_id:
            pytest.skip("No auto-generated code to deactivate")
        
        response = requests.delete(f"{BASE_URL}/api/subscriptions/discount-codes/{code_id}")
        assert response.status_code == 200
        assert "deactivated" in response.json()["message"].lower()
        print(f"✓ Deactivated discount code {code_id}")


class TestQuotes:
    """Test quote CRUD operations"""
    
    def test_list_quotes(self):
        """Test GET /api/subscriptions/quotes"""
        response = requests.get(f"{BASE_URL}/api/subscriptions/quotes")
        assert response.status_code == 200
        
        quotes = response.json()
        assert isinstance(quotes, list)
        print(f"✓ GET quotes: {len(quotes)} quotes found")
    
    def test_create_quote_individual_plan(self):
        """Test POST /api/subscriptions/quotes - individual monthly plan"""
        import random
        random_num = random.randint(1000, 9999)
        
        payload = {
            "plan_type": "individual",
            "plan_id": "monthly",
            "email": f"testquote{random_num}@example.com",
            "name": "Test Customer",
            "phone": "+1555123456",
            "title": "Sales Manager",
            "discount_percent": 10,
            "prepared_by_name": "Admin User",
            "notes": "Test quote for automation"
        }
        
        response = requests.post(f"{BASE_URL}/api/subscriptions/quotes", json=payload)
        assert response.status_code == 200
        
        quote = response.json()
        assert quote["quote_number"].startswith("Q-")
        assert quote["plan_type"] == "individual"
        assert quote["plan_id"] == "monthly"
        assert quote["plan_name"] == "Monthly"
        assert quote["customer"]["email"] == payload["email"]
        assert quote["customer"]["name"] == payload["name"]
        assert quote["pricing"]["base_price"] == 100.0
        assert quote["pricing"]["discount_percent"] == 10
        assert quote["pricing"]["discount_amount"] == 10.0
        assert quote["pricing"]["final_price"] == 90.0
        assert quote["status"] == "draft"
        
        # Store for later tests
        self.__class__.individual_quote_id = quote["_id"]
        print(f"✓ Created individual quote {quote['quote_number']}: ${quote['pricing']['final_price']}/month")
    
    def test_create_quote_store_plan(self):
        """Test POST /api/subscriptions/quotes - store plan with 5 users"""
        import random
        random_num = random.randint(1000, 9999)
        
        payload = {
            "plan_type": "store",
            "num_users": 5,
            "email": f"storetest{random_num}@company.com",
            "name": "Store Manager",
            "company_name": "Test Auto Dealership",
            "website": "https://testauto.com",
            "street_address": "123 Main St",
            "city": "Los Angeles",
            "state": "CA",
            "zip_code": "90001",
            "business_type": "LLC",
            "vertical": "Automotive",
            "discount_percent": 0,
            "prepared_by_name": "Super Admin"
        }
        
        response = requests.post(f"{BASE_URL}/api/subscriptions/quotes", json=payload)
        assert response.status_code == 200
        
        quote = response.json()
        assert quote["plan_type"] == "store"
        assert quote["plan_name"] == "Store Plan (5 users)"
        assert quote["business_info"]["company_name"] == "Test Auto Dealership"
        assert quote["business_info"]["address"]["city"] == "Los Angeles"
        assert quote["pricing"]["base_price"] == 375.0  # 5 * $75
        assert quote["pricing"]["num_users"] == 5
        assert quote["pricing"]["price_per_user"] == 75.0
        
        # Store for later tests
        self.__class__.store_quote_id = quote["_id"]
        print(f"✓ Created store quote {quote['quote_number']}: ${quote['pricing']['final_price']}/month for {quote['pricing']['num_users']} users")
    
    def test_create_quote_store_minimum_users(self):
        """Test store quote with less than 5 users returns error"""
        payload = {
            "plan_type": "store",
            "num_users": 3,
            "company_name": "Small Store"
        }
        
        response = requests.post(f"{BASE_URL}/api/subscriptions/quotes", json=payload)
        assert response.status_code == 400
        assert "Minimum 5 users" in response.json()["detail"]
        print("✓ Store quote <5 users returns 400")
    
    def test_get_quote_by_id(self):
        """Test GET /api/subscriptions/quotes/{quote_id}"""
        quote_id = getattr(self.__class__, 'individual_quote_id', None)
        if not quote_id:
            pytest.skip("No quote created to retrieve")
        
        response = requests.get(f"{BASE_URL}/api/subscriptions/quotes/{quote_id}")
        assert response.status_code == 200
        
        quote = response.json()
        assert quote["_id"] == quote_id
        assert quote["plan_type"] == "individual"
        print(f"✓ GET quote {quote['quote_number']}")
    
    def test_get_quote_not_found(self):
        """Test GET quote with invalid ID returns 404"""
        response = requests.get(f"{BASE_URL}/api/subscriptions/quotes/000000000000000000000000")
        assert response.status_code == 404
        print("✓ GET invalid quote returns 404")
    
    def test_list_quotes_with_filter(self):
        """Test GET /api/subscriptions/quotes?status=draft"""
        response = requests.get(f"{BASE_URL}/api/subscriptions/quotes?status=draft")
        assert response.status_code == 200
        
        quotes = response.json()
        for quote in quotes:
            assert quote["status"] == "draft"
        print(f"✓ GET draft quotes: {len(quotes)} found")


class TestQuoteWithDiscountCode:
    """Test quote creation with discount code validation"""
    
    def test_create_quote_with_valid_discount_code(self):
        """Test quote creation with valid discount code"""
        # First create a discount code
        import random
        random_suffix = ''.join([str(random.randint(0, 9)) for _ in range(4)])
        code_name = f"QUOTECODE{random_suffix}"
        
        # Create discount code
        code_response = requests.post(f"{BASE_URL}/api/subscriptions/discount-codes", json={
            "code": code_name,
            "discount_percent": 20,
            "plan_types": ["individual"]
        })
        assert code_response.status_code == 200
        
        # Create quote with discount code
        quote_payload = {
            "plan_type": "individual",
            "plan_id": "annual",
            "email": f"discountquote{random_suffix}@test.com",
            "name": "Discount Customer",
            "discount_code": code_name
        }
        
        response = requests.post(f"{BASE_URL}/api/subscriptions/quotes", json=quote_payload)
        assert response.status_code == 200
        
        quote = response.json()
        assert quote["pricing"]["discount_percent"] == 20
        assert quote["pricing"]["discount_code"] == code_name
        assert quote["pricing"]["base_price"] == 1000.0
        assert quote["pricing"]["discount_amount"] == 200.0  # 20% of $1000
        assert quote["pricing"]["final_price"] == 800.0
        
        print(f"✓ Created quote with code {code_name}: ${quote['pricing']['final_price']} (20% off)")
    
    def test_create_quote_with_invalid_discount_code(self):
        """Test quote creation with invalid discount code returns error"""
        quote_payload = {
            "plan_type": "individual",
            "plan_id": "monthly",
            "email": "invalid@test.com",
            "discount_code": "INVALID_CODE_12345"
        }
        
        response = requests.post(f"{BASE_URL}/api/subscriptions/quotes", json=quote_payload)
        assert response.status_code == 400
        assert "Invalid or expired" in response.json()["detail"]
        print("✓ Quote with invalid code returns 400")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])

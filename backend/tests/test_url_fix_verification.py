"""
Test to verify the URL fix for customer-facing links.
The fix replaces window.location.origin with EXPO_PUBLIC_APP_URL/app.imonsocial.com
for all outgoing customer-facing URLs.
"""
import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', 'https://scheduler-update-1.preview.emergentagent.com').rstrip('/')

class TestURLFixVerification:
    """Verify URL fix for customer-facing links"""
    
    def test_health_check(self):
        """Test API health"""
        response = requests.get(f"{BASE_URL}/api/health")
        assert response.status_code == 200
        print("Health check passed")
    
    def test_short_url_creation(self):
        """Test short URL API creates shortened links"""
        response = requests.post(f"{BASE_URL}/api/s/create", json={
            "original_url": "https://app.imonsocial.com/review/test-store?sp=test123",
            "link_type": "review_request",
            "user_id": "test123"
        })
        assert response.status_code == 200
        data = response.json()
        
        # Verify response structure
        assert "short_code" in data
        assert "short_url" in data
        assert "original_url" in data
        
        # The original_url should be preserved correctly
        assert data["original_url"] == "https://app.imonsocial.com/review/test-store?sp=test123"
        
        # The short_url will point to current environment (preview or prod)
        # This is expected behavior - short URLs redirect from current domain
        assert "/api/s/" in data["short_url"]
        assert data["short_code"] in data["short_url"]
        
        print(f"Short URL created: {data['short_url']}")
        print(f"Original URL preserved: {data['original_url']}")
    
    def test_short_url_preserves_app_imonsocial_domain(self):
        """Verify original URL with app.imonsocial.com is preserved"""
        test_urls = [
            "https://app.imonsocial.com/p/userId123",          # Digital Card
            "https://app.imonsocial.com/showcase/userId123",   # Showcase
            "https://app.imonsocial.com/l/username",           # Link Page
            "https://app.imonsocial.com/review/store-slug",    # Review
        ]
        
        for url in test_urls:
            response = requests.post(f"{BASE_URL}/api/s/create", json={
                "original_url": url,
                "link_type": "test",
                "user_id": "test_verify"
            })
            assert response.status_code == 200
            data = response.json()
            
            # Original URL must be preserved with app.imonsocial.com domain
            assert data["original_url"] == url
            assert "app.imonsocial.com" in data["original_url"]
            
            print(f"Verified: {url} -> preserved correctly")
    
    def test_short_url_redirect_works(self):
        """Test that short URL redirect actually works"""
        # Create a short URL
        create_response = requests.post(f"{BASE_URL}/api/s/create", json={
            "original_url": "https://app.imonsocial.com/test-redirect",
            "link_type": "test_redirect",
            "user_id": "test_redirect"
        })
        assert create_response.status_code == 200
        short_code = create_response.json()["short_code"]
        
        # Test redirect (don't follow redirects to verify behavior)
        redirect_response = requests.get(
            f"{BASE_URL}/api/s/{short_code}",
            allow_redirects=False
        )
        
        # Should be a redirect (302) to the original URL
        assert redirect_response.status_code == 302
        location = redirect_response.headers.get("Location")
        assert location == "https://app.imonsocial.com/test-redirect"
        
        print(f"Redirect works: /api/s/{short_code} -> {location}")


class TestFrontendCodeVerification:
    """Code review verification tests (assertions based on grep results)"""
    
    def test_frontend_env_has_expo_public_app_url(self):
        """Verify EXPO_PUBLIC_APP_URL is set in frontend .env"""
        env_path = "/app/frontend/.env"
        if os.path.exists(env_path):
            with open(env_path) as f:
                content = f.read()
            assert "EXPO_PUBLIC_APP_URL=https://app.imonsocial.com" in content
            print("Frontend .env contains correct EXPO_PUBLIC_APP_URL")
        else:
            pytest.skip("Frontend .env not accessible from test environment")
    
    def test_backend_env_has_app_url(self):
        """Verify APP_URL is set in backend .env"""
        env_path = "/app/backend/.env"
        if os.path.exists(env_path):
            with open(env_path) as f:
                content = f.read()
            assert 'APP_URL="https://app.imonsocial.com"' in content
            print("Backend .env contains correct APP_URL")
        else:
            pytest.skip("Backend .env not accessible from test environment")
    
    def test_home_tsx_uses_expo_public_app_url(self):
        """Verify home.tsx uses EXPO_PUBLIC_APP_URL for baseUrl"""
        file_path = "/app/frontend/app/(tabs)/home.tsx"
        if os.path.exists(file_path):
            with open(file_path) as f:
                content = f.read()
            # Check for the fix pattern
            assert "process.env.EXPO_PUBLIC_APP_URL || 'https://app.imonsocial.com'" in content
            # Ensure window.location.origin is NOT used for baseUrl
            assert "const baseUrl = window.location.origin" not in content
            print("home.tsx verified: uses EXPO_PUBLIC_APP_URL")
        else:
            pytest.skip("home.tsx not accessible from test environment")
    
    def test_more_tsx_uses_expo_public_app_url(self):
        """Verify more.tsx uses EXPO_PUBLIC_APP_URL for getShowroomUrl"""
        file_path = "/app/frontend/app/(tabs)/more.tsx"
        if os.path.exists(file_path):
            with open(file_path) as f:
                content = f.read()
            assert "process.env.EXPO_PUBLIC_APP_URL || 'https://app.imonsocial.com'" in content
            print("more.tsx verified: uses EXPO_PUBLIC_APP_URL")
        else:
            pytest.skip("more.tsx not accessible from test environment")
    
    def test_no_window_location_origin_for_customer_links(self):
        """Verify no window.location.origin in customer-facing URL generation
        
        Note: Line 1116 in contact/[id].tsx uses window.location.origin as a FALLBACK
        for photo URL absolutization (internal image paths). This is acceptable because:
        1. EXPO_PUBLIC_APP_URL is checked FIRST
        2. The fallback only applies to local dev/preview environments
        3. It's for uploaded images, not customer-facing outgoing links
        """
        import subprocess
        result = subprocess.run(
            ["grep", "-rn", "window.location.origin", "/app/frontend/app/"],
            capture_output=True, text=True
        )
        
        lines = result.stdout.strip().split('\n') if result.stdout.strip() else []
        
        # Filter out node_modules and acceptable uses
        customer_facing_violations = []
        for line in lines:
            # Skip node_modules
            if "node_modules" in line:
                continue
            # contact/[id].tsx line 1116 is for photo URL absolutization - acceptable
            # It uses EXPO_PUBLIC_APP_URL FIRST, window.location.origin is fallback only
            # The line is: const baseUrl = process.env.EXPO_PUBLIC_APP_URL || (IS_WEB ? window.location.origin : ...)
            if "contact/[id].tsx" in line and "EXPO_PUBLIC_APP_URL" in line:
                print(f"Acceptable use (photo URL with EXPO_PUBLIC_APP_URL primary): {line.split(':')[0]}")
                continue
            # Any other use in customer-facing URL paths would be a violation
            customer_facing_violations.append(line)
        
        if customer_facing_violations:
            print(f"WARNING: Found potential window.location.origin uses:")
            for v in customer_facing_violations:
                print(f"  {v}")
        else:
            print("No customer-facing window.location.origin violations found")
        
        # The test passes as long as there are no CUSTOMER-FACING URL violations
        # (excluding internal photo URL handling which has EXPO_PUBLIC_APP_URL as primary)
        assert len(customer_facing_violations) == 0, f"Found violations: {customer_facing_violations}"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

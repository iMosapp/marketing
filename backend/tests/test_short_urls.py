"""
Tests for URL Shortener API
"""
import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', 'https://imos-auth-ui.preview.emergentagent.com')

class TestURLShortener:
    """URL Shortener endpoint tests"""
    
    def test_create_short_url_success(self):
        """Test creating a short URL"""
        response = requests.post(
            f"{BASE_URL}/api/s/create",
            json={
                "original_url": "https://test-example.com/some-long-path?query=param",
                "link_type": "test"
            }
        )
        
        assert response.status_code == 200
        data = response.json()
        
        # Verify response structure
        assert "short_code" in data
        assert "short_url" in data
        assert "original_url" in data
        
        # Verify short_code format
        assert len(data["short_code"]) >= 6
        assert data["original_url"] == "https://test-example.com/some-long-path?query=param"
        
        print(f"PASS: Short URL created: {data['short_url']}")
        return data["short_code"]
    
    def test_create_short_url_missing_url(self):
        """Test creating short URL without required original_url"""
        response = requests.post(
            f"{BASE_URL}/api/s/create",
            json={
                "link_type": "test"
            }
        )
        
        assert response.status_code == 400
        print("PASS: Returns 400 for missing original_url")
    
    def test_redirect_short_url(self):
        """Test short URL redirect - should return 302"""
        # First create a short URL
        create_response = requests.post(
            f"{BASE_URL}/api/s/create",
            json={
                "original_url": "https://example.com/redirect-test",
                "link_type": "test"
            }
        )
        
        assert create_response.status_code == 200
        short_code = create_response.json()["short_code"]
        
        # Test redirect (allow_redirects=False to check the 302)
        redirect_response = requests.get(
            f"{BASE_URL}/api/s/{short_code}",
            allow_redirects=False
        )
        
        assert redirect_response.status_code == 302
        assert redirect_response.headers.get("location") == "https://example.com/redirect-test"
        print(f"PASS: Short URL redirects to correct location")
    
    def test_redirect_nonexistent_short_url(self):
        """Test redirect with non-existent short code"""
        response = requests.get(
            f"{BASE_URL}/api/s/nonexistent123",
            allow_redirects=False
        )
        
        assert response.status_code == 404
        print("PASS: Returns 404 for non-existent short code")
    
    def test_short_url_stats(self):
        """Test getting stats for a short URL"""
        # First create a short URL
        create_response = requests.post(
            f"{BASE_URL}/api/s/create",
            json={
                "original_url": "https://example.com/stats-test",
                "link_type": "test_stats"
            }
        )
        
        assert create_response.status_code == 200
        short_code = create_response.json()["short_code"]
        
        # Get stats
        stats_response = requests.get(
            f"{BASE_URL}/api/s/stats/{short_code}"
        )
        
        assert stats_response.status_code == 200
        stats = stats_response.json()
        
        assert "short_code" in stats
        assert "original_url" in stats
        assert "click_count" in stats
        assert stats["short_code"] == short_code
        assert stats["original_url"] == "https://example.com/stats-test"
        assert stats["link_type"] == "test_stats"
        
        print(f"PASS: Stats retrieved successfully")
    
    def test_short_url_deduplication(self):
        """Test that same URL doesn't create duplicate short codes"""
        unique_url = f"https://example.com/dedup-test-{os.urandom(4).hex()}"
        
        # Create first short URL
        response1 = requests.post(
            f"{BASE_URL}/api/s/create",
            json={
                "original_url": unique_url,
                "link_type": "test_dedup"
            }
        )
        
        assert response1.status_code == 200
        code1 = response1.json()["short_code"]
        
        # Create second short URL with same parameters
        response2 = requests.post(
            f"{BASE_URL}/api/s/create",
            json={
                "original_url": unique_url,
                "link_type": "test_dedup"
            }
        )
        
        assert response2.status_code == 200
        code2 = response2.json()["short_code"]
        
        # Should return the same short code
        assert code1 == code2
        print("PASS: Same URL returns same short code (deduplication works)")


class TestLogin:
    """Login endpoint tests"""
    
    def test_login_sales_user(self):
        """Test login with sales credentials"""
        response = requests.post(
            f"{BASE_URL}/api/auth/login",
            json={
                "email": "sales@mvpline.com",
                "password": "Sales123!"
            }
        )
        
        assert response.status_code == 200
        data = response.json()
        
        assert "token" in data
        assert "user" in data
        assert data["user"]["email"] == "sales@mvpline.com"
        assert data["user"]["role"] == "user"
        
        print("PASS: Sales user login successful")
    
    def test_login_super_admin(self):
        """Test login with super admin credentials"""
        response = requests.post(
            f"{BASE_URL}/api/auth/login",
            json={
                "email": "forest@mvpline.com",
                "password": "MVPLine2024!"
            }
        )
        
        assert response.status_code == 200
        data = response.json()
        
        assert "token" in data
        assert "user" in data
        assert data["user"]["email"] == "forest@mvpline.com"
        assert data["user"]["role"] == "super_admin"
        
        print("PASS: Super admin login successful")
    
    def test_login_invalid_credentials(self):
        """Test login with invalid credentials"""
        response = requests.post(
            f"{BASE_URL}/api/auth/login",
            json={
                "email": "invalid@example.com",
                "password": "wrongpass"
            }
        )
        
        assert response.status_code == 401
        print("PASS: Returns 401 for invalid credentials")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])

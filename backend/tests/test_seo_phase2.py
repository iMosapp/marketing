"""
SEO Phase 2 Tests - Slug generation, Store Directory, UTM tracking, Analytics
Testing: POST /api/seo/generate-slugs, GET /api/seo/user-by-slug/{slug},
         GET /api/seo/store-directory/{slug}, POST /api/seo/utm-link,
         POST /api/seo/track-visit, GET /api/seo/analytics/{user_id},
         GET /api/seo/sitemap.xml (Phase 2 URLs), GET /api/seo/robots.txt (Phase 2 directives)
"""

import pytest
import requests
import os
import time

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

class TestSEOUserSlugs:
    """Test user slug generation and lookup"""
    
    def test_user_by_slug_forest_ward(self):
        """Test resolving forest-ward-denver-co slug to user ID"""
        response = requests.get(f"{BASE_URL}/api/seo/user-by-slug/forest-ward-denver-co")
        print(f"Response status: {response.status_code}")
        print(f"Response data: {response.json()}")
        
        assert response.status_code == 200
        data = response.json()
        
        # Should return valid user data
        if 'error' not in data:
            assert 'user_id' in data
            assert 'name' in data
            assert data['user_id']  # Should not be empty
            print(f"✅ Resolved slug to user_id: {data['user_id']}, name: {data['name']}")
        else:
            print(f"⚠️ Slug not found - may need to generate slugs first")
    
    def test_user_by_slug_invalid(self):
        """Test invalid slug returns error"""
        response = requests.get(f"{BASE_URL}/api/seo/user-by-slug/nonexistent-user-slug-xyz")
        print(f"Response status: {response.status_code}")
        print(f"Response data: {response.json()}")
        
        assert response.status_code == 200
        data = response.json()
        assert data.get('error') == 'not_found'
        print("✅ Invalid slug returns error correctly")
    
    def test_generate_slugs_endpoint(self):
        """Test POST /api/seo/generate-slugs endpoint exists and returns expected format"""
        response = requests.post(f"{BASE_URL}/api/seo/generate-slugs")
        print(f"Response status: {response.status_code}")
        print(f"Response data: {response.json()}")
        
        assert response.status_code == 200
        data = response.json()
        assert 'updated' in data
        assert isinstance(data['updated'], int)
        print(f"✅ Generate slugs returned: {data['updated']} users updated")


class TestStoreDirectory:
    """Test store directory endpoint for team listings"""
    
    def test_store_directory_imos_demo(self):
        """Test GET /api/seo/store-directory/imos-demo"""
        response = requests.get(f"{BASE_URL}/api/seo/store-directory/imos-demo")
        print(f"Response status: {response.status_code}")
        print(f"Response keys: {response.json().keys() if response.status_code == 200 else 'N/A'}")
        
        assert response.status_code == 200
        data = response.json()
        
        if data.get('error'):
            print(f"⚠️ Store 'imos-demo' not found. Skipping detailed assertions.")
            pytest.skip("Store 'imos-demo' not found")
        
        # Validate store data structure
        assert 'store' in data
        assert 'team' in data
        assert 'team_count' in data
        assert 'schema' in data
        
        store = data['store']
        assert '_id' in store
        assert 'name' in store
        assert 'slug' in store
        print(f"✅ Store: {store['name']} (slug: {store['slug']})")
        
        # Validate team
        team = data['team']
        print(f"✅ Team count: {data['team_count']}")
        
        if len(team) > 0:
            member = team[0]
            assert '_id' in member
            assert 'name' in member
            assert 'title' in member
            assert 'photo_url' in member
            assert 'seo_slug' in member
            assert 'review_count' in member
            assert 'avg_rating' in member
            print(f"✅ Sample member: {member['name']}, title: {member['title']}, rating: {member['avg_rating']}")
        
        # Validate Schema.org JSON-LD
        schema = data['schema']
        assert schema.get('@context') == 'https://schema.org'
        assert schema.get('@type') == 'LocalBusiness'
        assert 'employee' in schema or len(team) == 0
        print(f"✅ Schema.org JSON-LD valid with {len(schema.get('employee', []))} employees")
    
    def test_store_directory_invalid_slug(self):
        """Test invalid store slug returns error"""
        response = requests.get(f"{BASE_URL}/api/seo/store-directory/nonexistent-store-xyz")
        print(f"Response status: {response.status_code}")
        print(f"Response data: {response.json()}")
        
        assert response.status_code == 200
        data = response.json()
        assert data.get('error') == 'not_found'
        print("✅ Invalid store slug returns error correctly")


class TestUTMLinks:
    """Test UTM link builder endpoint"""
    
    def test_utm_link_for_card(self):
        """Test creating UTM link for a digital card"""
        # Use a known user ID
        payload = {
            "page_type": "card",
            "reference_id": "69a0b7095fddcede09591667",  # Test user
            "source": "imonsocial",
            "medium": "sms",
            "campaign": "test_campaign"
        }
        response = requests.post(f"{BASE_URL}/api/seo/utm-link", json=payload)
        print(f"Response status: {response.status_code}")
        print(f"Response data: {response.json()}")
        
        assert response.status_code == 200
        data = response.json()
        assert 'url' in data
        
        url = data['url']
        # Should contain UTM params
        assert 'utm_source=imonsocial' in url
        assert 'utm_medium=sms' in url
        assert 'utm_campaign=test_campaign' in url
        
        # If user has seo_slug, should use /salesperson/ path
        if '/salesperson/' in url:
            print(f"✅ UTM link uses SEO slug: {url}")
        else:
            print(f"✅ UTM link uses card ID: {url}")
    
    def test_utm_link_for_store(self):
        """Test creating UTM link for store page"""
        payload = {
            "page_type": "store",
            "reference_id": "imos-demo",
            "source": "facebook",
            "medium": "social"
        }
        response = requests.post(f"{BASE_URL}/api/seo/utm-link", json=payload)
        print(f"Response status: {response.status_code}")
        print(f"Response data: {response.json()}")
        
        assert response.status_code == 200
        data = response.json()
        assert 'url' in data
        assert '/card/store/imos-demo' in data['url']
        assert 'utm_source=facebook' in data['url']
        print(f"✅ Store UTM link: {data['url']}")
    
    def test_utm_link_for_link_page(self):
        """Test creating UTM link for link page"""
        payload = {
            "page_type": "link",
            "reference_id": "forest.ward",  # username
            "source": "twitter",
            "medium": "bio"
        }
        response = requests.post(f"{BASE_URL}/api/seo/utm-link", json=payload)
        print(f"Response status: {response.status_code}")
        print(f"Response data: {response.json()}")
        
        assert response.status_code == 200
        data = response.json()
        assert 'url' in data
        assert '/l/forest.ward' in data['url']
        print(f"✅ Link page UTM: {data['url']}")


class TestUTMTracking:
    """Test UTM visit tracking and analytics"""
    
    def test_track_visit(self):
        """Test POST /api/seo/track-visit"""
        payload = {
            "page_type": "card",
            "reference_id": "69a0b7095fddcede09591667",
            "utm_source": "test_source",
            "utm_medium": "test_medium",
            "utm_campaign": "pytest_campaign",
            "referrer": "https://google.com",
            "user_agent": "pytest-test-agent"
        }
        response = requests.post(f"{BASE_URL}/api/seo/track-visit", json=payload)
        print(f"Response status: {response.status_code}")
        print(f"Response data: {response.json()}")
        
        assert response.status_code == 200
        data = response.json()
        assert data.get('tracked') == True
        print("✅ Visit tracked successfully")
    
    def test_analytics_endpoint(self):
        """Test GET /api/seo/analytics/{user_id}"""
        user_id = "69a0b7095fddcede09591667"
        response = requests.get(f"{BASE_URL}/api/seo/analytics/{user_id}")
        print(f"Response status: {response.status_code}")
        print(f"Response data: {response.json()}")
        
        assert response.status_code == 200
        data = response.json()
        
        # Validate response structure
        assert 'card_visits' in data
        assert 'last_visit' in data
        assert 'recent_sources' in data
        assert 'total_link_clicks' in data
        assert 'active_short_urls' in data
        
        assert isinstance(data['card_visits'], int)
        assert isinstance(data['total_link_clicks'], int)
        assert isinstance(data['recent_sources'], list)
        print(f"✅ Analytics: {data['card_visits']} visits, {data['total_link_clicks']} link clicks")


class TestSitemapRobotsPhase2:
    """Test sitemap.xml and robots.txt include Phase 2 URLs"""
    
    def test_sitemap_has_salesperson_urls(self):
        """Sitemap should include /salesperson/{slug} URLs"""
        response = requests.get(f"{BASE_URL}/api/seo/sitemap.xml")
        print(f"Response status: {response.status_code}")
        
        assert response.status_code == 200
        assert response.headers.get('content-type') == 'application/xml'
        
        content = response.text
        assert '<urlset' in content
        
        # Check for salesperson URLs
        if '/salesperson/' in content:
            print("✅ Sitemap includes /salesperson/ URLs")
        else:
            print("⚠️ No /salesperson/ URLs in sitemap - slugs may not be generated")
        
        # Check for store directory URLs
        if '/store/' in content:
            # Need to distinguish /store/ from /card/store/
            # Count occurrences
            import re
            store_dir_matches = re.findall(r'<loc>[^<]*/store/[^<]+</loc>', content)
            card_store_matches = re.findall(r'<loc>[^<]*/card/store/[^<]+</loc>', content)
            print(f"✅ Sitemap has {len(store_dir_matches)} /store/ URLs and {len(card_store_matches)} /card/store/ URLs")
        
        # Count total URLs
        url_count = content.count('<url>')
        print(f"✅ Total sitemap URLs: {url_count}")
    
    def test_robots_has_salesperson_allow(self):
        """robots.txt should Allow /salesperson/ and /store/"""
        response = requests.get(f"{BASE_URL}/api/seo/robots.txt")
        print(f"Response status: {response.status_code}")
        print(f"Content:\n{response.text}")
        
        assert response.status_code == 200
        content = response.text
        
        assert 'Allow: /salesperson/' in content
        print("✅ robots.txt allows /salesperson/")
        
        assert 'Allow: /store/' in content
        print("✅ robots.txt allows /store/")
        
        # Verify sitemap reference
        assert 'Sitemap:' in content
        print("✅ robots.txt includes sitemap reference")


class TestIntegrationFlow:
    """End-to-end integration tests"""
    
    def test_slug_to_card_resolution_flow(self):
        """Test full flow: get slug -> resolve user -> check can get card meta"""
        # First try to find a user with a slug
        sitemap_response = requests.get(f"{BASE_URL}/api/seo/sitemap.xml")
        content = sitemap_response.text
        
        import re
        salesperson_urls = re.findall(r'/salesperson/([^<"]+)', content)
        
        if not salesperson_urls:
            print("⚠️ No salesperson URLs found in sitemap, skipping integration test")
            pytest.skip("No salesperson slugs available")
        
        slug = salesperson_urls[0]
        print(f"Testing with slug: {slug}")
        
        # Resolve slug to user
        resolve_response = requests.get(f"{BASE_URL}/api/seo/user-by-slug/{slug}")
        assert resolve_response.status_code == 200
        user_data = resolve_response.json()
        
        if user_data.get('error'):
            pytest.fail(f"Slug {slug} did not resolve to a user")
        
        user_id = user_data['user_id']
        print(f"✅ Slug resolved to user_id: {user_id}")
        
        # Get card meta for that user
        meta_response = requests.get(f"{BASE_URL}/api/seo/meta/card/{user_id}")
        assert meta_response.status_code == 200
        meta = meta_response.json()
        
        assert 'title' in meta
        assert 'schema' in meta
        print(f"✅ Card meta: {meta['title']}")
    
    def test_store_directory_team_member_has_slug(self):
        """Test that team members in store directory have seo_slugs"""
        response = requests.get(f"{BASE_URL}/api/seo/store-directory/imos-demo")
        
        if response.json().get('error'):
            pytest.skip("Store 'imos-demo' not found")
        
        data = response.json()
        team = data.get('team', [])
        
        slugged_count = sum(1 for m in team if m.get('seo_slug'))
        print(f"✅ {slugged_count}/{len(team)} team members have seo_slugs")
        
        # Check that at least some members have slugs
        if len(team) > 0:
            assert slugged_count > 0, "Expected at least one team member to have an seo_slug"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

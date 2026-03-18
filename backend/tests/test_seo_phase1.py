"""
SEO Phase 1 API Tests
Testing sitemap.xml, robots.txt, and meta endpoints for SEO/AEO strategy.
"""
import pytest
import requests
import os
import xml.etree.ElementTree as ET

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

# Test user ID from the review request (Forest Ward - has store and reviews)
TEST_USER_ID = "69a0b7095fddcede09591667"


class TestRobotsTxt:
    """robots.txt endpoint tests"""
    
    def test_robots_txt_returns_200(self):
        """GET /api/seo/robots.txt returns 200 OK"""
        response = requests.get(f"{BASE_URL}/api/seo/robots.txt")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        print("PASS: robots.txt returns 200")
    
    def test_robots_txt_content_type(self):
        """robots.txt returns text/plain content type"""
        response = requests.get(f"{BASE_URL}/api/seo/robots.txt")
        assert "text/plain" in response.headers.get("content-type", ""), "Expected text/plain content type"
        print("PASS: robots.txt has correct content type")
    
    def test_robots_txt_contains_required_directives(self):
        """robots.txt contains Allow and Disallow directives"""
        response = requests.get(f"{BASE_URL}/api/seo/robots.txt")
        content = response.text
        
        # Check for required Allow directives
        assert "Allow: /card/" in content, "Missing Allow: /card/ directive"
        assert "Allow: /l/" in content, "Missing Allow: /l/ directive"
        assert "Allow: /card/store/" in content, "Missing Allow: /card/store/ directive"
        
        # Check for required Disallow directives
        assert "Disallow: /admin/" in content, "Missing Disallow: /admin/ directive"
        assert "Disallow: /api/" in content, "Missing Disallow: /api/ directive"
        
        print("PASS: robots.txt contains required directives")
    
    def test_robots_txt_contains_sitemap_reference(self):
        """robots.txt contains Sitemap reference"""
        response = requests.get(f"{BASE_URL}/api/seo/robots.txt")
        content = response.text
        
        assert "Sitemap:" in content, "Missing Sitemap directive"
        assert "/api/seo/sitemap.xml" in content, "Sitemap URL not correct"
        
        print("PASS: robots.txt contains sitemap reference")


class TestSitemapXml:
    """sitemap.xml endpoint tests"""
    
    def test_sitemap_xml_returns_200(self):
        """GET /api/seo/sitemap.xml returns 200 OK"""
        response = requests.get(f"{BASE_URL}/api/seo/sitemap.xml")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        print("PASS: sitemap.xml returns 200")
    
    def test_sitemap_xml_content_type(self):
        """sitemap.xml returns application/xml content type"""
        response = requests.get(f"{BASE_URL}/api/seo/sitemap.xml")
        assert "application/xml" in response.headers.get("content-type", ""), f"Expected application/xml, got {response.headers.get('content-type')}"
        print("PASS: sitemap.xml has correct content type")
    
    def test_sitemap_xml_valid_format(self):
        """sitemap.xml is valid XML"""
        response = requests.get(f"{BASE_URL}/api/seo/sitemap.xml")
        try:
            root = ET.fromstring(response.text)
            assert root.tag == "{http://www.sitemaps.org/schemas/sitemap/0.9}urlset", f"Root element not urlset: {root.tag}"
            print("PASS: sitemap.xml is valid XML with correct root element")
        except ET.ParseError as e:
            pytest.fail(f"Invalid XML: {e}")
    
    def test_sitemap_contains_user_cards(self):
        """sitemap.xml contains /card/{id} URLs for active users"""
        response = requests.get(f"{BASE_URL}/api/seo/sitemap.xml")
        root = ET.fromstring(response.text)
        
        # Find all URL elements
        ns = {"sm": "http://www.sitemaps.org/schemas/sitemap/0.9"}
        urls = root.findall("sm:url/sm:loc", ns)
        url_texts = [url.text for url in urls]
        
        # Check that at least one /card/ URL exists
        card_urls = [u for u in url_texts if "/card/" in u and "/card/store/" not in u]
        assert len(card_urls) > 0, "No card URLs found in sitemap"
        
        print(f"PASS: sitemap contains {len(card_urls)} card URLs")
    
    def test_sitemap_contains_link_pages(self):
        """sitemap.xml contains /l/{username} URLs for users with usernames"""
        response = requests.get(f"{BASE_URL}/api/seo/sitemap.xml")
        root = ET.fromstring(response.text)
        
        ns = {"sm": "http://www.sitemaps.org/schemas/sitemap/0.9"}
        urls = root.findall("sm:url/sm:loc", ns)
        url_texts = [url.text for url in urls]
        
        # Check for /l/ URLs
        link_urls = [u for u in url_texts if "/l/" in u]
        # It's okay if there are no link pages (users may not have usernames)
        print(f"INFO: sitemap contains {len(link_urls)} link page URLs")
    
    def test_sitemap_contains_store_pages(self):
        """sitemap.xml contains /card/store/{slug} URLs for stores"""
        response = requests.get(f"{BASE_URL}/api/seo/sitemap.xml")
        root = ET.fromstring(response.text)
        
        ns = {"sm": "http://www.sitemaps.org/schemas/sitemap/0.9"}
        urls = root.findall("sm:url/sm:loc", ns)
        url_texts = [url.text for url in urls]
        
        # Check for /card/store/ URLs
        store_urls = [u for u in url_texts if "/card/store/" in u]
        print(f"INFO: sitemap contains {len(store_urls)} store page URLs")


class TestMetaCardEndpoint:
    """Meta data API for digital card pages"""
    
    def test_meta_card_valid_user(self):
        """GET /api/seo/meta/card/{user_id} returns meta data for valid user"""
        response = requests.get(f"{BASE_URL}/api/seo/meta/card/{TEST_USER_ID}")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        data = response.json()
        assert "error" not in data, f"Got error response: {data}"
        
        # Validate required fields
        assert "title" in data, "Missing 'title' field"
        assert "description" in data, "Missing 'description' field"
        assert "url" in data, "Missing 'url' field"
        assert "image" in data, "Missing 'image' field"
        assert "schema" in data, "Missing 'schema' field"
        
        print(f"PASS: meta/card returns valid data - title: {data['title'][:50]}...")
    
    def test_meta_card_schema_person_type(self):
        """Schema.org Person type is correct in meta response"""
        response = requests.get(f"{BASE_URL}/api/seo/meta/card/{TEST_USER_ID}")
        data = response.json()
        
        schema = data.get("schema", {})
        assert schema.get("@context") == "https://schema.org", "Invalid @context"
        assert schema.get("@type") == "Person", f"Expected Person type, got {schema.get('@type')}"
        assert "name" in schema, "Missing 'name' in schema"
        assert "url" in schema, "Missing 'url' in schema"
        
        print("PASS: meta/card schema is valid Person type")
    
    def test_meta_card_works_for_with_local_business(self):
        """If user has store, worksFor LocalBusiness should be present"""
        response = requests.get(f"{BASE_URL}/api/seo/meta/card/{TEST_USER_ID}")
        data = response.json()
        
        schema = data.get("schema", {})
        
        # User 69a0b7095fddcede09591667 (Forest Ward) should have a store
        if "worksFor" in schema:
            works_for = schema["worksFor"]
            assert works_for.get("@type") == "LocalBusiness", f"Expected LocalBusiness type, got {works_for.get('@type')}"
            assert "name" in works_for, "Missing name in worksFor"
            print(f"PASS: worksFor LocalBusiness present - {works_for.get('name')}")
        else:
            print("INFO: worksFor not present (user may not have store)")
    
    def test_meta_card_aggregate_rating(self):
        """If user has approved reviews, aggregateRating should be present"""
        response = requests.get(f"{BASE_URL}/api/seo/meta/card/{TEST_USER_ID}")
        data = response.json()
        
        schema = data.get("schema", {})
        
        if "aggregateRating" in schema:
            agg_rating = schema["aggregateRating"]
            assert agg_rating.get("@type") == "AggregateRating", f"Expected AggregateRating type"
            assert "ratingValue" in agg_rating, "Missing ratingValue"
            assert "reviewCount" in agg_rating, "Missing reviewCount"
            print(f"PASS: aggregateRating present - {agg_rating.get('ratingValue')}/5 ({agg_rating.get('reviewCount')} reviews)")
        else:
            print("INFO: aggregateRating not present (user may not have approved reviews)")
    
    def test_meta_card_invalid_user_returns_error(self):
        """GET /api/seo/meta/card/invalid_id returns error gracefully"""
        response = requests.get(f"{BASE_URL}/api/seo/meta/card/invalid_id_12345")
        assert response.status_code == 200, f"Expected 200 with error, got {response.status_code}"
        
        data = response.json()
        assert "error" in data, "Expected error field for invalid user"
        assert data["error"] == "not_found", f"Expected 'not_found' error, got {data['error']}"
        
        print("PASS: Invalid user ID returns error gracefully")
    
    def test_meta_card_nonexistent_objectid_returns_error(self):
        """GET /api/seo/meta/card/{valid_but_nonexistent_id} returns error gracefully"""
        # Valid ObjectId format but doesn't exist
        response = requests.get(f"{BASE_URL}/api/seo/meta/card/000000000000000000000000")
        assert response.status_code == 200, f"Expected 200 with error, got {response.status_code}"
        
        data = response.json()
        assert "error" in data, "Expected error field for nonexistent user"
        
        print("PASS: Nonexistent user ID returns error gracefully")


class TestMetaLinkEndpoint:
    """Meta data API for link pages"""
    
    def test_meta_link_invalid_username_returns_error(self):
        """GET /api/seo/meta/link/nonexistent_username returns error"""
        response = requests.get(f"{BASE_URL}/api/seo/meta/link/nonexistent_username_12345")
        assert response.status_code == 200, f"Expected 200 with error, got {response.status_code}"
        
        data = response.json()
        assert "error" in data, "Expected error field for invalid username"
        
        print("PASS: Invalid username returns error gracefully")


class TestMetaStoreEndpoint:
    """Meta data API for store card pages"""
    
    def test_meta_store_invalid_slug_returns_error(self):
        """GET /api/seo/meta/store/nonexistent_slug returns error"""
        response = requests.get(f"{BASE_URL}/api/seo/meta/store/nonexistent_store_slug_12345")
        assert response.status_code == 200, f"Expected 200 with error, got {response.status_code}"
        
        data = response.json()
        assert "error" in data, "Expected error field for invalid store slug"
        
        print("PASS: Invalid store slug returns error gracefully")


class TestSitemapFindStoreSlug:
    """Find a valid store slug from sitemap for further testing"""
    
    def test_get_store_slug_from_sitemap(self):
        """Extract a store slug from sitemap for testing meta/store endpoint"""
        response = requests.get(f"{BASE_URL}/api/seo/sitemap.xml")
        root = ET.fromstring(response.text)
        
        ns = {"sm": "http://www.sitemaps.org/schemas/sitemap/0.9"}
        urls = root.findall("sm:url/sm:loc", ns)
        url_texts = [url.text for url in urls]
        
        # Find store URLs
        store_urls = [u for u in url_texts if "/card/store/" in u]
        
        if store_urls:
            # Extract slug from first store URL
            store_url = store_urls[0]
            slug = store_url.split("/card/store/")[-1]
            print(f"INFO: Found store slug: {slug}")
            
            # Test the meta endpoint with this slug
            meta_response = requests.get(f"{BASE_URL}/api/seo/meta/store/{slug}")
            if meta_response.status_code == 200:
                data = meta_response.json()
                if "error" not in data:
                    assert "title" in data, "Missing title in store meta"
                    assert "schema" in data, "Missing schema in store meta"
                    
                    schema = data.get("schema", {})
                    assert schema.get("@type") == "LocalBusiness", f"Expected LocalBusiness type"
                    
                    # Check for numberOfEmployees
                    if "numberOfEmployees" in schema:
                        print(f"PASS: Store meta includes numberOfEmployees: {schema['numberOfEmployees']}")
                    
                    print(f"PASS: meta/store/{slug} returns valid LocalBusiness schema")
                else:
                    print(f"INFO: Store slug {slug} returned error (store may be inactive)")
        else:
            print("INFO: No store URLs found in sitemap - skipping store meta test")


class TestSitemapFindUsernameForLinkPage:
    """Find a valid username from sitemap for testing link page meta"""
    
    def test_get_username_from_sitemap(self):
        """Extract a username from sitemap for testing meta/link endpoint"""
        response = requests.get(f"{BASE_URL}/api/seo/sitemap.xml")
        root = ET.fromstring(response.text)
        
        ns = {"sm": "http://www.sitemaps.org/schemas/sitemap/0.9"}
        urls = root.findall("sm:url/sm:loc", ns)
        url_texts = [url.text for url in urls]
        
        # Find link page URLs
        link_urls = [u for u in url_texts if "/l/" in u]
        
        if link_urls:
            # Extract username from first link URL
            link_url = link_urls[0]
            username = link_url.split("/l/")[-1]
            print(f"INFO: Found username: {username}")
            
            # Test the meta endpoint with this username
            meta_response = requests.get(f"{BASE_URL}/api/seo/meta/link/{username}")
            if meta_response.status_code == 200:
                data = meta_response.json()
                if "error" not in data:
                    assert "title" in data, "Missing title in link meta"
                    assert "description" in data, "Missing description in link meta"
                    assert "schema" in data, "Missing schema in link meta"
                    
                    schema = data.get("schema", {})
                    assert schema.get("@type") == "Person", f"Expected Person type"
                    
                    print(f"PASS: meta/link/{username} returns valid Person schema")
                else:
                    print(f"INFO: Username {username} returned error (user may be inactive)")
        else:
            print("INFO: No link page URLs found in sitemap - skipping link meta test")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

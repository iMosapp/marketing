#!/usr/bin/env python3
"""
MVPLine Authentication & Onboarding Flow Test
Focused test for the specific auth and onboarding flow requested
"""

import requests
import json
import random
import string
from datetime import datetime

def generate_test_email():
    """Generate a unique email for testing"""
    random_suffix = ''.join(random.choices(string.ascii_lowercase + string.digits, k=8))
    return f"backendtest_{random_suffix}@test.com"

def test_auth_onboarding_flow():
    """Test the complete authentication and onboarding flow"""
    
    # Backend URL from environment
    base_url = "https://sop-training.preview.emergentagent.com/api"
    
    test_results = {
        "signup": {"status": "FAIL", "details": ""},
        "login": {"status": "FAIL", "details": ""},
        "onboarding": {"status": "FAIL", "details": ""},
        "login_after_onboarding": {"status": "FAIL", "details": ""}
    }
    
    # Generate unique test credentials
    test_email = generate_test_email()
    test_password = "testpass123"
    test_name = "Backend Test User"
    test_phone = "+15551234567"
    
    print(f"🧪 Starting Backend API Test for Auth & Onboarding Flow")
    print(f"📧 Test Email: {test_email}")
    print(f"🔗 Backend URL: {base_url}")
    print("=" * 80)
    
    # 1. Test Signup
    print("1️⃣  Testing Signup - POST /api/auth/signup")
    try:
        signup_data = {
            "email": test_email,
            "password": test_password,
            "name": test_name,
            "phone": test_phone
        }
        
        response = requests.post(f"{base_url}/auth/signup", json=signup_data, timeout=10)
        print(f"   Status Code: {response.status_code}")
        
        if response.status_code == 200:
            signup_result = response.json()
            print(f"   ✅ Response Structure: {list(signup_result.keys())}")
            print(f"   📋 Full Response: {json.dumps(signup_result, indent=2)}")
            
            # Verify required fields
            if "_id" in signup_result and "onboarding_complete" in signup_result:
                if signup_result["onboarding_complete"] == False:
                    test_results["signup"]["status"] = "PASS"
                    test_results["signup"]["details"] = f"User created with ID: {signup_result['_id']}, onboarding_complete: false"
                    user_id = signup_result["_id"]
                else:
                    test_results["signup"]["details"] = f"onboarding_complete should be false for new users, got: {signup_result['onboarding_complete']}"
            else:
                test_results["signup"]["details"] = f"Missing required fields: _id={signup_result.get('_id', 'MISSING')}, onboarding_complete={signup_result.get('onboarding_complete', 'MISSING')}"
        else:
            test_results["signup"]["details"] = f"HTTP {response.status_code}: {response.text}"
            
    except Exception as e:
        test_results["signup"]["details"] = f"Request failed: {str(e)}"
        print(f"   ❌ Error: {str(e)}")
        return test_results  # Exit early if signup fails
    
    # 2. Test Login
    print("\n2️⃣  Testing Login - POST /api/auth/login")
    try:
        login_data = {
            "email": test_email,
            "password": test_password
        }
        
        response = requests.post(f"{base_url}/auth/login", json=login_data, timeout=10)
        print(f"   Status Code: {response.status_code}")
        
        if response.status_code == 200:
            login_result = response.json()
            print(f"   ✅ Response Structure: {list(login_result.keys())}")
            print(f"   📋 Full Response: {json.dumps(login_result, indent=2)}")
            
            # Verify required fields
            if "user" in login_result and "token" in login_result:
                user_data = login_result["user"]
                if "_id" in user_data:
                    test_results["login"]["status"] = "PASS"
                    onboarding_status = user_data.get('onboarding_complete', 'not_set')
                    test_results["login"]["details"] = f"Login successful, user ID: {user_data['_id']}, token received, onboarding_complete: {onboarding_status}"
                    user_id = user_data["_id"]
                    auth_token = login_result["token"]
                else:
                    test_results["login"]["details"] = f"Missing required field _id in user object: {user_data.get('_id', 'MISSING')}"
            else:
                test_results["login"]["details"] = f"Missing required fields: user={login_result.get('user', 'MISSING')}, token={login_result.get('token', 'MISSING')}"
        else:
            test_results["login"]["details"] = f"HTTP {response.status_code}: {response.text}"
            
    except Exception as e:
        test_results["login"]["details"] = f"Request failed: {str(e)}"
        print(f"   ❌ Error: {str(e)}")
        return test_results  # Exit early if login fails
    
    # 3. Test Onboarding
    print("\n3️⃣  Testing Onboarding - POST /api/onboarding/profile/{user_id}")
    try:
        persona_data = {
            "tone": "professional",
            "emoji_use": "light",
            "humor_level": "some",
            "brevity": "balanced",
            "professional_identity": "Sales Professional",
            "interests": ["technology", "sales", "networking"],
            "escalation_keywords": ["urgent", "asap", "emergency"]
        }
        
        print(f"   🎯 User ID: {user_id}")
        print(f"   📦 Persona Data: {json.dumps(persona_data, indent=2)}")
        
        response = requests.post(f"{base_url}/onboarding/profile/{user_id}", json=persona_data, timeout=10)
        print(f"   Status Code: {response.status_code}")
        
        if response.status_code == 200:
            onboarding_result = response.json()
            print(f"   ✅ Response: {json.dumps(onboarding_result, indent=2)}")
            
            if "message" in onboarding_result and "success" in onboarding_result["message"].lower():
                test_results["onboarding"]["status"] = "PASS"
                test_results["onboarding"]["details"] = "Onboarding persona saved successfully"
            else:
                test_results["onboarding"]["details"] = f"Unexpected response format: {onboarding_result}"
        else:
            test_results["onboarding"]["details"] = f"HTTP {response.status_code}: {response.text}"
            
    except Exception as e:
        test_results["onboarding"]["details"] = f"Request failed: {str(e)}"
        print(f"   ❌ Error: {str(e)}")
        return test_results  # Exit early if onboarding fails
    
    # 4. Test Login After Onboarding
    print("\n4️⃣  Testing Login After Onboarding - POST /api/auth/login")
    try:
        login_data = {
            "email": test_email,
            "password": test_password
        }
        
        response = requests.post(f"{base_url}/auth/login", json=login_data, timeout=10)
        print(f"   Status Code: {response.status_code}")
        
        if response.status_code == 200:
            final_login_result = response.json()
            print(f"   ✅ Response Structure: {list(final_login_result.keys())}")
            print(f"   📋 Full Response: {json.dumps(final_login_result, indent=2)}")
            
            # Verify onboarding_complete is now true and persona data is included
            if "user" in final_login_result:
                user_data = final_login_result["user"]
                onboarding_status = user_data.get("onboarding_complete")
                persona_data = user_data.get("persona")
                
                print(f"   🔍 Onboarding Complete: {onboarding_status}")
                print(f"   🔍 Persona Present: {bool(persona_data)}")
                
                if onboarding_status == True:
                    if persona_data and isinstance(persona_data, dict) and len(persona_data) > 0:
                        test_results["login_after_onboarding"]["status"] = "PASS"
                        test_results["login_after_onboarding"]["details"] = "Login after onboarding successful, onboarding_complete: true, persona data included"
                    else:
                        test_results["login_after_onboarding"]["details"] = f"onboarding_complete is true but persona data missing or empty: {persona_data}"
                else:
                    test_results["login_after_onboarding"]["details"] = f"onboarding_complete should be true, got: {onboarding_status}"
            else:
                test_results["login_after_onboarding"]["details"] = "Missing user object in response"
        else:
            test_results["login_after_onboarding"]["details"] = f"HTTP {response.status_code}: {response.text}"
            
    except Exception as e:
        test_results["login_after_onboarding"]["details"] = f"Request failed: {str(e)}"
        print(f"   ❌ Error: {str(e)}")
    
    return test_results

def print_test_summary(results):
    """Print a summary of test results"""
    print("\n" + "=" * 80)
    print("🏁 TEST SUMMARY")
    print("=" * 80)
    
    total_tests = len(results)
    passed_tests = sum(1 for result in results.values() if result["status"] == "PASS")
    
    for test_name, result in results.items():
        status_icon = "✅" if result["status"] == "PASS" else "❌"
        print(f"{status_icon} {test_name.upper()}: {result['status']} - {result['details']}")
    
    print(f"\n📊 Results: {passed_tests}/{total_tests} tests passed")
    
    if passed_tests == total_tests:
        print("🎉 ALL TESTS PASSED! Authentication and onboarding flow is working correctly.")
        return True
    else:
        print("⚠️  SOME TESTS FAILED. Please check the details above.")
        return False

if __name__ == "__main__":
    results = test_auth_onboarding_flow()
    success = print_test_summary(results)
    exit(0 if success else 1)
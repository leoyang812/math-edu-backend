import requests
import json

def test_signup():
    url = "http://localhost:8000/api/users/signup"
    
    # Test data
    test_user = {
        "name": "Test Student",
        "email": "teststudent@example.com",
        "password": "testpassword123",
        "language": "en"
    }
    
    try:
        print("Testing signup endpoint...")
        response = requests.post(url, json=test_user)
        
        print(f"Status Code: {response.status_code}")
        print(f"Response: {response.text}")
        
        if response.status_code == 200:
            print("✅ Signup successful!")
        else:
            print("❌ Signup failed!")
            
    except requests.exceptions.ConnectionError:
        print("❌ Could not connect to server. Make sure the backend is running on http://localhost:8000")
    except Exception as e:
        print(f"❌ Error: {e}")

if __name__ == "__main__":
    test_signup() 
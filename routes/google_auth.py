# routes/google_auth.py
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
import httpx
import os
from dotenv import load_dotenv
from motor.motor_asyncio import AsyncIOMotorClient
from bcrypt import hashpw, gensalt
import uuid
import jwt
from datetime import datetime, timedelta

load_dotenv()

# Database connection
client = AsyncIOMotorClient(os.getenv("MONGODB_URI"))
db = client["math_edu_db"]

router = APIRouter(prefix="/api/auth", tags=["google-auth"])

class GoogleAuthRequest(BaseModel):
    code: str

# Google OAuth configuration
GOOGLE_CLIENT_ID = os.getenv("GOOGLE_CLIENT_ID")
GOOGLE_CLIENT_SECRET = os.getenv("GOOGLE_CLIENT_SECRET")
GOOGLE_REDIRECT_URI = os.getenv("GOOGLE_REDIRECT_URI", "http://localhost:5173/auth/google/callback")
JWT_SECRET = os.getenv("JWT_SECRET", "your-secret-key")

@router.post("/google")
async def google_auth(request: GoogleAuthRequest):
    """
    Handle Google OAuth authentication
    """
    try:
        # Exchange authorization code for access token
        token_url = "https://oauth2.googleapis.com/token"
        token_data = {
            "client_id": GOOGLE_CLIENT_ID,
            "client_secret": GOOGLE_CLIENT_SECRET,
            "code": request.code,
            "grant_type": "authorization_code",
            "redirect_uri": GOOGLE_REDIRECT_URI
        }
        
        async with httpx.AsyncClient() as client:
            token_response = await client.post(token_url, data=token_data)
            token_response.raise_for_status()
            token_info = token_response.json()
            
            access_token = token_info["access_token"]
            
            # Get user info from Google
            user_info_url = "https://www.googleapis.com/oauth2/v2/userinfo"
            headers = {"Authorization": f"Bearer {access_token}"}
            user_response = await client.get(user_info_url, headers=headers)
            user_response.raise_for_status()
            user_info = user_response.json()
            
        # Extract user data
        google_id = user_info["id"]
        email = user_info["email"]
        name = user_info.get("name", "")
        picture = user_info.get("picture", "")
        
        # Check if user already exists
        existing_user = await db.users.find_one({"email": email})
        
        if existing_user:
            # User exists, generate JWT token
            user_id = existing_user["id"]
            role = existing_user["role"]
        else:
            # Create new user
            user_id = str(uuid.uuid4())
            role = "student"  # Default role for Google sign-up
            
            # Create user document
            user_doc = {
                "id": user_id,
                "googleId": google_id,
                "name": name,
                "email": email,
                "picture": picture,
                "role": role,
                "language": "en",
                "tutorId": None,
                "studentIds": [],
                "parentIds": [],
                "classroomIds": [],
                "disabled": False,
                "performanceData": {
                    "totalCorrect": 0,
                    "totalAttempts": 0,
                    "avgTimeTaken": 0.0,
                },
                "createdAt": datetime.utcnow(),
                "authProvider": "google"
            }
            
            await db.users.insert_one(user_doc)
        
        # Generate JWT token
        payload = {
            "user_id": user_id,
            "email": email,
            "role": role,
            "exp": datetime.utcnow() + timedelta(days=7)
        }
        
        token = jwt.encode(payload, JWT_SECRET, algorithm="HS256")
        
        # Get updated user info
        user = await db.users.find_one({"id": user_id})
        
        return {
            "access_token": token,
            "token_type": "bearer",
            "user": {
                "id": user["id"],
                "name": user["name"],
                "email": user["email"],
                "role": user["role"],
                "picture": user.get("picture", ""),
                "language": user.get("language", "en")
            }
        }
        
    except httpx.HTTPStatusError as e:
        raise HTTPException(status_code=400, detail=f"Google OAuth error: {e.response.text}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Authentication failed: {str(e)}") 
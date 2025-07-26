# Google OAuth Setup Guide

## Step 1: Create Google Cloud Project

1. Go to [Google Cloud Console](https://console.cloud.google.com/)
2. Create a new project or select an existing one
3. Enable the Google+ API and Google OAuth2 API

## Step 2: Configure OAuth Consent Screen

1. Go to "APIs & Services" > "OAuth consent screen"
2. Choose "External" user type
3. Fill in the required information:
   - App name: "Math Education App"
   - User support email: your email
   - Developer contact information: your email
4. Add scopes:
   - `openid`
   - `email`
   - `profile`
5. Add test users (your email addresses)

## Step 3: Create OAuth 2.0 Credentials

1. Go to "APIs & Services" > "Credentials"
2. Click "Create Credentials" > "OAuth 2.0 Client IDs"
3. Choose "Web application"
4. Set the following:
   - Name: "Math Education App Web Client"
   - Authorized JavaScript origins:
     - `http://localhost:5173`
     - `http://localhost:3000`
   - Authorized redirect URIs:
     - `http://localhost:5173/auth/google/callback`
     - `http://localhost:3000/auth/google/callback`
5. Click "Create"
6. Copy the Client ID and Client Secret

## Step 4: Configure Environment Variables

Add these to your `.env` file:

```env
GOOGLE_CLIENT_ID=your-client-id.apps.googleusercontent.com
GOOGLE_CLIENT_SECRET=your-client-secret
GOOGLE_REDIRECT_URI=http://localhost:5173/auth/google/callback
JWT_SECRET=your-super-secret-jwt-key
```

## Step 5: Update Frontend Configuration

In `Frontend/math-question-app2/src/components/Signup.jsx`, replace:
```javascript
const GOOGLE_CLIENT_ID = "YOUR_GOOGLE_CLIENT_ID.apps.googleusercontent.com";
```

With your actual Google Client ID.

## Step 6: Test the Integration

1. Start your backend server
2. Start your frontend application
3. Go to the signup page
4. Click "Sign up with Google"
5. Complete the OAuth flow

## Security Notes

- Never commit your `.env` file to version control
- Use environment variables for all sensitive data
- Regularly rotate your JWT secret
- Consider using refresh tokens for better security
- Implement proper error handling for OAuth failures

## Troubleshooting

### Common Issues:

1. **"redirect_uri_mismatch"**: Make sure the redirect URI in Google Console matches exactly
2. **"invalid_client"**: Check that your Client ID and Secret are correct
3. **CORS errors**: Ensure your backend CORS settings include your frontend URL
4. **"access_denied"**: User may have denied permission or consent screen not configured

### Debug Steps:

1. Check browser console for errors
2. Check backend logs for OAuth errors
3. Verify all environment variables are set correctly
4. Test with a different browser or incognito mode 
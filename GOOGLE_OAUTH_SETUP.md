# Google OAuth Setup Guide

## 1. Create Google Cloud Project

1. Go to [Google Cloud Console](https://console.cloud.google.com/)
2. Click "Select a project" → "NEW PROJECT"
3. Name it "ShipS Auth" (or whatever you prefer)
4. Click "CREATE"

## 2. Enable Google+ API

1. In the Google Cloud Console, go to "APIs & Services" → "Library"
2. Search for "Google+ API"
3. Click on it and press "ENABLE"

## 3. Create OAuth 2.0 Credentials

1. Go to "APIs & Services" → "Credentials"
2. Click "CREATE CREDENTIALS" → "OAuth client ID"
3. If prompted, configure the OAuth consent screen:
   - User Type: External
   - App name: ShipS*
   - User support email: your email
   - Developer contact: your email
   - Click "SAVE AND CONTINUE" through the remaining steps
4. Back in "Credentials", click "CREATE CREDENTIALS" → "OAuth client ID" again
5. Application type: "Web application"
6. Name: "ShipS Backend"
7. Authorized redirect URIs:
   - `http://localhost:8001/auth/google/callback`
8. Click "CREATE"
9. Copy the **Client ID** and **Client Secret**

## 4. Configure Environment Variables

Add to your `.env` file:

```
GOOGLE_CLIENT_ID=your-client-id-here.apps.googleusercontent.com
GOOGLE_CLIENT_SECRET=your-client-secret-here
SECRET_KEY=your-random-secret-key
```

Generate a secret key:
```bash
python -c "import secrets; print(secrets.token_urlsafe(32))"
```

## 5. Install Dependencies

```bash
cd ships-backend
pip install authlib itsdangerous
```

## 6. Test OAuth Flow

1. Start the backend: `uvicorn main:app --reload --port 8001`
2. Start the frontend: `npm run dev`
3. Click "Sign in with Google" button
4. You should be redirected to Google's consent screen
5. After approving, you'll be redirected back and logged in

## Troubleshooting

### "redirect_uri_mismatch" error
- Make sure `http://localhost:8001/auth/google/callback` is added to authorized redirect URIs
- Match the port exactly (8001)

### "access_denied" error
- User declined permissions
- Try again and click "Allow"

### Session not persisting
- Check that `SECRET_KEY` is set in `.env`
- Verify CORS is configured with `allow_credentials=True`

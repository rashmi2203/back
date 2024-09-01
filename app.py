import os
from flask import Flask, redirect, url_for, session, request
from flask import render_template
import msal

app = Flask(__name__)
app.secret_key = os.environ.get('FLASK_SECRET_KEY')  # Your Flask secret key

# Azure AD configuration
CLIENT_ID = os.environ.get('AZURE_CLIENT_ID')
CLIENT_SECRET = os.environ.get('AZURE_CLIENT_SECRET')
TENANT_ID = os.environ.get('AZURE_TENANT_ID')
AUTHORITY = f'https://login.microsoftonline.com/{TENANT_ID}'
REDIRECT_PATH = 'https://back1-dfcxgahzd2ewa8cf.eastasia-01.azurewebsites.net/getAToken'  # Must be the same as the redirect URI in Azure AD
SCOPE = ["User.Read"]  # Example scope

# MSAL configuration
app.config.update(
    CLIENT_ID=CLIENT_ID,
    CLIENT_SECRET=CLIENT_SECRET,
    AUTHORITY=AUTHORITY,
    REDIRECT_PATH=REDIRECT_PATH,
    SCOPE=SCOPE
)

# Create an MSAL instance
def _build_msal_app(cache=None):
    return msal.ConfidentialClientApplication(
        app.config['CLIENT_ID'],
        authority=app.config['AUTHORITY'],
        client_credential=app.config['CLIENT_SECRET'],
        token_cache=cache
    )

# Route to handle login
@app.route('/login')
def login():
    msal_app = _build_msal_app()
    auth_url = msal_app.get_authorization_request_url(
        scopes=app.config['SCOPE'],
        redirect_uri=url_for('authorized', _external=True)
    )
    return redirect(auth_url)

# Route to handle callback
@app.route(app.config['REDIRECT_PATH'])
def authorized():
    if 'error' in request.args:
        return f"Error: {request.args['error_description']}", 400
    
    msal_app = _build_msal_app()
    result = msal_app.acquire_token_by_authorization_code(
        request.args.get('code'),
        scopes=app.config['SCOPE'],
        redirect_uri=url_for('authorized', _external=True)
    )

    if 'access_token' in result:
        session['access_token'] = result['access_token']
        return redirect(url_for('profile'))
    else:
        return "Could not authenticate", 401

# Route to display user profile
@app.route('/profile')
def profile():
    if 'access_token' not in session:
        return redirect(url_for('login'))
    
    msal_app = _build_msal_app()
    user_info = msal_app.get('/me', headers={
        'Authorization': f'Bearer {session["access_token"]}'
    }).json()

    return render_template('profile.html', user_info=user_info)

# Route to log out
@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('home'))

# Home route
@app.route('/')
def home():
    return 'Welcome to the Home Page! <a href="/login">Login with Azure AD</a>'

if __name__ == '__main__':
    app.run(debug=True)

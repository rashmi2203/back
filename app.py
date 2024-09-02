import os
from flask import Flask, redirect, url_for, session, request, render_template
import msal
import pyodbc
import requests

app = Flask(__name__)
app.secret_key = os.environ.get('FLASK_SECRET_KEY')  # Your Flask secret key

# Azure AD configuration
CLIENT_ID = os.environ.get('AZURE_CLIENT_ID')
CLIENT_SECRET = os.environ.get('AZURE_CLIENT_SECRET')
TENANT_ID = os.environ.get('AZURE_TENANT_ID')
AUTHORITY = f'https://login.microsoftonline.com/{TENANT_ID}'
REDIRECT_URI = 'https://back1-dfcxgahzd2ewa8cf.eastasia-01.azurewebsites.net/getAToken'  # Must be the same as the redirect URI in Azure AD
SCOPE = ["User.Read"]  # Example scope

# MSAL configuration
app.config.update(
    CLIENT_ID=CLIENT_ID,
    CLIENT_SECRET=CLIENT_SECRET,
    AUTHORITY=AUTHORITY,
    REDIRECT_URI=REDIRECT_URI,
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

# Database connection function
def get_db_connection():
    conn_str = (
        f"Driver={{ODBC Driver 17 for SQL Server}};"
        f"Server={os.environ.get('DB_SERVER')};"
        f"Database={os.environ.get('DB_NAME')};"
        f"UID={os.environ.get('DB_USER')};"
        f"PWD={os.environ.get('DB_PASSWORD')};"
    )
    return pyodbc.connect(conn_str)

# Route to handle login
@app.route('/login')
def login():
    msal_app = _build_msal_app()
    auth_url = msal_app.get_authorization_request_url(
        scopes=app.config['SCOPE'],
        redirect_uri=app.config['REDIRECT_URI']
    )
    return redirect(auth_url)

# Route to handle callback
@app.route('/getAToken')
def authorized():
    if 'error' in request.args:
        return f"Error: {request.args['error_description']}", 400
    
    msal_app = _build_msal_app()
    result = msal_app.acquire_token_by_authorization_code(
        request.args.get('code'),
        scopes=app.config['SCOPE'],
        redirect_uri=app.config['REDIRECT_URI']
    )

    if 'access_token' in result:
        session['access_token'] = result['access_token']

        # Fetch user info from Microsoft Graph
        user_info = requests.get(
            'https://graph.microsoft.com/v1.0/me',
            headers={'Authorization': f'Bearer {session["access_token"]}'}
        ).json()

        session['user_email'] = user_info.get('mail')  # Store user's email in session

        # Store the user data in the database
        conn = get_db_connection()
        cursor = conn.cursor()

        # Check if the user already exists in the database
        cursor.execute('SELECT * FROM Users WHERE email = ?', (session['user_email'],))
        existing_user = cursor.fetchone()

        if not existing_user:
            # Insert new user into the database
            cursor.execute('''
                INSERT INTO Users (username, email, name)
                VALUES (?, ?, ?)
            ''', (user_info.get('userPrincipalName'), user_info.get('mail'), user_info.get('displayName')))
            conn.commit()

        conn.close()

        return redirect(url_for('profile'))
    else:
        return "Could not authenticate", 401
    
@app.route('/testdb')
def test_db_connection():
    try:
        conn = get_db_connection()
        conn.close()
        return "Database connection successful!"
    except Exception as e:
        return f"Error connecting to database: {str(e)}"


# Route to display user profile
@app.route('/profile')
def profile():
    if 'access_token' not in session:
        return redirect(url_for('login'))
    
    # Fetch user info from Microsoft Graph
    user_info = requests.get(
        'https://graph.microsoft.com/v1.0/me',
        headers={'Authorization': f'Bearer {session["access_token"]}'}
    ).json()

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

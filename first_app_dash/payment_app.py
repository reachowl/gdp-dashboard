import dash
from dash import dcc, html
from dash.dependencies import Input, Output, State
import dash_bootstrap_components as dbc
import pandas as pd
import datetime
import random
import threading
import os
import sys

# Attempt to import pyngrok and jupyter-dash; install if necessary (robustness)
try:
    from pyngrok import ngrok, conf
    from jupyter_dash import JupyterDash 
except ImportError:
    print("Installing necessary packages (pyngrok, jupyter-dash, dash-bootstrap-components)...")
    os.system('pip install pyngrok jupyter-dash dash-bootstrap-components --quiet')
    try:
        from pyngrok import ngrok, conf
        from jupyter_dash import JupyterDash
    except ImportError:
        print("ERROR: Failed to install packages. Please run 'python -m pip install pyngrok jupyter-dash dash-bootstrap-components' manually.")
        sys.exit(1)


# --- 1. CONFIGURATION (CRITICAL STEP) ---

# !!! IMPORTANT: REPLACE THIS LINE with your actual ngrok Auth Token !!!
NGROK_TOKEN = "33vBKy0TNn1qUvuQGdO2pfa8Ah1_3x2GVTXoBe6YdK9bYVmSh" 
conf.get_default().auth_token = NGROK_TOKEN 
DASH_PORT = 8055 # Using 8052 to avoid past conflicts

# --- 2. DATA GENERATION (165 Units in 88/xx Format) ---

house_ids = [f"88/{i:02d}" for i in range(1, 166)]
thai_first_names = ["Piyachat", "Somsak", "Chai", "Wichai", "Kanda", "Aree"]
thai_last_names = ["Wong", "Saetang", "Chotikul", "Sukhothai", "Prasert", "Thongdee"]

USER_DATA_LIST = []
for i, unit_id in enumerate(house_ids):
    first = random.choice(thai_first_names)
    last = random.choice(thai_last_names)
    name = f"{first} {last}" 
    balance = random.choice([-50000, -100000, 0, 50000])
    charge = random.choice([50000, 75000])
    
    start_date = datetime.date.today() - datetime.timedelta(days=180)
    random_days = random.randint(0, 180)
    last_payment_date = start_date + datetime.timedelta(days=random_days)
    
    password = '1234' if unit_id == '88/01' else str(random.randint(1000, 9999))
    
    USER_DATA_LIST.append({
        'House_ID': unit_id, 'Password': password, 'Full_Name': name, 
        'Current_Balance': balance, 'Monthly_Charge': charge, 
        'Last_Payment': last_payment_date.strftime('%Y-%m-%d')
    })

USER_DATA = pd.DataFrame(USER_DATA_LIST)
print(f"Generated {len(USER_DATA)} user records.") 

RECEIPT_HISTORY = pd.DataFrame(columns=['House_ID', 'Amount', 'Purpose', 'Date', 'Receipt_Filename'])

# --- 3. DASH APPLICATION SETUP & HELPERS ---
app = JupyterDash(__name__, external_stylesheets=[dbc.themes.LUMEN], suppress_callback_exceptions=True)

def calculate_due_date(last_payment_str):
    if pd.isna(last_payment_str): return 'N/A'
    try:
        last_payment = datetime.datetime.strptime(last_payment_str, '%Y-%m-%d').date()
    except ValueError: return 'N/A'
    
    current_year = last_payment.year
    current_month = last_payment.month
    
    if current_month == 12:
        next_month_date = datetime.date(current_year + 1, 1, 1)
    else:
        next_month_date = datetime.date(current_year, current_month + 1, 1)
    return next_month_date.strftime('%Y-%m-%d')
        
def format_currency(value): return f"Rp{abs(value):,.0f}"

def create_kpi_card(title, value, footer_text, color):
    return dbc.Card(
        dbc.CardBody([
            html.H6(title, className="card-title text-muted"),
            html.H3(value, className=f"card-text text-{color}"),
        ], style={'padding': '10px'}),
        dbc.CardFooter(footer_text, style={'fontSize': '0.75em'}),
        className="shadow-sm border-0 mb-3"
    )

# --- 4. LAYOUT COMPONENTS ---
dropdown_options = [{'label': f'Unit {id}', 'value': id} for id in house_ids]

login_layout = dbc.Container(
    [
        html.H4("🏡 Homeowner Maintenance Fee Portal", className="text-center text-primary my-4"),
        dbc.Card(
            dbc.CardBody([
                html.P("House ID:", className="mb-1"),
                dcc.Dropdown(id="house-id-input", options=dropdown_options, placeholder="Select House ID (e.g., 88/01)", className="mb-3", searchable=True ),
                dbc.Input(id="password-input", type="password", placeholder="Enter Password", className="mb-4"),
                dbc.Button("Login", id="login-button", color="success", className="w-100"),
                html.Div(id="login-status", className="mt-3 text-center")
            ])
        )
    ], fluid=True, className="p-3")

def create_dashboard_layout(user_data):
    user = user_data.iloc[0]
    balance_color = 'danger' if user['Current_Balance'] < 0 else 'success'
    balance_text = 'Outstanding' if user['Current_Balance'] < 0 else 'Credit'
    due_date = calculate_due_date(user['Last_Payment'])
    
    dashboard = dbc.Container([
        html.H5(f"Welcome, {user['Full_Name']} (Unit {user['House_ID']})!", className="text-center my-3 text-info"),
        html.Hr(className="mb-4"),
        dbc.Row([
            dbc.Col(create_kpi_card("Current Balance", format_currency(user['Current_Balance']), f"Status: {balance_text}", balance_color), xs=12, md=4),
            dbc.Col(create_kpi_card("Monthly Charge", format_currency(user['Monthly_Charge']), "Standard contribution amount.", 'primary'), xs=12, md=4),
            dbc.Col(create_kpi_card("Next Payment Due", due_date, "Based on last recorded payment.", 'info'), xs=12, md=4),
        ]),
        html.H5("💸 Submit New Receipt", className="mt-4 mb-3 text-primary"),
        dbc.Card(dbc.CardBody([
            dbc.Input(id="amount-input", type="number", placeholder="Transfer Amount", className="mb-3"),
            dbc.Input(id="purpose-input", type="text", placeholder="Payment Purpose", className="mb-4"),
            dcc.Upload(id='upload-receipt', children=html.Div(['Drag and Drop or ', html.A('Select Receipt File', className="text-info")]), style={'width': '100%', 'height': '60px', 'lineHeight': '60px', 'borderWidth': '1px', 'borderStyle': 'dashed', 'borderRadius': '5px', 'textAlign': 'center', 'marginBottom': '20px', 'cursor': 'pointer'}, accept='image/*', multiple=False ),
            html.Div(id='upload-status', className="text-muted small mb-4"),
            dbc.Button("Submit & Close LIFF", id="submit-button", color="success", className="w-100", n_clicks=0),
        ])),
        dcc.Store(id='current-house-id', data=user['House_ID']),
        html.Div(id='liff-command-output', style={'display': 'none'}),
    ], fluid=True, className="p-3")
    return dashboard

# --- 5. CALLBACKS ---

app.layout = html.Div([dcc.Location(id='url', refresh=False), html.Div(id='page-content', children=login_layout)])

@app.callback(
    [Output('page-content', 'children'), Output('login-status', 'children')],
    [Input('login-button', 'n_clicks')],
    [State('house-id-input', 'value'), State('password-input', 'value')]
)
def authenticate_user(n_clicks, house_id, password):
    if n_clicks is None or n_clicks == 0: return dash.no_update, ""
    input_house_id = str(house_id).strip() if house_id else '' 
    input_password = str(password).strip() if password else ''

    if not input_house_id or not input_password: return dash.no_update, dbc.Alert("Please select an ID and enter the Password.", color="warning", className="mb-0")
    user_match = USER_DATA[(USER_DATA['House_ID'] == input_house_id) & (USER_DATA['Password'] == input_password)]
    
    if not user_match.empty: return create_dashboard_layout(user_match), ""
    else: return dash.no_update, dbc.Alert(f"Invalid House ID or Password. Try 88/01/1234.", color="danger", className="mb-0")


@app.callback(
    [Output('upload-status', 'children'), Output('liff-command-output', 'children'), Output('page-content', 'children', allow_duplicate=True)],
    [Input('submit-button', 'n_clicks')],
    [State('upload-receipt', 'contents'), State('upload-receipt', 'filename'), State('amount-input', 'value'), State('purpose-input', 'value'), State('current-house-id', 'data')],
    prevent_initial_call=True
)
def process_submission(n_clicks, contents, filename, amount, purpose, house_id):
    global USER_DATA
    if n_clicks is None or n_clicks == 0: return dash.no_update, dash.no_update, dash.no_update
    if contents is None or not amount or not purpose: return "❌ Please fill in all fields and upload a receipt.", dash.no_update, dash.no_update

    try: amount = int(amount)
    except (ValueError, TypeError): return "❌ Amount must be a valid number.", dash.no_update, dash.no_update

    USER_DATA.loc[USER_DATA['House_ID'] == house_id, 'Current_Balance'] += amount
    USER_DATA.loc[USER_DATA['House_ID'] == house_id, 'Last_Payment'] = datetime.date.today().strftime('%Y-%m-%d')
    liff_script = html.Script("if (liff && liff.isInClient()) { liff.closeWindow(); }")
    
    return ("✅ Submission successful! Window is closing...", liff_script, dash.no_update)


# --- 6. NGORK EXECUTION BLOCK (Standard Python Script Run) ---

if __name__ == '__main__':
    
    try:
        # Start Dash app in a dedicated thread
        def run_app():
            app.run(host='0.0.0.0', port=DASH_PORT, debug=False, dev_tools_hot_reload=False, threaded=True)

        thread = threading.Thread(target=run_app)
        thread.start()
        
        # --- FIX FOR ERR_NGROK_334 ---
        # Connect ngrok tunnel using 'http' protocol to force a new, non-branded generic tunnel, 
        # bypassing the conflict with the previous locked subdomain.
        public_url = ngrok.connect(DASH_PORT, proto="http")
        
        print("\n" + "="*50)
        print(f"🚀 DASH APP IS LIVE AT: {public_url}")
        print("TEST WITH: House ID: 88/01, Password: 1234")
        print("="*50 + "\n")
        
    except Exception as e:
        print(f"🔴 Fatal Error during Ngrok execution: {e}")
        print("Ensure ngrok is correctly installed and authenticated.")
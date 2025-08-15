import dash
from dash import html, dcc, Input, Output, State, callback_context
import dash_bootstrap_components as dbc
import pandas as pd
import plotly.express as px
from datetime import datetime
import json
import os
import base64
import io
from dash.exceptions import PreventUpdate

DATA_FILE = 'transactions.json'
BOOTSTRAP = dbc.themes.BOOTSTRAP

CATEGORIES = ['Income', 'Food', 'Transport', 'Entertainment', 'Utilities', 'Other']

def load_transactions():
    if not os.path.exists(DATA_FILE):
        return []
    try:
        with open(DATA_FILE, 'r') as f:
            data = json.load(f)
            for t in data:
                t['amount'] = float(t.get('amount', 0))
                if 'date' not in t:
                    t['date'] = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            return data
    except Exception:
        try:
            os.rename(DATA_FILE, DATA_FILE + '.bak')
        except Exception:
            pass
        return []

def save_transactions(txns):
    with open(DATA_FILE, 'w') as f:
        json.dump(txns, f, indent=2, default=str)

app = dash.Dash(
    __name__,
    external_stylesheets=[dbc.themes.BOOTSTRAP],
    title="Expense Tracker"  # Change this
    # for logo #assets_url_path="/assets"  # Dash will pick up from assets folder
)

server = app.server
transactions = load_transactions()

app.layout = dbc.Container([
    html.H1("Personal Expenses Tracker", className="text-center my-4"),
    dbc.Row([
        dbc.Col([
            dbc.Card([
                dbc.CardBody([
                    html.H5("Add Transaction", className="card-title"),
                    dbc.Row([
                        dbc.Col(dbc.Input(id='amount', placeholder='Amount', type='number'), md=4),
                        dbc.Col(dcc.DatePickerSingle(id='date', date=datetime.now().date()), md=4),
                        dbc.Col(dbc.Select(id='category', options=[{'label': c, 'value': c} for c in CATEGORIES], placeholder='Category'), md=4),
                    ], className='mb-2'),
                    dbc.Row([
                        dbc.Col(dbc.Input(id='description', placeholder='Description'), md=10),
                        dbc.Col(dbc.Button('Add', id='add-btn', color='primary', className='w-100'), md=2),
                    ], className='mb-2'),
                    dbc.Row([
                        dbc.Col(dbc.Button('Export CSV', id='export-csv', color='secondary', className='me-2'), md=4),
                        dbc.Col(dbc.Button('Export Excel', id='export-xlsx', color='secondary'), md=4),
                        dbc.Col(dcc.Upload(
                            id='upload-data',
                            children=dbc.Button('Import Data', color='info', className='w-100'),
                            multiple=False
                        ), md=4),
                    ], className='mb-2'),
                    dbc.Toast(id='toast', header='Status', is_open=False, duration=3000, dismissable=True),
                ])
            ])
        ], md=4),
        dbc.Col([
            dbc.Card([
                dbc.CardBody([
                    html.H5('Filters', className='card-title'),
                    dbc.Row([
                        dbc.Col(dcc.DatePickerRange(id='date-range'), md=6),
                        dbc.Col(dbc.Select(id='filter-category', options=[{'label': 'All', 'value': 'All'}] + [{'label': c, 'value': c} for c in CATEGORIES], value='All'), md=3),
                        dbc.Col(dbc.Input(id='search', placeholder='Search description...'), md=3),
                    ], className='g-2'),
                ])
            ])
        ], md=8)
    ]),
    html.Hr(),
    dbc.Row([
        dbc.Col(dbc.Card(dbc.CardBody([html.H6('Spending by Category'), dcc.Graph(id='category-pie')])), md=4),
        dbc.Col(dbc.Card(dbc.CardBody([html.H6('Monthly Overview'), dcc.Graph(id='monthly-bar')])), md=4),
        dbc.Col(dbc.Card(dbc.CardBody([html.H6('Cumulative Spending'), dcc.Graph(id='cumulative-line')])), md=4),
    ], className='mb-4'),
    html.H4('Recent Transactions'),
    html.Div(id='transactions-table'),
    dcc.Download(id='download-dataframe-csv'),
    dcc.Download(id='download-dataframe-xlsx'),
    dcc.Store(id='transactions-store', data=transactions),
    dcc.Interval(id='auto-refresh', interval=10*1000, n_intervals=0)
], fluid=True)

@app.callback(
    Output('transactions-store', 'data'),
    Output('toast', 'children'),
    Output('toast', 'is_open'),
    Input('add-btn', 'n_clicks'),
    Input('auto-refresh', 'n_intervals'),
    Input('upload-data', 'contents'),
    State('upload-data', 'filename'),
    State('amount', 'value'),
    State('category', 'value'),
    State('description', 'value'),
    State('date', 'date'),
    State('transactions-store', 'data'),
    prevent_initial_call=True
)
def manage_transactions(add_clicks, n_intervals, uploaded_file, uploaded_filename, amount, category, description, date, store_data):
    ctx = callback_context
    trigger_id = ctx.triggered[0]['prop_id'].split('.')[0]
    store_data = store_data or []

    if trigger_id == 'add-btn':
        if not all([amount, category]):
            return store_data, 'Please provide at least amount and category.', True
        try:
            amount = float(amount)
        except Exception:
            return store_data, 'Invalid amount value.', True
        if date is None:
            date_str = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        else:
            date_obj = datetime.fromisoformat(date)
            date_str = date_obj.strftime('%Y-%m-%d') + ' ' + datetime.now().strftime('%H:%M:%S')
        new_tx = {'amount': amount, 'category': category, 'description': description or '', 'date': date_str}
        store_data.append(new_tx)
        save_transactions(store_data)
        return store_data, 'Transaction added!', True

    elif trigger_id == 'upload-data':
        if uploaded_file is None:
            raise PreventUpdate
        content_type, content_string = uploaded_file.split(',')
        decoded = base64.b64decode(content_string)
        try:
            if uploaded_filename.endswith('.csv'):
                df = pd.read_csv(io.StringIO(decoded.decode('utf-8')))
            elif uploaded_filename.endswith(('.xls', '.xlsx')):
                df = pd.read_excel(io.BytesIO(decoded))
            else:
                return store_data, 'Unsupported file format.', True
            if not all(col in df.columns for col in ['amount', 'category']):
                return store_data, 'File must contain "amount" and "category" columns.', True
            df['date'] = pd.to_datetime(df.get('date', datetime.now())).dt.strftime('%Y-%m-%d %H:%M:%S')
            df['description'] = df.get('description', '')
            imported_data = df.to_dict(orient='records')
            store_data.extend(imported_data)
            save_transactions(store_data)
            return store_data, f'Imported {len(imported_data)} transactions.', True
        except Exception as e:
            return store_data, f'Error importing file: {e}', True

    elif trigger_id == 'auto-refresh':
        disk_data = load_transactions()
        if disk_data != store_data:
            return disk_data, dash.no_update, dash.no_update
        raise PreventUpdate

    raise PreventUpdate

@app.callback(
    Output('transactions-table', 'children'),
    Output('category-pie', 'figure'),
    Output('monthly-bar', 'figure'),
    Output('cumulative-line', 'figure'),
    Input('transactions-store', 'data'),
    Input('date-range', 'start_date'),
    Input('date-range', 'end_date'),
    Input('filter-category', 'value'),
    Input('search', 'value')
)
def update_visuals(store_data, start_date, end_date, filter_category, search):
    df = pd.DataFrame(store_data or [])
    if df.empty:
        empty_fig = px.pie(values=[1], names=['No data'])
        return html.Div('No transactions yet.'), empty_fig, px.bar(), px.line()
    df['amount'] = df['amount'].astype(float)
    df['date'] = pd.to_datetime(df['date'])
    if start_date:
        df = df[df['date'] >= pd.to_datetime(start_date)]
    if end_date:
        df = df[df['date'] <= pd.to_datetime(end_date) + pd.Timedelta(days=1) - pd.Timedelta(seconds=1)]
    if filter_category and filter_category != 'All':
        df = df[df['category'] == filter_category]
    if search:
        df = df[df['description'].str.contains(search, case=False, na=False)]
    pie = px.pie(df, values='amount', names='category', hole=0.4)
    df['month'] = df['date'].dt.to_period('M').dt.to_timestamp()
    monthly = df.groupby(['month', 'category'])['amount'].sum().reset_index()
    bar = px.bar(monthly, x='month', y='amount', color='category')
    cum = df.sort_values('date').groupby('date', as_index=False)['amount'].sum()
    cum['cumulative'] = cum['amount'].cumsum()
    line = px.line(cum, x='date', y='cumulative')
    table_df = df.sort_values('date', ascending=False).head(10)
    table = dbc.Table.from_dataframe(table_df[['date', 'amount', 'category', 'description']].assign(date=lambda d: d['date'].dt.strftime('%Y-%m-%d %H:%M:%S')), striped=True, bordered=True, hover=True)
    return table, pie, bar, line

@app.callback(
    Output('download-dataframe-csv', 'data'),
    Input('export-csv', 'n_clicks'),
    State('transactions-store', 'data'),
    prevent_initial_call=True
)
def export_csv(n_clicks, store_data):
    df = pd.DataFrame(store_data or [])
    if df.empty:
        raise PreventUpdate
    return dcc.send_data_frame(df.to_csv, 'transactions.csv', index=False)

@app.callback(
    Output('download-dataframe-xlsx', 'data'),
    Input('export-xlsx', 'n_clicks'),
    State('transactions-store', 'data'),
    prevent_initial_call=True
)
def export_xlsx(n_clicks, store_data):
    df = pd.DataFrame(store_data or [])
    if df.empty:
        raise PreventUpdate
    return dcc.send_data_frame(df.to_excel, 'transactions.xlsx', index=False)

if __name__ == '__main__':
    app.run(debug=True, port=8050)

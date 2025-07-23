import dash
from dash import dcc, html, Input, Output, State, callback_context, dash_table
import dash_bootstrap_components as dbc
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import base64
import os
import io
from datetime import datetime, timedelta
import numpy as np
from dash.exceptions import PreventUpdate

# Import custom modules
from dashboard_dash import DashboardDash
from preprocess_descriptions import preprocess_description_files

# Performance optimization: Set pandas options
pd.options.mode.chained_assignment = None  # default='warn'

# Initialize Dash app
app = dash.Dash(__name__, external_stylesheets=[dbc.themes.BOOTSTRAP])
app.title = "TRUCCO Analytics"

# Function to get absolute path for assets
def get_asset_path(filename):
    current_dir = os.path.dirname(os.path.abspath(__file__))
    return os.path.join(current_dir, "assets", filename)

# Function to encode image for display
def encode_image(image_file):
    try:
        with open(image_file, "rb") as f:
            return base64.b64encode(f.read()).decode()
    except Exception as e:
        print(f"Error loading image {image_file}: {e}")
        return ""

# Load Excel data function
def load_excel_data(contents, filename):
    """Load and process Excel file from uploaded content"""
    try:
        content_type, content_string = contents.split(',')
        decoded = base64.b64decode(content_string)
        xls = pd.ExcelFile(io.BytesIO(decoded), engine="openpyxl")
        
        # Read sheets with optimized data types
        df_productos = pd.read_excel(
            xls, 
            sheet_name="Compra",
            dtype={
                'ACT': str,
                'Cantidad Pedida': 'Int64',
                'P.V.P.': 'Float64'
            },
            na_values=['', 'nan', 'NaN'],
            keep_default_na=False
        )
        
        df_traspasos = pd.read_excel(
            xls, 
            sheet_name="Traspasos de almacén a tienda",
            dtype={
                'ACT': str,
                'Enviado': 'Int64'
            },
            na_values=['', 'nan', 'NaN'],
            keep_default_na=False
        )
        
        df_ventas = pd.read_excel(
            xls, 
            sheet_name="ventas 23 24 25",
            dtype={
                'ACT': str,
                'Cantidad': 'Int64',
                'P.V.P.': 'Float64',
                'Subtotal': 'Float64'
            },
            na_values=['', 'nan', 'NaN'],
            keep_default_na=False
        )
        
        # Early data cleaning and type conversion
        for df, df_name in [(df_productos, 'Productos'), (df_traspasos, 'Traspasos'), (df_ventas, 'Ventas')]:
            # Convert string columns to more efficient types
            for col in df.columns:
                if df[col].dtype == 'object':
                    # Check if column contains mostly numeric data
                    numeric_count = pd.to_numeric(df[col], errors='coerce').notna().sum()
                    if numeric_count > len(df) * 0.8:  # If 80%+ is numeric
                        df[col] = pd.to_numeric(df[col], errors='coerce')
                    else:
                        # Convert to string and handle NaN values
                        df[col] = df[col].astype(str).replace('nan', '')
            
            # Remove completely empty rows and columns early
            df.dropna(how='all', inplace=True)
            df.dropna(axis=1, how='all', inplace=True)
        
        return df_productos, df_traspasos, df_ventas
        
    except Exception as e:
        print(f"Error loading Excel file: {str(e)}")
        return pd.DataFrame(), pd.DataFrame(), pd.DataFrame()

# Function to create login layout
def create_login_layout():
    logo_data = encode_image(get_asset_path('Logo.png'))
    fondo_data = encode_image(get_asset_path('fondo.png'))
    
    return dbc.Container([
        # Header with logo and background
        html.Div([
            html.Img(src=f"data:image/png;base64,{logo_data}", 
                    style={'height': '160px', 'margin-right': '48px'}),
            html.Img(src=f"data:image/png;base64,{fondo_data}", 
                    style={'height': '240px', 'width': '100%', 'object-fit': 'cover'})
        ], style={'display': 'flex', 'align-items': 'center', 'margin-bottom': '40px'}),
        
        # Login form
        html.Div([
            html.H3("Acceso a Trucco Analytics", 
                   style={'color': 'white', 'font-size': '22px', 'font-weight': '400', 
                         'margin-left': '8px', 'margin-bottom': '16px'}),
            dbc.Row([
                dbc.Col([
                    dbc.Input(id="username-input", placeholder="Usuario", type="text"),
                ], width=6),
            ], className="mb-3"),
            dbc.Row([
                dbc.Col([
                    dbc.Input(id="password-input", placeholder="Contraseña", type="password"),
                ], width=6),
            ], className="mb-3"),
            dbc.Button("Entrar", id="login-button", color="primary", className="mt-2"),
            html.Div(id="login-status", className="mt-3"),
        ])
    ], fluid=True)

# Function to create main dashboard layout
def create_dashboard_layout():
    logo_data = encode_image(get_asset_path('Logo.png'))
    
    return dbc.Container([
        # Header
        html.Div([
            html.Img(src=f"data:image/png;base64,{logo_data}", width="100", 
                    style={'margin-right': '30px'}),
            html.H1("Plataforma de Análisis y Predicción", 
                   style={'font-size': '32px', 'color': '#666666', 'font-weight': '600'})
        ], style={'display': 'flex', 'align-items': 'center', 'margin-bottom': '40px'}),
        
        # Sidebar and main content
        dbc.Row([
            dbc.Col([
                # Navigation menu
                html.H4("Menú de Navegación", className="mb-3"),
                dbc.RadioItems(
                    id="nav-radio",
                    options=[
                        {"label": "Análisis", "value": "analisis"},
                        {"label": "Predicción", "value": "prediccion"}
                    ],
                    value="analisis",
                    className="mb-3"
                ),
                
                # File upload (only for analysis)
                html.Div(id="file-upload-container", children=[
                    html.H5("Subir archivo Excel", className="mb-2"),
                    dcc.Upload(
                        id='upload-data',
                        children=html.Div([
                            'Arrastra o ',
                            html.A('selecciona archivo Excel')
                        ]),
                        style={
                            'width': '100%',
                            'height': '60px',
                            'lineHeight': '60px',
                            'borderWidth': '1px',
                            'borderStyle': 'dashed',
                            'borderRadius': '5px',
                            'textAlign': 'center',
                            'margin': '10px'
                        },
                        multiple=False
                    ),
                    html.Div(id='upload-status', className="mt-2"),
                ]),
                
                # Analysis section selector
                html.Div(id="section-selector-container", children=[
                    html.H5("Área de Análisis", className="mb-2 mt-3"),
                    dbc.Select(
                        id="section-selector",
                        options=[
                            {"label": "Resumen General", "value": "resumen"},
                            {"label": "Análisis de Descripciones", "value": "descripciones"},
                            {"label": "Geográfico y Tiendas", "value": "geografico"},
                            {"label": "Producto, Campaña, Devoluciones y Rentabilidad", "value": "producto"},
                            {"label": "Análisis PVP", "value": "pvp"}
                        ],
                        value="resumen"
                    ),
                ]),
                
                # Filters section
                html.Div(id="filters-container", children=[
                    html.H5("Filtros", className="mb-2 mt-3"),
                    # Season filter
                    html.Label("Temporada", className="mt-2"),
                    dbc.Select(id="season-filter", value="all"),
                    # Family filter  
                    html.Label("Familia", className="mt-2"),
                    dbc.Select(id="family-filter", value="all"),
                ]),
                
            ], width=3),
            
            dbc.Col([
                # Main content area
                html.Div(id="main-content")
            ], width=9)
        ])
    ], fluid=True)

# App layout
app.layout = html.Div([
    dcc.Store(id="session-store"),  # Store login state
    dcc.Store(id="data-store"),     # Store loaded data
    html.Div(id="page-content")
])

# Callback for login
@app.callback(
    [Output("session-store", "data"),
     Output("login-status", "children")],
    [Input("login-button", "n_clicks")],
    [State("username-input", "value"),
     State("password-input", "value")]
)
def handle_login(n_clicks, username, password):
    if n_clicks and username and password:
        # Simple authentication - in production, use proper authentication
        return {"logged_in": True}, ""
    elif n_clicks:
        return {"logged_in": False}, dbc.Alert("Por favor, introduce usuario y contraseña", color="warning")
    return {"logged_in": False}, ""

# Main page content callback
@app.callback(
    Output("page-content", "children"),
    [Input("session-store", "data")]
)
def display_page(session_data):
    if session_data and session_data.get("logged_in"):
        return create_dashboard_layout()
    else:
        return create_login_layout()

# File upload callback
@app.callback(
    [Output("data-store", "data"),
     Output("upload-status", "children")],
    [Input("upload-data", "contents")],
    [State("upload-data", "filename")]
)
def handle_file_upload(contents, filename):
    if contents is not None:
        try:
            df_productos, df_traspasos, df_ventas = load_excel_data(contents, filename)
            
            # Store data as JSON (for simple data) or use more sophisticated storage for large data
            data = {
                "productos": df_productos.to_dict('records'),
                "traspasos": df_traspasos.to_dict('records'), 
                "ventas": df_ventas.to_dict('records'),
                "filename": filename
            }
            
            return data, dbc.Alert(f"Archivo {filename} cargado correctamente", color="success")
        except Exception as e:
            return {}, dbc.Alert(f"Error al cargar archivo: {str(e)}", color="danger")
    
    return {}, ""

# Update filters based on loaded data
@app.callback(
    [Output("season-filter", "options"),
     Output("family-filter", "options")],
    [Input("data-store", "data")]
)
def update_filters(data):
    if not data or not data.get("ventas"):
        return [], []
    
    df_ventas = pd.DataFrame(data["ventas"])
    
    # Season options
    if "Temporada" in df_ventas.columns:
        seasons = df_ventas["Temporada"].dropna().unique().tolist()
        seasons.sort()
        season_options = [{"label": "Todas las temporadas", "value": "all"}] + \
                        [{"label": s, "value": s} for s in seasons]
    else:
        season_options = [{"label": "Todas las temporadas", "value": "all"}]
    
    # Family options
    if "Descripción Familia" in df_ventas.columns:
        families = df_ventas["Descripción Familia"].dropna().unique().tolist()
        families.sort()
        family_options = [{"label": "Todas las familias", "value": "all"}] + \
                        [{"label": f, "value": f} for f in families]
    else:
        family_options = [{"label": "Todas las familias", "value": "all"}]
    
    return season_options, family_options

# Hide/show components based on navigation
@app.callback(
    [Output("file-upload-container", "style"),
     Output("section-selector-container", "style"),
     Output("filters-container", "style")],
    [Input("nav-radio", "value")]
)
def toggle_components_visibility(nav_value):
    if nav_value == "analisis":
        return {}, {}, {}
    else:  # prediccion
        return {"display": "none"}, {"display": "none"}, {"display": "none"}

# Main content callback
@app.callback(
    Output("main-content", "children"),
    [Input("nav-radio", "value"),
     Input("data-store", "data"),
     Input("section-selector", "value"),
     Input("season-filter", "value"),
     Input("family-filter", "value")]
)
def update_main_content(nav_value, data, section, season_filter, family_filter):
    if nav_value == "prediccion":
        return create_prediction_interface()
    
    if not data or not data.get("ventas"):
        return dbc.Alert("Sube el archivo Excel para comenzar el análisis.", color="info")
    
    # Load data from store
    df_productos = pd.DataFrame(data["productos"]) 
    df_traspasos = pd.DataFrame(data["traspasos"])
    df_ventas = pd.DataFrame(data["ventas"])
    
    # Apply filters
    if season_filter != "all" and "Temporada" in df_ventas.columns:
        df_ventas = df_ventas[df_ventas["Temporada"] == season_filter]
    
    if family_filter != "all" and "Descripción Familia" in df_ventas.columns:
        df_ventas = df_ventas[df_ventas["Descripción Familia"] == family_filter]
    
    if df_ventas.empty:
        return dbc.Alert("No hay datos para mostrar con los filtros seleccionados.", color="warning")
    
    # Create dashboard instance and generate content
    dashboard = DashboardDash()
    return dashboard.create_dashboard_content(df_productos, df_traspasos, df_ventas, section)

def create_prediction_interface():
    """Create prediction interface - FIXED VERSION"""
    # Check if training data exists
    training_data_path = 'data/datos_modelo_catboost.xlsx'
    
    if not os.path.exists(training_data_path):
        return dbc.Container([
            html.H2("🔮 Predicciones de Ventas", className="mb-4"),
            dbc.Alert([
                html.H4("No se encontró el archivo de datos de entrenamiento.", className="mb-3"),
                html.P("Para usar las predicciones, necesitas:"),
                html.Ul([
                    html.Li("El archivo 'data/datos_modelo_catboost.xlsx' con los datos de entrenamiento"),
                    html.Li("Los modelos entrenados en la carpeta 'modelos_mejorados/' o 'modelos_finales/'")
                ]),
                html.P("Ejecuta `python run_model_improved.py` para entrenar los modelos mejorados.")
            ], color="danger")
        ])
    
    try:
        # Load training data for predictions
        df_training = pd.read_excel(training_data_path)
        df_training['Fecha Documento'] = pd.to_datetime(
            df_training['Fecha Documento'], 
            format='%d/%m/%Y', 
            errors='coerce', 
            dayfirst=True
        )
        
        return dbc.Container([
            html.H2("🔮 Predicciones de Ventas", className="mb-4"),
            html.P("Utiliza los modelos entrenados para predecir ventas futuras", className="mb-4"),
            
            # Prediction form
            dbc.Card([
                dbc.CardBody([
                    html.H4("Configurar Predicción", className="mb-3"),
                    dbc.Row([
                        dbc.Col([
                            html.Label("Fecha de predicción"),
                            dcc.DatePickerSingle(
                                id='prediction-date',
                                date=datetime.now().date() + timedelta(days=30),
                                display_format='DD/MM/YYYY'
                            )
                        ], width=4),
                        dbc.Col([
                            html.Label("Producto/Familia"),
                            dbc.Select(
                                id="prediction-product",
                                options=[{"label": "Todos", "value": "all"}] + 
                                       [{"label": f, "value": f} for f in df_training['Familia'].unique()[:20]]
                            )
                        ], width=4),
                        dbc.Col([
                            html.Label("Tienda"),
                            dbc.Select(
                                id="prediction-store",
                                options=[{"label": "Todas", "value": "all"}] + 
                                       [{"label": t, "value": t} for t in df_training['Tienda'].unique()[:20]]
                            )
                        ], width=4),
                    ], className="mb-3"),
                    dbc.Button("Generar Predicción", id="predict-button", color="primary"),
                ])
            ], className="mb-4"),
            
            # Results area
            html.Div(id="prediction-results")
        ])
        
    except Exception as e:
        return dbc.Container([
            html.H2("🔮 Predicciones de Ventas", className="mb-4"),
            dbc.Alert(f"Error al cargar los datos de entrenamiento: {e}", color="danger")
        ])

# Prediction callback
@app.callback(
    Output("prediction-results", "children"),
    [Input("predict-button", "n_clicks")],
    [State("prediction-date", "date"),
     State("prediction-product", "value"),
     State("prediction-store", "value")]
)
def generate_prediction(n_clicks, pred_date, product, store):
    if not n_clicks:
        return ""
    
    # Mock prediction results - replace with actual model prediction
    try:
        # Here you would load your trained models and make predictions
        predicted_sales = np.random.randint(100, 1000)  # Mock prediction
        confidence = np.random.uniform(0.7, 0.95)
        
        return dbc.Card([
            dbc.CardBody([
                html.H4("Resultados de Predicción", className="mb-3"),
                dbc.Row([
                    dbc.Col([
                        html.H5(f"Ventas Predichas: {predicted_sales:,} unidades"),
                        html.P(f"Confianza del modelo: {confidence:.1%}"),
                        html.P(f"Fecha: {pred_date}"),
                        html.P(f"Producto: {product}"),
                        html.P(f"Tienda: {store}")
                    ])
                ])
            ])
        ])
        
    except Exception as e:
        return dbc.Alert(f"Error generando predicción: {e}", color="danger")

if __name__ == '__main__':
    app.run_server(debug=True, host='0.0.0.0', port=8050)
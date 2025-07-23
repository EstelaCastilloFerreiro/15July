import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import seaborn as sns
import re
import os
import joblib
import json
from datetime import datetime, timedelta
import numpy as np
import dash_bootstrap_components as dbc
from dash import html, dcc, dash_table
import io

# Optional spacy import for description analysis
try:
    import spacy
    nlp = spacy.load("es_core_news_sm")
    SPACY_AVAILABLE = True
except (OSError, ImportError):
    SPACY_AVAILABLE = False

# Color palettes
COLOR_GRADIENT = ["#e6f3ff", "#cce7ff", "#99cfff", "#66b8ff", "#33a0ff", "#0088ff", "#006acc", "#004d99", "#003366"]
TEMPORADA_COLORS = ["#e6f3ff", "#99ccff", "#4d94ff", "#0066cc", "#004d99", "#003366", "#001a33", "#000d1a", "#000000"]
COLOR_GRADIENT_WARM = ["#fff5e6", "#ffebcc", "#ffd699", "#ffc266", "#ffad33", "#ff9900", "#cc7a00", "#995c00", "#663d00"]
COLOR_GRADIENT_GREEN = ["#e6ffe6", "#ccffcc", "#99ff99", "#66ff66", "#33ff33", "#00ff00", "#00cc00", "#009900", "#006600"]

TIENDAS_EXTRANJERAS = [
    "I301COINBERGAMO(TRUCCO)", "I302COINVARESE(TRUCCO)", "I303COINBARICASAMASSIMA(TRUCCO)",
    "I304COINMILANO5GIORNATE(TRUCCO)", "I305COINROMACINECITTA(TRUCCO)", "I306COINGENOVA(TRUCCO)",
    "I309COINSASSARI(TRUCCO)", "I314COINCATANIA(TRUCCO)", "I315COINCAGLIARI(TRUCCO)",
    "I316COINLECCE(TRUCCO)", "I317COINMILANOCANTORE(TRUCCO)", "I318COINMESTRE(TRUCCO)",
    "I319COINPADOVA(TRUCCO)", "I320COINFIRENZE(TRUCCO)", "I321COINROMASANGIOVANNI(TRUCCO)",
    "TRUCCOONLINEB2C"
]

COL_ONLINE = '#2ca02c'   # verde fuerte
COL_OTRAS = '#ff7f0e'    # naranja

def custom_sort_key(talla):
    """Custom sorting key for sizes"""
    talla_str = str(talla).upper().strip()
    
    # Priority 1: Numeric sizes (e.g., '36', '38')
    if talla_str.isdigit():
        return (0, int(talla_str))
    
    # Priority 2: Standard letter sizes
    size_order = ['XS', 'S', 'M', 'L', 'XL', 'XXL']
    if talla_str in size_order:
        return (1, size_order.index(talla_str))
        
    # Priority 3: Unique sizes
    if talla_str in ['U', 'ÚNICA', 'UNICA', 'TU']:
        return (2, talla_str)
        
    # Priority 4: Rest, alphabetically sorted
    return (3, talla_str)

class DashboardDash:
    def __init__(self):
        self.cached_data = {}
    
    def preprocess_ventas_data(self, df_ventas):
        """Preprocess sales data with error handling"""
        if df_ventas.empty:
            return df_ventas
            
        try:
            # Create copy to avoid modifying original
            df = df_ventas.copy()
            
            # Fix date columns
            date_columns = ['Fecha Documento', 'Fecha']
            for col in date_columns:
                if col in df.columns:
                    df[col] = pd.to_datetime(df[col], dayfirst=True, errors='coerce')
            
            # Add derived columns
            if 'Fecha Documento' in df.columns:
                df['Año'] = df['Fecha Documento'].dt.year
                df['Mes'] = df['Fecha Documento'].dt.month
                df['Mes_Nombre'] = df['Fecha Documento'].dt.strftime('%B')
            
            # Add online store classification
            df['Es_Online'] = df['Tienda'].isin(TIENDAS_EXTRANJERAS)
            
            # Calculate Beneficio if not present
            if 'Beneficio' not in df.columns:
                if all(col in df.columns for col in ['P.V.P.', 'Cantidad', 'Precio Coste']):
                    df['Beneficio'] = (df['P.V.P.'] - df['Precio Coste']) * df['Cantidad']
                elif all(col in df.columns for col in ['P.V.P.', 'Cantidad']):
                    # Fallback calculation without cost
                    df['Beneficio'] = df['P.V.P.'] * df['Cantidad'] * 0.5  # Assume 50% margin
            
            return df
            
        except Exception as e:
            print(f"Error preprocessing sales data: {e}")
            return df_ventas
    
    def preprocess_productos_data(self, df_productos):
        """Preprocess products data with error handling"""
        if df_productos.empty:
            return df_productos
            
        try:
            df = df_productos.copy()
            
            # Fix date columns
            date_columns = ['Fecha Entrada Almacén', 'Fecha Documento']
            for col in date_columns:
                if col in df.columns:
                    df[col] = pd.to_datetime(df[col], dayfirst=True, errors='coerce')
            
            return df
            
        except Exception as e:
            print(f"Error preprocessing products data: {e}")
            return df_productos
    
    def preprocess_traspasos_data(self, df_traspasos):
        """Preprocess transfers data with error handling"""
        if df_traspasos.empty:
            return df_traspasos
            
        try:
            df = df_traspasos.copy()
            
            # Fix date columns
            date_columns = ['Fecha Documento', 'Fecha Envío']
            for col in date_columns:
                if col in df.columns:
                    df[col] = pd.to_datetime(df[col], dayfirst=True, errors='coerce')
            
            return df
            
        except Exception as e:
            print(f"Error preprocessing transfers data: {e}")
            return df_traspasos
    
    def calculate_basic_kpis(self, df_ventas):
        """Calculate basic KPIs"""
        total_ventas_dinero = df_ventas['Beneficio'].sum() if 'Beneficio' in df_ventas.columns else 0
        total_familias = df_ventas['Familia'].nunique() if 'Familia' in df_ventas.columns else 0
        
        # Calculate returns (monetary amount of negative quantities)
        devoluciones = df_ventas[df_ventas['Cantidad'] < 0] if 'Cantidad' in df_ventas.columns else pd.DataFrame()
        total_devoluciones_dinero = abs(devoluciones['Beneficio'].sum()) if not devoluciones.empty and 'Beneficio' in devoluciones.columns else 0
        
        # Separate physical and online stores
        ventas_fisicas = df_ventas[~df_ventas['Es_Online']] if 'Es_Online' in df_ventas.columns else df_ventas
        ventas_online = df_ventas[df_ventas['Es_Online']] if 'Es_Online' in df_ventas.columns else pd.DataFrame()
        
        # Calculate KPIs by store type
        ventas_fisicas_dinero = ventas_fisicas['Beneficio'].sum() if 'Beneficio' in ventas_fisicas.columns else 0
        ventas_online_dinero = ventas_online['Beneficio'].sum() if not ventas_online.empty and 'Beneficio' in ventas_online.columns else 0
        tiendas_fisicas = ventas_fisicas['Tienda'].nunique() if 'Tienda' in ventas_fisicas.columns else 0
        tiendas_online = ventas_online['Tienda'].nunique() if not ventas_online.empty and 'Tienda' in ventas_online.columns else 0
        
        return (total_ventas_dinero, total_devoluciones_dinero, total_familias, 
                ventas_fisicas_dinero, ventas_online_dinero, tiendas_fisicas, tiendas_online)
    
    def create_kpi_cards(self, df_ventas):
        """Create KPI cards for dashboard"""
        try:
            kpis = self.calculate_basic_kpis(df_ventas)
            total_ventas_dinero, total_devoluciones_dinero, total_familias, ventas_fisicas_dinero, ventas_online_dinero, tiendas_fisicas, tiendas_online = kpis
            
            # General KPIs
            general_kpis = dbc.Card([
                dbc.CardHeader("KPIs Generales"),
                dbc.CardBody([
                    dbc.Row([
                        dbc.Col([
                            html.H4(f"{total_ventas_dinero:,.2f}€", className="text-primary"),
                            html.P("Total Ventas Netas", className="text-muted")
                        ], width=3),
                        dbc.Col([
                            html.H4(f"{total_devoluciones_dinero:,.2f}€", className="text-danger"),
                            html.P("Total Devoluciones", className="text-muted")
                        ], width=3),
                        dbc.Col([
                            html.H4(f"{total_familias}", className="text-info"),
                            html.P("Número de Familias", className="text-muted")
                        ], width=3),
                        dbc.Col([
                            html.H4(f"{tiendas_fisicas + tiendas_online}", className="text-success"),
                            html.P("Total Tiendas", className="text-muted")
                        ], width=3),
                    ])
                ])
            ], className="mb-3")
            
            # Store type KPIs
            store_kpis = dbc.Card([
                dbc.CardHeader("KPIs por Tipo de Tienda"),
                dbc.CardBody([
                    dbc.Row([
                        dbc.Col([
                            html.H4(f"{ventas_fisicas_dinero:,.2f}€", className="text-primary"),
                            html.P("Ventas Tiendas Físicas", className="text-muted")
                        ], width=4),
                        dbc.Col([
                            html.H4(f"{ventas_online_dinero:,.2f}€", className="text-success"),
                            html.P("Ventas Online", className="text-muted")
                        ], width=4),
                        dbc.Col([
                            html.H4(f"{tiendas_fisicas} / {tiendas_online}", className="text-info"),
                            html.P("Tiendas Físicas / Online", className="text-muted")
                        ], width=4),
                    ])
                ])
            ], className="mb-3")
            
            return [general_kpis, store_kpis]
            
        except Exception as e:
            return [dbc.Alert(f"Error calculando KPIs: {e}", color="danger")]
    
    def create_monthly_sales_chart(self, df_ventas):
        """Create monthly sales chart"""
        try:
            if 'Mes' not in df_ventas.columns or 'Es_Online' not in df_ventas.columns:
                return dbc.Alert("Datos insuficientes para crear gráfico mensual", color="warning")
            
            ventas_mes_tipo = df_ventas.groupby(['Mes', 'Es_Online']).agg({
                'Cantidad': 'sum',
                'Beneficio': 'sum'
            }).reset_index()
            
            ventas_mes_tipo['Tipo'] = ventas_mes_tipo['Es_Online'].map({True: 'Online', False: 'Física'})
            
            fig = px.bar(ventas_mes_tipo, x='Mes', y='Beneficio', color='Tipo',
                        title="Ventas Mensuales por Tipo de Tienda",
                        color_discrete_map={'Online': COL_ONLINE, 'Física': COL_OTRAS})
            
            fig.update_layout(height=400)
            
            return dcc.Graph(figure=fig)
            
        except Exception as e:
            return dbc.Alert(f"Error creando gráfico mensual: {e}", color="danger")
    
    def create_size_analysis_chart(self, df_ventas):
        """Create size analysis chart"""
        try:
            if 'Talla' not in df_ventas.columns:
                return dbc.Alert("No hay datos de tallas disponibles", color="warning")
            
            # Filter valid sizes
            tallas_validas = df_ventas.dropna(subset=['Talla'])
            tallas_validas = tallas_validas[tallas_validas['Talla'] != '']
            
            if tallas_validas.empty:
                return dbc.Alert("No hay tallas válidas en los datos", color="warning")
            
            # Group by size
            tallas_sumadas = tallas_validas.groupby('Talla')['Cantidad'].sum().reset_index()
            tallas_sumadas = tallas_sumadas.sort_values('Cantidad', ascending=False)
            
            # Create chart
            fig = px.bar(tallas_sumadas.head(20), x='Talla', y='Cantidad',
                        title="Análisis por Tallas (Top 20)")
            
            fig.update_layout(height=400)
            
            return dcc.Graph(figure=fig)
            
        except Exception as e:
            return dbc.Alert(f"Error creando análisis de tallas: {e}", color="danger")
    
    def create_top_products_table(self, df_ventas):
        """Create top products table"""
        try:
            if 'Familia' not in df_ventas.columns or 'Beneficio' not in df_ventas.columns:
                return dbc.Alert("Datos insuficientes para tabla de productos", color="warning")
            
            top_productos = df_ventas.groupby('Familia').agg({
                'Beneficio': 'sum',
                'Cantidad': 'sum'
            }).reset_index()
            
            top_productos = top_productos.sort_values('Beneficio', ascending=False).head(10)
            top_productos['Beneficio'] = top_productos['Beneficio'].round(2)
            
            return dash_table.DataTable(
                data=top_productos.to_dict('records'),
                columns=[
                    {"name": "Familia", "id": "Familia"},
                    {"name": "Beneficio (€)", "id": "Beneficio", "type": "numeric", "format": {"specifier": ",.2f"}},
                    {"name": "Cantidad", "id": "Cantidad", "type": "numeric"}
                ],
                style_cell={'textAlign': 'left'},
                style_data_conditional=[
                    {
                        'if': {'row_index': 0},
                        'backgroundColor': '#d4edda',
                        'color': 'black',
                    }
                ],
                page_size=10
            )
            
        except Exception as e:
            return dbc.Alert(f"Error creando tabla de productos: {e}", color="danger")
    
    def create_store_performance_chart(self, df_ventas):
        """Create store performance chart"""
        try:
            if 'Tienda' not in df_ventas.columns or 'Beneficio' not in df_ventas.columns:
                return dbc.Alert("Datos insuficientes para análisis de tiendas", color="warning")
            
            tiendas_performance = df_ventas.groupby('Tienda')['Beneficio'].sum().reset_index()
            tiendas_performance = tiendas_performance.sort_values('Beneficio', ascending=False).head(15)
            
            fig = px.bar(tiendas_performance, x='Beneficio', y='Tienda', orientation='h',
                        title="Top 15 Tiendas por Beneficio")
            
            fig.update_layout(height=600)
            
            return dcc.Graph(figure=fig)
            
        except Exception as e:
            return dbc.Alert(f"Error creando análisis de tiendas: {e}", color="danger")
    
    def create_dashboard_content(self, df_productos, df_traspasos, df_ventas, seccion):
        """Create dashboard content based on selected section"""
        # Preprocess data
        df_ventas = self.preprocess_ventas_data(df_ventas)
        df_productos = self.preprocess_productos_data(df_productos)
        df_traspasos = self.preprocess_traspasos_data(df_traspasos)
        
        # Merge cost data
        if 'Código único' in df_ventas.columns and 'Código único' in df_productos.columns:
            df_ventas = df_ventas.merge(
                df_productos[['Código único', 'Precio Coste']],
                on='Código único',
                how='left',
                suffixes=('', '_producto')
            )
            if 'Precio Coste_producto' in df_ventas.columns:
                df_ventas['Precio Coste'] = df_ventas['Precio Coste_producto'].combine_first(df_ventas.get('Precio Coste', 0))
                df_ventas = df_ventas.drop(columns=['Precio Coste_producto'])
        
        if seccion == "resumen":
            return self.create_general_summary(df_ventas)
        elif seccion == "descripciones":
            return self.create_descriptions_analysis(df_ventas)
        elif seccion == "geografico":
            return self.create_geographic_analysis(df_ventas)
        elif seccion == "producto":
            return self.create_product_analysis(df_ventas)
        elif seccion == "pvp":
            return self.create_pvp_analysis(df_ventas)
        else:
            return dbc.Alert("Sección no implementada", color="info")
    
    def create_general_summary(self, df_ventas):
        """Create general summary dashboard"""
        try:
            components = []
            
            # Add KPI cards
            kpi_cards = self.create_kpi_cards(df_ventas)
            components.extend(kpi_cards)
            
            # Add charts in rows
            components.append(
                dbc.Row([
                    dbc.Col([
                        dbc.Card([
                            dbc.CardHeader("Análisis Mensual"),
                            dbc.CardBody([
                                self.create_monthly_sales_chart(df_ventas)
                            ])
                        ])
                    ], width=6),
                    dbc.Col([
                        dbc.Card([
                            dbc.CardHeader("Top Productos"),
                            dbc.CardBody([
                                self.create_top_products_table(df_ventas)
                            ])
                        ])
                    ], width=6)
                ], className="mb-3")
            )
            
            components.append(
                dbc.Row([
                    dbc.Col([
                        dbc.Card([
                            dbc.CardHeader("Análisis por Tallas"),
                            dbc.CardBody([
                                self.create_size_analysis_chart(df_ventas)
                            ])
                        ])
                    ], width=6),
                    dbc.Col([
                        dbc.Card([
                            dbc.CardHeader("Performance por Tienda"),
                            dbc.CardBody([
                                self.create_store_performance_chart(df_ventas)
                            ])
                        ])
                    ], width=6)
                ], className="mb-3")
            )
            
            return components
            
        except Exception as e:
            return [dbc.Alert(f"Error creando resumen general: {e}", color="danger")]
    
    def create_descriptions_analysis(self, df_ventas):
        """Create descriptions analysis dashboard"""
        return [
            dbc.Card([
                dbc.CardHeader("Análisis de Descripciones"),
                dbc.CardBody([
                    html.P("Funcionalidad de análisis de descripciones en desarrollo."),
                    html.P("Esta sección incluirá análisis de texto de descripciones de productos.")
                ])
            ])
        ]
    
    def create_geographic_analysis(self, df_ventas):
        """Create geographic analysis dashboard"""
        return [
            dbc.Card([
                dbc.CardHeader("Análisis Geográfico y Tiendas"),
                dbc.CardBody([
                    self.create_store_performance_chart(df_ventas)
                ])
            ])
        ]
    
    def create_product_analysis(self, df_ventas):
        """Create product analysis dashboard"""
        components = []
        
        # Product performance analysis
        if 'Familia' in df_ventas.columns:
            components.append(
                dbc.Card([
                    dbc.CardHeader("Análisis de Productos y Rentabilidad"),
                    dbc.CardBody([
                        self.create_top_products_table(df_ventas)
                    ])
                ], className="mb-3")
            )
        
        # Returns analysis
        if 'Cantidad' in df_ventas.columns:
            devoluciones = df_ventas[df_ventas['Cantidad'] < 0]
            if not devoluciones.empty:
                components.append(
                    dbc.Card([
                        dbc.CardHeader("Análisis de Devoluciones"),
                        dbc.CardBody([
                            html.P(f"Total devoluciones: {len(devoluciones)} registros"),
                            html.P(f"Cantidad devuelta: {abs(devoluciones['Cantidad'].sum()):,} unidades")
                        ])
                    ], className="mb-3")
                )
        
        return components
    
    def create_pvp_analysis(self, df_ventas):
        """Create PVP analysis dashboard"""
        try:
            if 'P.V.P.' not in df_ventas.columns:
                return [dbc.Alert("No hay datos de PVP disponibles", color="warning")]
            
            # PVP distribution
            fig = px.histogram(df_ventas, x='P.V.P.', nbins=50, title="Distribución de Precios de Venta al Público")
            fig.update_layout(height=400)
            
            # Price ranges
            df_ventas['Rango_Precio'] = pd.cut(df_ventas['P.V.P.'], 
                                              bins=[0, 10, 25, 50, 100, float('inf')], 
                                              labels=['0-10€', '10-25€', '25-50€', '50-100€', '100€+'])
            
            precio_rango = df_ventas.groupby('Rango_Precio').agg({
                'Cantidad': 'sum',
                'Beneficio': 'sum'
            }).reset_index()
            
            fig2 = px.bar(precio_rango, x='Rango_Precio', y='Cantidad', 
                         title="Cantidad Vendida por Rango de Precio")
            fig2.update_layout(height=400)
            
            return [
                dbc.Card([
                    dbc.CardHeader("Análisis de Precios PVP"),
                    dbc.CardBody([
                        dbc.Row([
                            dbc.Col([dcc.Graph(figure=fig)], width=6),
                            dbc.Col([dcc.Graph(figure=fig2)], width=6)
                        ])
                    ])
                ])
            ]
            
        except Exception as e:
            return [dbc.Alert(f"Error en análisis PVP: {e}", color="danger")]
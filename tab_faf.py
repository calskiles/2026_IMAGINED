"""
tab 1: FAF zones and commodities
"""

from dash import dcc, html, Input, Output
import matlab.engine
from faf_demand import *


# Create a faf zone map
faf_map = plot_faf_shapefile()

# Get mapping
mappings = get_mappings()
commodity_mapping = mappings["commodity"]
mode_mapping = mappings["mode"]
faf_zone_mapping = mappings["faf_zone"]

years = [2017, 2018, 2019, 2020, 2021, 2022, 2023, 2025, 2030, 2035, 2040, 2045, 2050]


def get_faf_layout(app):
    # Layout for the FAF zones & Commodities tab
    return html.Div([
        # Title

    html.Div([
        html.Div([
            # html.Img(src=app.get_asset_url("Picture1.png"),
            #          style={"width": "150px", "height": "auto", "marginRight": "10px"}),
            html.Img(src=app.get_asset_url("NUTC_logo.jpg"),
                     style={"width": "300px", "height": "auto"})
        ], style={"width": "20%", "display": "flex", "justifyContent": "flex-start"}),
        html.Div(html.H1("U.S. Freight Flows by FAF Zone (in thousand tons)",
                         style={"textAlign": "center", "whiteSpace": "normal", "wordWrap": "break-word"}),
                 style={"width": "60%", "display": "inline-block", "verticalAlign": "middle"}),
        html.Div(html.Img(src=app.get_asset_url("VU_logo.png"),
                          style={"width": "200px", "height": "auto"}),
                 style={"width": "20%", "display": "inline-block", "textAlign": "right"})
    ], style={"display": "flex", "alignItems": "center", "justifyContent": "space-between",
              "marginBottom": "14px"}),

        # Input Dropdowns
        html.Div([
            html.Div([
                html.Label("Year"),
                dcc.Dropdown(
                    id="year-dropdown",
                    options=[{"label": year, "value": year} for year in years],
                    value=2035,
                    style={'marginBottom': '20px'}
                )
            ]),
            html.Div([
                html.Label("Origin"),
                dcc.Dropdown(
                    id="origin-dropdown",
                    options=[{"label": "All", "value": "all"}] + [
                        {"label": f"{code} - {desc}", "value": code}
                        for code, desc in faf_zone_mapping.items()
                    ],
                    value=61,
                    placeholder="Select Origin",
                    style={'marginBottom': '20px'}
                )
            ]),
            html.Div([
                html.Label("Destination"),
                dcc.Dropdown(
                    id="destination-dropdown",
                    options=[{"label": "All", "value": "all"}] + [
                        {"label": f"{code} - {desc}", "value": code}
                        for code, desc in faf_zone_mapping.items()
                    ],
                    value="all",
                    placeholder="Select Destination",
                    style={'marginBottom': '20px'}
                )
            ]),
            html.Div([
                html.Label("Mode"),
                dcc.Dropdown(
                    id="mode-dropdown",
                    options=[{"label": "All", "value": "all"}] + [
                        {"label": f"{code} - {desc}", "value": code}
                        for code, desc in mode_mapping.items()
                    ],
                    value="all",
                    placeholder="Select Mode",
                    style={'marginBottom': '20px'}
                )
            ]),
            html.Div([
                html.Label("Commodity"),
                dcc.Dropdown(
                    id="commodity-dropdown",
                    options=[{"label": "All", "value": "all"}] + [
                        {"label": f"{code} - {desc}", "value": code}
                        for code, desc in commodity_mapping.items()
                    ],
                    value="all",
                    placeholder="Select Commodity",
                    style={'marginBottom': '20px'}
                )
            ])
        ], style={
            'width': '30%', 'display': 'inline-block',
            'verticalAlign': 'top', 'padding': '10px', 'marginLeft': '20px'
        }),

        # Map with checkbox
        html.Div([
            html.Div([
                dcc.Checklist(
                    id='inflow-outflow-checklist',
                    options=[
                        {'label': 'Inflow', 'value': 'in_flow'},
                        {'label': 'Outflow', 'value': 'out_flow'}
                    ],
                    value=['in_flow', 'out_flow'],
                    labelStyle={'display': 'inline-block', 'margin-right': '10px'}
                )
            ], style={'textAlign': 'center'}),

            # Map with Overlay Loading
            dcc.Loading(
                id="loading-map",
                type="circle",  # Options: "default", "circle", "dot"
                children=dcc.Graph(id="faf-zone-map"),
                style={'position': 'relative'}  # Keeps the layout unchanged while loading
            ),
        ], style={'width': '60%', 'display': 'inline-block'}),

        # Bar charts with Overlay Loading
        html.Div([
            dcc.Loading(
                id="loading-charts",
                type="circle",
                children=html.Div([
                    html.Div([
                        dcc.Graph(id="mode-bar-chart")
                    ], style={'width': '48%', 'display': 'inline-block'}),
                    html.Div([
                        dcc.Graph(id="commodity-bar-chart")
                    ], style={'width': '48%', 'display': 'inline-block'}),
                ]),
                style={'position': 'relative'}  # Keeps layout fixed while loading
            )
        ])
    ])


def register_faf_callbacks(app):
    """Registers callbacks for the FAF Zones & Commodities tab."""

    @app.callback(
        Output("faf-zone-map", "figure"),
        Output("mode-bar-chart", "figure"),
        Output("commodity-bar-chart", "figure"),
        Input("year-dropdown", "value"),
        Input("origin-dropdown", "value"),
        Input("destination-dropdown", "value"),
        Input("mode-dropdown", "value"),
        Input("commodity-dropdown", "value"),
        Input("inflow-outflow-checklist", "value"),
    )
    def update_faf_dashboard(year, origin, destination, mode, commodity, inflow_outflow):
        # Determine if 'in_flow' and/or 'out_flow' are checked
        in_flow = 'in_flow' in inflow_outflow
        out_flow = 'out_flow' in inflow_outflow

        # Filter data
        origin = str(origin).zfill(3) if origin != 'all' else 'all'
        destination = str(destination).zfill(3) if destination != 'all' else 'all'
        mode = int(mode) if mode != 'all' else 'all'
        commodity = int(commodity) if commodity != 'all' else 'all'
        filtered_data = get_filtered_data(year, origin, destination, mode, commodity)

        # Generate updated visuals
        updated_map = update_faf_map(filtered_data, in_flow, out_flow)
        mode_chart = generate_mode_chart(filtered_data)
        commodity_chart = generate_commodity_chart(filtered_data)

        return updated_map, mode_chart, commodity_chart


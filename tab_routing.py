"""
tab 2: Routing options and associated performance metrics
"""

from dash import dcc, html, Input, Output, State
from dash.exceptions import PreventUpdate
import time
import plotly.graph_objects as go
import polyline
import matlab.engine

# from faf_demand import plot_faf_shapefile
from truck_routing import *
from rail_routing import *
from water_routing import *
from performance_value import *

km2mile = 0.621371  # mile/km
truck_speed = 60  # mile/hr

# faf_map = plot_faf_shapefile()

def get_routing_layout(app):
    return html.Div([
        # Title Section
    html.Div([
        html.Div([
            # html.Img(src=app.get_asset_url("Picture1.png"),
            #          style={"width": "150px", "height": "auto", "marginRight": "10px"}),
            html.Img(src=app.get_asset_url("NUTC_logo.jpg"),
                     style={"width": "300px", "height": "auto"})
        ], style={"width": "20%", "display": "flex", "justifyContent": "flex-start"}),
        html.Div(html.H1("Logistics Routing Optimization and Performance Metrics",
                         style={"textAlign": "center", "whiteSpace": "normal", "wordWrap": "break-word"}),
                 style={"width": "60%", "display": "inline-block", "verticalAlign": "middle"}),
        html.Div(html.Img(src=app.get_asset_url("VU_logo.png"),
                          style={"width": "200px", "height": "auto"}),
                 style={"width": "20%", "display": "inline-block", "textAlign": "right"})
    ], style={"display": "flex", "alignItems": "center", "justifyContent": "space-between",
              "marginBottom": "14px"}),

        # Main container
        html.Div([
            # Left margin (5%)
            html.Div(style={'width': '3%', 'display': 'inline-block'}),

            # Input section (20%)
            html.Div([
                html.Div([
                    html.Label("Origin"),
                    dcc.Input(
                        id="origin-input-2",
                        type="text",
                        placeholder="Enter Origin",
                        value='Chicago',
                        style={'marginBottom': '15px', 'width': '100%'}
                    )
                ]),

                html.Div([
                    html.Label("Destination"),
                    dcc.Input(
                        id="destination-input-2",
                        type="text",
                        placeholder="Enter Destination",
                        value='Los Angeles',
                        style={'marginBottom': '15px', 'width': '100%'}
                    )
                ]),

                html.Div([
                    html.Label("Commodity"),
                    dcc.Dropdown(
                        id="commodity-dropdown-2",
                        options=[
                            {"label": "Agriculture and Food", "value": "ag_food"},
                            {"label": "Chemical and Petroleum", "value": "chem_pet"},
                            {"label": "Coal", "value": "coal"},
                            {"label": "Forest Products", "value": "for_prod"},
                            {"label": "Intermodal", "value": "im"},
                            {"label": "Metal and Ores", "value": "met_ore"},
                            {"label": "Motor Vehicles", "value": "mo_veh"},
                            {"label": "Nonmetalic Products", "value": "nonmet_pro"}
                        ],
                        placeholder="Choose Commodity Type",
                        value="im",
                        style={'marginBottom': '15px', 'width': '100%'}
                    )
                ]),

                html.Div([
                    html.Label("Shipment Weight (tons)"),
                    dcc.Input(
                        id="shipment-weight",
                        type="number",
                        placeholder="Enter shipment weight",
                        value=100,
                        style={'marginBottom': '25px', 'width': '100%'}
                    )
                ]),

                html.Div([
                    html.Label("Mode"),
                    dcc.Checklist(
                        id="mode-checkboxes",
                        options=[
                            {"label": "Truck", "value": "truck"},
                            {"label": "Rail", "value": "rail"},
                            {"label": "Waterway", "value": "water"}
                        ],
                        value=["truck", "rail"],  # Default selected mode
                        inline=True,  # Display checkboxes horizontally
                        style={'marginBottom': '15px'}
                    )
                ]),

                html.Div([
                    html.Label("Fuel Technology (Drayage Truck)"),
                    dcc.Dropdown(
                        id="energy-short-truck-dropdown",
                        options=[
                            {"label": "Diesel", "value": "diesel"},
                            {"label": "Biodiesel", "value": "biodiesel"},
                            {"label": "Electric", "value": "electricity"},
                            {"label": "Hydrogen-NG w/o CCS", "value": "NG w/o CCS"},
                            {"label": "Hydrogen-NG w/ CCS", "value": "NG w/ CCS"},
                            {"label": "Hydrogen-Electrolysis Solar", "value": "Electrolysis Solar"},
                            {"label": "Hydrogen-Electrolysis Nuclear", "value": "Electrolysis Nuclear"},
                        ],
                        placeholder="Select Energy for Truck",
                        value="diesel",
                        style={'marginBottom': '15px'}
                    )
                ]),

                html.Div([
                    html.Label("Fuel Technology (Long-Haul Truck)"),
                    dcc.Dropdown(
                        id="energy-long-truck-dropdown",
                        options=[
                            {"label": "Diesel", "value": "diesel"},
                            {"label": "Biodiesel", "value": "biodiesel"},
                            {"label": "Electric", "value": "electricity"},
                            {"label": "Hydrogen-NG w/o CCS", "value": "NG w/o CCS"},
                            {"label": "Hydrogen-NG w/ CCS", "value": "NG w/ CCS"},
                            {"label": "Hydrogen-Electrolysis Solar", "value": "Electrolysis Solar"},
                            {"label": "Hydrogen-Electrolysis Nuclear", "value": "Electrolysis Nuclear"},
                        ],
                        placeholder="Select Energy for Truck",
                        value="diesel",
                        style={'marginBottom': '15px'}
                    )
                ]),

                html.Div([
                    html.Label("Fuel Technology (Rail)"),
                    dcc.Dropdown(
                        id="energy-rail-dropdown",
                        options=[
                            {"label": "Diesel", "value": "diesel"},
                            {"label": "Biodiesel", "value": "biodiesel"},
                            {"label": "Electric", "value": "electricity"},
                            {"label": "Hydrogen-NG w/o CCS", "value": "NG w/o CCS"},
                            {"label": "Hydrogen-NG w/ CCS", "value": "NG w/ CCS"},
                            {"label": "Hydrogen-Electrolysis Solar", "value": "Electrolysis Solar"},
                            {"label": "Hydrogen-Electrolysis Nuclear", "value": "Electrolysis Nuclear"},
                        ],
                        placeholder="Select Energy for Rail",
                        value="diesel",
                        style={'marginBottom': '15px'}
                    )
                ]),

                html.Div([
                    html.Label("Fuel Technology (Waterway)"),
                    dcc.Dropdown(
                        id="energy-water-dropdown",
                        options=[
                            {"label": "Diesel", "value": "diesel"},
                            {"label": "Biodiesel", "value": "biodiesel"},
                            {"label": "Electric", "value": "electricity"},
                            {"label": "Hydrogen-NG w/o CCS", "value": "NG w/o CCS"},
                            {"label": "Hydrogen-NG w/ CCS", "value": "NG w/ CCS"},
                            {"label": "Hydrogen-Electrolysis Solar", "value": "Electrolysis Solar"},
                            {"label": "Hydrogen-Electrolysis Nuclear", "value": "Electrolysis Nuclear"},
                        ],
                        placeholder="Select Energy for Waterway",
                        value="diesel",
                        style={'marginBottom': '15px'}
                    )
                ]),

                html.Div([
                    html.Button("Run", id="run-button", n_clicks=0, style={'marginTop': '10px', 'width': '100%'})
                ]),
            ], style={'width': '20%', 'display': 'inline-block', 'verticalAlign': 'top'}),

            html.Div(style={'width': '3%', 'display': 'inline-block'}),

            # Map section (70%)
            html.Div([
                dcc.Loading(
                    id="loading-routing-map-2",
                    type="circle",
                    children=[
                        dcc.Graph(
                            id="routing-map-2",
                            style={'height': '700px'}
                        )
                    ],
                    style={'height': '700px'}
                )
            ], style={'width': '70%', 'display': 'inline-block', 'verticalAlign': 'top'}),

        ], style={'display': 'flex'}),

        # Performance Metrics (Bar Charts)
        html.Div([
            # GHG Bar Chart with Loading
            html.Div([
                dcc.Loading(
                    id="loading-GHG-bar",
                    type="circle",
                    children=[
                        dcc.Graph(id="GHG-bar-chart-2")
                    ]
                )
            ], style={'width': '30%', 'display': 'inline-block'}),

            html.Div([],
                     style={'width': '5%', 'display': 'inline-block'}),

            # Time Bar Chart with Loading
            html.Div([
                dcc.Loading(
                    id="loading-time-bar",
                    type="circle",
                    children=[
                        dcc.Graph(id="time-bar-chart-2")
                    ]
                )
            ], style={'width': '30%', 'display': 'inline-block'}),

            html.Div([],
                     style={'width': '5%', 'display': 'inline-block'}),

            # Fuel Cost Bar Chart with Loading
            html.Div([
                dcc.Loading(
                    id="loading-fuel-cost-bar",
                    type="circle",
                    children=[
                        dcc.Graph(id="fuel-cost-bar-chart-2")
                    ]
                )
            ], style={'width': '30%', 'display': 'inline-block'}),
        ])

    ])

def register_routing_callbacks(app):
    @app.callback(
        [
            Output("routing-map-2", "figure"),
            Output("GHG-bar-chart-2", "figure"),
            Output("time-bar-chart-2", "figure"),
            Output("fuel-cost-bar-chart-2", "figure"),
        ],
        [
            Input("run-button", "n_clicks")
        ],
        [
            State("origin-input-2", "value"),
            State("destination-input-2", "value"),
            State("commodity-dropdown-2", "value"),
            State("shipment-weight", "value"),
            State("mode-checkboxes", "value"),
            State("energy-short-truck-dropdown", "value"),
            State("energy-long-truck-dropdown", "value"),
            State("energy-rail-dropdown", "value"),
            State("energy-water-dropdown", "value")
        ]
    )
    def update_map(n_clicks, orig, dest, commodity, ship_weight, mode, energy_s_truck, energy_l_truck,
                   energy_rail, energy_water):
        if n_clicks == 0:
            raise PreventUpdate

        # Initialize figures
        updated_fig = go.Figure()
        ghg_bar_chart = go.Figure()
        time_bar_chart = go.Figure()
        fuel_cost_bar_chart = go.Figure()

        # Get city location
        orig_geom = geocode_location(orig)
        dest_geom = geocode_location(dest)

        # Ensure routing functions return valid data before plotting
        if "truck" in mode:
            truck_route = get_truck_routes(orig_geom, dest_geom)

            if truck_route:
                # Update map
                updated_fig = plot_truck_routes(updated_fig, truck_route)

                # Calculate metrics
                truck_metrics = get_truck_metrics(truck_route[0], orig_geom, energy_l_truck, 'long truck',
                                                  commodity,
                                                  ship_weight)

                # Generate GHG emissions bar chart
                ghg_bar_chart.add_trace(
                    go.Bar(
                        name="Truck",
                        x=["Truck GHG"],
                        y=[truck_metrics[1] / 1e3],  # Convert to kg
                        text=[f"{truck_metrics[1] / 1e3:.2f} kg"],
                        textposition="auto",
                        marker=dict(color="gray")  # Change to desired color
                    )
                )

                # Generate trip time bar chart
                time_bar_chart.add_trace(
                    go.Bar(
                        name="Truck",
                        x=["Truck Trip time"],
                        y=[truck_metrics[0]],
                        text=[f"{truck_metrics[0]:.2f} hour"],
                        textposition="auto",
                        marker=dict(color="gray")  # Change to desired color
                    )
                )

                # Generate trip time bar chart
                fuel_cost_bar_chart.add_trace(
                    go.Bar(
                        name="Truck",
                        x=["Truck Fuel Cost"],
                        y=[truck_metrics[2]],
                        text=[f"{truck_metrics[2]:.2f} $"],
                        textposition="auto",
                        marker=dict(color="gray")  # Change to desired color
                    )
                )

        if "rail" in mode:
            rail_routes = get_rail_routes(orig_geom, dest_geom)
            if rail_routes:
                updated_fig = plot_dire_rail_routes(updated_fig, rail_routes)
                # Calculate metrics
                rail_metrics = get_dire_rail_metrics(rail_routes, energy_rail, energy_s_truck, commodity,
                                                     ship_weight)
                ghg_bar_chart = plot_dire_rail_ghg(ghg_bar_chart, rail_metrics)
                time_bar_chart = plot_dire_rail_time(time_bar_chart, rail_metrics)
                fuel_cost_bar_chart = plot_dire_rail_cost(fuel_cost_bar_chart, rail_metrics)

        if "water" in mode:
            water_routes = get_water_routes(orig_geom, dest_geom)
            if water_routes:
                updated_fig = plot_truck_water_route(updated_fig, water_routes)
                water_metrics = get_water_metrics(water_routes, energy_water, energy_s_truck, commodity,
                                                  ship_weight)
                ghg_bar_chart = plot_dire_water_ghg(ghg_bar_chart, water_metrics)
                time_bar_chart = plot_dire_water_time(time_bar_chart, water_metrics)
                fuel_cost_bar_chart = plot_dire_water_cost(fuel_cost_bar_chart, water_metrics)
            else:
                print(f"No water route available.")

        # Ensure updated_fig is not None before updating layout
        if updated_fig is None or not updated_fig.data:
            updated_fig = go.Figure()  # Re-initialize if no valid data

        updated_fig.update_layout(
            mapbox_style="open-street-map",
            mapbox_zoom=4,  # Adjust zoom level
            mapbox_center={"lat": 39.8283, "lon": -98.5795}  # US center
        )

        return updated_fig, ghg_bar_chart, time_bar_chart, fuel_cost_bar_chart


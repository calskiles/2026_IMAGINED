"""
Dashboard main file
"""

from dash import Dash, dcc, html, Input, Output
import time
import dash
import pandas as pd
import dash_bootstrap_components as dbc
import json
import matlab.engine

hub_open = True
sim_open = True
nufriend_open = True
faf_rout_open = True
fleet_app_open = True

# -------------------------initialize for hub location start
if hub_open:
    from hub_location import *
    nodes_gdf, water_edges_gdf, rail_edges_gdf_BNSF, rail_edges_gdf_UP, scenario_data = init()

#------------------------ end

#---------- initialize facility simulation start
if sim_open:
    from facility_sim import *
    def load_saved_figure1():
        try:
            with open("saved_figure1.json", "r") as f:
                fig1_json = f.read()
            return go.Figure(json.loads(fig1_json))
        except FileNotFoundError:
            return go.Figure()  # Return an empty figure if no file exists


    def load_saved_figure2():
        try:
            with open("saved_figure2.json", "r") as f:
                fig2_json = f.read()
            return go.Figure(json.loads(fig2_json))
        except FileNotFoundError:
            return go.Figure()  # Return an empty figure if no file exists
    initial_figure1 = load_saved_figure1()
    initial_figure2 = load_saved_figure2()
#------------------------------ end

#---------- initialize nufriend start
if nufriend_open:
    from nufriend.tab_dash_nufriend import *
#---------------------- end

#---------- initialize faf and routing start
if faf_rout_open:
    from tab_faf import *
    from tab_routing import *
    
#---------- initialize fleet app
if fleet_app_open:
    from fleet_app_tab import get_fleet_management_layout, register_fleet_management_callbacks  
    
#-------------- end

def create_module_section(image_src, title, description, video_url, video_id):
    """Create a module section with image, description, and video"""
    return html.Div([
        # Image section
        html.Div([
            html.Img(src=image_src, style={
                "width": "100%",
                "height": "300px",
                "objectFit": "cover",
                "borderRadius": "8px"
            })
        ], style={"width": "45%"}),

        # Text and video section
        html.Div([
            html.H5(title, style={"marginBottom": "10px", "color": "#2c3e50"}),
            html.P(description, style={"marginBottom": "15px", "lineHeight": "1.5"}),

            # Video prompt and button
            html.Div([
                html.P("🎥 Watch an introduction to this module:",
                       style={"marginBottom": "10px", "fontWeight": "bold", "color": "#34495e"}),
                html.Button(
                    "▶️ Play Introduction Video",
                    id=f"video-btn-{video_id}",
                    n_clicks=0,
                    style={
                        "backgroundColor": "#3498db",
                        "color": "white",
                        "border": "none",
                        "padding": "10px 20px",
                        "borderRadius": "5px",
                        "cursor": "pointer",
                        "fontSize": "14px",
                        "marginBottom": "10px"
                    }
                ),

                # Video container (initially hidden)
                html.Div(id=f"video-container-{video_id}", children=[
                    html.Video(
                        src=video_url,
                        controls=True,
                        style={
                            "width": "100%",
                            "maxWidth": "500px",
                            "height": "auto",
                            "borderRadius": "8px"
                        }
                    )
                ], style={"display": "none", "marginTop": "10px"})
            ])
        ], style={"width": "50%", "paddingLeft": "20px"})
    ], style={
        "display": "flex",
        "alignItems": "flex-start",
        "marginBottom": "30px",
        "padding": "20px",
        "backgroundColor": "#f8f9fa",
        "borderRadius": "10px",
        "boxShadow": "0 2px 5px rgba(0,0,0,0.1)"
    })

# Initialize the Dash app
app = dash.Dash(
    __name__,
    external_stylesheets=[dbc.themes.BOOTSTRAP],
    suppress_callback_exceptions=True,
    meta_tags=[
        {"name": "description", "content": "IMAGINED Dashboard for Intermodal Analytics for Logistics Network Efficiency."},
        {"name": "keywords", "content": "IMAGINED, logistics, dashboard, ARPA-E, intermodal analytics, northwestern university"},
        {"name": "viewport", "content": "width=device-width, initial-scale=1.0"}
    ]
)

app.title = "IMAGINED Dashboard"
app._favicon = "favicon.ico"



#################################################




app.layout = html.Div([

    html.Div([
        # Left Logo
        html.Img(src=app.get_asset_url("ARPA-E Subbrand_Awardee Logo-Light.png"),
                 style={"width": "250px", "height": "auto", "marginRight": "20px"}),

        # Title and Subtitle Container
        html.Div([
            html.H1("IMAGINED Dashboard (Beta)", style={"margin": "0", "textAlign": "center"}),
            html.H2("Inter Modal Analytics for Logistics Network Efficiency",
                    style={"margin": "0", "fontSize": "18px", "color": "gray", "textAlign": "center"})
        ], style={"flex": "1", "textAlign": "center"}),  # Centers the text while allowing flex behavior

        # Right Logo (Duplicate of Left Logo)
        html.Img(src=app.get_asset_url("ARPA-E Subbrand_Awardee Logo-Light.png"),
                 style={"width": "250px", "height": "auto", "marginLeft": "20px"})
    ], style={"display": "flex", "alignItems": "center", "justifyContent": "space-between",
              "padding": "10px 20px", "width": "100%"}),

    # Tabs Section
    dcc.Tabs([
        # Homepage Tab - Overview of the Dashboard
        dcc.Tab(label="Home", children=[
            html.Div([

                html.Div([
                    # Top Row with Logos and Centered Titles
                    html.Div([
                        # Left logo (NUTC)
                        html.Div([
                            html.Img(src=app.get_asset_url("NUTC_logo.jpg"),
                                     style={"width": "300px", "height": "auto"})
                        ], style={"width": "20%", "display": "flex", "justifyContent": "flex-start"}),

                        # Centered Text Block (H1, Subtitle, H2)
                        html.Div([
                            html.H1("Welcome to the IMAGINED Dashboard", style={
                                "textAlign": "center",
                                "marginBottom": "10px",
                                "marginTop": "10px"
                            }),
                            html.P(
                                "This dashboard provides analytical tools to optimize multimodal freight transportation, "
                                "evaluate logistics routing, simulate intermodal facility operations, and assess energy infrastructure deployment.",
                                style={"textAlign": "center", "fontSize": "16px", "marginBottom": "20px"}
                            ),
                            html.H2("Dashboard Modules:", style={
                                "textAlign": "center",
                                "textDecoration": "underline",
                                "marginBottom": "15px"
                            })
                        ], style={"width": "60%", "textAlign": "center", "display": "flex", "flexDirection": "column",
                                  "justifyContent": "center"}),

                        # Right logo (VU)
                        html.Div([
                            html.Img(src=app.get_asset_url("VU_logo.png"),
                                     style={"width": "200px", "height": "auto"})
                        ], style={"width": "20%", "display": "flex", "justifyContent": "flex-end"})
                    ], style={
                        "display": "flex",
                        "alignItems": "center",
                        "justifyContent": "space-between",
                        "marginBottom": "30px"
                    })
                ]),

                # List of Modules with Images and Videos
                html.Div([
                    create_module_section(
                        "assets/faf.png",
                        "Freight Flows Visualization",
                        "Provides forecasts for freight flows and commodity market trends based on mode, origin-destination, and forecast year.",
                        "assets/louder_IMAGINED_homepage_FAF_tab_with_captions.mp4",
                        'faf'
                    ),

                    create_module_section(
                        "assets/routing.png",
                        "Logistics Routing",
                        "Optimizes alternative routes to minimize shipment costs, emissions, and travel times while improving reliability.",
                        "assets/Logistics_Routing_tab_demo.mp4",
                        'routing'
                    ),

                    create_module_section(
                        "assets/hub_logo.png",
                        "Multimodal Network Optimization",
                        "Determines optimal locations for multimodal transfer facilities and freight routing on the national network.",
                        "assets/facility_location.mp4",
                        'hub'
                    ),

                    create_module_section(
                        "assets/merged_image.png",
                        "Intermodal Facility Simulation",
                        "Simulates facility operations and evaluates the impact of alternative energy technologies on multimodal transfer processes.",
                        "assets/IMAGINED_Dashboard_Simulation_tab_demo_with_captions.mp4",
                        'facility'
                    ),

                    create_module_section(
                        "assets/nufriend.png",
                        "Energy Infrastructure Deployment (NUFRIEND)",
                        "Simulates the deployment of new energy technologies across U.S. freight rail networks, estimating emissions reductions and investment costs.",
                        "assets/IMAGINED_Dashboard_NUFRIEND_tab_with_captions.mp4",
                        'nufriend'
                    ),

                ], style={"padding": "10px 20px"}),

                html.P("Please select a tab above to explore the different tools available.",
                       style={"textAlign": "center", "marginTop": "20px"}),
            #], style={"padding": "20px"}),


                html.P(["Please give us feedback using this ",
                html.A("survey", href="https://forms.gle/WD8GzT5a7adDXuh77", target="_blank", style={"textDecoration": "underline"})
                ], style={"textAlign": "center", "marginTop": "10px"})
                ], style={"padding": "20px"})
        ]),

        # Existing Functional Tabs
        dcc.Tab(label="Freight Flows Visualization Tool", children=get_faf_layout(app)),
        dcc.Tab(label="Logistics Routing", children=get_routing_layout(app)),
        # dcc.Tab(label="Multimodal Network Optimization",
        #         children=get_hub_location(app, nodes_gdf, water_edges_gdf, rail_edges_gdf_BNSF, rail_edges_gdf_UP, scenario_data)),
        dcc.Tab(label="Multimodal Network Optimization", children=[
            html.Div(
                id="hub-location-container",  # ✅ Unique container for this tab
                children=[
                    get_hub_location(app, nodes_gdf, water_edges_gdf, rail_edges_gdf_BNSF,
                                     rail_edges_gdf_UP, scenario_data)
                ]
            )
        ]),

        dcc.Tab(label="Intermodal Facility Simulation", children=get_facility_simulation(app, initial_figure1, initial_figure2)),
        dcc.Tab(label="Energy Infrastructure Deployment", children=get_nufriend_layout(app)),
        # Fleet management Dashboard
        dcc.Tab(label="Fleet Management", children=get_fleet_management_layout(app)),
        
    ])
], style={'fontFamily': 'Arial, Helvetica, sans-serif'})

# Callbacks for video toggle functionality
@app.callback(
    Output('video-container-faf', 'style'),
    Input('video-btn-faf', 'n_clicks'),
    prevent_initial_call=True
)
def toggle_video_faf(n_clicks):
    if n_clicks and n_clicks % 2 == 1:
        return {"display": "block", "marginTop": "10px"}
    return {"display": "none", "marginTop": "10px"}


@app.callback(
    Output('video-container-routing', 'style'),
    Input('video-btn-routing', 'n_clicks'),
    prevent_initial_call=True
)
def toggle_video_routing(n_clicks):
    if n_clicks and n_clicks % 2 == 1:
        return {"display": "block", "marginTop": "10px"}
    return {"display": "none", "marginTop": "10px"}


@app.callback(
    Output('video-container-hub', 'style'),
    Input('video-btn-hub', 'n_clicks'),
    prevent_initial_call=True
)
def toggle_video_hub(n_clicks):
    if n_clicks and n_clicks % 2 == 1:
        return {"display": "block", "marginTop": "10px"}
    return {"display": "none", "marginTop": "10px"}


@app.callback(
    Output('video-container-facility', 'style'),
    Input('video-btn-facility', 'n_clicks'),
    prevent_initial_call=True
)
def toggle_video_facility(n_clicks):
    if n_clicks and n_clicks % 2 == 1:
        return {"display": "block", "marginTop": "10px"}
    return {"display": "none", "marginTop": "10px"}


@app.callback(
    Output('video-container-nufriend', 'style'),
    Input('video-btn-nufriend', 'n_clicks'),
    prevent_initial_call=True
)
def toggle_video_nufriend(n_clicks):
    if n_clicks and n_clicks % 2 == 1:
        return {"display": "block", "marginTop": "10px"}
    return {"display": "none", "marginTop": "10px"}


register_faf_callbacks(app)
register_routing_callbacks(app)
register_hub_location_callbacks(app, nodes_gdf, water_edges_gdf, rail_edges_gdf_BNSF, rail_edges_gdf_UP, scenario_data)
register_facility_simulation_callbacks(app, initial_figure1, initial_figure2)
register_nufriend_callbacks(app)
register_fleet_management_callbacks(app)


if __name__ == "__main__":
    app.run_server( port=8051, debug=False)
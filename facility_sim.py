import time
import pandas as pd
from dash import dcc, html, Input, Output, State, dash_table
from concurrent.futures import ThreadPoolExecutor
import geopandas as gpd
import plotly.express as px
import networkx as nx
import gurobipy as gp
from gurobipy import GRB
import pyproj
import random
import dash
from dash import dcc, html, Output, Input, callback_context
import dash_bootstrap_components as dbc
import dash_leaflet as dl
import pickle
import numpy as np
import matlab.engine
import plotly.graph_objects as go
import dash
from dash import dcc, html, dash_table
from dash.dependencies import Input, Output, State
import json
import os

def get_facility_simulation(app, initial_figure1, initial_figure2):
    return html.Div([
        # Header Section
        html.Div([
            html.Div([
                html.Img(src=app.get_asset_url("NUTC_logo.jpg"),
                         style={"width": "300px", "height": "auto"})
            ], style={"width": "20%", "display": "flex", "justifyContent": "flex-start"}),

            html.Div(html.H1("Intermodal Facility Simulation",
                             style={"textAlign": "center", "whiteSpace": "normal", "wordWrap": "break-word"}),
                     style={"width": "60%", "display": "inline-block", "verticalAlign": "middle"}),

            html.Div(html.Img(src=app.get_asset_url("VU_logo.png"),
                              style={"width": "200px", "height": "auto"}),
                     style={"width": "20%", "display": "inline-block", "textAlign": "right"})
        ], style={"display": "flex", "alignItems": "center", "justifyContent": "space-between",
                  "marginBottom": "14px"}),

        # Inputs + Run Button + Images in a single row
        html.Div([
            # Inputs and Button Section
            html.Div([
                html.Div([
                    html.Label("Average Hostler Refueling Time:", style={'fontFamily': 'Arial, Helvetica, sans-serif'}),
                    dcc.Input(id="input-param-1", type="number", value=90, step=0.1)
                ], style={'display': 'grid', 'grid-template-columns': '300px 75px'}),

                html.Div([
                    html.Label("Number of Hostler Charging Stations:",
                               style={'fontFamily': 'Arial, Helvetica, sans-serif'}),
                    dcc.Input(id="input-param-3", type="number", value=8, step=1)
                ], style={'display': 'grid', 'grid-template-columns': '300px 75px'}),

                html.Div([
                    html.Label("Average Hostler Move Cycle Time:",
                               style={'fontFamily': 'Arial, Helvetica, sans-serif'}),
                    dcc.Input(id="input-param-2", type="number", value=20, step=0.1)
                ], style={'display': 'grid', 'grid-template-columns': '300px 75px'}),

                html.Button("Run Simulation", id="run-button-sim", n_clicks=0,
                            style={'fontSize': '18px', 'padding': '15px 30px', 'width': '200px', 'height': '60px',
                                   'fontFamily': 'Arial, Helvetica, sans-serif'}),

                html.Div([
                    # html.Br(),
                    html.H4("Model Description"),
                    html.P(
                        "The hostler trucks handle moving the containers from the crane unloading staging area to the parking area for storage."),
                    html.P(
                        "Baseline scenario is for the operation of an intermodal rail yard with 25 diesel-powered hostler trucks and 4 refueling stations."),
                    html.P(
                        "Simulated scenario changes the number of hostlers to 30 and allows for testing the impact of longer charging times on the implementation of battery-electric hostlers.")
                ], style={'fontFamily': 'Arial, Helvetica, sans-serif'}),
            ], style={'width': '20%', 'paddingRight': '2%', 'display': 'inline-block', 'verticalAlign': 'top'}),

            dcc.Loading(
                id="loading-spinner",
                type="circle",  # you can use "default", "circle", "dot", or "cube"
                color="blue",
                children=html.Div(id="loading-spinner-output"),
                style={"margin-left": "10px", "height": "165px"}
            ),

            # Images Section (next to inputs and button)
            html.Div([
                html.Img(src=app.get_asset_url("Intermodal_Yard_Unloading.png"),
                         style={"width": "50%", "height": "auto", "marginBottom": "10px"}),
                html.Img(src=app.get_asset_url("Intermodal_Yard_Flowchart.png"),
                         style={"width": "50%", "height": "auto"})
            ], style={'width': '80%', 'display': 'inline-block', 'verticalAlign': 'top'})
        ], style={'display': 'flex', 'justifyContent': 'space-between', 'alignItems': 'flex-start', 'marginBottom': '30px'}),

        # Graph 1
        html.Div([
            html.Div([
                dcc.Graph(id="sim-graph-1", figure=initial_figure1)
            ], style={"width": "70%", "display": "inline-block"}),

            html.Div([
                html.Br(), html.Br(), html.Br(),  # html.Br(),
                html.H4("Average Charger Wait Time"),
                html.P("This graph shows the average charger wait time over the simulation period of one week."),
                html.P(
                    "The spike at the beginning is due to the initialization of the operation leading to more of the hostlers needing to charge at the same time."),
                html.P(
                    "When this curve levelizes over time, it shows the steady state operation of the hostler charging operations at an intermodal transfer facility.")
            ], style={'fontFamily': 'Arial, Helvetica, sans-serif', "width": "30%", "padding": "10px",
                      "display": "inline-block", "verticalAlign": "top"})
        ], style={"display": "flex", "margin-bottom": "20px"}),

        # Graph 2
        html.Div([
            html.Div([
                dcc.Graph(id="sim-graph-2", figure=initial_figure2)
            ], style={"width": "70%", "display": "inline-block"}),

            html.Div([
                html.Br(), html.Br(), html.Br(),  # html.Br(),
                html.H4("Containers in Staging Area"),
                html.P(
                    "This graph shows the number of containers in the staging area over the simulation period of one week."),
                html.P(
                    "The staging area is where the cranes unload the containers from the train, and the hostlers come to pick up the containers."),
                html.P(
                    "When this curve levelizes over time, it shows the steady state operation and flow of the containers at the intermodal facility."),
            ], style={'fontFamily': 'Arial, Helvetica, sans-serif', "width": "30%", "padding": "10px",
                      "display": "inline-block", "verticalAlign": "top"})
        ], style={"display": "flex"}),

        # Summary Table
        html.H3("Simulation Summary Statistics", style={'fontFamily': 'Arial, Helvetica, sans-serif', 'textAlign': 'center', 'margin-bottom': '5px'}),
        dash_table.DataTable(id="summary-table-1",
                             columns=[{"name": i, "id": i} for i in ["Statistic", "Average Charger Wait (minutes)", "Containers in Staging Area"]],
                             style_table={'width': '50%', 'margin': 'auto'}),

        html.Br(),
        html.Button("Quit MATLAB", id="quit-matlab-button", n_clicks=0,
                    style={'margin-left': '10px', 'backgroundColor': 'red', 'color': 'white'})
    ])

def register_facility_simulation_callbacks(app, initial_figure1, initial_figure2):
    # Start MATLAB Engine
    eng = matlab.engine.start_matlab()

    # Load Simulink Model
    model_path = 'Intermodal_simulation_IBonly_Dash.slx'
    eng.load_system(model_path, nargout=0)

    @app.callback(
        [Output("sim-graph-1", "figure"),
         Output("sim-graph-2", "figure"),
         Output("summary-table-1", "data"),
         Output("loading-spinner-output", "children"),
         # ,
         # Output("summary-table-2", "data")
         ],
        Input("run-button-sim", "n_clicks"),
        [State("input-param-1", "value"),
         State("input-param-2", "value"),
         State("input-param-3", "value")],
        prevent_initial_call=True
    )
    def run_simulation(n_clicks, input_value_1, input_value_2, input_value_3):
        try:
            model_name = 'Intermodal_simulation_IBonly_Dash'

            simulation_time = 10000  # Example: User-defined run time
            eng.set_param('Intermodal_simulation_IBonly_Dash', 'StopTime', str(simulation_time),
                          nargout=0)  # Set simulation run time dynamically

            # Set input parameters in the model
            eng.set_param(f"{model_name}/Hostler Charging/meanChargingTime", 'Value', str(input_value_1), nargout=0)
            eng.set_param(f"{model_name}/Hostler Container Move/meanServiceTime", 'Value', str(input_value_2),
                          nargout=0)
            eng.set_param(f"{model_name}/Hostler Charging/Hostler Charging", 'Capacity', str(input_value_3), nargout=0)

            # Run the simulation
            eng.eval("out = sim('Intermodal_simulation_IBonly_Dash')", nargout=0)
            eng.eval("data = struct(out)", nargout=0)
            data = eng.workspace['data']
            # print(data)

            # Access Charger_Wait Data
            charger_wait_data = data['Data']['Charger_Wait']
            time_data_1 = np.array(charger_wait_data['time']).flatten()
            values_1 = np.array(charger_wait_data['signals']['values']).flatten()

            # Access Staging data"
            other_signal_data = data['Data']['Staging_IBonly']
            time_data_2 = np.array(other_signal_data['time']).flatten()
            values_2 = np.array(other_signal_data['signals']['values']).flatten()

            # Create first figure
            fig1 = go.Figure(initial_figure1)
            fig1.add_trace(
                go.Scatter(x=time_data_1, y=values_1, mode="lines", name="Charger Wait Time (Simulation Run)"))
            fig1.update_layout(title="Average Charger Wait Time", title_x=0.4, margin=dict(t=40, b=20),
                               xaxis_title="Simulation Time (minutes)", yaxis_title="Wait Time (minutes)",
                               legend=dict(
                                   x=0.98,  # Position from left (0 = left edge, 1 = right edge)
                                   xanchor="right",
                                   y=0.98,  # Position from bottom (0 = bottom edge, 1 = top edge)
                                   bgcolor="rgba(255,255,255,0.7)",
                                   # Transparent white background for better visibility
                                   bordercolor="black",
                                   borderwidth=1)
                               ),

            # Save the figure as JSON
            # fig1_json = fig1.to_json()
            # with open("saved_figure1.json", "w") as f:
            #    f.write(fig1_json)

            # Create second figure
            fig2 = go.Figure(initial_figure2)
            fig2.add_trace(go.Scatter(x=time_data_2, y=values_2, mode="lines", name="Staging Spaces (Simulation Run)"))
            fig2.update_layout(title="Containers in Staging Area", title_x=0.4, margin=dict(t=40, b=20),
                               xaxis_title="Simulation Time (minutes)", yaxis_title="Staging Spaces in Use",
                               legend=dict(
                                   x=0.98,  # Position from left (0 = left edge, 1 = right edge)
                                   xanchor="right",
                                   y=0.02,  # Position from bottom (0 = bottom edge, 1 = top edge)
                                   bgcolor="rgba(255,255,255,0.7)",
                                   # Transparent white background for better visibility
                                   bordercolor="black",
                                   borderwidth=1))

            # Save the figure as JSON
            # fig2_json = fig2.to_json()
            # with open("saved_figure2.json", "w") as f:
            #   f.write(fig2_json)

            # Compute Summary Statistics
            summary_stats_1 = pd.DataFrame({
                "Statistic": ["Mean", "Median", "Min", "Max", "Std Dev"],
                "Average Charger Wait (minutes)": [np.mean(values_1), np.median(values_1), np.min(values_1),
                                                   np.max(values_1), np.std(values_1)],
                "Containers in Staging Area": [np.mean(values_2), np.median(values_2), np.min(values_2),
                                               np.max(values_2), np.std(values_2)]
            })

            # summary_stats_2 = pd.DataFrame({
            #     "Statistic": ["Mean", "Median", "Min", "Max", "Std Dev"],
            #     "Value": [np.mean(values_2), np.median(values_2), np.min(values_2), np.max(values_2), np.std(values_2)]
            # })

            # Round values to 2 decimal places
            summary_stats_1["Average Charger Wait (minutes)"] = summary_stats_1["Average Charger Wait (minutes)"].round(
                2)
            summary_stats_1["Containers in Staging Area"] = summary_stats_1["Containers in Staging Area"].round(0)

            return fig1, fig2, summary_stats_1.to_dict("records"), ""  # , summary_stats_2.to_dict("records")

        except Exception as e:
            print(f"Error during simulation: {e}")
            return go.Figure(), go.Figure(), None, None  # Return empty figures in case of error

        # finally:
        #    if eng is not None:
        #        eng.quit()

        def quit_matlab(n_clicks):
            global eng
            if eng is not None:
                eng.quit()
                eng = None  # Reset engine to prevent further calls
            return True  # Disable the button to prevent multiple clicks






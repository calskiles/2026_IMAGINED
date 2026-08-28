# -*- coding: utf-8 -*-
"""
Created on Sun Mar  8 19:50:46 2026

@author: dmonz
"""

import json
import importlib
from pathlib import Path
from dash import Dash, html, dcc, Input, Output

# -------------------------------------------------
# BASE DIRECTORY
# -------------------------------------------------
BASE_DIR = Path(__file__).parent / "Fleet_Management"
BASE_DIR.mkdir(exist_ok=True)

# -------------------------------------------------
# LOAD MODEL DESCRIPTIONS
# -------------------------------------------------
json_path = BASE_DIR / "models_description.json"
with open(json_path) as f:
    MODEL_INFO = json.load(f)

# -------------------------------------------------
# DISCOVER MODEL FOLDERS
# -------------------------------------------------
def find_models():
    models = []
    for folder in BASE_DIR.iterdir():
        if folder.is_dir() and folder.name.startswith("Model_"):
            py_file = folder / f"{folder.name}.py"
            if py_file.exists():
                models.append(folder.name)
    return models

AVAILABLE_MODELS = find_models()



# -------------------------------------------------
# MAIN DASH APP
# -------------------------------------------------
#app = Dash(__name__, suppress_callback_exceptions=True)


# -------------------------------------------------
# IMPORT MODELS AND REGISTER CALLBACKS
# -------------------------------------------------
MODEL_MODULES = {}

for model in AVAILABLE_MODELS:
    try:
        module = importlib.import_module(f"Fleet_Management.{model}.{model}")
        MODEL_MODULES[model] = module
    except Exception as e:
        print(f"Error loading {model}: {e}")



def get_fleet_management_layout(app):

    return html.Div([

        # -------------------------------------------------
        # HEADER (matching other tabss)
        # -------------------------------------------------

        html.Div([

            html.Div([
                html.Img(
                    src=app.get_asset_url("NUTC_logo.jpg"),
                    style={"width": "300px", "height": "auto"}
                )
            ], style={"width": "20%", "display": "flex", "justifyContent": "flex-start"}),

            html.Div(
                html.H1(
                    "Fleet Management Dashboard",
                    style={
                        "textAlign": "center",
                        "whiteSpace": "normal",
                        "wordWrap": "break-word"
                    }
                ),
                style={
                    "width": "60%",
                    "display": "inline-block",
                    "verticalAlign": "middle"
                }
            ),

            html.Div([
                html.Img(
                    src=app.get_asset_url("VU_logo.png"),
                    style={"width": "200px", "height": "auto"}
                )
            ], style={
                "width": "20%",
                "display": "inline-block",
                "textAlign": "right"
            })

        ], style={
            "display": "flex",
            "alignItems": "center",
            "justifyContent": "space-between",
            "marginBottom": "14px"
        }),

        # -------------------------------------------------
        # MODEL SELECTION SECTION
        # -------------------------------------------------

        html.Div([

            html.Label("Select Model:", style={
                "fontFamily": "Arial, Helvetica, sans-serif",
                "fontWeight": "bold"
            }),

            dcc.Dropdown(
                id="model_selector",
                options=[{"label": m, "value": m} for m in AVAILABLE_MODELS],
                placeholder="Select a model",
                style={"width": "400px"}
            ),

            html.Br(),

            html.Div(id="model_description"),

        ], style={
            "marginBottom": "20px",
            "fontFamily": "Arial, Helvetica, sans-serif"
        }),

        # -------------------------------------------------
        # MODEL LAYOUT CONTAINER
        # -------------------------------------------------

        html.Div(id="model_layout_container")

    ])

# -------------------------------------------------
# CALLBACKS
# -------------------------------------------------
def register_fleet_management_callbacks(app):
    
    
    # Register callbacks for all models once
    for model_name, module in MODEL_MODULES.items():
        if hasattr(module, "register_callbacks"):
            module.register_callbacks(app, model_name)

    @app.callback(
        Output("model_description", "children"),
        Input("model_selector", "value")
    )
    def show_description(model):
        if not model:
            return ""
        return html.P(MODEL_INFO.get(model, "No description available."))


    @app.callback(
    Output("model_layout_container", "children"),
    Input("model_selector", "value")
    )
    def load_model_layout(model):
    
        if not model:
            return ""
    
        try:
            module = MODEL_MODULES[model]
    
            #  pass model name as prefix
            layout = module.get_layout(prefix=model)
    
            return layout
    
        except Exception as e:
            return html.Div(
                f"Error loading model layout: {e}",
                style={"color": "red"}
            )

import numpy as np
import pandas as pd
from dash import Dash, dcc, html, Input, Output, State
import plotly.graph_objects as go

def id_(prefix, name):
    return f"{prefix}-{name}"

############################################################
# FORMATTING
############################################################




color_map = {
    -1: "lightblue",   # Keep
    1: "orange",       # Replace tech 1
    0: "grey"
}





############################################################
# MODEL FUNCTION 
############################################################

def run_model(ra_1,  rd_1, 
              rt_1, p1, m0_1, T, dr):

    ############################################################
    # MODEL DIMENSIONS
    ############################################################

    K = 1
    
    inAge = 10
    N = 10+T
    delta = 1/(1+dr)

    ############################################################
    # ARRAYS
    ############################################################

    m = np.zeros((T+1, N+1, K))
    f = np.zeros((T+1, N+1, K))
    p = np.zeros((T+1, K))

    v = np.zeros((T+1, N+1, K))
    w = np.zeros((T+1, N+1, K))

    ############################################################
    # TECHNOLOGY COST RELATIONSHIPS
    ############################################################

    

    m[:,0,0] = m0_1

    ############################################################
    # BUILD COST MATRICES
    ############################################################

    for i in range(T+1):

        if i == 0:
            p[i,0] = p1
           
        else:
            p[i,0] = p[i-1,0]*(1-rt_1)
           

        for j in range(N+1):

            if j < N:

                m[i,j,0] = round(m[i,0,0]*(1+ra_1)**j,0)
              

                f[i,j,0] = round(p[i,0]*(1-rd_1)**j,0)
               

            else:

                f[i,j,0] = round(p[i,0]*(1-rd_1)**j,0)
                

    ############################################################
    # TERMINAL CONDITION
    ############################################################

    for k in range(K):
        for j in range(N):
            v[T, j, k] = -f[T, j, k]

    ############################################################
    # BACKWARD DYNAMIC PROGRAMMING
    ############################################################

    for i in range(T-1, -1, -1):

        for k in range(K):

            for j in range(0, inAge + i):

                ############################################
                # OPTION 1 : KEEP
                ############################################

                tempV = m[i,j,k] + delta*v[i+1, j+1, k]
                tempW = -1

                ############################################
                # OPTION 2 : REPLACE
                ############################################
                epsilon = 10.0 # if savings of replacement is 100 or less, skip it. 

                for challengerTech in range(K):

                   

                    replace_cost = (
                        p[i, challengerTech]
                        - f[i, j, k]
                        + m[i,0, challengerTech]
                        + delta*v[i+1,1,challengerTech]
                    )

                    if replace_cost < tempV - epsilon:

                        tempV = replace_cost
                        tempW = challengerTech + 1
                        #epsilon = 0.0

                ############################################
                # STORE RESULTS
                ############################################

                v[i,j,k] = tempV
                w[i,j,k] = tempW

    return w

############################################################
# PARAMETER INPUT COMPONENT
############################################################

def parameter_input(prefix, param_id, title, description,
                    min_val=None, max_val=None, default=None):

    return html.Div(

        [

            html.Div([
                html.Span("• ", style={"fontSize":"20px"}),
                html.B(title)
            ]),


            html.Div(
                description,
                style={
                    "color": "gray",
                    "fontSize": "12px",
                    "whiteSpace": "normal",
                    "wordWrap": "break-word",
                    "maxWidth": "250px"
                }
            ),

              dcc.Input(
                  id=id_(prefix,param_id),
                  type="number",
                  min=min_val,
                  max=max_val,
                  value=default,
                  step="any",
                  style={
                      "width":"180px",
                      "padding":"6px",
                      "fontSize":"14px"
                  }
              )

        ],
        
        
        
        
      

        style={"marginBottom":"18px"}
    )


############################################################
# APP
############################################################

#app = Dash(__name__)

#app.layout = html.Div([
#def get_layout():
def get_layout(prefix):
    return html.Div([

        html.H2(
            "Fleet Replacement Policy Optimization",
            style={"color":"darkorange"}
        ),

        html.Div(
            "Disclaimer: k is fixed at 2 technologies. Modify backend code to change technology count.",
            style={"marginBottom":"25px","color":"gray"}
        ),

        ####################################################
        # RESPONSIVE MAIN CONTAINER
        ####################################################

        html.Div(

            [

                ####################################################
                # INPUT PANEL
                ####################################################

                html.Div(

                    [

                        html.H3("Model Inputs", style={"color":"darkorange"}),

                        ####################################################
                        # COST PARAMETERS
                        ####################################################

                        html.H4("Cost Parameters"),

                        parameter_input(prefix,
                            "p1",
                            "p₁",
                            "Purchase cost of technology 1",
                            10000,
                            None,
                            250000
                        ),
                        
                        parameter_input(prefix,
                            "m0_1",
                            "m₀₁",
                            "Initial operating and maintenance cost of technology 1",
                            1000,
                            None,
                            60000
                        ),

                        ####################################################
                        # GROWTH RATES
                        ####################################################

                        html.H4("Aging Rates"),

                        parameter_input(prefix,
                            "ra_1",
                            "ra₁",
                            "O&M increase rate for technology 1",
                            0,5,
                            0.1
                        ),
                        
                       


                        ####################################################
                        # DEPRECIATION
                        ####################################################

                        html.H4("Depreciation Rates"),

                        parameter_input(prefix,
                            "rd_1",
                            "rd₁",
                            "Depreciation rate of technology 1",
                            0,1,
                            0.16
                        ),
                        
                      

                       
                        ####################################################
                        # TECHNOLOGY TRENDS
                        ####################################################

                        html.H4("Technology Trends"),

                        parameter_input(prefix,
                            "rt_1",
                            "rt₁",
                            "Purchase cost trend for technology 1",
                            -1,1,
                            0.0
                        ),
                        
                     

                        ####################################################
                        # MODEL HORIZON
                        ####################################################

                        html.H4("Model Horizon"),

                        parameter_input(prefix,
                            "T",
                            "T",
                            "Time horizon (15–50)",
                            15,50,
                            25
                        ),
                        
                        parameter_input(prefix,
                            "dr",
                            "dr",
                            "Discount rate",
                            0,1,
                            0.10
                        ),
                        
                       

                        html.Br(),
                        
                        html.Button(
                            "Reset to Default Values",
                            id=id_(prefix,"reset-btn"),
                            n_clicks=0,
                            style={
                                "marginTop": "20px",
                                "padding": "8px 16px",
                                "fontSize": "14px",
                                "borderRadius": "6px",
                                "border": "1px solid #ccc",
                                "backgroundColor": "#f5f5f5",
                                "cursor": "pointer"
                            }
                        ),

                        html.Button(
                            "Run Model",
                            id=id_(prefix,"run-model"),
                            n_clicks=0,
                            style={
                                "backgroundColor":"darkorange",
                                "color":"white",
                                "border":"none",
                                "padding":"10px 20px",
                                "fontSize":"16px"
                            }
                        ),

                       
                        
                        html.Div(
                            id=id_(prefix,"input-error"),
                            style={
                                "color": "red",
                                "marginTop": "10px",
                                "fontWeight": "500"
                            }
)

                    ],

                    style={
                        "flex":"1",
                        "minWidth":"320px",
                        "maxWidth":"420px"
                    }

                ),

                ####################################################
                # OUTPUT PANEL
                ####################################################

                html.Div(

                    [

                        html.Label("Existing Technology (k) of Fleet"),

                        dcc.Dropdown(
                            id=id_(prefix,"k-dropdown"),
                            options=[
                                {"label":"Technology 1","value":0}
                            ],
                            value=0
                        ),

                        dcc.Loading(
                            type="circle",
                            children=[
                                dcc.Graph(id=id_(prefix,"policy-heatmap"))
                                
                            ]
                        ),

                        html.Div(
                            "This figure shows the optimal schedule for replacing each asset depending on its age for each year in the plannning horizon. The grey cells are not explored in the model.",
                            style={"marginTop":"10px"}
                        )

                    ],

                    style={
                        "flex":"2",
                        "minWidth":"400px"
                    }

                )

            ],

            style={
                "display":"flex",
                "flexWrap":"wrap",
                "gap":"40px"
            }

        ),

        dcc.Store(id=id_(prefix,"model-results"))

    ],

    style={"padding":"40px","fontFamily":"Arial"}
)


############################################################
# Callbacks
############################################################
#def register_callbacks(app):
def register_callbacks(app, prefix):
    ############################################################
    # RESET BUTTON
    ############################################################
    @app.callback(
        [
        Output(id_(prefix,"ra_1"),"value"),
        Output(id_(prefix,"rd_1"),"value"),
        Output(id_(prefix,"rt_1"),"value"),
        Output(id_(prefix,"p1"),"value"),
        Output(id_(prefix,"m0_1"),"value"),
        Output(id_(prefix,"T"),"value"),
        Output(id_(prefix,"dr"),"value"),
        ],
        Input(id_(prefix,"reset-btn"),"n_clicks")
    )
    def reset_defaults(n_clicks):
    
        return (
            0.1,
            0.16,
            0.00,
            250000,
            60000,
            25,
            0.1
        )


    ############################################################
    # RUN MODEL CALLBACK
    ############################################################
    
    @app.callback(
        Output(id_(prefix,"model-results"),"data"),
        Output(id_(prefix,"input-error"),"children"),
        Input(id_(prefix,"run-model"),"n_clicks"),
        State(id_(prefix,"ra_1"),"value"),
        State(id_(prefix,"rd_1"),"value"),
        State(id_(prefix,"rt_1"),"value"),
        State(id_(prefix,"p1"),"value"),
        State(id_(prefix,"m0_1"),"value"),
        State(id_(prefix,"T"),"value"),
        State(id_(prefix,"dr"),"value"),
        prevent_initial_call=True
    )
    def run_model_callback(n, ra_1,  rd_1,  
                           rt_1,  p1, m0_1, T, dr):
    
        try:
    
            w = run_model(
                ra_1,  rd_1, 
            
                rt_1,
                p1, m0_1, T, dr
            )
    
            return {"w": w.tolist()}, ""
    
        except Exception:
    
            return None, "These inputs resulted in an unexpected error. Please try again or contact support."
    
    
    ############################################################
    # HEATMAP CALLBACK
    ############################################################
    
    ############################################################
    # HEATMAP CALLBACK  
    ############################################################
    
    @app.callback(
        Output(id_(prefix,"policy-heatmap"),"figure"),
        Input(id_(prefix,"model-results"),"data"),
        Input(id_(prefix,"k-dropdown"),"value")
    )
    def update_heatmap(data, k):
    
        if data is None:
            return go.Figure()
    
        w = np.array(data["w"])
    
        slice_w = w[:,1:,k]
        #slice_w = slice_w[:,1:]

        # LIMIT DISPLAY SIZE 
        #slice_w = slice_w[:50, :12]
    
        # --- fill zeros with last nonzero (max age) in same period ---
        for t in range(slice_w.shape[0]):
            col = slice_w[t, :]
            nonzero = col[col != 0]
            if len(nonzero) > 0:
                fill_value = nonzero[-1]
                col[col == 0] = fill_value
                slice_w[t, :] = col
    
        z = slice_w.T
    
        colorscale = [
            [0.0, color_map[-1]],
            [0.5, color_map[0]],
            [1.0, color_map[1]]
        ]
    
        fig = go.Figure(data=go.Heatmap(
            z=z,
            x=list(range(slice_w.shape[0])),
            y=list(range(1, slice_w.shape[1])),
            text=slice_w,
            colorscale=colorscale,
            zmin=-1,
            zmax=2,
            showscale=False,
            hovertemplate="Age: %{y}<br>Period: %{x}<br>Policy: %{z}<extra></extra>"
        ))
    
        fig.update_traces(xgap=1, ygap=1)
    
        fig.update_xaxes(
            tickmode="linear",
            dtick=1,
            tick0=0,
            showgrid=True,
            gridcolor="lightgray",
            zeroline=False,
            title="Period (i)",
            tickangle=-45
        )
    
        fig.update_yaxes(
            tickmode="linear",
            dtick=1,
            tick0=0,
            showgrid=True,
            gridcolor="lightgray",
            zeroline=False,
            title="Age (j)",
            autorange="reversed"
        )
    
        # legend
        for val, color in color_map.items():
            fig.add_trace(go.Scatter(
                x=[0], y=[0],
                mode="markers",
                marker=dict(size=10, color=color),
                name=f"{val}: " + ("Keep" if val == -1 else f"Replace {val}"),
                visible="legendonly"
            ))
    
        fig.update_layout(
            width=1000,
            height=800,
            title="Optimal Policy (w) by Period (i) and Age (j)",
            legend_title="Policy",
            legend=dict(
                orientation="h",
                yanchor="top",
                y=-0.40,
                xanchor="center",
                x=0.5
            ),
            margin=dict(t=60, b=140)
        )
    
        return fig
    




############################################################
'''
if __name__ == "__main__":
    app.run_server(debug=False, port=8702)
'''

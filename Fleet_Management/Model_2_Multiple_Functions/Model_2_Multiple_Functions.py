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
    2: "green",        # Replace tech 2
    0: "grey"
}

############################################################
# PARAMETER GENERATING FUNCTIONS 
############################################################


def OM_func(M0, j, ra, func_type):

    if func_type == "geometric":
        return M0 * (1 + ra)**j

    elif func_type == "linear":
        return M0 * (j + 1) * (1 + ra)

    elif func_type == "logarithmic":
        return M0 * (1 + np.log(1 + j*(1 + ra)))

    elif func_type == "quadratic":
        return M0 * (1 + j*ra)**2

    else:
        raise ValueError("Invalid OM function")


def salvage_func(P, j, rd, func_type):

    if func_type == "geometric":
        return P * (1 - rd)**j

    elif func_type == "linear":
        return P * max(0, 1 - j*rd)

    elif func_type == "logarithmic":
        return P * max(0, 1 - rd*np.log(1 + j))

    elif func_type == "quadratic":
        return P * (max(0, 1 - j*rd))**2

    else:
        raise ValueError("Invalid salvage function")
############################################################
# MODEL FUNCTION 
############################################################

def run_model(ra_1, ra_2, rd_1, rd_2, rp_2_1, rm_2_1,
              rt_1, rt_2, p1, m0_1, T, dr, L, OM_type, salvage_type):

    ############################################################
    # MODEL DIMENSIONS
    ############################################################

    K = 2
    
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

    p2 = p1*(1-rp_2_1)
    m0_2 = m0_1*(1-rm_2_1)

    m[:,0,0] = m0_1
    m[:,0,1] = m0_2

    ############################################################
    # BUILD COST MATRICES
    ############################################################

    for i in range(T+1):

        if i == 0:
            p[i,0] = p1
            p[i,1] = p2
        else:
            p[i,0] = p[i-1,0]*(1-rt_1)
            p[i,1] = p[i-1,1]*(1-rt_2)

        for j in range(N+1):

            if j < N:

                #m[i,j,0] = round(m[i,0,0]*(1+ra_1)**j,0)
                #m[i,j,1] = round(m[i,0,1]*(1+ra_2)**j,0)

                #f[i,j,0] = round(p[i,0]*(1-rd_1)**j,0)
                #f[i,j,1] = round(p[i,1]*(1-rd_2)**j,0)
                
                m[i,j,0] = round(OM_func(m[i,0,0], j, ra_1, OM_type), 0)
                m[i,j,1] = round(OM_func(m[i,0,1], j, ra_2, OM_type), 0)
                
                f[i,j,0] = round(salvage_func(p[i,0], j, rd_1, salvage_type), 0)
                f[i,j,1] = round(salvage_func(p[i,1], j, rd_2, salvage_type), 0)

            else:

                #f[i,j,0] = round(p[i,0]*(1-rd_1)**j,0)
                #f[i,j,1] = round(p[i,1]*(1-rd_2)**j,0)
                f[i,j,0] = round(salvage_func(p[i,0], j, rd_1, salvage_type), 0)
                f[i,j,1] = round(salvage_func(p[i,1], j, rd_2, salvage_type), 0)

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

                    if challengerTech == 1 and i < L:
                        continue

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
                            200000
                        ),
                        
                        parameter_input(prefix,
                            "m0_1",
                            "m₀₁",
                            "Initial operating and maintenance cost of technology 1",
                            1000,
                            None,
                            40000
                        ),

                        ####################################################
                        # PARAMETER GENERATING FUNCTIONS
                        ####################################################

                        html.H4("Function Types"),
                        
                        html.Label("O&M Function"),
                        dcc.Dropdown(
                            id=id_(prefix,"om_func"),
                            options=[
                                {"label":"Geometric: M = M0(1+ra)^j", "value":"geometric"},
                                {"label":"Linear: M = M0*(j+1)*(1+ra)", "value":"linear"},
                                {"label":"Logarithmic: M = M0*(1+log(j(1+ra)))", "value":"logarithmic"},
                                {"label":"Quadratic: M = M0*(1+j*ra)^2", "value":"quadratic"},
                            ],
                            value="logarithmic"
                        ),
                        
                        html.Br(),
                        
                        html.Label("Salvage Function"),
                        dcc.Dropdown(
                            id=id_(prefix,"salvage_func"),
                            options=[
                                {"label":"Geometric: f = P(1-rd)^j", "value":"geometric"},
                                {"label":"Linear: f = P*max(0,1-jrd)", "value":"linear"},
                                {"label":"Logarithmic: f = P*max(0,1-rd ln(1+j))", "value":"logarithmic"},
                                {"label":"Quadratic: f = P*(max(0,1-jrd))^2", "value":"quadratic"},
                            ],
                            value="geometric"
                        ),
                        
                        dcc.Markdown(
                            id=id_(prefix,"function-display"),
                            mathjax=True,
                            style={"marginTop":"15px", "fontSize":"16px"}
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
                            0.02
                        ),
                        
                        parameter_input(prefix,
                            "ra_2",
                            "ra₂",
                            "O&M increase rate for technology 2",
                            0,5,
                            0.4
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
                            0.4
                        ),
                        
                        parameter_input(prefix,
                            "rd_2",
                            "rd₂",
                            "Depreciation rate of technology 2",
                            0,1,
                            0.4
                        ),

                        ####################################################
                        # RELATIVE COST
                        ####################################################

                        html.H4("Relative Cost Parameters"),

                        parameter_input(prefix,
                            "rp_2_1",
                            "rp₂₁",
                            "Relative purchase cost difference of technology 2 vs 1. When negative, it means technology 2 is more expensive, and cheaper otherwise.",
                            -1,1,
                            -0.3
                        ),
                        
                        parameter_input(prefix,
                            "rm_2_1",
                            "rm₂₁",
                            "Relative O&M cost difference of technology 2 vs 1. When negative, it means technology 2 is more expensive, and cheaper otherwise.",
                            -1,1,
                            0
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
                        
                        parameter_input(prefix,
                            "rt_2",
                            "rt₂",
                            "Purchase cost trend for technology 2",
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
                        
                        parameter_input(prefix,
                            "L",
                            "L",
                            "Year when technology 2 becomes available",
                            0,None,
                            5
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
                                {"label":"Technology 1","value":0},
                                {"label":"Technology 2","value":1}
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
        Output(id_(prefix,"ra_2"),"value"),
        Output(id_(prefix,"rd_1"),"value"),
        Output(id_(prefix,"rd_2"),"value"),
        Output(id_(prefix,"rp_2_1"),"value"),
        Output(id_(prefix,"rm_2_1"),"value"),
        Output(id_(prefix,"rt_1"),"value"),
        Output(id_(prefix,"rt_2"),"value"),
        Output(id_(prefix,"p1"),"value"),
        Output(id_(prefix,"m0_1"),"value"),
        Output(id_(prefix,"T"),"value"),
        Output(id_(prefix,"dr"),"value"),
        Output(id_(prefix,"L"),"value"),
        ],
        Input(id_(prefix,"reset-btn"),"n_clicks")
    )
    def reset_defaults(n_clicks):
    
        return (
            0.02,
            0.4,
            0.4,
            0.4,
            -0.3,
            0,
            0.00,
            0.00,
            200000,
            40000,
            25,
            0.1,
            5
        )

    ############################################################
    # PARAMETER FUNCTIONS CALLBACK
    ############################################################
    @app.callback(
    Output(id_(prefix,"function-display"), "children"),
    Input(id_(prefix,"om_func"), "value"),
    Input(id_(prefix,"salvage_func"), "value"),
    )
    def update_formula(om, salvage):
    
        om_map = {
            "geometric": r"$M_{jk}=M_{0k}(1+ra)^j$",
            "linear": r"$M_{jk}=M_{0k}(j+1)(1+ra)$",
            "logarithmic": r"$M_{jk}=M_{0k}(1+\ln(j(1+ra)))$",
            "quadratic": r"$M_{jk}=M_{0k}(1+jra)^2$",
        }
    
        f_map = {
            "geometric": r"$f_{jk}=P_k(1-rd)^j$",
            "linear": r"$f_{jk}=P_k\max(0,1-jrd)$",
            "logarithmic": r"$f_{jk}=P_k\max(0,1-rd\ln(1+j))$",
            "quadratic": r"$f_{jk}=P_k(\max(0,1-jrd))^2$",
        }
    
        return f"**O&M costs selected function:** {om_map[om]}  \n\n**Salvage value selected function:** {f_map[salvage]}"

    ############################################################
    # RUN MODEL CALLBACK
    ############################################################
    
    @app.callback(
        Output(id_(prefix,"model-results"),"data"),
        Output(id_(prefix,"input-error"),"children"),
        Input(id_(prefix,"run-model"),"n_clicks"),
        State(id_(prefix,"ra_1"),"value"),
        State(id_(prefix,"ra_2"),"value"),
        State(id_(prefix,"rd_1"),"value"),
        State(id_(prefix,"rd_2"),"value"),
        State(id_(prefix,"rp_2_1"),"value"),
        State(id_(prefix,"rm_2_1"),"value"),
        State(id_(prefix,"rt_1"),"value"),
        State(id_(prefix,"rt_2"),"value"),
        State(id_(prefix,"p1"),"value"),
        State(id_(prefix,"m0_1"),"value"),
        State(id_(prefix,"T"),"value"),
        State(id_(prefix,"dr"),"value"),
        State(id_(prefix,"L"),"value"),
        State(id_(prefix,"om_func"),"value"),
        State(id_(prefix,"salvage_func"),"value"),
        prevent_initial_call=True
    )
    def run_model_callback(n, ra_1, ra_2, rd_1, rd_2, rp_2_1, rm_2_1,
                           rt_1, rt_2, p1, m0_1, T, dr, L, OM_type, salvage_type):
    
        try:
    
            w = run_model(
                ra_1, ra_2, rd_1, rd_2,
                rp_2_1, rm_2_1,
                rt_1, rt_2,
                p1, m0_1, T, dr, L, OM_type, salvage_type
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
            [0.333, color_map[0]],
            [0.667, color_map[1]],
            [1.0, color_map[2]]
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
 

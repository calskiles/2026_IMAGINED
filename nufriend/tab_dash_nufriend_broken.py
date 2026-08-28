"""
tab 1: FAF zones and commodities
"""

from dash import dcc, html, Input, Output
from nufriend.plotting import *
from nufriend.run import run_scenario

RR_list = ['WCAN', 'EAST', 'USA1']
RR_list_value = "WCAN"
RR_name_selected = RR_list_value
RR_list_show = ['Western & Canadian', 'Eastern', 'Transcontinental']
range_list = [200, 400, 800, 1000, 1500]
range_list_value = 400
RR_range_selected = range_list_value
ES_list = ['diesel', 'biodiesel', 'e-fuel', "battery", "hydrogen", 'hybrid2:1', 'hybrid1:1']
ES_list_value = 'battery'
ES_name_selected = ES_list_value
ES_list_show = ['Diesel', 'Biofuel', 'e-fuel', "Battery-electric", "Hydrogen", 'Hybrid 2:1', 'Hybrid 1:1']
# TODO: change to be only general?
db_list = ['General', 'Parameters']
db_list_value = 'General'
legend_switch_value = True
legend_switch_selected = legend_switch_value
comm_list = ['TOTAL', 'AG_FOOD', 'CHEM_PET', 'COAL', 'FOR_PROD', 'MET_ORE', 'MO_VEH', 'NONMET_PRO', 'IM', 'OTHER']
comm_list_value = 'TOTAL'
comm_name_selected = comm_list_value
comm_list_show = ['All', 'Agricultural & Food', "Chemicals & Petroleum", "Coal", "Forest Product", "Metal and Ores",
                  "Motor Vehicles", "Non-metallic Products", 'Intermodal', 'Others']
deploy_pct_list = [0.2, 0.4, 0.6, 0.8, 1]
deploy_pct_value = 0.6
deploy_pct_selected = deploy_pct_value
charger_speed_value = 3
hydrogen_dispense_value = 'Cryo-pump'
last_n_run_click = 0  # to track how many times run button is clicked
clean_energy_value = False
battery_ppa_cost_box_value = 0
re_routing_switch_value = True
loco_switching_switch_value = False
battery_capa_value = 10
battery_cost_p_tonmi_box_value = None
diesel_cost_p_gal_box_value = None
year_value = 2035
discount_rate_value = 7
hydrogen_no_hour_value = 20
hydrogen_PPA_cost_box_value = 0
hydrogen_fuel_list_value = 'Natural Gas'
hydrogen_dispense_list_value = hydrogen_dispense_value

# TODO: error likely coming from n_clicks issue not specified as what to do if n_clicks is 0


def get_nufriend_layout(app):
    RR_dropdown = html.Div(
        [
            dbc.Label("Railroad"),
            dcc.Dropdown([{'value': x, 'label': y}
                          for x, y in zip(RR_list, RR_list_show)],
                         RR_list_value,
                         id='RR_dropdown',
                         persistence=True, persistence_type="memory", ),
        ], className="dash-bootstrap"
    )
    ES_dropdown = html.Div(
        [
            dbc.Label("Energy"),
            dcc.Dropdown([{'value': x, 'label': y}
                          for x, y in zip(ES_list, ES_list_show)],
                         ES_list_value,
                         id='ES_dropdown',
                         persistence=True, persistence_type="memory"),
        ]
    )
    # Slider for range selection
    range_slider = html.Div(
        [
            dbc.Collapse(
                dbc.Row([
                    dbc.Label("Battery Range (mi)", html_for="slider"),
                    dcc.Slider(0, 1500,
                               step=None,
                               marks={
                                   x: str(x) for x in range_list
                               },
                               value=range_list_value,
                               id="range_slider",
                               persistence=True, persistence_type="memory",
                               )
                ]),
                id="battery_range_collapse",
                is_open=True,
            )
        ],
        className="mb-3",
    )
    # Slider for facility distance selection for hybrid
    facility_dist_slider = html.Div(
        [
            dbc.Collapse(
                dbc.Row([
                    dbc.Label("Inter-facility Distance (mi)", html_for="slider"),
                    dcc.Slider(0, 1500,
                               step=None,
                               marks={
                                   x: str(x) for x in range_list
                               },
                               value=range_list_value,
                               id="facility_dist_slider",
                               persistence=True, persistence_type="memory",
                               )
                ]),
                id="facility_dist_collapse",
                is_open=True,
            )
        ],
        className="mb-3",
    )
    # Slider for deployment % selection
    deploy_pct_slider = html.Div(
        [
            dbc.Collapse(
                dbc.Row([
                    dbc.Label("Target Deployment % (Overall)", html_for="slider"),
                    dcc.Slider(0, 1,
                               step=None,
                               marks={
                                   x: str(int(x * 100)) + '%' for x in deploy_pct_list
                               },
                               value=deploy_pct_value,
                               id="deploy_pct_slider",
                               persistence=True, persistence_type="memory",
                               )
                ]),
                id='deploy_pct_collapse',
                is_open=True,
            )
        ],
        className="mb-3",
    )
    comm_dropdown = html.Div(
        [
            dbc.Label("Commodity"),
            dcc.Dropdown([{'value': x, 'label': y}
                          for x, y in zip(comm_list, comm_list_show)],
                         comm_list_value,
                         id='comm_dropdown',
                         persistence=True, persistence_type="memory",
                         ),
        ]
    )
    # Legend switch
    legend_switch = html.Div(
        [
            dbc.Switch(
                # options=[
                #     {"label": "Re-routing allowed", "value": 1},
                # ],
                label="Show legend",
                value=legend_switch_value,
                id="legend_switch",
                persistence=True, persistence_type="memory",
                # switch=True,
            ),
        ]
    )
    # Loading spinner
    loading_spinner = html.Div(
        [
            dbc.Spinner(html.Div(id="loading-output")),
        ]
    )
    RR_map = dls.Hash(
        dbc.Row(children="", id="RR_basemap"),
        color="#435278",
        speed_multiplier=2,
        size=100,
    )
    run_button = html.Div(
        [
            dbc.Button("Run",
                       color="primary",
                       className="me-1",
                       id="run_button",
                       n_clicks=0,
                       ),
            dls.Hash(
                html.Div(children="", id="cache_output"),
                color="#435278",
                speed_multiplier=2,
                size=100,
            )
        ]
    )

    general_dashboard = [
        dbc.Row([
            dbc.Col([dbc.Row(RR_dropdown),
                     dbc.Row(style={"height": "1vh"}),
                     dbc.Row(ES_dropdown),
                     dbc.Row(style={"height": "1vh"}),
                     dbc.Row(range_slider),
                     dbc.Row(style={"height": "1vh"}),
                     dbc.Row(facility_dist_slider),
                     dbc.Row(style={"height": "1vh"}),
                     dbc.Row(deploy_pct_slider),
                     dbc.Row(style={"height": "1vh"}),
                     dbc.Row(comm_dropdown),
                     dbc.Row(style={"height": "1vh"}),
                     dbc.Row(legend_switch),
                     dbc.Row(style={"height": "1vh"}),
                     dbc.Row(run_button),
                     dbc.Row(style={"height": "1vh"}),
                     # html.Div(children="Preliminary Results"),
                     ], width=2),
            dbc.Col([
                dbc.Row(RR_map),
                dbc.Row(loading_spinner),
            ], width=10),
        ],
        ),
        dbc.Row(style={"height": "1vh"}),
    ]

    return general_dashboard


def register_nufriend_callbacks(app):
    # Read parameter changes
    @app.callback(
        [Output("battery_range_collapse", "is_open"),
         Output("facility_dist_collapse", "is_open"),
         Output("deploy_pct_collapse", "is_open"),
         ],
        [Input("RR_dropdown", "value"),
         Input("ES_dropdown", "value"),
         Input("comm_dropdown", "value"),
         Input("range_slider", "value"),
         Input("facility_dist_slider", "value"),
         Input("deploy_pct_slider", "value"),
         Input("legend_switch", "value"),
         ]
    )
    def read_parameter(RR_name, ES_name, comm_name, RR_range, fac_dist, deploy_pct, legend_show):
        global RR_name_selected, ES_name_selected, comm_name_selected, RR_range_selected, deploy_pct_selected, legend_switch_selected
        if 'hybrid' in ES_name:
            RR_name_selected, ES_name_selected, comm_name_selected, RR_range_selected, deploy_pct_selected, legend_switch_selected = RR_name, ES_name, comm_name, fac_dist, deploy_pct, legend_show
        else:
            RR_name_selected, ES_name_selected, comm_name_selected, RR_range_selected, deploy_pct_selected, legend_switch_selected = RR_name, ES_name, comm_name, RR_range, deploy_pct, legend_show
        # Expand/Collapse battery range slider depending on ES
        if ES_name == 'battery':
            battery_range_collapse_open = True
            facility_dist_collapse_open = False
            deploy_pct_collapse_open = True
        elif 'hybrid' in ES_name:
            battery_range_collapse_open = False
            facility_dist_collapse_open = True
            deploy_pct_collapse_open = False
        else:
            battery_range_collapse_open = False
            facility_dist_collapse_open = False
            deploy_pct_collapse_open = True
        return [battery_range_collapse_open, facility_dist_collapse_open, deploy_pct_collapse_open]

    def return_chart_fig_card(fig_list):
        card_list = []
        if not fig_list:
            return dbc.Row()
        else:
            n_card = len(fig_list) - 2
            no_col = 2  # Number of columns to show the cards (excluding map and metrics)
            width_total = 12
            width_map = 8
            height_total = 50

            card_list = []
            for i, fig in enumerate(fig_list[2:]):
                card = dbc.Card(
                    [
                        dbc.CardBody(
                            [
                                dcc.Graph(figure=fig,
                                          id="card_" + str(i + 2),
                                          style={
                                              # 'width': '90vh',
                                              'height': str(height_total / no_col) + 'vh',
                                              #     'height': '20%',
                                          },
                                          # className="h-100",
                                          config={
                                              'displayModeBar': False
                                          }
                                          ),
                            ]
                        ),
                    ],
                    style={"border": "none"},
                )
                card_list.append(card)

            card_row_list = []

            i = 0
            temp_row = []
            while i < len(card_list):
                temp_row.append(
                    dbc.Col(card_list[i], width=int((width_total) / int(n_card / no_col)))
                )
                if i % no_col == 1:
                    card_row_list.append(temp_row)
                    temp_row = []
                i += 1
            if temp_row:
                card_row_list.append(temp_row)

            # Combine cards of charts with the RR map
            metric_row_list = [
                dbc.Row(card_row, className="g-0") for card_row in card_row_list
            ]

            # Add metric table
            metric_row_list.append(dbc.Row(dbc.Card(
                [
                    dbc.CardBody(
                        [
                            dcc.Graph(figure=fig_list[1],
                                      id="card_1",
                                      style={
                                          'height': str(height_total) + 'vh',
                                      },
                                      config={
                                          'displayModeBar': False
                                      }
                                      ),
                        ]
                    ),
                ],
                className="g-0",
                style={"border": "none"},
            )))

            # Add card of main RR map
            output_row_list = [dbc.Col(metric_row_list, width=width_total - width_map),
                               dbc.Col(
                                   dbc.Card([
                                       dbc.CardBody(
                                           [
                                               dcc.Graph(figure=fig_list[0],
                                                         id="card_0",
                                                         style={
                                                             'width': '100vh',
                                                             'height': '100vh',
                                                         }
                                                         ),
                                           ]
                                       ),
                                   ]
                                       , style={"border": "none"},
                                   )
                                   , width=width_map

                               )
                               ]
            output_row = dbc.Row(output_row_list, className="g-0", )

            return output_row

    def return_station_type(ES_name):
        if ES_name == "battery":
            return str(charger_speed_value) + "MW"
        elif ES_name == "hydrogen":
            return hydrogen_dispense_value
        else:
            return None

    # Load / reload a scenario
    @app.callback(
        [Output("RR_basemap", "children"),
         Output("cache_output", "children"),
         ],
        [
            Input("run_button", "n_clicks"),
        ]
    )
    def display_RR_range_map(n_run):
        RR_name, ES_name, comm_name, RR_range, deploy_pct, legend_show = [RR_name_selected, ES_name_selected,
                                                                          comm_name_selected, RR_range_selected,
                                                                          deploy_pct_selected, legend_switch_selected]
        global last_n_run_click
        update_graph = False  # Flag whether to update a graph

        # Check run
        if (n_run <= last_n_run_click) or (n_run == 0):
            output = ""
        else:
            last_n_run_click = n_run
            update_graph = True
            output = "Run successful"

        load_scenario = False

        if update_graph:
            current_scenario = RR_name, ES_name, comm_name, RR_range, deploy_pct, re_routing_switch_value, loco_switching_switch_value
            print(request.remote_addr, current_scenario)
            logging.info(request.remote_addr)  # IP address
            logging.info(current_scenario)  # Scenario
            station_type = return_station_type(ES_name)

            if ES_name == 'battery':
                fig_list, label = return_RR_range_map(RR_name, ES_name, comm_name, RR_range, deploy_pct,
                                                      load_scenario=load_scenario, legend_show=legend_show,
                                                      clean_energy=clean_energy_value,
                                                      clean_energy_cost=battery_ppa_cost_box_value,
                                                      station_type=station_type, reroute=re_routing_switch_value,
                                                      switch_tech=loco_switching_switch_value,
                                                      tender_cost_p_tonmi=battery_cost_p_tonmi_box_value,
                                                      diesel_cost_p_gal=diesel_cost_p_gal_box_value)
            elif ES_name == 'hydrogen':
                fig_list, label = return_RR_range_map(RR_name, ES_name, comm_name, 0, deploy_pct,
                                                      load_scenario=load_scenario, legend_show=legend_show,
                                                      clean_energy=clean_energy_value,
                                                      clean_energy_cost=hydrogen_PPA_cost_box_value,
                                                      h2_fuel_type=hydrogen_fuel_list_value,
                                                      station_type=station_type, reroute=re_routing_switch_value,
                                                      switch_tech=loco_switching_switch_value,
                                                      diesel_cost_p_gal=diesel_cost_p_gal_box_value)
            elif 'hybrid' in ES_name:
                fig_list, label = return_RR_range_map(RR_name, ES_name, comm_name, RR_range, deploy_pct,
                                                      load_scenario=load_scenario, legend_show=legend_show,
                                                      clean_energy=clean_energy_value,
                                                      clean_energy_cost=battery_ppa_cost_box_value,
                                                      station_type=station_type, reroute=re_routing_switch_value,
                                                      switch_tech=loco_switching_switch_value,
                                                      tender_cost_p_tonmi=battery_cost_p_tonmi_box_value,
                                                      diesel_cost_p_gal=diesel_cost_p_gal_box_value)
            elif ES_name == 'diesel':
                fig_list, label = return_RR_range_map(RR_name, ES_name, comm_name, 0, 1, load_scenario=load_scenario,
                                                      legend_show=legend_show)
            else:
                fig_list, label = return_RR_range_map(RR_name, ES_name, comm_name, 0, deploy_pct,
                                                      load_scenario=load_scenario,
                                                      legend_show=legend_show, station_type=station_type,
                                                      reroute=re_routing_switch_value,
                                                      switch_tech=loco_switching_switch_value)

            return return_chart_fig_card(fig_list), output

    def return_RR_range_map(RR_name, ES_name, comm_name, RR_range, deploy_pct, load_scenario=True,
                            cache_scenario=True,
                            plot=True, legend_show=True, station_type=None,
                            clean_energy=False, clean_energy_cost=0, h2_fuel_type=None,
                            reroute=re_routing_switch_value, switch_tech=loco_switching_switch_value,
                            tender_cost_p_tonmi=battery_cost_p_tonmi_box_value,
                            diesel_cost_p_gal=diesel_cost_p_gal_box_value):
        load_scenario = False
        cache_scenario = False
        # TODO: <load_plot> currently useless, must decide whether se want this or not
        # <load_plot> = True - load the fig from the cached file if it exists, = False - rerun scenario and cache plot file
        if 'hybrid' in ES_name:
            _, fig, label = run_scenario(rr=RR_name, fuel_type=ES_name, comm_group=comm_name, D=RR_range * 1.6,
                                         deployment_perc=deploy_pct, perc_ods=1.0, cache_scenario=cache_scenario,
                                         # deployment_table=True,
                                         reroute=reroute, switch_tech=switch_tech,
                                         clean_energy=clean_energy, clean_energy_cost=clean_energy_cost,
                                         h2_fuel_type=h2_fuel_type, tender_cost_p_tonmi=tender_cost_p_tonmi,
                                         diesel_cost_p_gal=diesel_cost_p_gal,
                                         plot=plot, load_scenario=load_scenario, legend_show=legend_show,
                                         station_type=station_type)
        else:
            _, fig, label = run_scenario(rr=RR_name, fuel_type=ES_name, comm_group=comm_name, D=RR_range * 1.6,
                                         deployment_perc=deploy_pct, cache_scenario=cache_scenario,
                                         reroute=reroute, switch_tech=switch_tech,
                                         clean_energy=clean_energy, clean_energy_cost=clean_energy_cost,
                                         h2_fuel_type=h2_fuel_type, tender_cost_p_tonmi=tender_cost_p_tonmi,
                                         diesel_cost_p_gal=diesel_cost_p_gal,
                                         plot=plot, load_scenario=load_scenario, legend_show=legend_show,
                                         station_type=station_type)

        return fig, label

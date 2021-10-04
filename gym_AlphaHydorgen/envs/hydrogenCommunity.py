import gym
from gym import error, spaces, utils
from gym.utils import seeding

import pandas as pd
import numpy as np

from model import *

'''
In this version:
1. The time step is fixed at 1 hour
2. The tank volume of H2 station is unlimited
3. Generating H2 using electricity is not supported
'''
class hydrogenCommunity(gym.Env):
    """ AlphaHydorgen is a custom Gym Environment to simulate a community equiped with on-site renewables,
    hydrogen station, hydrogen vehicles and smart grid
    ------------------------------------------------------------------------------------------------------
    Args:
        - stepLenth: length of time step, unit: s
        - building_list: a list of buildings, each element in the list is a tuple of (buildingLoad.csv, number of buildings)
            example: [('inputs/building1.csv', 10), ('inputs/building2.csv', 10), ('inputs/building3.csv', 10)]
        - pv_list: a list of on-site pvs, each element in the list is a tuple of (pvGeneration.csv, number of PVs)
            example: [('inputs/pv1.csv', 10), ('inputs/pv2.csv', 10), ('inputs/pv3.csv', 10)]
        - vehicle_list: a list of hydrogen vehicles, 
            first element is parkSchedule.csv, 
            the remaining elements in the list are tuples of 
                (vehicleParameter.csv, fuelCellEff, fuelCellCap, number of vehicles)
            example: ['inputs/vehicle_atHomeSchd.csv', ('inputs/vehicle1.csv', 100, 300, 10), 
                      ('inputs/vehicle2.csv', 100, 300, 10), ('inputs/vehicle3.csv', 100, 300, 10)]
        - h2Station: NOT CONSIDERED IN V1.0
            a dictionary of hydrogen station parameters
            example: {'pipeChargingCapacity':60*1000,
                      'vehicleDischargingCapacity':1000,
                      'storageCapacity':1000*1000,
                      'electrolyzerEff':0.01,
                      'electrolyzerCapacity':10}
    ------------------------------------------------------------------------------------------------------
    States:
        - buildingLoad: total building load of the community, [kW]
        - pvGeneration: total on-site PV generation, [kW] 
        - vehicle_park: binary variable, whether the vechile is parked at home or not
        - vehicle_max_dist: predicted maximum travel distance of today, dist_mu_wd+5*dist_sigma_wd [km]
        - vehicle_tank: hydorgen stored in the vehicle's tank, [g]
        - station_tank: hydorgen stored in the station's tank, [g]
    ------------------------------------------------------------------------------------------------------
    Actions:
        - vehicle_charge: array, each element is H2 charge/discharge rate of each vehicle,
            positive means charge from H2 station, negative means discharge to grid/building, [g]
        - h2Station_charge: NOT CONSIDERED IN V1.0
            H2 station charge from the pipeline, [g]     
        - h2Station_generation: NOT CONSIDERED IN V1.0
            H2 station generation using the renewable/grid electricity, [g]
    """

    def __init__(self, building_list, pv_list, vehicle_list):
        '''
        In this version: 
            -- The step length is fixed at 1 hour
            -- The h2Station is assumed to have unlimited tank volumn and therefore not modelled
        '''
        super().__init__()
        self.episode_idx = 0

        self.stepLenth =3600          # To be revised when the step length is not 1 hour
        self.simulationYear = 2019    # Fixed in this version
        start_time = datetime(year = self.simulationYear, month = 1, day =1)
        self.n_steps = 8760*3600//self.stepLenth   # Simulate a whole year
        freq = '{}H'.format(self.stepLenth/3600)
        self.timeIndex = pd.date_range(start_time, periods=self.n_steps, freq=freq)

        # Calculate the load for each time step
        self.buildingLoad = self._calculateBuildingLoad(building_list, self.stepLenth, self.simulationYear)
        self.pvGeneration = self._calculatePVGeneration(pv_list, self.stepLenth, self.simulationYear)

        # Initialize the vehicles
        self.vehicles = []
        self.vehicle_schl_file = vehicle_list[0]
        for vehicle_tuple in vehicle_list[1:]:
            fuelCell =FuelCell(vehicle_tuple[1], vehicle_tuple[2])
            vehicle = Vehicle(vehicle_tuple[0], self.vehicle_schl_file, fuelCell, self.stepLenth)
            for _ in range(vehicle_tuple[3]):
                self.vehicles.append(vehicle)

        # define the state and action space
        vehicle_n = len(self.vehicles)           # Only control the vehicles
        self.action_names = ['vehicle_{}'.format(vehicle_i) for vehicle_i in range(vehicle_n)]
        self.actions_low = np.ones(vehicle_n)*-100    # Maximum discharging rate -100g/s
        self.actions_high = np.ones(vehicle_n)*100    # Maximum charging rate 100g/s
        self.action_space = spaces.Box(low=self.actions_low,
                                       high=self.actions_high,
                                       dtype=np.float32)  

        self.obs_names = ['buildingLoad', 'pvGeneration'] + \
            ['vehicle_park_{}'.format(vehicle_i) for vehicle_i in range(vehicle_n)] + \
            ['vehicle_max_dist_{}'.format(vehicle_i) for vehicle_i in range(vehicle_n)] + \
            ['vehicle_tank_{}'.format(vehicle_i) for vehicle_i in range(vehicle_n)]
        self.obs_low  = np.array([0,  0] + [0 for _ in range(vehicle_n)] + \
            [0 for _ in range(vehicle_n)] + [0 for _ in range(vehicle_n)])
        self.obs_high = np.array([10000, 10000] + [1 for _ in range(vehicle_n)] + \
            [1000 for _ in range(vehicle_n)] + [10000 for _ in range(vehicle_n)])
        self.observation_space = spaces.Box(low=self.obs_low, 
                                            high=self.obs_high, 
                                            dtype=np.float32)

    def reset(self):
        self.episode_idx += 1
        self.time_step_idx = 0
        load = self._getLoad(self.time_step_idx)
        vehicles_park = []
        vehicles_max_dist = []
        vehicles_tank = []
        for vehicle in self.vehicles:
            vehicle_park, vehicle_max_dist, _ = self._getVihicleStateStatic(vehicle)
            vehicles_park.append(vehicle_park)
            vehicles_max_dist.append(vehicle_max_dist)           
            vehicles_tank.append(vehicle.tankVol)   # Half the tank at the begining
        obs = load + vehicles_park + vehicles_max_dist + vehicles_tank

        return obs

    def step(self, actions):
        load = self._getLoad(self.time_step_idx)
        vehicles_park = []
        vehicles_max_dist = []
        vehicles_tank = []
        totalGridLoad = load[0] - load[1]   # building load minus the pv generation
        totalH2Charging = 0

        for action, vehicle in zip(actions, self.vehicles):
            vehicle_park, vehicle_max_dist, cruiseBackHour = self._getVihicleStateStatic(vehicle)
            if action > 0:   # Charge the vehicle tank from the H2 station
                realH2ChargeRate = vehicle.h2FromStation(action)
                totalH2Charging += realH2ChargeRate
            elif action < 0: # discharge the grid
                realDischargePower = vehicle.eleToGrid(-action)
                totalGridLoad -= realDischargePower
            # Vehicle's gas tank is reduced at the hour vehicle is back 
            if cruiseBackHour:
                workingDay = self.timeIndex[self.time_step_idx].weekday()
                vehicle.cruise(workingDay)

            vehicles_park.append(vehicle_park)
            vehicles_max_dist.append(vehicle_max_dist)
            vehicles_tank.append(vehicle.tankVol)
        
        obs = load + vehicles_park + vehicles_max_dist + vehicles_tank

        reward = (totalGridLoad, totalH2Charging)
        done = self.time_step_idx == len(self.timeIndex)-1
        
        self.time_step_idx += 1
        comments = None

        return obs, reward, done, comments

    def _calculateBuildingLoad(self, building_list, stepLenth, simulationYear):
        '''Calculate the total building load from the building list
        '''
        
        buildings = pd.DataFrame()
        for building_tuple in building_list:
            building_csv = building_tuple[0]
            building_numbers = building_tuple[1]
            building_obj = Building(building_csv, stepLenth, simulationYear)
            building = building_obj.getLoadFullYear()*building_numbers
            buildings = pd.concat([buildings,building], axis=1)
        totalLoad = buildings.sum(axis=1).values
        return totalLoad

    def _calculatePVGeneration(self, pv_list, stepLenth, simulationYear):
        '''Calculate the total PV generation from the PV list
        '''
        pvs = pd.DataFrame()
        for pv_tuple in pv_list:
            pv_csv = pv_tuple[0]
            pv_numbers = pv_tuple[1]
            pv_obj = PV(pv_csv, stepLenth, simulationYear)
            pv = pv_obj.getPowerFullYear()*pv_numbers
            pvs = pd.concat([pvs,pv], axis=1)
        totalGeneration = pvs.sum(axis=1).values
        return totalGeneration
    
    def _getLoad(self, time_step_idx):
        '''Get the building load and pv generation for the given time step
        Return a list
        '''
        load = [self.buildingLoad[time_step_idx], self.pvGeneration[time_step_idx]]
        return load
    
    def _getVihicleStateStatic(self, vehicle):
        '''Get the park state and maximum traveling distance of the vehicle
        Return: park state (1 for at home, 0 for not at home)
                predicted maximum travel distance
                cruiseBackHour: Boolean, Whether it is the hour vehicle returns to home, 
                    the tankVol is reduced at this hour
        '''
        weekday = self.timeIndex[self.time_step_idx].weekday()
        hour = self.timeIndex[self.time_step_idx].hour
        if weekday:
            vehicle_park = vehicle.parkSchd_wd[hour]
            cruiseHour = vehicle.parkSchd_wd.index[vehicle.parkSchd_wd==0].max()+1
            vehicle_max_dist = vehicle.dist_mu_wd+5*vehicle.dist_sigma_wd
        else:
            vehicle_park = vehicle.parkSchd_nwd[hour]
            cruiseHour = vehicle.parkSchd_wd.index[vehicle.parkSchd_wd==0].max()+1
            vehicle_max_dist = vehicle.dist_mu_nwd+5*vehicle.dist_sigma_nwd
        cruiseBackHour = hour == cruiseHour
        return vehicle_park, vehicle_max_dist, cruiseBackHour